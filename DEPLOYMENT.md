# Deployment Information

## Public URL
<!-- TODO: https://<tên-service>.up.railway.app -->

## Platform
Railway: agent build từ `06-lab-complete/Dockerfile` (theo `06-lab-complete/railway.toml`) + Railway Redis.

## Test Commands

Đặt biến trước khi test (không ghi key thật vào file này):
```bash
BASE=https://<tên-service>.up.railway.app
AGENT_API_KEY=<key đã đặt trên Railway>
```

### Health / Readiness
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"   # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"    # 200 (Redis kết nối được)
```

### API Test
```bash
# Không có key → 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'

# Có key → 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"user_id":"test","question":"Hello"}'
```

### Kết quả
```text
<!-- TODO: dán 4 mã HTTP: 200 / 200 / 401 / 200 -->
```

## Environment Variables Set (trên Railway, không ghi trong code)
| Biến | Giá trị |
|------|---------|
| `PORT` | Railway tự cấp |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | secret (đặt trong tab Variables) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (reference tới service Redis) |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `LOG_LEVEL` | `INFO` |

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
