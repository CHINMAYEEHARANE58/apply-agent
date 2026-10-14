"""Read-only source/browser-bundle checks. Never print matched secret values."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


def scan(root: Path) -> dict[str, object]:
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
    patterns = [re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}"), re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")]
    findings = []
    for relative in paths:
        if not relative or relative.endswith("package-lock.json"):
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_text(errors="replace")
        if any(pattern.search(content) for pattern in patterns):
            findings.append({"file": relative, "issue": "possible committed credential", "action": "ROTATION REQUIRED if genuine"})
    secrets = []
    for path in [root / ".env", root / ".env.qa", root / "frontend/.env.local"]:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            key, separator, value = line.partition("=")
            value = value.strip().strip('"\'')
            if not separator or not value or value.startswith("replace-"):
                continue
            if key in {"APP_ENCRYPTION_KEY", "CLERK_SECRET_KEY"}:
                secrets.append(value)
            if key in {"DATABASE_URL", "DATABASE_DIRECT_URL"}:
                password = urlsplit(value.replace("postgresql+psycopg:", "postgresql:")).password
                if password and not password.startswith("replace-"):
                    secrets.append(unquote(password))
    bundles = list((root / "frontend/.next/static").rglob("*.js"))
    for path in bundles:
        content = path.read_text(errors="replace")
        if any(secret in content for secret in secrets if len(secret) >= 12):
            findings.append({"file": str(path.relative_to(root)), "issue": "private environment value in browser bundle", "action": "ROTATION REQUIRED"})
    return {"source_files_checked": len([path for path in paths if path]), "browser_bundles_checked": len(bundles), "findings": findings}


if __name__ == "__main__":
    result = scan(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["findings"] else 0)
