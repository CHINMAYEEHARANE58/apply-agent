import pytest

from app.config.connection import postgres_connection_url


def test_neon_connection_uses_psycopg_and_tls() -> None:
    url = postgres_connection_url("postgresql://user:pass@ep-test-pooler.neon.tech/db")
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"
    assert url.host == "ep-test-pooler.neon.tech"


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer"])
def test_neon_cannot_disable_tls(mode: str) -> None:
    with pytest.raises(ValueError, match="TLS"):
        postgres_connection_url(f"postgresql://user:pass@ep-test.neon.tech/db?sslmode={mode}")


def test_connection_preserves_encoded_password_and_tls_parameters() -> None:
    url = postgres_connection_url("postgres://user:a%40b%25c@ep-test.neon.tech/db?sslmode=verify-full&channel_binding=require")
    assert url.password == "a@b%c"
    assert url.query == {"sslmode": "verify-full", "channel_binding": "require"}


def test_local_and_test_connections_are_preserved() -> None:
    assert postgres_connection_url("sqlite://").drivername == "sqlite"
    assert not postgres_connection_url("postgresql+psycopg://localhost/db").query
