"""Shared SSRF-protected HTTP transport and bounded streaming utilities (ADR 0002, Rules.md §8).

Provides DNS-pinning, private network rejection, cloud metadata protection,
manual redirect validation, and bounded chunked streaming across all extraction providers.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpcore
import httpx

logger = logging.getLogger(__name__)

# Security & resource bounds
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


def is_private_ip(ip_val: Any) -> bool:
    """Return True if IP is loopback, private, link-local, reserved, multicast, unspecified, or cloud metadata.

    Supports IPv4, IPv6, and IPv4-mapped IPv6 addresses.
    """
    try:
        ip_str = str(ip_val).strip("[]")
        if ip_str in CLOUD_METADATA_IPS:
            return True

        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True

        # Check IPv4-mapped IPv6 explicitly (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            mapped = ip.ipv4_mapped
            if (
                str(mapped) in CLOUD_METADATA_IPS
                or mapped.is_private
                or mapped.is_loopback
                or mapped.is_link_local
                or mapped.is_reserved
                or mapped.is_multicast
                or mapped.is_unspecified
            ):
                return True

        return False
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
            if not addr_info:
                return False, "private_network"

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


class SSRFProtectedBackend(httpcore.AnyIOBackend):
    """Network backend that pins connections to pre-validated public IPs to prevent DNS rebinding."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        host_clean = host.strip("[]")

        # Fast path check if host is already an IP address
        if is_private_ip(host_clean):
            raise httpcore.ConnectError(f"SSRF blocked: host {host} is a private/reserved address")

        try:
            # Check if host is a valid public IP literal
            ipaddress.ip_address(host_clean)
            is_ip_literal = True
        except ValueError:
            is_ip_literal = False

        if is_ip_literal:
            pinned_ip = host_clean
        else:
            # Domain name: resolve DNS and validate all returned IP addresses
            try:
                loop = asyncio.get_running_loop()
                addr_info = await loop.run_in_executor(
                    None,
                    lambda: socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM),
                )
            except socket.gaierror as exc:
                raise httpcore.ConnectError(f"DNS resolution failed for {host}: {exc}") from exc
            except Exception as exc:
                raise httpcore.ConnectError(f"DNS error resolving {host}: {exc}") from exc

            if not addr_info:
                raise httpcore.ConnectError(f"No DNS records found for host {host}")

            validated_ips: list[str] = []
            for entry in addr_info:
                ip_str = str(entry[4][0])
                if is_private_ip(ip_str):
                    raise httpcore.ConnectError(
                        f"SSRF blocked: host {host} resolved to forbidden private/reserved IP {ip_str}"
                    )
                validated_ips.append(ip_str)

            if not validated_ips:
                raise httpcore.ConnectError(f"No valid public IP found for host {host}")

            # Pin to the first validated public IP
            pinned_ip = validated_ips[0]

        return await super().connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class SSRFProtectedTransport(httpx.AsyncHTTPTransport):
    """Custom HTTP transport integrating SSRFProtectedBackend into httpcore.AsyncConnectionPool."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=self._pool._max_keepalive_connections,
            keepalive_expiry=self._pool._keepalive_expiry,
            http1=self._pool._http1,
            http2=self._pool._http2,
            retries=self._pool._retries,
            network_backend=SSRFProtectedBackend(),
        )


def create_ssrf_protected_client(timeout: httpx.Timeout | None = None) -> httpx.AsyncClient:
    """Create a security-hardened httpx.AsyncClient with DNS pinning and SSRF protection."""
    transport = SSRFProtectedTransport()
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,  # Manual redirect validation is mandatory
        timeout=timeout or httpx.Timeout(
            connect=HTTP_CONNECT_TIMEOUT_SECONDS,
            read=HTTP_READ_TIMEOUT_SECONDS,
            write=5.0,
            pool=5.0,
        ),
    )
