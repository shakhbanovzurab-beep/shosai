"""PKCE for the desktop browser sign-in (RFC 7636, S256; ADR 0045 point 9).

The shipped macOS client sends a challenge to `/app/connect` and its verifier with the
exchange; the draft ignored both, so an app that hijacked the URL scheme could exchange a
stolen code. A code issued with a challenge now requires its verifier. A code issued
without one (the shipped Windows client) needs none, as before.
"""

import hashlib
import re
import secrets
from base64 import urlsafe_b64encode
from typing import Final

S256: Final = "S256"
VERIFIER: Final = re.compile(r"[A-Za-z0-9._~-]{43,128}")
CHALLENGE: Final = re.compile(r"[A-Za-z0-9_-]{43}")


def valid_challenge(challenge: str) -> bool:
    """Whether the text is an S256 challenge: 43 characters of base64url without padding."""
    return CHALLENGE.fullmatch(challenge) is not None


def verifier_matches(challenge: str, verifier: str | None) -> bool:
    """Whether the verifier's S256 hash is the challenge, compared in constant time."""
    if verifier is None or not VERIFIER.fullmatch(verifier):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = urlsafe_b64encode(digest).rstrip(b"=")
    return secrets.compare_digest(expected, challenge.encode("ascii"))
