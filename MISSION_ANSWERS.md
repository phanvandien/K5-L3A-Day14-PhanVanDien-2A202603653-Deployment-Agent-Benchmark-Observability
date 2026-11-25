# Day 14 Lab — Mission Answers

> Lớp: K5-L3A · Bài cá nhân

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns tìm thấy trong `01-localhost-vs-production/develop/app.py`

| # | Dòng | Anti-pattern | Hậu quả khi lên production |
|---|------|--------------|----------------------------|
| 1 | 17–18 | Hardcode secret: `OPENAI_API_KEY = "sk-..."`, `DATABASE_URL` chứa `admin:password123` | Push lên GitHub là lộ key/mật khẩu; muốn đổi key phải sửa code và deploy lại |
| 2 | 34 | Log ra secret: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | Key nằm trong log, ai đọc được log (dev, hệ thống log tập trung) đều thấy |
| 3 | 21–22 | Không có config management: `DEBUG = True`, `MAX_TOKENS = 500` cố định | Không đổi được giữa dev/staging/prod; debug bật trên production |
| 4 | 33, 38 | Dùng `print()` thay vì logging có cấu trúc | Không có level, timestamp, không parse được bằng Loki/Datadog; còn in toàn bộ câu hỏi/câu trả lời của user |
| 5 | 42 | Không có health check (`/health`, `/ready`) | Platform không biết agent đã treo/crash để restart; load balancer không biết khi nào được route traffic |
| 6 | 51 | `host="localhost"` | Trong container chỉ nhận kết nối từ chính nó → bên ngoài không gọi được; phải bind `0.0.0.0` |
| 7 | 52 | `port=8000` cố định | Railway/Render inject `PORT` qua env var; cứng port thì platform không route được |
| 8 | 53 | `reload=True` | Chế độ dev: tốn tài nguyên theo dõi file, không ổn định trên production |
| 9 | cả file | Không xử lý SIGTERM / graceful shutdown | Khi deploy bản mới hoặc scale down, request đang chạy bị cắt ngang |

### Exercise 1.2: Chạy bản develop

Lệnh:
```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```

Kết quả:
```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:40:23 GMT
server: uvicorn
content-length: 126
content-type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Quan sát: app chạy được, nhưng terminal server in ra `[DEBUG] Using key: sk-hardcoded-...` → minh hoạ anti-pattern #2. Gọi bằng JSON body trả **422** vì bản develop nhận `question` qua query string.

### Exercise 1.3: So sánh develop vs production

| Feature | Develop | Production | Tại sao quan trọng? |
|---------|---------|------------|---------------------|
| Config | Hardcode trong `app.py` (dòng 17–22) | Đọc từ env var qua `config.py` (`Settings` dataclass, `os.getenv`) | Cùng một code chạy được ở dev/staging/prod; đổi cấu hình không cần sửa code (12-Factor: Config) |
| Secrets | Ghi thẳng trong code và in ra log | Lấy từ env (`OPENAI_API_KEY`, `AGENT_API_KEY`); `validate()` báo lỗi nếu thiếu `AGENT_API_KEY` ở production; log không chứa secret | Tránh lộ key qua Git và log; fail fast khi cấu hình thiếu |
| Health check | Không có | `GET /health` (liveness, trả uptime/version) và `GET /ready` (readiness, 503 khi chưa sẵn sàng) | Platform tự restart khi agent chết; load balancer chỉ gửi traffic khi agent sẵn sàng |
| Logging | `print()` | JSON qua `logging` (`{"time":..,"level":..,"msg":..}`), chỉ log độ dài câu hỏi, không log nội dung/secret | Máy parse được, lọc theo level, đưa vào hệ thống log tập trung; bảo vệ dữ liệu người dùng |
| Host / Port | `localhost:8000` cố định | `HOST` mặc định `0.0.0.0`, `PORT` từ env | Chạy được trong container và trên cloud (platform cấp PORT) |
| Reload / Debug | `reload=True` luôn bật | `reload=settings.debug` (chỉ khi `DEBUG=true`) | Production không chạy chế độ dev |
| Shutdown | Đột ngột | `lifespan` đặt `is_ready=False` rồi dọn dẹp; có handler SIGTERM | Request đang xử lý được hoàn thành trước khi tắt, không mất request khi deploy/scale |
| CORS | Không cấu hình | `ALLOWED_ORIGINS` từ env | Chỉ cho phép origin được cấu hình gọi API |

Kết quả chạy bản production:
```text

HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:41:45 GMT
server: uvicorn
content-length: 130
content-type: application/json

{"status":"ok","uptime_seconds":10.0,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:41:46.066216+00:00"}
```

---

## Part 2: Docker

### Exercise 2.1: Câu hỏi về Dockerfile
1. Base image: python:3.11, bản Python đầy đủ khoảng 1GB
2. Working directory: /app
3. Tại sao COPY requirements.txt trước: Docker cache theo từng layer . Nếu chỉ sửa code mà requirements không đổi thì layer pip install được dùng lại từ cache, nên build nhanh hơn
4. CMD vs ENTRYPOINT: CMD là lệnh mặc định , có thể ghi đè bằng docker run image. ENTRYPOINT là lệnh cố định , tham số truyền vào sẽ được nối thêm vào sau đó.

### Exercise 2.2: Build và chạy container
```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:17:14 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:17:43 GMT
server: uvicorn
content-length: 54
content-type: application/json

{"status":"ok","uptime_seconds":45.5,"container":true}
```

### Exercise 2.3: So sánh kích thước image (đo bằng `docker images`)
- Develop (`python:3.11`, single-stage): 426 MB
- Production (`python:3.11-slim`, multi-stage): 57.4 MB
- Chênh lệch: (426 − 57.4) / 426 ≈ **86.5%** nhỏ hơn

Stage 1 (`builder`): cài gcc, libpq-dev và `pip install --user` các dependency.
Stage 2 (`runtime`): image slim mới, chỉ copy `/root/.local` (package đã cài) và code; chạy user non-root, có `HEALTHCHECK`.
Image nhỏ hơn vì base `slim` thay cho bản full, và build tools (gcc, apt cache) nằm lại ở stage 1, không vào image cuối.

### Exercise 2.4: Docker Compose stack
Sơ đồ service:
```text
Client ──:8081──▶ nginx:80 ──▶ agent:8000 (FastAPI, uvicorn 2 workers)
                                  ├──▶ redis:6379   (cache / rate limit)
                                  └──▶ qdrant:6333  (vector DB)
         (tất cả trong network "internal"; chỉ nginx mở port ra ngoài)
```
Agent gọi các service khác bằng tên service nhờ DNS nội bộ của Docker. `depends_on` + `condition: service_healthy` nghĩa là agent chỉ khởi động sau khi Redis và Qdrant đã healthy. Nginx là reverse proxy / load balancer, chuyển request tới upstream `agent:8000`.

Ghi chú: máy có IIS chiếm cổng 80 (lần test đầu trả `404` từ `Server: Microsoft-IIS/10.0`), nên đổi port của nginx trong `docker-compose.yml` thành `8081:80` và `8443:443`.

`curl -i http://localhost:8081/health` (qua Nginx):
```text
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 08:34:59 GMT
Content-Type: application/json
Content-Length: 96
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":20.6,"version":"2.0.0","timestamp":"2026-11-25T08:34:59.741884"}
```

`curl -i -X POST http://localhost:8081/ask` (qua Nginx):
```text
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 08:37:19 GMT
Content-Type: application/json
Content-Length: 103
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6
- Nền tảng:
- URL:
- Screenshot: `screenshots/`

### So sánh `railway.toml` và `render.yaml`

### Exercise 3.3: Pipeline Cloud Run (`cloudbuild.yaml` + `service.yaml`)

---

## Part 4: API Security

### Exercise 4.1: API Key (401 / 200)
```text
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:59:15 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 08:59:59 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"detail":"Invalid API key."}

HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:00:19 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

```

- Key được check ở đâu? Hàm verify_api_key ở dòng 39, gắn vào /ask bằng Depends(verify_api_key) ở dòng 70.
- Sai key thì sao? Thiếu key trả 401, sai key trả 403. Ghi chú thêm: Part 6 yêu cầu cả hai trường hợp đều trả 401.
- Rotate key thế nào? Đổi biến môi trường AGENT_API_KEY rồi restart, không phải sửa code.

### Exercise 4.2: JWT
Lấy token bằng `POST /auth/token` (tài khoản `student`/`demo123`), rồi gọi `/ask` với header `Authorization: Bearer <token>` (token đã che):
```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:27:22 GMT
server: uvicorn
content-length: 215
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
```


### Exercise 4.3: Rate limiting (429)
```text
Request 1: 200
Request 2: 200
Request 3: 200
Request 4: 200
Request 5: 200
Request 6: 200
Request 7: 200
Request 8: 200
Request 9: 200
Request 10: 200
Request 11: 429
Request 12: 429
Request 13: 429
Request 14: 429
Request 15: 429

HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 09:29:05 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795599005
retry-after: 36
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":36}}
```

### Exercise 4.4: Cost guard
- Cách tính chi phí: theo token, giá kiểu GPT-4o-mini là $0.15/1M input và $0.60/1M output (dòng 20–21).
- Ngân sách: $1/ngày mỗi user và $10/ngày tổng (dòng 128).
- Trước khi gọi LLM, check_budget() kiểm tra:
  - vượt ngân sách user thì trả 402 Payment Required;
  - vượt ngân sách tổng thì trả 503;
  - dùng tới ngưỡng cảnh báo (warn_at_pct) thì ghi log warning.
- Sau khi gọi LLM, record_usage() cộng dồn chi phí cho user và cho tổng.
- Rate limit và cost guard khác nhau: rate limit chặn tốc độ (số request), cost guard chặn tiền. Mười request/phút với prompt rất dài vẫn có thể đốt hết ngân sách, nên cần cả hai.
- Hạn chế: dữ liệu lưu trong RAM. Ở Part 6 sẽ chuyển sang Redis với key theo ngày, kiểu budget:<user>:<YYYY-MM-DD>, và đặt TTL.
---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks
### Exercise 5.2: Graceful shutdown
### Exercise 5.3: Stateless design
### Exercise 5.4: Load balancing
### Exercise 5.5: Test stateless
```text
<!-- TODO -->
```

---

## Part 6: Final Project — output `check_production_ready.py`
```text
<!-- TODO: dán phần "📋 Checklist Deliverable" -->
```

---

## AI log

| Ngày | Hỏi AI gì | Nhận được gì | Tôi tự sửa / kiểm tra thế nào |
|------|-----------|--------------|-------------------------------|
| 2026-11-25 | Claude Code: đọc repo và hướng dẫn từng bước; cài WSL2 + Docker | Lộ trình CP0–CP8, cách cài Ubuntu WSL, tạo venv | Tự chạy lệnh, kiểm tra `os.name` = `posix`, `docker run hello-world` |
| 2026-11-25 | Claude Code: phân tích `develop/app.py` và `production/app.py` cho Part 1 | Bảng anti-pattern 1.1 và bảng so sánh 1.3 | Đối chiếu từng dòng code được trích; tự chạy 1.2 và 1.3 và dán output thật |
| 2026-11-25 | Claude Code: hướng dẫn Part 2, sửa lỗi cổng 80 bị IIS chiếm | Gợi ý trả lời 2.1, giải thích multi-stage, đổi port nginx sang 8081 | Tự build image, tự đo `docker images`, tự chạy compose và curl |
| 2026-11-25 | Claude Code: kiểm tra Part 2 và Part 4 | Phát hiện token JWT bị lộ trong bài và lỗi 403 `Invalid token` do biến `TOKEN` đặt sai | Che token, chạy lại 4.2 và 4.3 |
