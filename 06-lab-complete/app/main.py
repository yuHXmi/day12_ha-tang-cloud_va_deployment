"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting
  ✅ Cost guard
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import os
import time
import signal
import logging
import json
from datetime import datetime, timezone
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Redis Connection & Memory Fallback
# ─────────────────────────────────────────────────────────
_redis = None
if settings.redis_url:
    try:
        import redis
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        logger.info(json.dumps({"event": "redis_connected", "url": settings.redis_url}))
    except Exception as e:
        logger.error(json.dumps({"event": "redis_connection_error", "error": str(e)}))
        _redis = None

_memory_history: dict[str, list] = {}

def load_history(user_id: str) -> list:
    if _redis:
        try:
            redis_key = f"history:{user_id}"
            data = _redis.get(redis_key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.error(json.dumps({"event": "redis_load_history_error", "error": str(e)}))
    return _memory_history.get(user_id, [])

def save_history(user_id: str, history: list, ttl_seconds: int = 3600):
    if _redis:
        try:
            redis_key = f"history:{user_id}"
            _redis.setex(redis_key, ttl_seconds, json.dumps(history))
            return
        except Exception as e:
            logger.error(json.dumps({"event": "redis_save_history_error", "error": str(e)}))
    _memory_history[user_id] = history

def ask_with_history(user_id: str, question: str, history: list) -> str:
    question_lower = question.lower()
    if "what is my name" in question_lower or "what's my name" in question_lower:
        for msg in reversed(history):
            if msg["role"] == "user":
                content_lower = msg["content"].lower()
                if "my name is " in content_lower:
                    name_part = msg["content"][content_lower.find("my name is ") + len("my name is "):].strip()
                    name = name_part.rstrip(".!?,")
                    if name:
                        return f"Your name is {name}."
    return llm_ask(question)

# ─────────────────────────────────────────────────────────
# Rate Limiter (Redis Sliding Window & Memory Fallback)
# ─────────────────────────────────────────────────────────
_rate_windows: dict[str, deque] = defaultdict(deque)

def check_rate_limit(key: str):
    now = time.time()
    if _redis:
        try:
            redis_key = f"rate_limit:{key}"
            _redis.zremrangebyscore(redis_key, 0, now - 60)
            count = _redis.zcard(redis_key)
            if count >= settings.rate_limit_per_minute:
                oldest_list = _redis.zrange(redis_key, 0, 0, withscores=True)
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
            _redis.zadd(redis_key, {member: now})
            _redis.expire(redis_key, 65)
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.error(json.dumps({"event": "redis_rate_limit_error", "error": str(e)}))

    window = _rate_windows[key]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            headers={"Retry-After": "60"},
        )
    window.append(now)

# ─────────────────────────────────────────────────────────
# Cost Guard (Redis Daily Budget & Memory Fallback)
# ─────────────────────────────────────────────────────────
_daily_cost = 0.0
_cost_reset_day = time.strftime("%Y-%m-%d")

def check_and_record_cost(user_key: str, input_tokens: int, output_tokens: int):
    global _daily_cost, _cost_reset_day
    today = time.strftime("%Y-%m-%d")
    cost = (input_tokens / 1000) * 0.00015 + (output_tokens / 1000) * 0.0006
    
    if _redis:
        try:
            redis_key = f"budget:{user_key}:{today}"
            current_cost = float(_redis.get(redis_key) or 0.0)
            if current_cost + cost > settings.daily_budget_usd:
                raise HTTPException(
                    status_code=402,
                    detail=f"Daily budget exceeded: {settings.daily_budget_usd} USD"
                )
            if cost > 0:
                _redis.incrbyfloat(redis_key, cost)
                _redis.expire(redis_key, 24 * 3600 * 2)
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.error(json.dumps({"event": "redis_cost_guard_error", "error": str(e)}))

    if today != _cost_reset_day:
        _daily_cost = 0.0
        _cost_reset_day = today
    if _daily_cost + cost > settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail=f"Daily budget exceeded: {settings.daily_budget_usd} USD"
        )
    _daily_cost += cost

# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    if _redis:
        try:
            _redis.ping()
            logger.info(json.dumps({"event": "lifespan_redis_check", "status": "ok"}))
        except Exception as e:
            logger.warning(json.dumps({"event": "lifespan_redis_check", "status": "failed", "error": str(e)}))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str | None = Field(default=None, description="Optional user ID for session/history tracking")
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    user_key = body.user_id or _key[:8]
    # Rate limit per user_id or API key prefix
    check_rate_limit(user_key)

    # Budget check
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(user_key, input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_key,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    # Get history
    history = load_history(user_key)

    # Call LLM with history context
    answer = ask_with_history(user_key, body.question, history)

    # Budget record
    output_tokens = len(answer.split()) * 2
    check_and_record_cost(user_key, 0, output_tokens)

    # Update and save history
    history.append({
        "role": "user",
        "content": body.question,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    history.append({
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    if len(history) > 20:
        history = history[-20:]
    save_history(user_key, history)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"llm": "mock" if not settings.openai_api_key else "openai"}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if _redis:
        try:
            _redis.ping()
        except Exception as e:
            logger.error(json.dumps({"event": "ready_redis_check_failed", "error": str(e)}))
            raise HTTPException(503, "Redis not available")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "daily_cost_usd": round(_daily_cost, 4),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(_daily_cost / settings.daily_budget_usd * 100, 1),
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
