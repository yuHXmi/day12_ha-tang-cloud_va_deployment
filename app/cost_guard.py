import time
from fastapi import HTTPException
from .config import settings
from .rate_limiter import r

def check_budget(user_id: str, estimated_cost: float):
    if not r:
        return
        
    today = time.strftime("%Y-%m-%d")
    redis_key = f"budget:{user_id}:{today}"
    try:
        current_cost = float(r.get(redis_key) or 0.0)
        if current_cost + estimated_cost > settings.daily_budget_usd:
            raise HTTPException(
                status_code=402,
                detail=f"Daily budget exceeded: {settings.daily_budget_usd} USD"
            )
        if estimated_cost > 0:
            r.incrbyfloat(redis_key, estimated_cost)
            r.expire(redis_key, 172800) # 2 days TTL
    except HTTPException:
        raise
    except Exception:
        pass
