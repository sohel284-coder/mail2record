"""Encrypt mailbox credentials (OAuth tokens / IMAP app passwords) at rest.

The key comes from ``settings.EMAIL_CREDENTIALS_KEY``; if that's unset we derive
a stable key from ``SECRET_KEY`` so local dev works with no extra setup (a real
deployment should set an explicit key — see settings.py).
"""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = getattr(settings, "EMAIL_CREDENTIALS_KEY", "") or ""
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    derived = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(derived)


def encrypt_dict(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data or {}).encode()).decode()


def decrypt_dict(token: str) -> dict:
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError, TypeError):
        return {}
