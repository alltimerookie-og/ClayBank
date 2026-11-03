"""Canonicalize captured URLs and derive their platform."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {"fbclid", "gclid", "igsh", "si"}


def canonicalize_url(raw_url: str) -> str:
    """Strip tracking parameters and normalize known YouTube URL variants."""
    parts = urlsplit(raw_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    hostname = (parts.hostname or "").lower()
    if hostname in {"youtube.com", "www.youtube.com"} and path.startswith("/shorts/"):
        video_id = path.removeprefix("/shorts/").split("/", 1)[0]
        path, query = "/watch", [("v", video_id)]
    netloc = hostname
    if parts.port:
        netloc = f"{hostname}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def platform_for_url(url: str) -> str:
    """Return the contract platform value derived from a URL host."""
    hostname = (urlsplit(url).hostname or "").lower()
    hostname = hostname.removeprefix("www.")
    if hostname in {"youtube.com", "youtu.be"}:
        return "youtube"
    if hostname == "instagram.com" or hostname.endswith(".instagram.com"):
        return "instagram"
    if hostname == "tiktok.com" or hostname.endswith(".tiktok.com"):
        return "tiktok"
    if hostname == "facebook.com" or hostname.endswith(".facebook.com"):
        return "facebook"
    return hostname
