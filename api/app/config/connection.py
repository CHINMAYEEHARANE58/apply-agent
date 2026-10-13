"""SQLAlchemy/psycopg URLs for local PostgreSQL and Neon."""

from sqlalchemy.engine import URL, make_url


def postgres_connection_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.host and url.host.endswith(".neon.tech"):
        if url.query.get("sslmode") not in {None, "require", "verify-ca", "verify-full"}:
            raise ValueError("Neon connections must use TLS.")
        sslmode = url.query.get("sslmode", "require")
        if not isinstance(sslmode, str):
            raise ValueError("Neon requires exactly one TLS mode.")
        url = url.update_query_dict({"sslmode": sslmode})
    return url
