import asyncio
import os
from uuid import uuid4

from app.config.settings import get_settings
from app.security.http import RateLimitMiddleware


def test_production_limits_are_shared_across_middleware_instances(monkeypatch):
    url = os.environ.get("TEST_REDIS_URL", "")
    assert url.startswith("redis://127.0.0.1:"), "Use dedicated local TEST_REDIS_URL"
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("REDIS_URL", url)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    statuses = []
    identity = "qa-" + uuid4().hex
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    async def run():
        first, second = RateLimitMiddleware(endpoint), RateLimitMiddleware(endpoint)
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(message):
            if message["type"] == "http.response.start":
                statuses.append(message["status"])
        scope = {"type": "http", "path": "/protected", "scheme": "https", "client": (identity, 1)}
        try:
            await first(scope, receive, send)
            await second(scope, receive, send)
            await first(scope, receive, send)
            assert statuses == [200, 200, 429]
            import hashlib
            key = "internagent:rate:" + hashlib.sha256(identity.encode()).hexdigest()
            assert 0 < await first._redis.ttl(key) <= 60
            await first._redis.delete(key)
        finally:
            await first._redis.aclose()
            await second._redis.aclose()
    asyncio.run(run())
    get_settings.cache_clear()


def test_production_redis_failure_does_not_fall_back_to_per_process_quota(monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    async def forbidden(scope, receive, send):
        raise AssertionError("Protected endpoint must not execute when shared protection fails")
    from redis.exceptions import ConnectionError
    class FailedRedis:
        async def eval(self, *args):
            raise ConnectionError("sensitive-connection-string")
    middleware = RateLimitMiddleware(forbidden)
    middleware._redis = FailedRedis()
    responses = []
    async def run():
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(message):
            responses.append(message)
        await middleware({"type": "http", "path": "/protected", "scheme": "https", "client": ("qa", 1)}, receive, send)
    asyncio.run(run())
    assert responses[0]["status"] == 503
    assert b"sensitive" not in responses[1]["body"]
    get_settings.cache_clear()
