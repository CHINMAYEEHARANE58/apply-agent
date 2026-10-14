"""Transport headers, HTTPS enforcement, and a privacy-preserving rate limit."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config.settings import get_settings


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        if (
            settings.app_environment.casefold() == "production"
            and settings.require_https
            and scope.get("scheme") != "https"
        ):
            response = JSONResponse(
                status_code=400,
                content={"error": {"code": "https_required", "message": "HTTPS is required."}},
            )
            await response(scope, receive, send)
            return

        async def secured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (
                            b"content-security-policy",
                            b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                        ),
                    ]
                )
                if settings.app_environment.casefold() == "production":
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, secured_send)


class RateLimitMiddleware:
    """Shared atomic Redis limits in production; bounded local development limits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.max_clients = 10_000
        self._next_cleanup = 0.0
        self._redis: Any = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in {
            "/api/v1/health",
            "/api/v1/openapi.json",
        }:
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        settings = get_settings()
        if settings.app_environment == "production":
            if settings.require_https and scope.get("scheme") != "https":
                await self.app(scope, receive, send)
                return
            if self._redis is None:
                self._redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            identity = hashlib.sha256(key.encode()).hexdigest()
            script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n"
            try:
                used = int(await self._redis.eval(script, 1, "internagent:rate:" + identity))
            except (RedisError, OSError):
                await JSONResponse(status_code=503, content={"error": {"code": "rate_limit_unavailable", "message": "Request protection is temporarily unavailable."}})(scope, receive, send)
                return  # No process-local fallback that multiplies the quota.
            if used > settings.rate_limit_per_minute:
                await JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests."}}, headers={"Retry-After": "60"})(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        if now >= self._next_cleanup:
            for existing, entries in list(self.requests.items()):
                if not entries or entries[-1] <= now - 60:
                    del self.requests[existing]
            self._next_cleanup = now + 5
        if key not in self.requests and len(self.requests) >= self.max_clients:
            response = JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests."}}, headers={"Retry-After": "60"})
            await response(scope, receive, send)
            return
        bucket = self.requests[key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= get_settings().rate_limit_per_minute:
            response = JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too many requests."}},
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return
        bucket.append(now)
        await self.app(scope, receive, send)
