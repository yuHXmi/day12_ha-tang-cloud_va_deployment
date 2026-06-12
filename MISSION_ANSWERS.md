# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `develop/app.py`
1. **Hardcoded Secrets:** API Key (`OPENAI_API_KEY`) và Database URL (`DATABASE_URL`) được ghi trực tiếp (hardcode) trong code, dẫn đến nguy cơ lộ lọt thông tin nhạy cảm khi đẩy lên hệ thống quản lý phiên bản (Git).
2. **Thiếu Config Management:** Chế độ debug (`DEBUG = True`) và cấu hình hệ thống (`MAX_TOKENS = 500`) được viết trực tiếp mà không cho phép cấu hình linh hoạt thông qua biến môi trường (Environment Variables).
3. **Sử dụng `print()` cho Logging:** Sử dụng `print()` thay vì thư viện logging chuyên nghiệp. Điều này làm log không có cấu trúc cấu hình (Unstructured) và cực kỳ nguy hại khi ghi thẳng thông tin bí mật (API Key) ra log.
4. **Thiếu các cổng kiểm tra trạng thái (Health Check Endpoints):** Không cấu hình các endpoint `/health` (Liveness) và `/ready` (Readiness), khiến nền tảng Cloud (Railway/Render/Kubernetes) không thể tự động giám sát và khởi động lại container khi gặp lỗi.
5. **Cấu hình Port và Host cứng:** Dịch vụ Uvicorn bị gán cứng chạy tại `host="localhost"` và `port=8000` với `reload=True`. Điều này ngăn cản ứng dụng nhận traffic từ mạng bên ngoài khi chạy trong container và không thể nhận cổng tự động inject từ Cloud platform.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Config** | Hardcoded trong code | Environment Variables (12-Factor App) | Giúp dễ dàng chuyển đổi cấu hình giữa các môi trường (Dev, Staging, Prod) mà không cần sửa code; tăng tính bảo mật (không lộ secrets). |
| **Health Check** | Không có (❌) | Endpoint `/health` (Liveness) và `/ready` (Readiness) (✅) | Giúp các nền tảng điều phối (Orchestrator) và Load Balancer biết khi nào dịch vụ bị lỗi để khởi động lại hoặc tạm ngưng định tuyến traffic. |
| **Logging** | Dùng `print()` thủ công | Structured JSON Logging | Dễ dàng thu thập, truy vấn và phân tích log tự động (qua ELK Stack, Datadog, Loki) mà không gây lộ thông tin nhạy cảm. |
| **Shutdown** | Đột ngột khi tắt process | Graceful Shutdown (xử lý SIGTERM) | Đảm bảo hệ thống hoàn tất các tiến trình/request đang xử lý dở dang (in-flight requests) và đóng kết nối DB/Redis an toàn trước khi dừng hẳn. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` (Chứa toàn bộ hệ điều hành Debian và môi trường phát triển Python đầy đủ, dung lượng lớn ~1GB).
2. **Working directory:** `/app` (Thư mục làm việc mặc định chứa mã nguồn và tài nguyên của ứng dụng bên trong container).
3. **Tại sao COPY requirements.txt trước?** Để tận dụng cơ chế Docker Layer Caching. Docker sẽ bỏ qua việc cài lại các thư viện Python (tốn thời gian) ở các lần build sau nếu file `requirements.txt` không có thay đổi nào.
4. **CMD vs ENTRYPOINT khác nhau thế nào?** 
   * `ENTRYPOINT` định nghĩa file thực thi chính của container, không thể bị ghi đè một cách dễ dàng khi chạy container.
   * `CMD` định nghĩa các tham số mặc định truyền vào `ENTRYPOINT` hoặc lệnh chạy mặc định, có thể dễ dàng bị ghi đè khi ta truyền đối số lúc chạy lệnh `docker run`.

### Exercise 2.3: Image size comparison
* **Develop Image Size:** ~1.02 GB (1020 MB) - Sử dụng base image đầy đủ và không tối ưu hóa các layer.
* **Production Image Size:** ~145 MB - Sử dụng base image rút gọn `python:3.11-slim` kết hợp chiến thuật Multi-stage build.
* **Difference (Giảm thiểu):** ~85.8% (Giúp tối ưu băng thông mạng, giảm thời gian deploy và thu nhỏ bề mặt tấn công bảo mật).

### Exercise 2.4: Docker Compose stack
Sơ đồ luồng xử lý yêu cầu (Architecture Diagram):
```
Client (Port 80/443) ──> Nginx (Load Balancer & Reverse Proxy)
                           │
                           ├──> Agent Instance 1 (FastAPI - Port 8000) ──> Redis Session & Limit Store (Port 6379)
                           ├──> Agent Instance 2 (FastAPI - Port 8000) ──> Redis Session & Limit Store (Port 6379)
                           └──> Agent Instance 3 (FastAPI - Port 8000) ──> Redis Session & Limit Store (Port 6379)
```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
* **URL:** `https://perfect-reflection-production-1552.up.railway.app`
* **Screenshot:** [railway_dashboard.png](screenshots/railway_dashboard.png)

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results
Dưới đây là kết quả kiểm thử bảo mật API:
1. **Khi không gửi X-API-Key:**
   ```json
   {
     "detail": "Invalid or missing API key. Include header: X-API-Key: <key>"
   }
   ```
   => Trả về mã lỗi HTTP `401 Unauthorized`.
2. **Khi gửi đúng X-API-Key:**
   ```json
   {
     "question": "Hello",
     "answer": "Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.",
     "model": "gpt-4o-mini",
     "timestamp": "2026-06-12T07:30:00Z"
   }
   ```
   => Trả về mã HTTP `200 OK`.
3. **Khi vượt quá tần suất (Rate Limit - >10 req/min):**
   ```json
   {
     "detail": "Rate limit exceeded: 10 req/min"
   }
   ```
   => Trả về mã lỗi HTTP `429 Too Many Requests`.

### Exercise 4.4: Cost guard implementation
* **Giải pháp triển khai:**
  Sử dụng Redis để theo dõi chi phí theo ngày của từng định danh API Key (`user_id`). Khi có yêu cầu đến, hệ thống tính toán sơ bộ token đầu vào để kiểm tra budget trong Redis thông qua key `budget:{user_id}:{today}`. Nếu chi phí vượt quá giới hạn ($1.0/ngày cho mỗi user hoặc $10.0/ngày toàn cục), hệ thống sẽ từ chối xử lý bằng mã lỗi `402 Payment Required` hoặc `503 Service Unavailable`. Sau khi gọi LLM thành công, chi phí thực tế sẽ được cộng dồn vào Redis.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
1. **Health Checks:** Endpoint `/health` trả về trạng thái hoạt động của tiến trình. Endpoint `/ready` ping tới Redis/Database để kiểm tra xem hệ thống đã sẵn sàng xử lý request chưa.
2. **Graceful Shutdown:** Lắng nghe tín hiệu `SIGTERM` từ Cloud Orchestrator, thiết lập biến `_is_ready = False` để các Load Balancer ngừng điều phối traffic mới tới instance này, chờ các requests hiện tại hoàn thành xử lý trong khoảng 30s trước khi shutdown hoàn toàn.
3. **Stateless Design:** Chuyển toàn bộ dữ liệu lịch sử chat từ bộ nhớ RAM sang lưu trữ tập trung tại Redis. Điều này cho phép mở rộng quy mô (Scale Out) lên nhiều instance mà không sợ mất lịch sử hội thoại khi requests của người dùng được phân bổ ngẫu nhiên giữa các instances.
4. **Load Balancing:** Cấu hình Nginx sử dụng DNS Service Discovery của Docker để phân bổ các cuộc gọi đến 3 instances agent bằng cơ chế Round Robin.
