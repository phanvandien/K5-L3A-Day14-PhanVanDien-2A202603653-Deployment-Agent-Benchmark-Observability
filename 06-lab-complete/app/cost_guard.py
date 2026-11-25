"""
Cost guard (tiêu chí 8).

  • Cộng dồn chi phí LLM (tính theo token) vào Redis, key theo ngày: cost:daily:YYYY-MM-DD
  • Tổng chi phí trong ngày ≥ DAILY_BUDGET_USD → HTTP 402
"""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

KEY_TTL_SECONDS = 2 * 24 * 3600  # giữ 2 ngày rồi tự xoá


def _daily_key() -> str:
    return "cost:daily:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def estimate_tokens(text: str) -> int:
    """Ước lượng token (~4 ký tự / token) — đủ dùng cho mock LLM."""
    return max(1, len(text) // 4)


def current_spend() -> float:
    return float(r.get(_daily_key()) or 0.0)


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        spent = current_spend()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable (Redis)")
    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={"error": "Daily budget exceeded",
                    "spent_usd": round(spent, 6),
                    "budget_usd": settings.daily_budget_usd},
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(_daily_key(), cost)
        pipe.expire(_daily_key(), KEY_TTL_SECONDS)
        pipe.execute()
    except redis.RedisError:
        pass  # không làm hỏng request đã trả lời xong chỉ vì không ghi được chi phí
    return cost
