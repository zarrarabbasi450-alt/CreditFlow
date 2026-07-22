# CreditFlow Content Service

Stores generated and manually-created content drafts before scheduling/publishing.

## Owns

- PostgreSQL schema: `content`
- Tables: `content`, `content_versions`
- Local dev upload volume: `uploads/`

## API

- `GET /health`, `/ready`, `/version`
- `GET /api/v1/content`
- `POST /api/v1/content`
- `GET /api/v1/content/{content_id}`
- `PATCH /api/v1/content/{content_id}`
- `DELETE /api/v1/content/{content_id}`
- `POST /api/v1/content/{content_id}/approve`
- `POST /api/v1/content/{content_id}/publish`
- `POST /api/v1/content/{content_id}/image`

## Events

- Publishes: `content.created`, `content.updated`
- Consumes: `ai.generation_completed`

Run:

```powershell
cd C:\Development\CreditFlow\content-service
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn content_service.main:app --reload --port 8007
```
