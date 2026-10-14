"""Opt-in live provider QA. Never point this runner at Neon or production Clerk."""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
config = {key: value for key, value in dotenv_values(ROOT / ".env.qa").items() if value is not None}
database = urlsplit(config.get("DATABASE_URL", ""))
if (database.hostname != "127.0.0.1" or database.port != 55432
        or not database.path.startswith("/internagent_test")):
    sys.exit("Refusing non-local or non-test database.")
if config.get("DATABASE_DIRECT_URL") != config.get("DATABASE_URL"):
    sys.exit("Direct and application connections must target the same disposable database.")
if config.get("REDIS_URL") != "redis://127.0.0.1:56379/0":
    sys.exit("Refusing a non-test Redis target.")
if not config.get("CLERK_SECRET_KEY", "").startswith("sk_test_") or not config.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").startswith("pk_test_"):
    sys.exit("Dedicated Clerk test keys are not configured. No live tests ran.")
if config.get("APP_ENVIRONMENT") != "test" or config.get("AUTH_PROVIDER") != "clerk":
    sys.exit("This runner requires test environment and Clerk authentication.")
if config.get("INTERNAGENT_API_URL") != "http://127.0.0.1:8110/api/v1":
    sys.exit("Refusing a non-local API target.")
env = os.environ.copy()
for key in list(env):
    if key.startswith(("CLERK_", "NEXT_PUBLIC_CLERK_")):
        env.pop(key)
env.update(config)
env["CLERK_JWT_KEY"] = config.get("CLERK_JWT_KEY", "")
subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", env=env, check=True)
backend = subprocess.Popen([
    str(ROOT / "api/.venv/bin/uvicorn"), "app.main:app", "--host", "127.0.0.1",
    "--port", "8110", "--no-access-log", "--log-level", "warning",
], cwd=ROOT / "api", env=env)
try:
    result = subprocess.run(["npx", "playwright", "test", "--config=playwright.clerk.config.ts"], cwd=ROOT / "frontend", env=env, check=False)
    sys.exit(result.returncode)
finally:
    backend.terminate()
    backend.wait(timeout=15)
