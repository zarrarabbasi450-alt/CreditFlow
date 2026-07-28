from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from scraper_service.core.errors import ScraperError


@dataclass(frozen=True)
class SerpResult:
    query: str
    title: str
    organic_results: list[dict[str, Any]] = field(default_factory=list)
    related_searches: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class SerpClientProtocol(Protocol):
    async def search(self, query: str) -> SerpResult: ...
    async def close(self) -> None: ...


class SerpApiClient:
    """Thin client around SerpApi (https://serpapi.com) for search-engine data.

    Using an API instead of scraping Google/Bing directly keeps trend and
    competitor-keyword jobs compliant with those engines' robots.txt / ToS.
    """

    def __init__(self, api_key: str, base_url: str, engine: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.engine = engine
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def search(self, query: str) -> SerpResult:
        if not self.api_key:
            raise ScraperError(
                503,
                "SERPAPI_NOT_CONFIGURED",
                "SERPAPI_API_KEY is not configured for this environment",
            )
        response = await self.client.get(
            self.base_url,
            params={"q": query, "engine": self.engine, "api_key": self.api_key},
        )
        if response.status_code >= 400:
            raise ScraperError(
                502,
                "SERPAPI_REQUEST_FAILED",
                "SerpApi request failed",
                {"status_code": response.status_code, "body": response.text[:500]},
            )
        payload = dict(response.json())
        if "error" in payload:
            raise ScraperError(502, "SERPAPI_REQUEST_FAILED", str(payload["error"]))
        return SerpResult(
            query=query,
            title=str(payload.get("search_information", {}).get("query_displayed", query)),
            organic_results=list(payload.get("organic_results") or []),
            related_searches=list(payload.get("related_searches") or []),
            raw=payload,
        )

    async def close(self) -> None:
        await self.client.aclose()
