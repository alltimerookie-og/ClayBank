"""Focused tests for tier-1 extraction providers."""

import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from Backend.extraction.rescue import RescueExtractor
from Backend.extraction.result import ExtractionResult
from Backend.extraction.trafilatura import ArticleExtractor, Crawl4AIArticleFetcher
from Backend.extraction.ytdlp import VideoExtractor, transient_media_download
from Backend.main import app
from Backend.processing.orchestrator import ExtractionOrchestrator
from Backend.store.database import Database


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


class MissingArticle:
    """Completely empty fetch result."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Simulate no HTML."""
        del url
        return None, {"host": "example.com"}


class TitleOnlyArticle:
    """Homepage-style source with metadata but little article body."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Return homepage HTML."""
        del url
        return (
            "<html><head><title>Example Homepage</title></head>"
            "<body><nav><a href='/'>Home</a></nav>"
            "<main><p>Welcome to the example homepage.</p></main></body></html>",
            {"host": "example.com"},
        )


class StaticVideo:
    """Deterministic video metadata source."""

    def fetch(self, url: str) -> dict:
        """Return fixed video metadata."""
        del url
        return {
            "title": "Creamy garlic pasta",
            "channel": "@chefmara",
            "duration": 58,
            "upload_date": "20261003",
            "subtitles": {"en": [{"url": "https://example.com/captions"}]},
        }


class StaticVideoWithoutCaptions:
    """Deterministic video metadata source without captions."""

    def fetch(self, url: str) -> dict:
        """Return fixed video metadata."""
        del url
        return {
            "title": "Silent pasta clip",
            "channel": "@chefmara",
            "duration": 42,
            "upload_date": "20261003",
            "subtitles": {},
        }


class StaticArticle:
    """Deterministic article source."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Return fixed article HTML and metadata."""
        del url
        return (
            "<html><head><title>Sous vide basics</title>"
            "<meta name='author' content='Example Kitchen'>"
            "<meta property='article:published_time' content='2026-10-14T12:00:00Z'>"
            "</head><body><article><h1>Sous vide basics</h1>"
            "<p>Sous vide cooking keeps the water bath at the target temperature.</p>"
            "<p>Season the food, seal the bag, and cook it gently for even results.</p>"
            "<p>Finish with a hot sear before serving the meal.</p>"
            "</article></body></html>",
            {"host": "example.com"},
        )


class FailingVideo:
    """Failing video source."""

    def fetch(self, url: str) -> dict:
        """Simulate an unavailable provider."""
        raise RuntimeError("yt-dlp unavailable")


class EmptyArticle:
    """Article source with no extractable body."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Simulate a JavaScript-only page."""
        del url
        return "<html><body><div id='app'></div></body></html>", {"host": "example.com"}


class RenderedArticle:
    """Tier-1.5 rendered article source."""

    def fetch(self, url: str) -> tuple[str | None, dict]:
        """Return rendered article HTML."""
        del url
        paragraphs = "".join(
            f"<p>Paragraph {index} contains enough rendered text for reliable extraction.</p>"
            for index in range(1, 8)
        )
        return (
            "<html><head><title>Rendered article</title></head><body><main><article>"
            "<h1>Rendered article</h1>"
            f"{paragraphs}"
            "</article></main></body></html>",
            {"host": "example.com", "renderer": "crawl4ai"},
        )


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "extraction.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_video_extraction_persists_metadata(tmp_path: Path) -> None:
    """Video extraction stores metadata and advances the job."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://www.youtube.com/watch?v=abc123"}).json()["data"]
        orchestrator = ExtractionOrchestrator(app.state.database, video=VideoExtractor(StaticVideo()))
        outcome = orchestrator.extract_save(save["id"])

        assert outcome["kind"] == "video"
        assert outcome["state"] == "transcribing"
        bundle = client.get(f"/saves/{save['id']}", headers=HEADERS).json()["data"]
        assert bundle["save"]["title"] == "Creamy garlic pasta"
        assert bundle["job"]["state"] == "transcribing"


def test_article_extraction_persists_body(tmp_path: Path) -> None:
    """Article extraction stores the deterministic article body."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/article"}).json()["data"]
        orchestrator = ExtractionOrchestrator(app.state.database, article=ArticleExtractor(StaticArticle()))
        outcome = orchestrator.extract_save(save["id"])

        assert outcome["kind"] == "article"
        assert outcome["result"]["body"] is not None


def test_failed_extraction_degrades_to_unknown(tmp_path: Path) -> None:
    """Failed extraction degrades cleanly and records tier-2 rescue."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://www.youtube.com/watch?v=missing"}).json()["data"]
        orchestrator = ExtractionOrchestrator(
            app.state.database,
            video=VideoExtractor(FailingVideo()),
            rescue=RescueExtractor(),
        )
        outcome = orchestrator.extract_save(save["id"])

        assert outcome["kind"] == "unknown"
        assert outcome["tier"] == 2
        assert isinstance(ExtractionResult(tier=1, kind="unknown").to_contract(), dict)


def test_transient_media_cleanup(tmp_path: Path) -> None:
    """Transient downloads are deleted even when processing succeeds."""
    created: dict[str, Path] = {}

    class FakeYoutubeDL:
        """Deterministic yt-dlp stand-in that writes one file."""

        def __init__(self, options: dict) -> None:
            """Record download options."""
            self.options = options

        def __enter__(self) -> "FakeYoutubeDL":
            """Enter the fake downloader."""
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            """Exit the fake downloader."""
            del exc_type, exc, traceback

        def extract_info(self, url: str, download: bool = False) -> dict:
            """Write a fake media file and return metadata."""
            del url, download
            target = Path(str(self.options["outtmpl"]).replace("%(ext)s", "mp4"))
            target.write_bytes(b"fake video")
            created["directory"] = target.parent
            return {"duration": 42}

    with patch("yt_dlp.YoutubeDL", FakeYoutubeDL):
        with transient_media_download("https://www.youtube.com/watch?v=dQw4w9WgXcQ") as media:
            assert media.path is not None
            assert media.path.exists()
            assert media.kind == "video"
            assert media.has_video is True
            assert media.has_audio is True
    assert created["directory"] is not None
    assert not created["directory"].exists()

    extractor = VideoExtractor(StaticVideoWithoutCaptions(), allow_transient_media=False)
    result = extractor.extract("https://www.youtube.com/watch?v=abc123")
    assert result.kind == "video"
    assert result.transcript_available is False


def test_crawl4ai_tier15_fallback_recovers_js_page() -> None:
    """Tier-1.5 rendering is used only after trafilatura has no body."""
    extractor = ArticleExtractor(EmptyArticle(), fallback_fetcher=RenderedArticle())
    result = extractor.extract("https://example.com/js-page")

    assert result.kind == "article"
    assert result.body is not None
    assert result.source_meta["extractor"] == "crawl4ai"

    disabled = ArticleExtractor(EmptyArticle(), fallback_fetcher=Crawl4AIArticleFetcher(enabled=False))
    assert disabled.extract("https://example.com/js-page").kind == "unknown"


def test_homepage_without_body_uses_fallback_then_unknown() -> None:
    """Empty pages try Crawl4AI and degrade to unknown without a body."""
    extractor = ArticleExtractor(EmptyArticle(), fallback_fetcher=RenderedArticle())
    result = extractor.extract("https://example.com/")

    assert result.kind == "article"
    assert result.body is not None

    degraded = ArticleExtractor(
        EmptyArticle(),
        fallback_fetcher=MissingArticle(),
        deep_fetcher=MissingArticle(),
    )
    assert degraded.extract("https://example.com/").kind == "unknown"


def test_dynamic_dfs_deep_crawl_recovers_multi_page_article() -> None:
    """DFS deep crawl is used after single-page rendering has no body."""
    extractor = ArticleExtractor(
        EmptyArticle(),
        fallback_fetcher=MissingArticle(),
        deep_fetcher=RenderedArticle(),
        enable_deep_crawl=True,
    )
    result = extractor.extract("https://example.com/guides")

    assert result.kind == "article"
    assert result.body is not None
    assert result.source_meta["extractor"] == "crawl4ai"

    disabled = ArticleExtractor(
        EmptyArticle(),
        fallback_fetcher=MissingArticle(),
        deep_fetcher=Crawl4AIArticleFetcher(enabled=False),
    )
    assert disabled.extract("https://example.com/guides").kind == "unknown"


def test_parallel_extraction_improves_batch_latency(tmp_path: Path) -> None:
    """Bounded parallel extraction overlaps slow provider calls."""
    with make_client(tmp_path) as client:
        save_ids = [
            client.post("/saves", headers=HEADERS, json={"url": f"https://example.com/{index}"}).json()["data"]["id"]
            for index in range(4)
        ]

        class SlowArticle(StaticArticle):
            """Simulated slow article provider."""

            def fetch(self, url: str) -> tuple[str | None, dict]:
                """Delay before returning deterministic HTML."""
                time.sleep(0.3)
                return super().fetch(url)

        sequential = ExtractionOrchestrator(app.state.database, article=ArticleExtractor(SlowArticle()), max_workers=1)
        start = time.perf_counter()
        sequential_results = sequential.extract_many(save_ids)
        sequential_elapsed = time.perf_counter() - start

        parallel = ExtractionOrchestrator(app.state.database, article=ArticleExtractor(SlowArticle()), max_workers=4)
        start = time.perf_counter()
        parallel_results = parallel.extract_many(save_ids)
        parallel_elapsed = time.perf_counter() - start

        assert len(sequential_results) == 4
        assert len(parallel_results) == 4
        assert parallel_elapsed < sequential_elapsed
