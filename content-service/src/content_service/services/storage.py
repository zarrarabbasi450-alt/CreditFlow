from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from content_service.core.errors import ContentError


class LocalStorage:
    def __init__(self, upload_dir: str, public_base_url: str) -> None:
        self.upload_dir = Path(upload_dir)
        self.public_base_url = public_base_url.rstrip("/")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, file: UploadFile) -> tuple[str, str]:
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise ContentError(415, "UNSUPPORTED_MEDIA_TYPE", "Only image uploads are supported")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            suffix = ".png"
        asset_ref = f"{uuid4()}{suffix}"
        target = self.upload_dir / asset_ref
        data = await file.read()
        if len(data) > 5 * 1024 * 1024:
            raise ContentError(413, "UPLOAD_TOO_LARGE", "Images must be 5MB or smaller")
        target.write_bytes(data)
        return f"{self.public_base_url}/{asset_ref}", asset_ref
