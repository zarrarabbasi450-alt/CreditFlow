# CreditFlow Social Publishing Service

Owns LinkedIn OAuth connections and publishing scheduled content to LinkedIn.

## Responsibilities

- LinkedIn OAuth 2.0 / OpenID Connect connect flow.
- Encrypted token storage per account.
- Text-only and image post publishing.
- Image upload via LinkedIn Images API.
- Consumes `content.scheduled`.
- Publishes `post.published` and `post.failed`.
- Records publish jobs and media metadata.

## Local setup

1. Create a LinkedIn Developer App.
2. Add products:
   - Sign In with LinkedIn using OpenID Connect
   - Share on LinkedIn
3. Add scopes:
   - `openid`
   - `profile`
   - `email`
   - `w_member_social`
4. Set callback URL:
   - `http://localhost:8109/api/v1/publishing/linkedin/callback`
5. Generate a Fernet key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

6. Copy `.env.example` to `.env` and fill values.

## Run

```powershell
cd C:\Development\CreditFlow\social-publishing-service
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m pip install -e .
..\.venv\Scripts\alembic.exe upgrade head
python -m uvicorn social_publishing_service.main:app --reload --port 8109
```
