"""Transport headers, HTTPS enforcement, and a privacy-preserving rate limit."""

from __future__ import annotations

import time
from collections import defaultdict, deque

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
    """In-process fallback; deploy Redis-backed shared limits in production."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in {
            "/api/v1/health",
            "/api/v1/openapi.json",
        }:
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        now = time.monotonic()
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
