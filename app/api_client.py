"""Reusable API client — envelopes, auth headers, timeouts, error mapping.

Never hardcodes the base URL (see app/client_config.py). Credentials never
appear in UI messages or logs — only status codes + contract error codes.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiError(Exception):
    code: str
    message: str
    detail: object = None
    status: int = 0


@dataclass
class ApiResult:
    ok: bool
    status: int
    data: object = None
    error: ApiError | None = None


@dataclass
class ClayBankClient:
    base_url: str
    dev_token: str
    device_id: str
    timeout: float = 15.0
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.dev_token}",
                "X-Device-Id": self.device_id}

    def _fresh_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout,
                                 headers=self._headers())

    async def _handle(self) -> httpx.AsyncClient:
        # One client per event loop: reusing a client bound to a closed loop
        # raises RuntimeError on the next request (seen in smoke tests).
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._fresh_client()
        if (self._client is None or getattr(self._client, "_loop", None) not in
                (None, loop)):
            try:
                if self._client is not None:
                    await self._client.aclose()
            except Exception:
                pass
            self._client = self._fresh_client()
            try:
                self._client._loop = loop  # type: ignore[attr-defined]
            except Exception:
                pass
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def __del__(self) -> None:  # best effort; event loop may be gone
        try:
            client = self._client
            if client is not None and not client.is_closed:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return
                loop.create_task(client.aclose())
        except Exception:
            pass

    def new_idempotency_key(self) -> str:
        return str(uuid.uuid4())

    async def request(self, method: str, path: str, **kwargs) -> ApiResult:
        client = await self._handle()
        try:
            resp = await client.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            log.warning("api unreachable: %s %s", type(exc).__name__, path)
            return ApiResult(ok=False, status=0,
                             error=ApiError(code="offline",
                                            message="Offline / unreachable",
                                            status=0))
        except Exception as exc:  # never leak internals to UI
            # httpx wraps transport failures (e.g. DNS on Android) in
            # RequestError subclasses that are NOT ConnectError. Probe the
            # chain: network-level -> offline; anything else -> honest error.
            name = type(exc).__name__
            chained = str(exc.__cause__ or exc.__context__ or "")
            network_marks = ("connect", "timeout", "dns", "unreachable",
                             "refused", "reset", "network", "nodename",
                             "getaddrinfo", "timed out")
            blob = f"{name} {exc} {chained}".lower()
            if isinstance(exc, httpx.RequestError) or any(
                    m in blob for m in network_marks):
                log.warning("api unreachable: %s %s", name, path)
                return ApiResult(ok=False, status=0,
                                 error=ApiError(code="offline",
                                                message="Offline / unreachable",
                                                status=0))
            log.warning("api error: %s %s", name, path)
            return ApiResult(ok=False, status=-1,
                             error=ApiError(code="request_error",
                                            message=f"{name} (see logs)",
                                            status=-1))
        try:
            body = resp.json()
        except Exception:
            body = {}
        if 200 <= resp.status_code < 300:
            data = body.get("data", body) if isinstance(body, dict) else body
            return ApiResult(ok=True, status=resp.status_code, data=data)
        err = body.get("error", {}) if isinstance(body, dict) else {}
        return ApiResult(
            ok=False, status=resp.status_code,
            error=ApiError(code=str(err.get("code", f"http_{resp.status_code}")),
                           message=str(err.get("message", "Request failed")),
                           detail=err.get("detail"),
                           status=resp.status_code))

    async def health(self) -> ApiResult:
        return await self.request("GET", "/health")

    async def list_saves(self, *, inbox: bool | None = None, cursor: str | None = None,
                         limit: int = 20) -> ApiResult:
        params: dict[str, str] = {"limit": str(limit)}
        if inbox is not None:
            params["inbox"] = "true" if inbox else "false"
        if cursor:
            params["cursor"] = cursor
        return await self.request("GET", "/saves", params=params)

    async def read_save(self, save_id: str) -> ApiResult:
        return await self.request("GET", f"/saves/{save_id}")

    async def put_note(self, save_id: str, markdown: str, updated_at: str) -> ApiResult:
        payload = {"markdown": markdown, "updated_at": updated_at}
        return await self.request("PUT", f"/saves/{save_id}/note", json=payload)

    async def reprocess(self, save_id: str, from_stage: str = "extracting") -> ApiResult:
        return await self.request("POST", f"/saves/{save_id}/reprocess", params={"from": from_stage})

    async def capture(self, url: str, user_context: str = "",
                      idempotency_key: str | None = None,
                      force: bool = False) -> ApiResult:
        headers = {"Idempotency-Key": idempotency_key or self.new_idempotency_key()}
        payload: dict[str, object] = {"url": url, "user_context": user_context}
        if force:
            payload["force"] = True
        return await self.request("POST", "/saves", json=payload, headers=headers)
