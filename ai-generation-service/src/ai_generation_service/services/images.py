from typing import Protocol
from urllib.parse import quote

from ai_generation_service.core.config import Settings


class ImageProviderProtocol(Protocol):
    def image_url(self, prompt: str) -> str: ...


class PollinationsImageProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def image_url(self, prompt: str) -> str:
        return f"{self.settings.pollinations_base_url}/{quote(prompt)}?width=1200&height=630&nologo=true"
