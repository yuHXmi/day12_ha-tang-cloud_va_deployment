import time
import redis
from fastapi import HTTPException
from .config import settings

# Khởi tạo Redis client
r = redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None

def check_rate_limit(user_id: str):
    if not r:
        return # Skip nếu không có Redis
    
    now = time.time()
    redis_key = f"rate_limit:{user_id}"
    try:
        r.zremrangebyscore(redis_key, 0, now - 60)
        count = r.zcard(redis_key)
        if count >= settings.rate_limit_per_minute:
            oldest_list = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = 60
            if oldest_list:
                oldest_ts = oldest_list[0][1]
                retry_after = max(1, int(oldest_ts + 60 - now))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
                headers={"Retry-After": str(retry_after)},
            )
        member = f"{now}:{time.time_ns()}"
        r.zadd(redis_key, {member: now})
        r.expire(redis_key, 65)
    except HTTPException:
        raise
    except Exception:
        pass # Dự phòng lỗi kết nối Redis
