# CreditFlow Scheduler Service

Owns account content calendars and emits `content.scheduled` when a scheduled post becomes due.

## Run locally

```powershell
cd C:\Development\CreditFlow\scheduler-service
..\ .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn scheduler_service.main:app --reload --port 8108
```

Worker and beat:

```powershell
celery -A scheduler_service.worker.celery_app worker --loglevel=info --pool=solo
celery -A scheduler_service.worker.celery_app beat --loglevel=info
```

## Events

- Publishes: `content.scheduled`
- Consumes: `content.created`

All schedule times are stored in UTC. Calendar responses can be localized with the `timezone` query parameter.
