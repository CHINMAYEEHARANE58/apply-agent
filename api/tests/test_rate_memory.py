import asyncio

from app.security.http import RateLimitMiddleware


def test_rate_limiter_cannot_grow_without_bound_for_new_clients() -> None:
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    middleware = RateLimitMiddleware(endpoint)
    middleware.max_clients = 2
    statuses = []
    async def run():
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(message):
            if message["type"] == "http.response.start":
                statuses.append(message["status"])
        for identity in ["one", "two", "three"]:
            await middleware({"type": "http", "path": "/protected", "client": (identity, 1)}, receive, send)
    asyncio.run(run())
    assert statuses == [200, 200, 429]
    assert len(middleware.requests) == 2
