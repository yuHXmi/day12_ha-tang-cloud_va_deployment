#  Code Lab: Deploy Your AI Agent to Production

> **AICB-P1 · VinUniversity 2026**  
> Thời gian: 3-4 giờ | Độ khó: Intermediate

##  Mục Tiêu

Sau khi hoàn thành lab này, bạn sẽ:
- Hiểu sự khác biệt giữa development và production
- Containerize một AI agent với Docker
- Deploy agent lên cloud platform
- Bảo mật API với authentication và rate limiting
- Thiết kế hệ thống có khả năng scale và reliable

---

##  Yêu Cầu

```bash
 Python 3.11+
 Docker & Docker Compose
 Git
 Text editor (VS Code khuyến nghị)
 Terminal/Command line
```

**Không cần:**
-  OpenAI API key (dùng mock LLM)
-  Credit card
-  Kinh nghiệm DevOps trước đó

---

##  Lộ Trình Lab

| Phần | Thời gian | Nội dung |
|------|-----------|----------|
| **Part 1** | 30 phút | Localhost vs Production |
| **Part 2** | 45 phút | Docker Containerization |
| **Part 3** | 45 phút | Cloud Deployment |
| **Part 4** | 40 phút | API Security |
| **Part 5** | 40 phút | Scaling & Reliability |
| **Part 6** | 60 phút | Final Project |

---

## Part 1: Localhost vs Production (30 phút)

###  Concepts

**Vấn đề:** "It works on my machine" — code chạy tốt trên laptop nhưng fail khi deploy.

**Nguyên nhân:**
- Hardcoded secrets
- Khác biệt về environment (Python version, OS, dependencies)
- Không có health checks
- Config không linh hoạt

**Giải pháp:** 12-Factor App principles

###  Exercise 1.1: Phát hiện anti-patterns

```bash
cd 01-localhost-vs-production/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm ít nhất 5 vấn đề.

1. **Hardcoded Secrets:** API Key (`OPENAI_API_KEY`) và Database URL (`DATABASE_URL`) được ghi trực tiếp (hardcode) trong code, dẫn đến nguy cơ lộ lọt thông tin nhạy cảm khi đẩy lên hệ thống quản lý phiên bản (Git).
2. **Thiếu Config Management:** Chế độ debug (`DEBUG = True`) và cấu hình hệ thống (`MAX_TOKENS = 500`) được viết trực tiếp mà không cho phép cấu hình linh hoạt thông qua biến môi trường (Environment Variables).
3. **Sử dụng `print()` cho Logging:** Sử dụng `print()` thay vì thư viện logging chuyên nghiệp. Điều này làm log không có cấu trúc cấu hình (Unstructured) và cực kỳ nguy hại khi ghi thẳng thông tin bí mật (API Key) ra log.
4. **Thiếu các cổng kiểm tra trạng thái (Health Check Endpoints):** Không cấu hình các endpoint `/health` (Liveness) và `/ready` (Readiness), khiến nền tảng Cloud (Railway/Render/Kubernetes) không thể tự động giám sát và khởi động lại container khi gặp lỗi.
5. **Cấu hình Port và Host cứng:** Dịch vụ Uvicorn bị gán cứng chạy tại `host="localhost"` và `port=8000` với `reload=True`. Điều này ngăn cản ứng dụng nhận traffic từ mạng bên ngoài khi chạy trong container và không thể nhận cổng tự động inject từ Cloud platform.

###  Exercise 1.2: Chạy basic version

```bash
pip install -r requirements.txt
python app.py
```

Test:
```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

**Quan sát:** Nó chạy! Nhưng có production-ready không?

###  Exercise 1.3: So sánh với advanced version

```bash
cd ../production
cp .env.example .env
pip install -r requirements.txt
python app.py
```

**Nhiệm vụ:** So sánh 2 files `app.py`. Điền vào bảng:

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Config** | Hardcoded trong code | Environment Variables (12-Factor App) | Giúp dễ dàng chuyển đổi cấu hình giữa các môi trường (Dev, Staging, Prod) mà không cần sửa code; tăng tính bảo mật (không lộ secrets). |
| **Health Check** | Không có (❌) | Endpoint `/health` (Liveness) và `/ready` (Readiness) (✅) | Giúp các nền tảng điều phối (Orchestrator) và Load Balancer biết khi nào dịch vụ bị lỗi để khởi động lại hoặc tạm ngưng định tuyến traffic. |
| **Logging** | Dùng `print()` thủ công | Structured JSON Logging | Dễ dàng thu thập, truy vấn và phân tích log tự động (qua ELK Stack, Datadog, Loki) mà không gây lộ thông tin nhạy cảm. |
| **Shutdown** | Đột ngột khi tắt process | Graceful Shutdown (xử lý SIGTERM) | Đảm bảo hệ thống hoàn tất các tiến trình/request đang xử lý dở dang (in-flight requests) và đóng kết nối DB/Redis an toàn trước khi dừng hẳn. |
###  Checkpoint 1

- [✅] Hiểu tại sao hardcode secrets là nguy hiểm
- [✅] Biết cách dùng environment variables
- [✅] Hiểu vai trò của health check endpoint
- [✅] Biết graceful shutdown là gì

---

## Part 2: Docker Containerization (45 phút)

###  Concepts

**Vấn đề:** "Works on my machine" part 2 — Python version khác, dependencies conflict.

**Giải pháp:** Docker — đóng gói app + dependencies vào container.

**Benefits:**
- Consistent environment
- Dễ deploy
- Isolation
- Reproducible builds

###  Exercise 2.1: Dockerfile cơ bản

```bash
cd ../../02-docker/develop
```

**Nhiệm vụ:** Đọc `Dockerfile` và trả lời:

1. **Base image:** `python:3.11` (Chứa toàn bộ hệ điều hành Debian và môi trường phát triển Python đầy đủ, dung lượng lớn ~1GB).
2. **Working directory:** `/app` (Thư mục làm việc mặc định chứa mã nguồn và tài nguyên của ứng dụng bên trong container).
3. **Tại sao COPY requirements.txt trước?** Để tận dụng cơ chế Docker Layer Caching. Docker sẽ bỏ qua việc cài lại các thư viện Python (tốn thời gian) ở các lần build sau nếu file `requirements.txt` không có thay đổi nào.
4. **CMD vs ENTRYPOINT khác nhau thế nào?** 
   * `ENTRYPOINT` định nghĩa file thực thi chính của container, không thể bị ghi đè một cách dễ dàng khi chạy container.
   * `CMD` định nghĩa các tham số mặc định truyền vào `ENTRYPOINT` hoặc lệnh chạy mặc định, có thể dễ dàng bị ghi đè khi ta truyền đối số lúc chạy lệnh `docker run`.

###  Exercise 2.2: Build và run

```bash
# Build image
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .

# Run container
docker run -p 8000:8000 my-agent:develop

# Test
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

**Quan sát:** Image size là bao nhiêu?
```bash
docker images my-agent:develop
```

###  Exercise 2.3: Multi-stage build

```bash
cd ../production
```

**Nhiệm vụ:** Đọc `Dockerfile` và tìm:
- Stage 1 làm gì?
- Stage 2 làm gì?
- Tại sao image nhỏ hơn?

* **Develop Image Size:** ~1.02 GB (1020 MB) - Sử dụng base image đầy đủ và không tối ưu hóa các layer.
* **Production Image Size:** ~145 MB - Sử dụng base image rút gọn `python:3.11-slim` kết hợp chiến thuật Multi-stage build.
* **Difference (Giảm thiểu):** ~85.8% (Giúp tối ưu băng thông mạng, giảm thời gian deploy và thu nhỏ bề mặt tấn công bảo mật).

###  Exercise 2.4: Docker Compose stack

**Nhiệm vụ:** Đọc `docker-compose.yml` và vẽ architecture diagram.

```bash
docker compose up
```

Services nào được start? Chúng communicate thế nào?

Test:
```bash
# Health check
curl http://localhost/health

# Agent endpoint
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

###  Checkpoint 2

- [ ] Hiểu cấu trúc Dockerfile
- [ ] Biết lợi ích của multi-stage builds
- [ ] Hiểu Docker Compose orchestration
- [ ] Biết cách debug container (`docker logs`, `docker exec`)

---

## Part 3: Cloud Deployment (45 phút)

###  Concepts

**Vấn đề:** Laptop không thể chạy 24/7, không có public IP.

**Giải pháp:** Cloud platforms — Railway, Render, GCP Cloud Run.

**So sánh:**

| Platform | Độ khó | Free tier | Best for |
|----------|--------|-----------|----------|
| Railway | ⭐ | $5 credit | Prototypes |
| Render | ⭐⭐ | 750h/month | Side projects |
| Cloud Run | ⭐⭐⭐ | 2M requests | Production |

###  Exercise 3.1: Deploy Railway (15 phút)

```bash
cd ../../03-cloud-deployment/railway
```

**Steps:**

1. Install Railway CLI:
```bash
npm i -g @railway/cli
```

2. Login:
```bash
railway login
```

3. Initialize project:
```bash
railway init
```

4. Set environment variables:
```bash
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
```

5. Deploy:
```bash
railway up
```

6. Get public URL:
```bash
railway domain
```

**Nhiệm vụ:** Test public URL với curl hoặc Postman.

Test:
```bash
# Health check
curl http://student-agent-domain/health

# Agent endpoint
curl http://studen-agent-domain/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": ""}'
```

###  Exercise 3.2: Deploy Render (15 phút)

```bash
cd ../render
```

**Steps:**

1. Push code lên GitHub (nếu chưa có)
2. Vào [render.com](https://render.com) → Sign up
3. New → Blueprint
4. Connect GitHub repo
5. Render tự động đọc `render.yaml`
6. Set environment variables trong dashboard
7. Deploy!

**Nhiệm vụ:** So sánh `render.yaml` với `railway.toml`. Khác nhau gì?
* **Khác biệt chính:**
  * `railway.toml` là file cấu hình cục bộ của Railway, chủ yếu định nghĩa lệnh khởi chạy (`startCommand`) và cấu hình liveness probe / restart policy. Việc cấu hình hạ tầng (như thêm cơ sở dữ liệu Redis, Postgres) thường được thực hiện trực quan trên giao diện Railway Dashboard.
  * `render.yaml` là file đặc tả Blueprint (Infrastructure as Code - IaC) của Render. Nó cho phép định nghĩa toàn bộ hạ tầng (gồm Web Service, Database Redis, biến môi trường, ổ đĩa mount Disk,...) trực tiếp trong một file YAML duy nhất. Khi đồng bộ với Git, Render sẽ tự động khởi tạo toàn bộ các tài nguyên này.

###  Exercise 3.3: (Optional) GCP Cloud Run (15 phút)

```bash
cd ../production-cloud-run
```

**Yêu cầu:** GCP account (có free tier).

**Nhiệm vụ:** Đọc `cloudbuild.yaml` và `service.yaml`. Hiểu CI/CD pipeline.

###  Checkpoint 3

- [✅] Deploy thành công lên ít nhất 1 platform
- [✅] Có public URL hoạt động
- [✅] Hiểu cách set environment variables trên cloud
- [✅] Biết cách xem logs

---

## Part 4: API Security (40 phút)

###  Concepts

**Vấn đề:** Public URL = ai cũng gọi được = hết tiền OpenAI.

**Giải pháp:**
1. **Authentication** — Chỉ user hợp lệ mới gọi được
2. **Rate Limiting** — Giới hạn số request/phút
3. **Cost Guard** — Dừng khi vượt budget

###  Exercise 4.1: API Key authentication

```bash
cd ../../04-api-gateway/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm:
1. **API key được check ở đâu?**
   * Được kiểm tra trong Dependency Function `verify_api_key` bằng cách lấy giá trị từ HTTP Header `X-API-Key` (thông qua đối tượng `APIKeyHeader`).
2. **Điều gì xảy ra nếu sai key?**
   * Nếu thiếu API key trong header, hệ thống trả về mã lỗi `401 Unauthorized` kèm chi tiết *"Missing API key..."*.
   * Nếu gửi sai API key, hệ thống trả về mã lỗi `403 Forbidden` kèm chi tiết *"Invalid API key."*.
3. **Làm sao rotate key?**
   * Rotate key bằng cách cập nhật giá trị của biến môi trường `AGENT_API_KEY` trên hệ thống Cloud (Railway/Render) mà không cần thay đổi hay build lại mã nguồn. Container sẽ tự động nhận key mới sau khi restart.

Test:
```bash
python app.py

#  Không có key
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

#  Có key
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

###  Exercise 4.2: JWT authentication (Advanced)

```bash
cd ../production
```

**Nhiệm vụ:** 
1. Đọc `auth.py` — hiểu JWT flow
2. Lấy token:
```bash
python app.py

curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

3. Dùng token để gọi API:
```bash
TOKEN="<token_từ_bước_2>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

###  Exercise 4.3: Rate limiting

**Nhiệm vụ:** Đọc `rate_limiter.py` và trả lời:
1. **Algorithm nào được dùng? (Token bucket? Sliding window?)**
   * Thuật toán **Sliding Window Counter** được sử dụng. Nó sử dụng một hàng đợi double-ended queue (`deque`) để lưu trữ dấu thời gian (timestamps) của các request và liên tục loại bỏ các timestamps nằm ngoài cửa sổ thời gian (window) quy định.
2. **Limit là bao nhiêu requests/minute?**
   * Với user thường (`rate_limiter_user`): Giới hạn là **10 requests/minute**.
   * Với tài khoản admin (`rate_limiter_admin`): Giới hạn là **100 requests/minute**.
3. **Làm sao bypass limit cho admin?**
   * Dựa trên thông tin giải mã từ token JWT, hệ thống kiểm tra vai trò (role) của người dùng. Nếu role là `"admin"`, hệ thống sẽ sử dụng bộ giới hạn dành riêng cho admin (`rate_limiter_admin`) với hạn mức cao hơn (100 req/min), từ đó nâng cao hạn mức hoặc bypass giới hạn chặt của user thường.

Test:
```bash
# Gọi liên tục 20 lần
for i in {1..20}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Test '$i'"}'
  echo ""
done
```

Quan sát response khi hit limit.

###  Exercise 4.4: Cost guard

**Nhiệm vụ:** Đọc `cost_guard.py` và implement logic:

```python
def check_budget(user_id: str, estimated_cost: float) -> bool:
    """
    Return True nếu còn budget, False nếu vượt.
    
    Logic:
    - Mỗi user có budget $10/tháng
    - Track spending trong Redis
    - Reset đầu tháng
    """
    # TODO: Implement
    pass
```

<details>
<summary> Solution</summary>

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 days
    return True
```

</details>

###  Checkpoint 4

- [✅] Implement API key authentication
- [✅] Hiểu JWT flow
- [✅] Implement rate limiting
- [✅] Implement cost guard với Redis

---

## Part 5: Scaling & Reliability (40 phút)

###  Concepts

**Vấn đề:** 1 instance không đủ khi có nhiều users.

**Giải pháp:**
1. **Stateless design** — Không lưu state trong memory
2. **Health checks** — Platform biết khi nào restart
3. **Graceful shutdown** — Hoàn thành requests trước khi tắt
4. **Load balancing** — Phân tán traffic

###  Exercise 5.1: Health checks

```bash
cd ../../05-scaling-reliability/develop
```

**Nhiệm vụ:** Implement 2 endpoints:

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    # TODO: Return 200 nếu process OK
    pass

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic không?"""
    # TODO: Check database connection, Redis, etc.
    # Return 200 nếu OK, 503 nếu chưa ready
    pass
```

<details>
<summary> Solution</summary>

```python
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    try:
        # Check Redis
        r.ping()
        # Check database
        db.execute("SELECT 1")
        return {"status": "ready"}
    except:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready"}
        )
```

</details>

###  Exercise 5.2: Graceful shutdown

**Nhiệm vụ:** Implement signal handler:

```python
import signal
import sys

def shutdown_handler(signum, frame):
    """Handle SIGTERM from container orchestrator"""
    global _is_ready
    logger.info(f"Received signal {signum} — starting graceful shutdown...")
    # 1. Stop accepting new requests
    _is_ready = False
    
    # 2. Finish current requests (in-flight requests)
    timeout = 30
    elapsed = 0
    while _in_flight_requests > 0 and elapsed < timeout:
        logger.info(f"Waiting for {_in_flight_requests} requests to complete...")
        time.sleep(1)
        elapsed += 1
        
    # 3. Close connections
    # db.close()
    
    # 4. Exit
    logger.info("Graceful shutdown complete. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
```

Test:
```bash
python app.py &
PID=$!

# Gửi request
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Long task"}' &

# Ngay lập tức kill
kill -TERM $PID

# Quan sát: Request có hoàn thành không?
```

###  Exercise 5.3: Stateless design

```bash
cd ../production
```

**Nhiệm vụ:** Refactor code để stateless.

**Anti-pattern:**
```python
#  State trong memory
conversation_history = {}

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])
    # ...
```

**Correct:**
```python
#  State trong Redis
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)
    # ...
```

Tại sao? Vì khi scale ra nhiều instances, mỗi instance có memory riêng.

###  Exercise 5.4: Load balancing

**Nhiệm vụ:** Chạy stack với Nginx load balancer:

```bash
docker compose up --scale agent=3
```

Quan sát:
- 3 agent instances được start
- Nginx phân tán requests
- Nếu 1 instance die, traffic chuyển sang instances khác

Test:
```bash
# Gọi 10 requests
for i in {1..10}; do
  curl http://localhost/ask -X POST \
    -H "Content-Type: application/json" \
    -d '{"question": "Request '$i'"}'
done

# Check logs — requests được phân tán
docker compose logs agent
```

###  Exercise 5.5: Test stateless

```bash
python test_stateless.py
```

Script này:
1. Gọi API để tạo conversation
2. Kill random instance
3. Gọi tiếp — conversation vẫn còn không?

###  Checkpoint 5

- [✅] Implement health và readiness checks
- [✅] Implement graceful shutdown
- [✅] Refactor code thành stateless
- [✅] Hiểu load balancing với Nginx
- [✅] Test stateless design

---

## Part 6: Final Project (60 phút)

###  Objective

Build một production-ready AI agent từ đầu, kết hợp TẤT CẢ concepts đã học.

###  Requirements

**Functional:**
- [✅] Agent trả lời câu hỏi qua REST API
- [✅] Support conversation history
- [ ] Streaming responses (optional)

**Non-functional:**
- [✅] Dockerized với multi-stage build
- [✅] Config từ environment variables
- [✅] API key authentication
- [✅] Rate limiting (10 req/min per user)
- [✅] Cost guard ($10/month per user)
- [✅] Health check endpoint
- [✅] Readiness check endpoint
- [✅] Graceful shutdown
- [✅] Stateless design (state trong Redis)
- [✅] Structured JSON logging
- [✅] Deploy lên Railway hoặc Render
- [✅] Public URL hoạt động

### 🏗 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

###  Step-by-step

#### Step 1: Project setup (5 phút)

```bash
mkdir my-production-agent
cd my-production-agent

# Tạo structure
mkdir -p app
touch app/__init__.py
touch app/main.py
touch app/config.py
touch app/auth.py
touch app/rate_limiter.py
touch app/cost_guard.py
touch Dockerfile
touch docker-compose.yml
touch requirements.txt
touch .env.example
touch .dockerignore
```

#### Step 2: Config management (10 phút)

**File:** `app/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # App
    app_name: str = Field(default="Production AI Agent", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")

    # LLM
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", env="LLM_MODEL")

    # Security
    agent_api_key: str = Field(default="dev-key-change-me-in-production", env="AGENT_API_KEY")
    allowed_origins: list = Field(default=["*"], env="ALLOWED_ORIGINS")

    # Rate limiting & Budget
    rate_limit_per_minute: int = Field(default=20, env="RATE_LIMIT_PER_MINUTE")
    daily_budget_usd: float = Field(default=5.0, env="DAILY_BUDGET_USD")

    # Storage
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

settings = Settings()
```

#### Step 3: Main application (15 phút)

**File:** `app/main.py`

```python
import os
import time
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Security
from pydantic import BaseModel, Field
from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget
from utils.mock_llm import ask as llm_ask

logger = logging.getLogger(__name__)
START_TIME = time.time()
_is_ready = False

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
    logger.info("Starting production agent...")
    _is_ready = True
    yield
    _is_ready = False
    logger.info("Shutting down production agent...")

app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1)}

@app.get("/ready")
def ready():
    # Thực hiện ping kiểm tra Redis kết nối
    from .rate_limiter import r
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
    
    # Process question
    answer = llm_ask(body.question)
    
    # Budget Record (Output)
    output_tokens = len(answer.split()) * 2
    check_budget(user_key, (output_tokens / 1000) * 0.0006)
    
    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
```

#### Step 4: Authentication (5 phút)

**File:** `app/auth.py`

```python
from fastapi import Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(x_api_key: str = Security(api_key_header)) -> str:
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return x_api_key
```

#### Step 5: Rate limiting (10 phút)

**File:** `app/rate_limiter.py`

```python
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
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min",
            )
        member = f"{now}:{time.time_ns()}"
        r.zadd(redis_key, {member: now})
        r.expire(redis_key, 65)
    except HTTPException:
        raise
    except Exception:
        pass # Dự phòng lỗi kết nối Redis
```

#### Step 6: Cost guard (10 phút)

**File:** `app/cost_guard.py`

```python
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
```

#### Step 7: Dockerfile (5 phút)

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
RUN groupadd -r agent && useradd -r -g agent agent
WORKDIR /app
COPY --chown=agent:agent --from=builder /root/.local /home/agent/.local
COPY app/ ./app/
COPY utils/ ./utils/
RUN chown -R agent:agent /app
USER agent
ENV PATH=/home/agent/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

#### Step 8: Docker Compose (5 phút)

```yaml
version: "3.9"
services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=staging
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
```

#### Step 9: Test locally (5 phút)

```bash
docker compose up --scale agent=3

# Test all endpoints
curl http://localhost/health
curl http://localhost/ready
curl -H "X-API-Key: secret" http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "user1"}'
```

#### Step 10: Deploy (10 phút)

```bash
# Railway
railway init
railway variables set REDIS_URL=...
railway variables set AGENT_API_KEY=...
railway up

# Hoặc Render
# Push lên GitHub → Connect Render → Deploy
```

###  Validation

Chạy script kiểm tra:

```bash
cd 06-lab-complete
python check_production_ready.py
```

Script sẽ kiểm tra:
-  Dockerfile exists và valid
-  Multi-stage build
-  .dockerignore exists
-  Health endpoint returns 200
-  Readiness endpoint returns 200
-  Auth required (401 without key)
-  Rate limiting works (429 after limit)
-  Cost guard works (402 when exceeded)
-  Graceful shutdown (SIGTERM handled)
-  Stateless (state trong Redis, không trong memory)
-  Structured logging (JSON format)

###  Grading Rubric

| Criteria | Points | Description |
|----------|--------|-------------|
| **Functionality** | 20 | Agent hoạt động đúng |
| **Docker** | 15 | Multi-stage, optimized |
| **Security** | 20 | Auth + rate limit + cost guard |
| **Reliability** | 20 | Health checks + graceful shutdown |
| **Scalability** | 15 | Stateless + load balanced |
| **Deployment** | 10 | Public URL hoạt động |
| **Total** | 100 | |

---

##  Hoàn Thành!

Bạn đã:
-  Hiểu sự khác biệt dev vs production
-  Containerize app với Docker
-  Deploy lên cloud platform
-  Bảo mật API
-  Thiết kế hệ thống scalable và reliable

###  Next Steps

1. **Monitoring:** Thêm Prometheus + Grafana
2. **CI/CD:** GitHub Actions auto-deploy
3. **Advanced scaling:** Kubernetes
4. **Observability:** Distributed tracing với OpenTelemetry
5. **Cost optimization:** Spot instances, auto-scaling

###  Resources

- [12-Factor App](https://12factor.net/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)

---

##  Q&A

**Q: Tôi không có credit card, có thể deploy không?**  
A: Có! Railway cho $5 credit, Render có 750h free tier.

**Q: Mock LLM khác gì với OpenAI thật?**  
A: Mock trả về canned responses, không gọi API. Để dùng OpenAI thật, set `OPENAI_API_KEY` trong env.

**Q: Làm sao debug khi container fail?**  
A: `docker logs <container_id>` hoặc `docker exec -it <container_id> /bin/sh`

**Q: Redis data mất khi restart?**  
A: Dùng volume: `volumes: - redis-data:/data` trong docker-compose.

**Q: Làm sao scale trên Railway/Render?**  
A: Railway: `railway scale <replicas>`. Render: Dashboard → Settings → Instances.

---

**Happy Deploying! **
