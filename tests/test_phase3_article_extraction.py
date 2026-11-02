"""Tests for Phase 3 Component 3.3: Article Content & Metadata Extractor (ADR 0002, Rules.md §8).

Verifies protocol conformance, metadata extraction, honest handling of missing fields,
date normalization, text normalization, non-article rejection, timeouts, size caps,
SSRF protections, safe redirect handling, safe logging, and zero disk persistence.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any
import pytest
import httpx

from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.extraction.article import (
    ArticleExtractor,
    MAX_ARTICLE_BYTES,
    normalize_author,
    normalize_body,
    normalize_canonical_url,
    normalize_publication_date,
    normalize_title,
    validate_url_security,
)
from backend.extraction.protocol import Extractor


# --- Deterministic HTML Fixtures ---

VALID_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Understanding Modern Software Architecture</title>
    <meta property="article:author" content="Alice Montgomery">
    <meta name="date" content="2026-03-15">
    <link rel="canonical" href="https://tech-journal.org/modern-software-architecture">
</head>
<body>
    <header>
        <nav><a href="/">Home</a><a href="/archive">Archive</a></nav>
    </header>
    <main>
        <article>
            <h1>Understanding Modern Software Architecture</h1>
            <p>Modern software systems demand clear component boundaries and strict contracts.
               By isolating data models from infrastructure concerns, systems remain resilient
               and testable across multiple architectural iterations.</p>
            <p>In this comprehensive guide, we explore the core principles that make software
               maintainable over decade-long lifespans. We analyze modularization, event-driven
               communication patterns, and safe degradation strategies.</p>
        </article>
    </main>
    <footer>
        <p>&copy; 2026 Tech Journal. All rights reserved.</p>
    </footer>
</body>
</html>
"""

ARTICLE_MISSING_METADATA_HTML = """<!DOCTYPE html>
<html>
<head>
</head>
<body>
    <article>
        <p>This is an article that contains substantive readable text without any explicit
           title tags, author metadata, or publication date fields in the document header.</p>
        <p>It continues for multiple paragraphs to ensure it easily surpasses any minimum word
           or character count threshold required for meaningful article validation.</p>
    </article>
</body>
</html>
"""

NON_ARTICLE_LOGIN_HTML = """<!DOCTYPE html>
<html>
<head><title>Sign In</title></head>
<body>
    <form action="/login" method="POST">
        <label for="user">Username</label>
        <input type="text" id="user" name="user">
        <button type="submit">Log In</button>
    </form>
</body>
</html>
"""

NAVIGATION_HEAVY_HTML = """<!DOCTYPE html>
<html>
<head><title>Site Directory</title></head>
<body>
    <nav>
        <ul>
            <li><a href="/section/news">News</a></li>
            <li><a href="/section/sports">Sports</a></li>
            <li><a href="/section/finance">Finance</a></li>
            <li><a href="/section/tech">Technology</a></li>
            <li><a href="/section/culture">Culture</a></li>
        </ul>
    </nav>
    <footer>
        <p>&copy; 2026 Global News Network</p>
    </footer>
</body>
</html>
"""

MALFORMED_HTML = """<!DOCTYPE html>
<html>
<head><title>Malformed Document Example</title></head>
<body>
    <article>
        <h1>Architectural Integrity</h1>
        <p>Paragraph missing closing tag
        <div>Nested inappropriately<span>Substantive content detailing the importance of
        defensive programming and resilient input parsing for mission critical tools.
    </article>
</body>
"""


# --- Unit Tests: Normalizers & URL Validation ---

def test_extractor_conforms_to_protocol() -> None:
    """Verify ArticleExtractor implements the Extractor protocol."""
    extractor = ArticleExtractor()
    assert isinstance(extractor, Extractor)


def test_normalize_publication_date() -> None:
    """Verify strict date normalization to YYYY-MM-DD."""
    assert normalize_publication_date("2026-03-15") == "2026-03-15"
    assert normalize_publication_date("2026-03-15T12:30:00Z") == "2026-03-15"
    assert normalize_publication_date("2026/03/15") == "2026-03-15"
    assert normalize_publication_date("20260315") == "2026-03-15"
    assert normalize_publication_date("  2026-03-15  ") == "2026-03-15"

    # Invalid dates must honestly return None without crashing
    assert normalize_publication_date("invalid-date") is None
    assert normalize_publication_date("2026-13-45") is None
    assert normalize_publication_date("2026-02-30") is None
    assert normalize_publication_date("1850-01-01") is None  # Out of reasonable range
    assert normalize_publication_date("") is None
    assert normalize_publication_date(None) is None


def test_normalize_author() -> None:
    """Verify author normalization and boilerplate stripping."""
    assert normalize_author("By Jane Doe") == "Jane Doe"
    assert normalize_author("by  Alice Smith  ") == "Alice Smith"
    assert normalize_author("John Doe") == "John Doe"
    assert normalize_author("") is None
    assert normalize_author("   ") is None
    assert normalize_author(None) is None


def test_normalize_title() -> None:
    """Verify title whitespace normalization."""
    assert normalize_title("  My   Title  ") == "My Title"
    assert normalize_title("") is None
    assert normalize_title(None) is None


def test_normalize_body() -> None:
    """Verify body text normalization and minimum content gating."""
    substantive = (
        "This is a substantive paragraph with sufficient length and vocabulary "
        "to clearly represent valid article content in the extraction pipeline."
    )
    norm = normalize_body(substantive)
    assert norm is not None
    assert "substantive paragraph" in norm

    # Empty or trivial text must be rejected
    assert normalize_body("") is None
    assert normalize_body("   ") is None
    assert normalize_body("Login now") is None
    assert normalize_body(None) is None


def test_normalize_canonical_url() -> None:
    """Verify canonical URL normalization and tracking parameter removal."""
    clean = normalize_canonical_url("https://example.com/article?utm_source=twitter&id=42")
    assert clean is not None
    assert "utm_source" not in clean
    assert "id=42" in clean
    assert normalize_canonical_url("invalid-url") is None
    assert normalize_canonical_url(None) is None


def test_validate_url_security() -> None:
    """Verify scheme, localhost, private IP, and cloud metadata blocking."""
    # Allowed
    safe, _ = validate_url_security("https://tech-journal.org/post", resolve_dns=False)
    assert safe is True

    # Schemes
    assert validate_url_security("file:///etc/passwd")[1] == "unsupported_scheme"
    assert validate_url_security("ftp://example.com/doc")[1] == "unsupported_scheme"
    assert validate_url_security("javascript:alert(1)")[1] == "unsupported_scheme"

    # Localhost & Loopback
    assert validate_url_security("http://localhost/admin")[1] == "private_network"
    assert validate_url_security("http://127.0.0.1/test")[1] == "private_network"
    assert validate_url_security("http://[::1]/secret")[1] == "private_network"
    assert validate_url_security("http://app.localhost/doc")[1] == "private_network"

    # Private IP ranges
    assert validate_url_security("http://10.0.0.1/status")[1] == "private_network"
    assert validate_url_security("http://192.168.1.1/router")[1] == "private_network"
    assert validate_url_security("http://172.16.0.1/intranet")[1] == "private_network"

    # Cloud metadata endpoints
    assert validate_url_security("http://169.254.169.254/latest/meta-data")[1] == "private_network"
    assert validate_url_security("http://metadata.google.internal/")[1] == "private_network"

    # Invalid URLs
    assert validate_url_security("")[1] == "invalid_url"
    assert validate_url_security("http://")[1] == "invalid_url"


# --- Component Integration Tests: Article Extraction ---

@pytest.mark.anyio
async def test_valid_article_extraction() -> None:
    """Test full extraction of a valid article with complete metadata."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=VALID_ARTICLE_HTML,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://tech-journal.org/modern-software-architecture")

    assert result.tier == 1
    assert result.kind == Kind.ARTICLE
    assert result.title == "Understanding Modern Software Architecture"
    assert result.channel == "Alice Montgomery"
    assert result.published == "2026-03-15"
    assert result.duration is None
    assert result.transcript_available is False
    assert result.capability_flags == CapabilityFlags(has_audio=False, has_timeline=False, has_images=False)
    assert result.body is not None
    assert "Modern software systems demand clear component boundaries" in result.body
    assert result.source_meta.get("canonical_url") == "https://tech-journal.org/modern-software-architecture"
    assert result.source_meta.get("extractor") == "trafilatura"
    assert result.needs_tier2_rescue() is False


@pytest.mark.anyio
async def test_missing_metadata_honestly_reported() -> None:
    """Test that missing title, author, or date are reported as None rather than fabricated."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ARTICLE_MISSING_METADATA_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/plain-article")

    assert result.kind == Kind.ARTICLE
    assert result.title is None
    assert result.channel is None
    assert result.published is None
    assert result.body is not None
    assert "substantive readable text" in result.body
    assert result.needs_tier2_rescue() is False


@pytest.mark.anyio
async def test_empty_article_body_rejected() -> None:
    """Test that pages with empty bodies degrade to UNKNOWN and qualify for rescue."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>", headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/empty")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "no_content"
    assert result.needs_tier2_rescue() is True


@pytest.mark.anyio
async def test_non_article_page_rejected() -> None:
    """Test that non-article forms or pages degrade to UNKNOWN."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=NON_ARTICLE_LOGIN_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/login")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "no_content"


@pytest.mark.anyio
async def test_navigation_heavy_html_rejected() -> None:
    """Test that directory or navigation-only pages are rejected as no_content."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=NAVIGATION_HEAVY_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/directory")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "no_content"


@pytest.mark.anyio
async def test_malformed_html_handled_safely() -> None:
    """Test that unclosed and badly nested tags parse safely without crashing."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=MALFORMED_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/malformed")

    assert result.kind == Kind.ARTICLE
    assert result.body is not None
    assert "Architectural Integrity" in (result.title or "") or "Architectural Integrity" in result.body


@pytest.mark.anyio
@pytest.mark.parametrize("status_code,expected_category", [
    (403, "http_403"),
    (404, "http_404"),
    (429, "http_429"),
    (500, "http_5xx"),
    (502, "http_5xx"),
    (503, "http_5xx"),
])
async def test_http_error_statuses(status_code: int, expected_category: str) -> None:
    """Test degradation on non-200 HTTP statuses."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="Error page")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract(f"https://example.com/error/{status_code}")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == expected_category


@pytest.mark.anyio
async def test_connection_failure() -> None:
    """Test degradation when connection fails."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/offline")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "connection_failed"


@pytest.mark.anyio
async def test_timeout_handling() -> None:
    """Test degradation on HTTP read timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Socket timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/timeout")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "timeout"


@pytest.mark.anyio
async def test_oversized_response_rejected() -> None:
    """Test rejection when response exceeds MAX_ARTICLE_BYTES (2MB)."""
    large_payload = "a" * (MAX_ARTICLE_BYTES + 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=large_payload, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/large")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "oversized"


@pytest.mark.anyio
async def test_oversized_content_length_header() -> None:
    """Test early rejection when Content-Length header announces an oversized payload."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="Small preview",
            headers={"Content-Type": "text/html", "Content-Length": str(MAX_ARTICLE_BYTES + 5000)},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/declared-oversized")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "oversized"


@pytest.mark.anyio
async def test_invalid_content_type_rejected() -> None:
    """Test rejection when Content-Type indicates non-textual media."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x00\x01\x02", headers={"Content-Type": "application/octet-stream"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/binary.dat")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "invalid_content_type"


@pytest.mark.anyio
async def test_safe_redirect_followed() -> None:
    """Test following a safe redirect to a target with valid article content."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old-url":
            return httpx.Response(301, headers={"Location": "/new-url"})
        if request.url.path == "/new-url":
            return httpx.Response(200, text=VALID_ARTICLE_HTML, headers={"Content-Type": "text/html"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/old-url")

    assert result.kind == Kind.ARTICLE
    assert result.title == "Understanding Modern Software Architecture"
    assert result.body is not None


@pytest.mark.anyio
async def test_redirect_loop_detected() -> None:
    """Test detection of cyclical redirects."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/loop-a":
            return httpx.Response(302, headers={"Location": "/loop-b"})
        if request.url.path == "/loop-b":
            return httpx.Response(302, headers={"Location": "/loop-a"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/loop-a")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "redirect_loop"


@pytest.mark.anyio
async def test_unsafe_redirect_target_blocked() -> None:
    """Test SSRF block when a redirect points to a private network target."""
    def handler(request: httpx.Request) -> httpx.Response:
        # Redirect points to internal private IP
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/admin-console"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/redirect-to-internal")

    assert result.kind == Kind.UNKNOWN
    assert result.body is None
    assert result.source_meta.get("category") == "private_network"


@pytest.mark.anyio
@pytest.mark.parametrize("private_url", [
    "http://localhost/article",
    "http://127.0.0.1/article",
    "http://[::1]/article",
    "http://192.168.1.1/article",
    "http://10.0.0.5/article",
    "http://172.16.0.1/article",
    "http://169.254.169.254/latest/meta-data",
    "http://metadata.google.internal/article",
])
async def test_private_network_urls_blocked_pre_fetch(private_url: str) -> None:
    """Test that private-network and metadata endpoints are rejected before sending requests."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text="Should never reach here")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract(private_url)

    assert not called  # Zero requests made to private network
    assert result.kind == Kind.UNKNOWN
    assert result.source_meta.get("category") == "private_network"


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_url,expected_cat", [
    ("file:///etc/passwd", "unsupported_scheme"),
    ("ftp://example.com/doc", "unsupported_scheme"),
    ("not-a-valid-url", "invalid_url"),
    ("", "invalid_url"),
])
async def test_invalid_urls_rejected_pre_fetch(invalid_url: str, expected_cat: str) -> None:
    """Test that invalid schemes and malformed URLs are rejected without network calls."""
    extractor = ArticleExtractor()
    result = await extractor.extract(invalid_url)

    assert result.kind == Kind.UNKNOWN
    assert result.source_meta.get("category") == expected_cat


@pytest.mark.anyio
async def test_strict_extraction_result_validation() -> None:
    """Verify that ExtractionResult and CapabilityFlags forbid undeclared extra fields."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=VALID_ARTICLE_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)
    result = await extractor.extract("https://tech-journal.org/modern-software-architecture")

    # Serialize and re-validate to ensure strict conformance
    dumped = result.model_dump()
    revalidated = ExtractionResult.model_validate(dumped)
    assert revalidated == result

    # Verify forbidden extra fields raise ValidationError
    dumped_with_extra = dict(dumped)
    dumped_with_extra["unexpected_field"] = "illegal"
    with pytest.raises(Exception):
        ExtractionResult.model_validate(dumped_with_extra)


@pytest.mark.anyio
async def test_safe_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Verify logs record only bounded categories without leaking URLs, query tokens, or bodies."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Confidential internal system failure body text")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    url_with_secret = "https://example.com/article?auth_token=super_secret_token_12345"

    with caplog.at_level(logging.WARNING):
        await extractor.extract(url_with_secret, platform="web")

    log_text = caplog.text

    # Category and platform must be present
    assert "platform=web" in log_text
    assert "category=http_403" in log_text

    # Sensitive details must NEVER appear in logs
    assert "super_secret_token_12345" not in log_text
    assert "auth_token=" not in log_text
    assert "Confidential internal system failure body text" not in log_text


@pytest.mark.anyio
async def test_no_permanent_html_persistence() -> None:
    """Verify extraction does not leave temporary HTML files on disk."""
    temp_dir = tempfile.gettempdir()
    initial_files = set(os.listdir(temp_dir))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=VALID_ARTICLE_HTML, headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/test-article")
    assert result.kind == Kind.ARTICLE

    final_files = set(os.listdir(temp_dir))
    new_files = final_files - initial_files

    # Confirm zero new HTML files were created
    html_leaks = [f for f in new_files if f.endswith(".html") or f.endswith(".htm")]
    assert len(html_leaks) == 0


# --- Remediation Tests: CB-P3-003 & CB-P3-005 ---

@pytest.mark.anyio
async def test_dns_rebinding_rejected_by_ssrf_backend() -> None:
    """Verify SSRFProtectedBackend detects and aborts on private/loopback resolution (CB-P3-003)."""
    import socket
    import httpcore
    from unittest.mock import patch
    from backend.extraction.transport import SSRFProtectedBackend

    backend = SSRFProtectedBackend()

    # Simulate DNS rebinding: host resolves to private loopback 127.0.0.1
    fake_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    with patch("socket.getaddrinfo", return_value=fake_dns):
        with pytest.raises(httpcore.ConnectError, match="SSRF blocked"):
            await backend.connect_tcp("rebinder.attacker.com", 80)


@pytest.mark.anyio
async def test_mixed_dns_responses_rejected() -> None:
    """Verify DNS responses containing both public and private IPs are rejected (CB-P3-003)."""
    import socket
    import httpcore
    from unittest.mock import patch
    from backend.extraction.transport import SSRFProtectedBackend

    backend = SSRFProtectedBackend()

    # Mixed DNS response: one public, one private
    mixed_dns = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80)),
    ]

    with patch("socket.getaddrinfo", return_value=mixed_dns):
        with pytest.raises(httpcore.ConnectError, match="SSRF blocked"):
            await backend.connect_tcp("mixed.attacker.com", 80)


@pytest.mark.anyio
async def test_ipv6_private_and_mapped_ipv6_rejected() -> None:
    """Verify IPv6 ULA, link-local, and IPv4-mapped IPv6 private IPs are rejected (CB-P3-003)."""
    import socket
    import httpcore
    from unittest.mock import patch
    from backend.extraction.transport import SSRFProtectedBackend, is_private_ip

    assert is_private_ip("fc00::1")  # IPv6 ULA
    assert is_private_ip("fe80::1")  # IPv6 Link-local
    assert is_private_ip("::ffff:127.0.0.1")  # IPv4-mapped loopback
    assert is_private_ip("::ffff:169.254.169.254")  # IPv4-mapped cloud metadata
    assert is_private_ip("::ffff:192.168.1.1")  # IPv4-mapped private
    assert not is_private_ip("2606:4700:4700::1111")  # Public Cloudflare IPv6

    backend = SSRFProtectedBackend()
    mapped_dns = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 80, 0, 0))]

    with patch("socket.getaddrinfo", return_value=mapped_dns):
        with pytest.raises(httpcore.ConnectError, match="SSRF blocked"):
            await backend.connect_tcp("mapped.attacker.com", 80)


@pytest.mark.anyio
async def test_redirect_to_private_address_and_cloud_metadata_blocked() -> None:
    """Verify manual redirect validation rejects private IPs and cloud metadata targets (CB-P3-003)."""
    # 1. Redirect to 169.254.169.254
    def handler_metadata(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, text="Metadata content")

    client_meta = httpx.AsyncClient(transport=httpx.MockTransport(handler_metadata))
    extractor_meta = ArticleExtractor(client=client_meta)
    res_meta = await extractor_meta.extract("https://example.com/start")
    assert res_meta.kind == Kind.UNKNOWN
    assert res_meta.source_meta.get("category") == "private_network"

    # 2. Redirect to localhost loopback
    def handler_local(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1:8000/internal"})
        return httpx.Response(200, text="Internal admin")

    client_local = httpx.AsyncClient(transport=httpx.MockTransport(handler_local))
    extractor_local = ArticleExtractor(client=client_local)
    res_local = await extractor_local.extract("https://example.com/start")
    assert res_local.kind == Kind.UNKNOWN
    assert res_local.source_meta.get("category") == "private_network"


@pytest.mark.anyio
async def test_bounded_streaming_exact_cap_and_exceeded() -> None:
    """Verify streaming response size boundaries at exact limit and exceeded limit (CB-P3-005)."""
    # Exactly at limit (2 MB)
    exact_data = b"A" * MAX_ARTICLE_BYTES

    def handler_exact(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=exact_data, headers={"Content-Type": "text/html"})

    client_exact = httpx.AsyncClient(transport=httpx.MockTransport(handler_exact))
    extractor_exact = ArticleExtractor(client=client_exact)
    res_exact = await extractor_exact.extract("https://example.com/exact")
    # Content was processed by streaming; category is not oversized
    assert res_exact.source_meta.get("category") != "oversized"

    # Exceeding limit by 1 byte (2 MB + 1)
    over_data = b"A" * (MAX_ARTICLE_BYTES + 1)

    def handler_over(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=over_data, headers={"Content-Type": "text/html"})

    client_over = httpx.AsyncClient(transport=httpx.MockTransport(handler_over))
    extractor_over = ArticleExtractor(client=client_over)
    res_over = await extractor_over.extract("https://example.com/over")
    assert res_over.kind == Kind.UNKNOWN
    assert res_over.source_meta.get("category") == "oversized"


@pytest.mark.anyio
async def test_streaming_unbounded_generator_stops_immediately_without_memory_leak() -> None:
    """Verify streaming reader breaks immediately upon exceeding byte limit (CB-P3-005)."""
    chunks_yielded = 0

    class InfiniteByteStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            nonlocal chunks_yielded
            while True:
                chunks_yielded += 1
                yield b"X" * 8192

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=InfiniteByteStream(), headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/infinite")
    assert result.kind == Kind.UNKNOWN
    assert result.source_meta.get("category") == "oversized"

    # Max 2 MB / 8 KB = 256 chunks. It must stop reading right around 257 chunks, not infinite!
    assert 255 <= chunks_yielded <= 260


@pytest.mark.anyio
async def test_streaming_incorrect_and_missing_content_length() -> None:
    """Verify streaming enforces true byte limits even if Content-Length is missing or dishonest (CB-P3-005)."""
    oversized_body = b"P" * (MAX_ARTICLE_BYTES + 5000)

    # Dishonest Content-Length: claims 100 bytes, sends 2MB+
    def handler_dishonest(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=oversized_body,
            headers={"Content-Type": "text/html", "Content-Length": "100"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler_dishonest))
    extractor = ArticleExtractor(client=client)

    result = await extractor.extract("https://example.com/dishonest-cl")
    assert result.kind == Kind.UNKNOWN
    assert result.source_meta.get("category") == "oversized"
