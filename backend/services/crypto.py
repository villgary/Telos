"""Re-exports the project's AES-256-GCM encrypt/decrypt and adds a
sha256[:16] fingerprint helper used by the cloud discovery channel.

The cloud discovery code imports from this module so tests have a single seam
and we don't have two copies of the fingerprint scheme drifting apart.
"""
import hashlib
from typing import Optional

from backend.encryption import encrypt, decrypt  # re-export


def fingerprint(plaintext: Optional[str]) -> Optional[str]:
    """Return a 16-char hex prefix of sha256(plaintext), or None for empty input.

    Never returns any portion of the key itself; the output is the first
    16 hex chars (8 bytes) of the digest, sufficient to detect key reuse
    across connections without persisting the secret.
    """
    if not plaintext:
        return None
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:16]
