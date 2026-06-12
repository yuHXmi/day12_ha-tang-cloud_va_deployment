# Deployment Information

## Public URL
https://perfect-reflection-production-1552.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://perfect-reflection-production-1552.up.railway.app/health
# Expected: {"status": "ok", "version": "1.0.0", "environment": "production", ...}
```

### Readiness Check
```bash
curl https://perfect-reflection-production-1552.up.railway.app/ready
# Expected: {"ready": true} (or 503 if dependencies fail)
```

### API Test (with authentication)
```bash
curl -X POST https://perfect-reflection-production-1552.up.railway.app/ask \
  -H "X-API-Key: your-production-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "question": "Hello"}'
```

### Multi-turn Conversation Context Test
```bash
# Turn 1: Introduce name
curl -X POST https://perfect-reflection-production-1552.up.railway.app/ask \
  -H "X-API-Key: your-production-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "question": "My name is Alice"}'

# Turn 2: Query name
curl -X POST https://perfect-reflection-production-1552.up.railway.app/ask \
  -H "X-API-Key: your-production-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "question": "What is my name?"}'
# Expected response: {"question": "What is my name?", "answer": "Your name is Alice.", ...}
```

## Environment Variables Set
- `PORT` = `8000`
- `ENVIRONMENT` = `production`
- `REDIS_URL` = `redis://...` (Cloud Redis instance URL)
- `AGENT_API_KEY` = `your-production-secret-key`
- `DAILY_BUDGET_USD` = `5.0`
- `RATE_LIMIT_PER_MINUTE` = `20`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
