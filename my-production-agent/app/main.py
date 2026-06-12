import os
import time
import json
import logging
import signal
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit, r
from .cost_guard import check_budget
from utils.mock_llm import ask as llm_ask

# Logging — JSON structured
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

_memory_history: dict[str, list] = {}

def load_history(user_id: str) -> list:
    if r:
        try:
            redis_key = f"history:{user_id}"
            data = r.get(redis_key)
            return json.loads(data) if data else []
        except Exception as e:
            logger.error(json.dumps({"event": "redis_load_history_error", "error": str(e)}))
    return _memory_history.get(user_id, [])

def save_history(user_id: str, history: list, ttl_seconds: int = 3600):
    if r:
        try:
            redis_key = f"history:{user_id}"
            r.setex(redis_key, ttl_seconds, json.dumps(history))
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

class AskRequest(BaseModel):
    user_id: str | None = Field(default=None, description="Optional user ID for tracking")
    question: str = Field(..., min_length=1, max_length=2000)

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({"event": "startup", "msg": "Starting production agent..."}))
    _is_ready = True
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown", "msg": "Shutting down production agent..."}))

app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response = await call_next(request)
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
        logger.error(json.dumps({"event": "request_error", "error": str(e)}))
        raise

@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1)}

@app.get("/ready")
def ready():
    # Ping check Redis connection
    if r:
        try:
            r.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="Redis connection failed")
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent is not ready")
    return {"ready": True}

@app.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    _key: str = Depends(verify_api_key),
):
    user_key = body.user_id or _key[:8]
    
    # Rate Limiting
    check_rate_limit(user_key)
    
    # Budget Check (Input)
    input_tokens = len(body.question.split()) * 2
    check_budget(user_key, (input_tokens / 1000) * 0.00015)
    
    # Load history
    history = load_history(user_key)
    
    # Process question with history
    answer = ask_with_history(user_key, body.question, history)
    
    # Budget Record (Output)
    output_tokens = len(answer.split()) * 2
    check_budget(user_key, (output_tokens / 1000) * 0.0006)
    
    # Save history
    history.append({"role": "user", "content": body.question})
    history.append({"role": "assistant", "content": answer})
    save_history(user_key, history)
    
    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

# Graceful shutdown signal handling
def handle_sigterm(signum, frame):
    logger.info(json.dumps({"event": "signal", "signum": signum, "msg": "Received SIGTERM, preparing for shutdown"}))

signal.signal(signal.SIGTERM, handle_sigterm)
