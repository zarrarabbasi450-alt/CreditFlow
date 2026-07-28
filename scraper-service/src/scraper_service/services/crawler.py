from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from scraper_service.core.errors import ScraperError


@dataclass(frozen=True)
class PageFetchResult:
    url: str
    status_code: int
    title: str | None
    text: str
    links: list[str] = field(default_factory=list)


def _extract(url: str, status_code: int, html: str, max_chars: int) -> PageFetchResult:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = " ".join(soup.get_text(separator=" ").split())[:max_chars]
    domain = urlparse(url).netloc
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        absolute = urljoin(url, href)
        if urlparse(absolute).netloc == domain and absolute not in links:
            links.append(absolute)
    return PageFetchResult(url=url, status_code=status_code, title=title, text=text, links=links)


class CrawlerProtocol(Protocol):
    async def fetch(self, url: str) -> PageFetchResult: ...
    async def close(self) -> None: ...


class HttpxCrawler:
    """Default crawler: fast, dependency-light, works without a browser install.

    Cannot execute client-side JavaScript. Use the Playwright engine for
    JS-rendered targets (see PlaywrightCrawler).
    """

    def __init__(self, user_agent: str, timeout_seconds: float, max_document_chars: int) -> None:
        self.max_document_chars = max_document_chars
        self.client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    async def fetch(self, url: str) -> PageFetchResult:
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as exc:
            raise ScraperError(502, "FETCH_FAILED", f"Unable to fetch {url}: {exc}") from exc
        if response.status_code >= 400:
            raise ScraperError(
                502, "FETCH_FAILED", f"{url} responded with {response.status_code}",
                {"status_code": response.status_code},
            )
        return _extract(str(response.url), response.status_code, response.text, self.max_document_chars)

    async def close(self) -> None:
        await self.client.aclose()


class PlaywrightCrawler:
    """Headless-browser crawler for JS-rendered pages.

    Requires `playwright install chromium` (see the Dockerfile). Kept behind
    the same CrawlerProtocol as HttpxCrawler so the rest of the service is
    engine-agnostic.
    """

    def __init__(self, user_agent: str, timeout_seconds: float, max_document_chars: int) -> None:
        self.user_agent = user_agent
        self.timeout_ms = timeout_seconds * 1000
        self.max_document_chars = max_document_chars
        self._playwright: object | None = None
        self._browser: object | None = None

    async def _ensure_browser(self) -> object:
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def fetch(self, url: str) -> PageFetchResult:
        browser = await self._ensure_browser()
        page = await browser.new_page(user_agent=self.user_agent)  # type: ignore[attr-defined]
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            if response is None:
                raise ScraperError(502, "FETCH_FAILED", f"Unable to fetch {url}")
            if response.status >= 400:
                raise ScraperError(
                    502, "FETCH_FAILED", f"{url} responded with {response.status}",
                    {"status_code": response.status},
                )
            html = await page.content()
            return _extract(page.url, response.status, html, self.max_document_chars)
        finally:
            await page.close()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()  # type: ignore[attr-defined]
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[attr-defined]
