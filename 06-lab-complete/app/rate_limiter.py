"""
Rate limiting (tiêu chí 7) — sliding window trên Redis sorted set.

  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây
  • Vượt giới hạn → HTTP 429 kèm header Retry-After
  • State nằm trong Redis → mọi worker / instance dùng chung, còn nguyên sau khi restart agent
"""
import hashlib
import math
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def _redis_key(api_key: str) -> str:
    # Không lưu API key thô trong Redis, chỉ lưu hash
    return "ratelimit:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]


def check_rate_limit(key: str) -> None:
    limit = settings.rate_limit_per_minute
    rkey = _redis_key(key)
    now = time.time()
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - WINDOW_SECONDS)  # bỏ request cũ ngoài cửa sổ
        pipe.zcard(rkey)                                      # đếm request còn trong cửa sổ
        _, count = pipe.execute()

        if count >= limit:
            oldest = r.zrange(rkey, 0, 0, withscores=True)
            retry_after = WINDOW_SECONDS
            if oldest:
                retry_after = max(1, math.ceil(oldest[0][1] + WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=429,
                detail={"error": "Rate limit exceeded", "limit": limit,
                        "window_seconds": WINDOW_SECONDS},
                headers={"Retry-After": str(retry_after)},
            )

        pipe = r.pipeline()
        pipe.zadd(rkey, {f"{now}-{uuid.uuid4().hex[:8]}": now})
        pipe.expire(rkey, WINDOW_SECONDS + 1)
        pipe.execute()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable (Redis)")
