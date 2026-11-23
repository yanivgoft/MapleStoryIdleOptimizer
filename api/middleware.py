"""Pure-ASGI middleware: request logging (JSON lines), request-body size limit, per-IP sliding-window rate limit."""
import json
import logging
import time
import uuid
from collections import deque

log = logging.getLogger("msi.access")


def client_ip(scope, proxy_hops=0):
    """Client address: the socket peer, or (behind ``proxy_hops`` trusted proxies) the entry ``proxy_hops`` from the right of X-Forwarded-For."""
    if proxy_hops > 0:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                parts = [p.strip() for p in value.decode("latin-1").split(",") if p.strip()]
                if len(parts) >= proxy_hops:
                    return parts[-proxy_hops]
    client = scope.get("client")
    return client[0] if client else "unknown"


async def _send_json(send, status, payload, extra_headers=()):
    body = json.dumps(payload).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *extra_headers]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class RequestLogMiddleware:
    """One structured log line per request (+ ``x-request-id`` response header; the id is also on ``scope['state']``)."""

    def __init__(self, app, proxy_hops=0):
        self.app, self.proxy_hops = app, proxy_hops

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = rid
        started, status = time.perf_counter(), 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info(json.dumps(dict(event="request", id=rid, method=scope["method"], path=scope["path"], status=status,
                                     ms=round((time.perf_counter() - started) * 1000, 1), ip=client_ip(scope, self.proxy_hops))))


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.max_bytes <= 0:
            return await self.app(scope, receive, send)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > self.max_bytes
                except ValueError:
                    too_big = True
                if too_big:
                    return await _send_json(send, 413, {"detail": f"request body too large (max {self.max_bytes} bytes)"})
        seen, started = 0, False

        async def receive_wrapper():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def send_wrapper(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except _BodyTooLarge:
            if not started:
                await _send_json(send, 413, {"detail": f"request body too large (max {self.max_bytes} bytes)"})


class RateLimitMiddleware:
    """Per-IP sliding window over ``/api/*`` (``/api/health`` and CORS preflights are exempt); ``limit <= 0`` disables.  In-memory, so each
    server instance counts on its own - fine as an abuse brake, not as a quota."""

    def __init__(self, app, limit, window_s=60, proxy_hops=0, clock=time.monotonic, match=None):
        # ``match(scope) -> bool`` narrows which requests this instance counts (default: every /api/* request; used for the tighter sensitivity limit)
        self.app, self.limit, self.window, self.hops, self.clock = app, limit, window_s, proxy_hops, clock
        self.match = match
        self.hits = {}
        self._last_sweep = clock()

    def _sweep(self, now):
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        for ip in [ip for ip, q in self.hits.items() if not q or now - q[-1] > self.window]:
            del self.hits[ip]

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (scope["type"] != "http" or self.limit <= 0 or not path.startswith("/api/") or path == "/api/health"
                or scope["method"] == "OPTIONS" or (self.match is not None and not self.match(scope))):
            return await self.app(scope, receive, send)
        now = self.clock()
        self._sweep(now)
        q = self.hits.setdefault(client_ip(scope, self.hops), deque())
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            retry = max(1, int(self.window - (now - q[0])) + 1)
            return await _send_json(send, 429, {"detail": "rate limit exceeded, slow down"}, [(b"retry-after", str(retry).encode())])
        q.append(now)
        await self.app(scope, receive, send)


def is_sensitivity_call(scope):
    """``POST /api/classes/{id}/sensitivity`` (the expensive endpoint with its own, tighter limit)."""
    return scope.get("method") == "POST" and scope.get("path", "").endswith("/sensitivity")


def is_cubes_call(scope):
    """``POST /api/classes/{id}/cubes`` (the cube optimizer: seconds of CPU per call, its own limit)."""
    return scope.get("method") == "POST" and scope.get("path", "").endswith("/cubes")


def is_compare_call(scope):
    """``POST .../equipment-compare`` and ``POST .../artifact-potentials`` (cheap once the character's stat rates are cached, a sensitivity run otherwise)."""
    return scope.get("method") == "POST" and scope.get("path", "").endswith(("/equipment-compare", "/artifact-potentials"))
