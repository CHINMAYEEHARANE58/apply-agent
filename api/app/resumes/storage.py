import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import get_settings

_ENVELOPE_MAGIC = b"INTERNAGENT-RESUME-V1\x00"
_NONCE_BYTES = 12


class PrivateResumeStorage:
    """Encrypted local storage adapter that exposes opaque keys, never public URLs.

    The application encryption secret is supplied through configuration, then
    derived into an AES-256-GCM key.  Each record uses a new random nonce and
    binds its ciphertext to its opaque storage key, preventing undetected
    swapping between candidate records.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().private_resume_storage_path).resolve()

    def save(self, user_id: uuid.UUID, resume_id: uuid.UUID, extension: str, content: bytes) -> str:
        if extension not in {"pdf", "docx"}:
            raise ValueError("Unsupported private resume storage extension.")
        relative_key = f"{user_id}/{resume_id}.{extension}"
        destination = self._path_for_key(relative_key)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(destination.parent, 0o700)
        except OSError:
            pass
        encrypted_content = self._encrypt(relative_key, content)
        descriptor, temporary_path = tempfile.mkstemp(prefix=".upload-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(encrypted_content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, destination)
        except BaseException:
            Path(temporary_path).unlink(missing_ok=True)
            raise
        return relative_key

    def delete(self, key: str) -> None:
        self._path_for_key(key).unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        """Decrypt a private resume for an authorized internal workflow.

        No API route exposes this method or its filesystem path.  It exists so
        future internal processing can read the same authenticated ciphertext
        without falling back to public object-storage URLs.
        """

        encrypted_content = self._path_for_key(key).read_bytes()
        return self._decrypt(key, encrypted_content)

    def _encrypt(self, key: str, content: bytes) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._cipher().encrypt(nonce, content, key.encode("utf-8"))
        return _ENVELOPE_MAGIC + nonce + ciphertext

    def _decrypt(self, key: str, encrypted_content: bytes) -> bytes:
        minimum_length = len(_ENVELOPE_MAGIC) + _NONCE_BYTES + 16
        if (
            len(encrypted_content) < minimum_length
            or not encrypted_content.startswith(_ENVELOPE_MAGIC)
        ):
            raise ValueError("Private resume storage content is invalid.")
        nonce_start = len(_ENVELOPE_MAGIC)
        nonce_end = nonce_start + _NONCE_BYTES
        try:
            return self._cipher().decrypt(
                encrypted_content[nonce_start:nonce_end],
                encrypted_content[nonce_end:],
                key.encode("utf-8"),
            )
        except InvalidTag as error:
            raise ValueError("Private resume storage integrity check failed.") from error

    @staticmethod
    def _cipher() -> AESGCM:
        configured_secret = get_settings().app_encryption_key
        if len(configured_secret) < 32 or configured_secret.startswith("replace-"):
            raise RuntimeError("APP_ENCRYPTION_KEY must be configured for private resume storage.")
        secret = configured_secret.encode("utf-8")
        return AESGCM(hashlib.sha256(secret).digest())

    def _path_for_key(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("Invalid private storage key.")
        return candidate


private_resume_storage = PrivateResumeStorage()
