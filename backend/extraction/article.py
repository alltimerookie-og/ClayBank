"""Article content and metadata extractor using trafilatura (ADR 0002, Rules.md §8).

Extracts article title, author, publication date, canonical URL, and readable
body text while enforcing strict HTTP timeouts, response size limits, and
SSRF/private-network protections without persisting raw HTML.
"""
from __future__ import annotations

import asyncio
import datetime
import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from backend.capture.urls import canonicalize_url
from backend.config import settings
from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult

logger = logging.getLogger(__name__)

# Security & resource bounds
MAX_ARTICLE_BYTES = 2 * 1024 * 1024  # 2 MB response size cap
MAX_REDIRECTS = 5
HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
HTTP_READ_TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = "ClayBank/1.0 (+https://github.com/alltimerookie-og/ClayBank)"

FORBIDDEN_HOSTNAMES = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "instance-data",
})

FORBIDDEN_DOMAIN_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".test",
    ".invalid",
)

CLOUD_METADATA_IPS = frozenset({
    "169.254.169.254",   # AWS / GCP / Azure link-local metadata
    "fd00:ec2::254",     # AWS IPv6 metadata
})

_DATE_PREFIX_PATTERN = re.compile(r"^(\d{4})[-/]?(\d{2})[-/]?(\d{2})")


def is_private_ip(ip_val: Any) -> bool:
    """Return True if IP is loopback, private, link-local, reserved, multicast, or unspecified."""
    try:
        ip_str = str(ip_val).strip("[]")
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_url_security(url: str, resolve_dns: bool = True) -> tuple[bool, str]:
    """Validate URL scheme and host against SSRF, private networks, and cloud metadata.

    Args:
        url: The target URL to validate.
        resolve_dns: Whether to resolve hostnames via DNS to detect private IP targets.

    Returns:
        tuple[bool, str]: (is_safe, category). If unsafe, category is the bounded error reason.
    """
    if not url or not isinstance(url, str):
        return False, "invalid_url"

    cleaned = url.strip()
    if not cleaned:
        return False, "invalid_url"

    try:
        parsed = urlparse(cleaned)
    except Exception:
        return False, "invalid_url"

    scheme = (parsed.scheme or "").lower()
    if not scheme:
        return False, "invalid_url"
    if scheme not in ("http", "https"):
        return False, "unsupported_scheme"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "invalid_url"

    # Textual host inspection
    if host in FORBIDDEN_HOSTNAMES:
        return False, "private_network"

    for suffix in FORBIDDEN_DOMAIN_SUFFIXES:
        if host.endswith(suffix):
            return False, "private_network"

    if host in CLOUD_METADATA_IPS:
        return False, "private_network"

    # Direct IP literal check
    cleaned_ip = host.strip("[]")
    if is_private_ip(cleaned_ip):
        return False, "private_network"

    # DNS resolution check for domain names (to prevent DNS rebinding to private networks)
    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for entry in addr_info:
                sockaddr = entry[4]
                ip_str = str(sockaddr[0])
                if is_private_ip(ip_str):
                    return False, "private_network"
        except socket.gaierror:
            # Domain could not be resolved
            pass
        except Exception:
            return False, "invalid_url"

    return True, ""


def normalize_publication_date(raw_date: Any) -> str | None:
    """Normalize raw publication date into strict ISO 8601 (YYYY-MM-DD).

    Returns None if raw_date is missing, empty, or invalid. Never fabricates dates.
    """
    if not raw_date or not isinstance(raw_date, str):
        return None
    cleaned = raw_date.strip()
    if not cleaned:
        return None

    m = _DATE_PREFIX_PATTERN.match(cleaned)
    if m:
        year, month, day = m.groups()
        candidate = f"{year}-{month}-{day}"
        try:
            d = datetime.date.fromisoformat(candidate)
            if 1900 <= d.year <= 2100:
                return candidate
            return None
        except ValueError:
            return None

    return None


def normalize_author(raw_author: Any) -> str | None:
    """Normalize author by stripping redundant prefixes (e.g. 'By ') and extra whitespace."""
    if not raw_author or not isinstance(raw_author, str):
        return None
    cleaned = raw_author.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("by "):
        cleaned = cleaned[3:].strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else None


def normalize_title(raw_title: Any) -> str | None:
    """Normalize title by collapsing whitespace and stripping edges."""
    if not raw_title or not isinstance(raw_title, str):
        return None
    cleaned = re.sub(r"\s+", " ", raw_title).strip()
    return cleaned if cleaned else None


def normalize_body(raw_body: Any) -> str | None:
    """Normalize article body text and confirm it contains meaningful content."""
    if not raw_body or not isinstance(raw_body, str):
        return None
    # Normalize unicode whitespace
    text = raw_body.replace("\u00a0", " ").replace("\u200b", "")
    # Normalize excessive newlines while preserving paragraph separation
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse irregular horizontal whitespace within lines
    text = re.sub(r"[ \t]+", " ", text).strip()

    # Reject empty, boilerplate, or trivial content (minimum 5 words and 30 characters)
    words = text.split()
    if len(words) < 5 or len(text) < 30:
        return None
    return text


def normalize_canonical_url(raw_url: Any) -> str | None:
    """Sanitize and validate extracted canonical URL."""
    if not raw_url or not isinstance(raw_url, str):
        return None
    cleaned = raw_url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        return None
    try:
        parsed = urlparse(cleaned)
        if not parsed.netloc:
            return None
        return canonicalize_url(cleaned)
    except Exception:
        return None


class FetchResult:
    """Internal result container for HTTP retrieval."""

    def __init__(
        self,
        is_success: bool,
        category: str = "",
        status_code: int = 0,
        content: str = "",
        final_url: str = "",
    ) -> None:
        self.is_success = is_success
        self.category = category
        self.status_code = status_code
        self.content = content
        self.final_url = final_url


class ArticleExtractor:
    """Tier-1 article extractor using trafilatura with strict SSRF and resource bounds."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        resolve_dns: bool | None = None,
    ) -> None:
        self._client = client
        # Default DNS resolution: enabled for live clients, disabled for mock/test clients
        self._resolve_dns = (client is None) if resolve_dns is None else resolve_dns

    async def extract(self, url: str, platform: str = "web") -> ExtractionResult:
        """Extract article metadata and body from a web URL.

        Args:
            url: Target web URL.
            platform: Platform name derived from host (defaults to 'web').

        Returns:
            ExtractionResult: Populated with article content, or degraded to UNKNOWN on failure.
        """
        # 1. URL and SSRF validation
        is_safe, sec_category = validate_url_security(url, resolve_dns=self._resolve_dns)
        if not is_safe:
            self._log_failure(platform, sec_category)
            return self._degraded_result(sec_category)

        # 2. HTTP retrieval within timeout budget
        timeout_budget = settings.EXTRACTION_TIMEOUT_SECONDS
        try:
            async with asyncio.timeout(timeout_budget):
                fetch_res = await self._fetch_html(url)
                if not fetch_res.is_success:
                    self._log_failure(platform, fetch_res.category)
                    return self._degraded_result(fetch_res.category)
                html_content = fetch_res.content
                final_url = fetch_res.final_url
        except TimeoutError:
            self._log_failure(platform, "timeout")
            return self._degraded_result("timeout")
        except Exception as err:
            category = self._categorize_exception(err)
            self._log_failure(platform, category)
            return self._degraded_result(category)

        # 3. Offload trafilatura parsing to worker thread
        try:
            extracted_data = await asyncio.to_thread(
                self._extract_trafilatura_sync,
                html_content,
                final_url,
            )
        except Exception:
            self._log_failure(platform, "extraction_error")
            return self._degraded_result("extraction_error")

        # 4. Normalize and validate extracted content
        body = normalize_body(extracted_data.get("body"))
        if not body:
            self._log_failure(platform, "no_content")
            return self._degraded_result("no_content")

        title = normalize_title(extracted_data.get("title"))
        author = normalize_author(extracted_data.get("author"))
        published = normalize_publication_date(extracted_data.get("date"))
        canon_url = normalize_canonical_url(extracted_data.get("canonical_url"))

        source_meta: dict[str, Any] = {"extractor": "trafilatura"}
        if canon_url:
            source_meta["canonical_url"] = canon_url

        return ExtractionResult(
            tier=1,
            kind=Kind.ARTICLE,
            title=title,
            channel=author,
            duration=None,
            published=published,
            body=body,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
            source_meta=source_meta,
        )

    async def _fetch_html(self, url: str) -> FetchResult:
        """Fetch HTML content with bounded redirects, response size limits, and SSRF checks."""
        current_url = url
        visited_urls: set[str] = {current_url}
        redirect_count = 0

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        if self._client is not None:
            return await self._fetch_with_client(self._client, current_url, visited_urls, redirect_count, headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=HTTP_CONNECT_TIMEOUT_SECONDS,
                read=HTTP_READ_TIMEOUT_SECONDS,
                write=5.0,
                pool=5.0,
            ),
            follow_redirects=False,
        ) as client:
            return await self._fetch_with_client(client, current_url, visited_urls, redirect_count, headers)

    async def _fetch_with_client(
        self,
        client: httpx.AsyncClient,
        start_url: str,
        visited_urls: set[str],
        redirect_count: int,
        headers: dict[str, str],
    ) -> FetchResult:
        current_url = start_url

        while True:
            resp = await client.get(current_url, headers=headers)

            # Handle redirects manually for strict target verification
            if resp.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    return FetchResult(is_success=False, category="redirect_loop", status_code=resp.status_code)

                location = resp.headers.get("location")
                if not location:
                    return FetchResult(is_success=False, category="invalid_redirect", status_code=resp.status_code)

                next_url = urljoin(current_url, location)
                if next_url in visited_urls:
                    return FetchResult(is_success=False, category="redirect_loop", status_code=resp.status_code)

                visited_urls.add(next_url)

                # Validate redirect target for SSRF/private networks
                is_safe, sec_cat = validate_url_security(next_url, resolve_dns=self._resolve_dns)
                if not is_safe:
                    return FetchResult(is_success=False, category=sec_cat, status_code=resp.status_code)

                current_url = next_url
                continue

            # Validate HTTP status
            if resp.status_code == 403:
                return FetchResult(is_success=False, category="http_403", status_code=403)
            if resp.status_code == 404:
                return FetchResult(is_success=False, category="http_404", status_code=404)
            if resp.status_code == 429:
                return FetchResult(is_success=False, category="http_429", status_code=429)
            if 500 <= resp.status_code < 600:
                return FetchResult(is_success=False, category="http_5xx", status_code=resp.status_code)
            if resp.status_code != 200:
                return FetchResult(
                    is_success=False,
                    category=f"http_{resp.status_code}",
                    status_code=resp.status_code,
                )

            # Content-Type validation
            content_type = (resp.headers.get("content-type") or "").lower()
            if content_type and not any(
                allowed in content_type for allowed in ("text/", "application/xhtml+xml", "application/xml")
            ):
                return FetchResult(is_success=False, category="invalid_content_type", status_code=200)

            # Content-Length check
            cl_header = resp.headers.get("content-length")
            if cl_header:
                try:
                    if int(cl_header) > MAX_ARTICLE_BYTES:
                        return FetchResult(is_success=False, category="oversized", status_code=200)
                except ValueError:
                    pass

            # Body size check
            body_bytes = resp.content
            if len(body_bytes) > MAX_ARTICLE_BYTES:
                return FetchResult(is_success=False, category="oversized", status_code=200)

            # Decode content without persisting to disk
            html_text = resp.text
            return FetchResult(
                is_success=True,
                status_code=200,
                content=html_text,
                final_url=current_url,
            )

    def _extract_trafilatura_sync(self, html: str, url: str) -> dict[str, Any]:
        """Execute trafilatura extraction synchronously in a thread."""
        doc = trafilatura.bare_extraction(
            html,
            url=url,
            with_metadata=True,
            favor_precision=True,
            include_comments=False,
            include_tables=True,
            include_links=False,
        )

        meta = trafilatura.extract_metadata(html, default_url=url)

        title: str | None = None
        author: str | None = None
        date: str | None = None
        canonical_url: str | None = None
        body: str | None = None

        if doc:
            title = getattr(doc, "title", None)
            author = getattr(doc, "author", None)
            date = getattr(doc, "date", None)
            canonical_url = getattr(doc, "url", None)
            body = getattr(doc, "text", None)

        if meta:
            if not title and getattr(meta, "title", None):
                title = meta.title
            if not author and getattr(meta, "author", None):
                author = meta.author
            if not date and getattr(meta, "date", None):
                date = meta.date
            if not canonical_url and getattr(meta, "url", None):
                canonical_url = meta.url

        # Fallback metadata regexes if still missing
        if not title:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                t = re.sub(r"\s+", " ", m.group(1)).strip()
                if t:
                    title = t

        if not author:
            m = re.search(r"""<meta\s+[^>]*name=["']author["'][^>]*content=["']([^"']+)["']""", html, re.IGNORECASE)
            if not m:
                m = re.search(r"""<meta\s+[^>]*content=["']([^"']+)["'][^>]*name=["']author["']""", html, re.IGNORECASE)
            if m:
                a = m.group(1).strip()
                if a:
                    author = a

        if not date:
            m = re.search(
                r"""<meta\s+[^>]*name=["'](?:date|pubdate|publishdate|article:published_time)["'][^>]*content=["']([^"']+)["']""",
                html,
                re.IGNORECASE,
            )
            if not m:
                m = re.search(
                    r"""<meta\s+[^>]*content=["']([^"']+)["'][^>]*name=["'](?:date|pubdate|publishdate|article:published_time)["']""",
                    html,
                    re.IGNORECASE,
                )
            if m:
                d = m.group(1).strip()
                if d:
                    date = d

        if not canonical_url:
            m = re.search(r"""<link\s+[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["']""", html, re.IGNORECASE)
            if not m:
                m = re.search(r"""<link\s+[^>]*href=["']([^"']+)["'][^>]*rel=["']canonical["']""", html, re.IGNORECASE)
            if m:
                c = m.group(1).strip()
                if c:
                    canonical_url = c

        return {
            "title": title,
            "author": author,
            "date": date,
            "canonical_url": canonical_url,
            "body": body,
        }

    def _categorize_exception(self, err: Exception) -> str:
        """Map exception to a bounded error category string."""
        if isinstance(err, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException, TimeoutError)):
            return "timeout"
        if isinstance(err, (httpx.ConnectError, httpx.NetworkError, socket.error)):
            return "connection_failed"
        if isinstance(err, httpx.InvalidURL):
            return "invalid_url"
        return "unavailable"

    def _degraded_result(self, category: str) -> ExtractionResult:
        """Construct a standardized degraded ExtractionResult on extraction failure."""
        return ExtractionResult(
            tier=1,
            kind=Kind.UNKNOWN,
            title=None,
            channel=None,
            duration=None,
            published=None,
            body=None,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
            source_meta={"category": category, "status": "unavailable"},
        )

    def _log_failure(self, platform: str, category: str) -> None:
        """Log failure with bounded category and platform only (zero sensitive details)."""
        logger.warning(
            "Article extraction failed for platform=%s category=%s",
            platform,
            category,
        )
