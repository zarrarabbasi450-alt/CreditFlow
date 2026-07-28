from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from ai_generation_service.core.config import Settings
from ai_generation_service.core.errors import AIServiceError

SCOPE_SYSTEM_PROMPT = (
    "You are CreditFlow's AI Studio, a content-generation assistant. You ONLY write "
    "marketing and social-media content on request: posts (e.g. LinkedIn posts), "
    "articles, campaign briefs, carousels, job postings, and closely related "
    "copywriting such as headlines, captions, hashtags, or outlines for the above. "
    "If the user's request is not asking you to create this kind of content — for "
    "example general knowledge questions, math, coding help, or anything unrelated "
    "to posts/content creation — you must refuse. When refusing, respond with "
    "exactly this and nothing else: \"I can't help with that here — AI Studio only "
    "generates posts and related content.\""
)


class AIProviderProtocol(Protocol):
    def stream_completion(self, model: str, prompt: str) -> AsyncIterator[str]: ...
    async def close(self) -> None: ...


class OpenRouterProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=60)

    async def stream_completion(self, model: str, prompt: str) -> AsyncIterator[str]:
        if not self.settings.openrouter_api_key:
            raise AIServiceError(503, "OPENROUTER_NOT_CONFIGURED", "OpenRouter API key is not configured")
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }
        payload = {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": SCOPE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            async with self.client.stream(
                "POST", f"{self.settings.openrouter_base_url}/chat/completions", headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise AIServiceError(
                        502,
                        "OPENROUTER_REJECTED_REQUEST",
                        body[:500] or "OpenRouter rejected the generation request",
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    token = _extract_delta(data)
                    if token:
                        yield token
        except AIServiceError:
            raise
        except httpx.HTTPError as exc:
            raise AIServiceError(502, "OPENROUTER_UNAVAILABLE", "OpenRouter request failed") from exc

    async def close(self) -> None:
        await self.client.aclose()


def _extract_delta(data: str) -> str:
    import json

    payload = json.loads(data)
    choices = payload.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return str(delta.get("content") or "")


class InMemoryAIProvider:
    def __init__(self, tokens: list[str] | None = None) -> None:
        self.tokens = tokens or ["CreditFlow", " turns", " content", " operations", " into", " momentum."]

    async def stream_completion(self, model: str, prompt: str) -> AsyncIterator[str]:
        del model, prompt
        for token in self.tokens:
            yield token

    async def close(self) -> None:
        return None
