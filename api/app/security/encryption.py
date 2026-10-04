"""Small authenticated-encryption primitives for candidate-owned sensitive data."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import get_settings

_ENCRYPTED_TEXT_PREFIX = "internagent:v1:"
_NONCE_BYTES = 12


def encrypt_text(value: str, *, purpose: str) -> str:
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = _cipher().encrypt(nonce, value.encode("utf-8"), _associated_data(purpose))
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_ENCRYPTED_TEXT_PREFIX}{token}"


def decrypt_text(value: str, *, purpose: str) -> str:
    if not value.startswith(_ENCRYPTED_TEXT_PREFIX):
        # Every encrypted database field must carry the authenticated format.
        # Legacy parsed resume JSON is handled explicitly in its own migration;
        # accepting arbitrary plaintext here would turn a database write into
        # an unverified candidate qualification.
        raise ValueError("Encrypted data is missing its authenticated format.")
    try:
        payload = base64.urlsafe_b64decode(value[len(_ENCRYPTED_TEXT_PREFIX) :].encode("ascii"))
        nonce, ciphertext = payload[:_NONCE_BYTES], payload[_NONCE_BYTES:]
        if len(nonce) != _NONCE_BYTES or not ciphertext:
            raise ValueError("Encrypted data is invalid.")
        return _cipher().decrypt(nonce, ciphertext, _associated_data(purpose)).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError, InvalidTag) as error:
        raise ValueError("Encrypted data integrity check failed.") from error


def encrypt_json(value: Mapping[str, Any], *, purpose: str) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return encrypt_text(serialized, purpose=purpose)


def decrypt_json(value: str, *, purpose: str) -> dict[str, Any]:
    decoded = decrypt_text(value, purpose=purpose)
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as error:
        raise ValueError("Encrypted JSON data is invalid.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Encrypted JSON data is invalid.")
    return parsed


def sensitive_text_fingerprint(value: str, *, purpose: str) -> str:
    return hmac.new(_key(), _associated_data(purpose) + value.encode("utf-8"), hashlib.sha256).hexdigest()


def _cipher() -> AESGCM:
    return AESGCM(_key())


def _key() -> bytes:
    configured_secret = get_settings().app_encryption_key
    if len(configured_secret) < 32 or configured_secret.startswith("replace-"):
        raise RuntimeError("APP_ENCRYPTION_KEY must be configured for sensitive data encryption.")
    return hashlib.sha256(configured_secret.encode("utf-8")).digest()


def _associated_data(purpose: str) -> bytes:
    return f"internagent:{purpose}:v1".encode()
