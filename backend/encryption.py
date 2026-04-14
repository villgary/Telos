"""
AES-256-GCM encryption service for credentials.
Keys are loaded from the ACCOUNTSCAN_MASTER_KEY environment variable.
"""

import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

# 32 bytes = 256 bits
KEY_SIZE = 32
NONCE_SIZE = 12  # 96 bits, recommended for GCM


def _get_key() -> bytes:
    """Load the master key from environment variable."""
    raw = os.getenv("ACCOUNTSCAN_MASTER_KEY")
    if not raw:
        # For development only — raise in production
        raise RuntimeError(
            "ACCOUNTSCAN_MASTER_KEY environment variable is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    # Support both hex (64 chars) and raw base64
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return bytes.fromhex(raw)
    elif len(raw) == 44:  # base64 of 32 bytes
        return base64.b64decode(raw)
    else:
        # Treat as raw bytes (e.g. from a KMS)
        return raw.encode()[:KEY_SIZE].ljust(KEY_SIZE, b"\0")


_aesgcm = AESGCM(_get_key())


def encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext with AES-256-GCM.
    Returns: base64(nonce || ciphertext || tag)
    """
    nonce = secrets.token_bytes(NONCE_SIZE)
    ct = _aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    combined = nonce + ct
    return base64.b64encode(combined).decode("ascii")


def decrypt(ciphertext_b64: str) -> str:
    """
    Decrypt a ciphertext produced by encrypt().
    Raises cryptography.exceptions.InvalidTag if tampered.
    """
    combined = base64.b64decode(ciphertext_b64)
    nonce = combined[:NONCE_SIZE]
    ct = combined[NONCE_SIZE:]
    pt = _aesgcm.decrypt(nonce, ct, None)
    return pt.decode("utf-8")
