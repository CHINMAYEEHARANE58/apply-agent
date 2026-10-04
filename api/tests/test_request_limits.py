import asyncio

import pytest
from fastapi import HTTPException
from starlette.types import Message, Receive, Scope, Send

from app.security.request_limits import RequestBodyLimitMiddleware


def test_chunked_resume_upload_is_limited_without_content_length() -> None:
    async def exercise_middleware() -> None:
        messages = iter(
            [
                {"type": "http.request", "body": b"abc", "more_body": True},
                {"type": "http.request", "body": b"def", "more_body": False},
            ]
        )

        async def receive() -> Message:
            return next(messages)

        async def send(_: Message) -> None:
            return None

        async def downstream(_: Scope, limited_receive: Receive, __: Send) -> None:
            await limited_receive()
            await limited_receive()

        middleware = RequestBodyLimitMiddleware(
            downstream,
            path="/api/v1/resumes/upload",
            max_bytes=5,
        )
        scope: Scope = {"type": "http", "path": "/api/v1/resumes/upload", "headers": []}
        with pytest.raises(HTTPException) as error:
            await middleware(scope, receive, send)
        assert error.value.status_code == 413
        assert error.value.detail["code"] == "request_body_too_large"

    asyncio.run(exercise_middleware())
