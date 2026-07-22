# CreditFlow AI Generation Service

Wraps OpenRouter streaming generation, publishes token chunks through Redis pub/sub, records prompt history, and emits AI usage events for the Usage Service.

## Run

```powershell
cd C:\Development\CreditFlow\ai-generation-service
..\ .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn ai_generation_service.main:app --reload --port 8006
```

Set `OPENROUTER_API_KEY` in `.env` for real OpenRouter calls. Without a key, tests can still use the in-memory provider.
