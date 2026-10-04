"""ASGI-level request limits for uploads that contain sensitive candidate data."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    """Reject oversized request bodies before multipart parsing can spool them.

    ``UploadFile`` is constructed after Starlette has consumed multipart bytes,
    so endpoint-level reads alone cannot defend against a large or chunked body.
    This guard checks a declared Content-Length early and also counts every
    ASGI receive chunk for requests without a trustworthy length header.
    """

    def __init__(self, app: ASGIApp, *, path: str, max_bytes: int) -> None:
        self.app = app
        self.path = path
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != self.path:
            await self.app(scope, receive, send)
            return

        if _declared_content_length(scope) > self.max_bytes:
            await _send_body_too_large(scope, receive, send)
            return

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    # FastAPI's exception layer translates this to the same
                    # standardized JSON response if multipart parsing is in
                    # progress when the streaming limit is crossed.
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "request_body_too_large",
                            "message": "The uploaded resume must be 5 MB or smaller.",
                        },
                    )
            return message

        await self.app(scope, limited_receive, send)


def _declared_content_length(scope: Scope) -> int:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return max(int(value), 0)
        except ValueError:
            return 0
    return 0


async def _send_body_too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=413,
        content={
            "error": {
                "code": "request_body_too_large",
                "message": "The uploaded resume must be 5 MB or smaller.",
            }
        },
    )
    await response(scope, receive, send)
