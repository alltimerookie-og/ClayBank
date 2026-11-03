"""Article extraction provider using trafilatura."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from Backend.extraction.result import ExtractionResult, merge_kind


@dataclass(frozen=True, slots=True)
class CrawlOptions:
    """Bounded dynamic crawl configuration."""

    max_depth: int = 0
    max_pages: int = 1
    page_timeout_ms: int = 15000
    overall_timeout_s: int = 60
    workers: int = 5


class ArticleFetcher(Protocol):
    """Structural source for deterministic article extraction."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Return HTML and metadata for one URL."""
        ...


class HttpArticleFetcher:
    """HTTP article source with a short timeout."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Download article HTML without persisting media."""
        import httpx

        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        return response.text, {"host": urlsplit(url).hostname}


class Crawl4AIArticleFetcher:
    """Optional tier-1.5 JavaScript-rendered article source."""

    def __init__(self, enabled: bool = False, max_depth: int = 0, max_pages: int = 1, workers: int = 5) -> None:
        self.enabled = enabled
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.workers = workers

    def fetch(self, url: str, crawl_options: CrawlOptions | None = None) -> tuple[str | None, dict]:
        """Render JavaScript-heavy pages only when explicitly enabled."""
        if not self.enabled:
            raise RuntimeError("Crawl4AI tier-1.5 fallback is disabled")
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DFSDeepCrawlStrategy

        import asyncio

        options = crawl_options or CrawlOptions(
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            workers=self.workers,
        )

        async def _crawl() -> tuple[str | None, dict]:
            browser = BrowserConfig(headless=True, verbose=False)
            config_kwargs: dict = {
                "page_timeout": options.page_timeout_ms,
                "verbose": False,
            }
            if options.max_depth > 0:
                config_kwargs["deep_crawl_strategy"] = DFSDeepCrawlStrategy(
                    max_depth=options.max_depth,
                    max_pages=options.max_pages,
                )
                config_kwargs["semaphore_count"] = options.workers
            config = CrawlerRunConfig(**config_kwargs)
            async with AsyncWebCrawler(config=browser) as crawler:
                if options.max_depth <= 0:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url, config=config),
                        timeout=options.overall_timeout_s,
                    )
                    if not result or not getattr(result, "success", False):
                        raise RuntimeError("Crawl4AI could not render the page")
                    return getattr(result, "html", None), {
                        "host": urlsplit(url).hostname,
                        "renderer": "crawl4ai",
                    }
                results = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=options.overall_timeout_s,
                )
                pages = results.results if hasattr(results, "results") else []
                best_html: str | None = None
                best_length = 0
                for page in pages:
                    if not getattr(page, "success", False):
                        continue
                    html = getattr(page, "html", None)
                    if html and len(html) > best_length:
                        best_html = html
                        best_length = len(html)
                if best_html is None:
                    raise RuntimeError("Crawl4AI DFS crawl found no readable page")
                return best_html, {
                    "host": urlsplit(url).hostname,
                    "renderer": "crawl4ai-dfs",
                }

        return asyncio.run(_crawl())


class Crawl4AIDeepFetcher(Crawl4AIArticleFetcher):
    """Dynamic DFS deep-crawl fetcher for multi-page article sites."""

    def __init__(self, enabled: bool = False, options: CrawlOptions | None = None) -> None:
        super().__init__(
            enabled=enabled,
            max_depth=options.max_depth if options else 1,
            max_pages=options.max_pages if options else 3,
            workers=options.workers if options else 5,
        )
        self.options = options or CrawlOptions(max_depth=1, max_pages=3)

    def fetch(self, url: str, crawl_options: CrawlOptions | None = None) -> tuple[str | None, dict]:
        """Deep-crawl linked pages with strict DFS bounds."""
        if not self.enabled:
            raise RuntimeError("Crawl4AI DFS deep crawl is disabled")
        options = crawl_options or self.options
        if options.max_depth <= 0:
            return Crawl4AIArticleFetcher.fetch(self, url, CrawlOptions(
                max_depth=0,
                max_pages=options.max_pages,
                page_timeout_ms=options.page_timeout_ms,
                overall_timeout_s=options.overall_timeout_s,
                workers=options.workers,
            ))
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DFSDeepCrawlStrategy

        import asyncio

        async def _crawl() -> tuple[str | None, dict]:
            strategy = DFSDeepCrawlStrategy(max_depth=options.max_depth, max_pages=options.max_pages)
            browser = BrowserConfig(headless=True, verbose=False)
            config = CrawlerRunConfig(
                deep_crawl_strategy=strategy,
                page_timeout=options.page_timeout_ms,
                semaphore_count=options.workers,
                verbose=False,
            )
            async with AsyncWebCrawler(config=browser) as crawler:
                results = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=options.overall_timeout_s,
                )
                pages = results.results if hasattr(results, "results") else []
                best_html: str | None = None
                best_length = 0
                for page in pages:
                    if not getattr(page, "success", False):
                        continue
                    html = getattr(page, "html", None)
                    if html and len(html) > best_length:
                        best_html = html
                        best_length = len(html)
                if best_html is None:
                    raise RuntimeError("Crawl4AI DFS crawl found no readable page")
                return best_html, {
                    "host": urlsplit(url).hostname,
                    "renderer": "crawl4ai-dfs",
                }

        return asyncio.run(_crawl())


class ArticleExtractor:
    """Extract tier-1 article bodies into an ExtractionResult."""

    def __init__(
        self,
        fetcher: ArticleFetcher | None = None,
        fallback_fetcher: ArticleFetcher | None = None,
        deep_fetcher: ArticleFetcher | None = None,
        enable_crawl4ai_fallback: bool = False,
        enable_deep_crawl: bool = False,
        crawl_options: CrawlOptions | None = None,
    ) -> None:
        self.fetcher = fetcher or HttpArticleFetcher()
        self.fallback_fetcher = fallback_fetcher or Crawl4AIArticleFetcher(enable_crawl4ai_fallback)
        self.enable_deep_crawl = enable_deep_crawl
        self.crawl_options = crawl_options or CrawlOptions()
        self.deep_fetcher = deep_fetcher

    def extract(self, url: str, crawl_options: CrawlOptions | None = None) -> ExtractionResult:
        """Return article metadata and body text."""
        html: str | None = None
        meta: dict = {}
        try:
            html, meta = self.fetcher.fetch(url)
        except Exception:
            html = None
        result = self._from_html(html, meta)
        if result.kind == "article" and result.body:
            return result
        fetchers: list[ArticleFetcher | None] = [self.fallback_fetcher]
        if crawl_options is not None:
            fetchers.append(Crawl4AIDeepFetcher(True, crawl_options))
        elif self.deep_fetcher is not None and self.enable_deep_crawl:
            fetchers.append(self.deep_fetcher)
        for fetcher in fetchers:
            if fetcher is None:
                continue
            try:
                fallback_html, fallback_meta = fetcher.fetch(url)
            except Exception:
                continue
            fallback_result = self._from_html(fallback_html, fallback_meta)
            if fallback_result.kind == "article" and fallback_result.body:
                return fallback_result
        return ExtractionResult(tier=1, kind="unknown")

    @staticmethod
    def _from_html(html: str | None, meta: dict) -> ExtractionResult:
        """Parse HTML with trafilatura and degrade cleanly."""
        if not html:
            return ExtractionResult(tier=1, kind="unknown")
        from trafilatura import extract
        from trafilatura.metadata import extract_metadata

        body = extract(html, include_comments=False, include_tables=False)
        document = extract_metadata(html)
        title = getattr(document, "title", None)
        channel = getattr(document, "author", None) or getattr(document, "sitename", None)
        published = getattr(document, "date", None)
        if not body and not title:
            return ExtractionResult(tier=1, kind="unknown")
        return ExtractionResult(
            tier=1,
            kind=merge_kind("article", title, body),
            title=title,
            channel=channel,
            duration=None,
            published=published[:10] if isinstance(published, str) and len(published) >= 10 else None,
            body=body,
            transcript_available=False,
            capability_flags={"has_audio": False, "has_timeline": False, "has_images": True},
            source_meta={"extractor": meta.get("renderer", "trafilatura"), "host": meta.get("host")},
        )
