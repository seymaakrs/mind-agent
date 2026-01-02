# Docker Calistirma

Bu proje iki servisle ayaga kalkar:

- `api`: FastAPI + orchestrator
- `ngrok`: `learning-partially-rabbit.ngrok-free.app` uzerinden 8000 portunu disariya acar

## Gerekli degiskenler

Ortam degiskenlerini host tarafinda tanimlayin (tercihen `.env` icinde):

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (opsiyonel)
- `N8N_BASE_URL` (opsiyonel; set edilmezse varsayilan kullanilir)
- `NGROK_AUTHTOKEN`

## Calistirma

```bash
docker compose up --build
```

API local: `http://localhost:8000/task`

## Test

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"task":"Selam de"}'
```
