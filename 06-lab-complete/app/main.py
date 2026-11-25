"""
Production AI Agent — Part 6 Final Project.

Chạy:  uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
Chấm:  python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Tiêu chí 10: Structured logging — mỗi dòng log là 1 JSON object ──
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "lvl": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            entry["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(entry, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.handlers = [_handler]
logger.setLevel(settings.log_level)
logger.propagate = False


def log(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"extra_fields": fields})


# ── Tiêu chí 11: Graceful shutdown qua lifespan ──
# uvicorn tự bắt SIGTERM: ngừng nhận request mới, chờ request đang chạy xong,
# rồi chạy phần sau `yield`. Không tự đăng ký signal handler để khỏi đè handler của uvicorn.
_state = {"ready": False, "started_at": time.time()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment, port=settings.port,
        redis_ok=redis_healthy())
    _state["ready"] = True
    yield
    _state["ready"] = False
    log("shutdown", reason="SIGTERM or stop — in-flight requests finished")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log("request", method=request.method, path=request.url.path, status=status,
            ms=round((time.perf_counter() - started) * 1000, 1))


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Không trả stack trace cho client; chỉ ghi loại lỗi vào log
    log("unhandled_error", logging.ERROR, path=request.url.path, error=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=100)


# ── Tiêu chí 4: liveness — luôn 200 khi process còn sống, không phụ thuộc Redis ──
@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _state["started_at"], 1),
        "environment": settings.environment,
    }


# ── Tiêu chí 5: readiness — 503 khi đang tắt hoặc mất Redis ──
@app.get("/ready")
def ready():
    redis_ok = redis_healthy()
    if not _state["ready"] or not redis_ok:
        return JSONResponse(status_code=503,
                            content={"ready": False, "redis": redis_ok, "accepting": _state["ready"]})
    return {"ready": True, "redis": True}


# ── Tiêu chí 6, 7, 8: auth → rate limit → budget → LLM → ghi chi phí ──
@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)          # 429
    check_budget()                     # 402
    answer = llm_ask(body.question)
    cost = record_cost(estimate_tokens(body.question), estimate_tokens(answer))
    log("ask", question_len=len(body.question), answer_len=len(answer), cost_usd=round(cost, 8))
    return {"question": body.question, "answer": answer}
