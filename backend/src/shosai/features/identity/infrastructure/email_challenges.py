"""Challenges of sign-in by an emailed code (ADR 0048): sealed for the browser, counted in Valkey.

The browser keeps the challenge as a Fernet token under a key derived from the signing key:
the address, the home its mail was written in, where the person was going and the language
travel inside, encrypted and expiring in 15 minutes. Valkey keeps only what must be shared
between processes, under the hash of the challenge's nonce: the code's hash, the wrong
attempts and the resends — ids and hashes, no address (nfr-4). One script per change keeps
counting atomic under parallel requests.
"""

import asyncio
import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from cryptography.fernet import Fernet, InvalidToken
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.features.identity.domain.email_codes import CHALLENGE_LIFETIME

DERIVATION: Final = b"shosai.identity.email_challenge.v1"
DEADLINE: Final = timedelta(milliseconds=200)

CREATE_SCRIPT: Final = """
redis.call('HSET', KEYS[1], 'code', ARGV[1], 'attempts', 0, 'resends', 0, 'sent', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""
# Ошибка кода: счётчик растёт до сравнения, поэтому параллельный перебор не обгонит лимит.
ATTEMPT_SCRIPT: Final = """
if redis.call('EXISTS', KEYS[1]) == 0 then return false end
local attempts = redis.call('HINCRBY', KEYS[1], 'attempts', 1)
return {redis.call('HGET', KEYS[1], 'code'), attempts}
"""
# Новый код: не чаще интервала и не больше лимита; ответ — 0, -1 нет вызова, -2 лимит, -3 рано.
RENEW_SCRIPT: Final = """
if redis.call('EXISTS', KEYS[1]) == 0 then return {-1, 0} end
local resends = tonumber(redis.call('HGET', KEYS[1], 'resends'))
local sent = tonumber(redis.call('HGET', KEYS[1], 'sent'))
local now, interval = tonumber(ARGV[2]), tonumber(ARGV[3])
if resends >= tonumber(ARGV[4]) then return {-2, 0} end
if now - sent < interval then return {-3, interval - (now - sent)} end
redis.call('HSET', KEYS[1], 'code', ARGV[1], 'resends', resends + 1, 'sent', now, 'attempts', 0)
redis.call('EXPIRE', KEYS[1], ARGV[5])
return {0, 0}
"""


class ChallengesUnavailableError(Exception):
    """Valkey did not answer: no challenge can be started or checked now."""


@dataclass(frozen=True, slots=True)
class ChallengeClaim:
    """What a sealed challenge carries."""

    nonce: bytes
    email: str
    home: Home
    next_path: str
    language: str


@dataclass(frozen=True, slots=True)
class Renewal:
    """The answer to a request for a new code: 0 sent, else the refusal and the wait."""

    outcome: int
    wait_seconds: int


class ChallengeSeals:
    """Seal and open challenges."""

    def __init__(self, signing_key: bytes) -> None:
        derived = hashlib.sha256(DERIVATION + signing_key).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def seal(self, claim: ChallengeClaim) -> str:
        """The challenge the browser keeps."""
        payload = {
            "nonce": claim.nonce.hex(), "email": claim.email, "home": claim.home.value,
            "next": claim.next_path, "language": claim.language,
        }  # fmt: skip
        return self._fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")

    def open(self, challenge: str) -> ChallengeClaim | None:
        """The claim of a valid, unexpired challenge, or None."""
        try:
            raw = self._fernet.decrypt(
                challenge.encode("ascii"), ttl=int(CHALLENGE_LIFETIME.total_seconds())
            )
        except InvalidToken, UnicodeEncodeError:
            return None
        payload = json.loads(raw)
        return ChallengeClaim(
            nonce=bytes.fromhex(payload["nonce"]), email=payload["email"],
            home=Home(payload["home"]), next_path=payload["next"], language=payload["language"],
        )  # fmt: skip


class ChallengeStates:
    """The shared state of live challenges in Valkey."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey
        self._create = valkey.register_script(CREATE_SCRIPT)
        self._attempt = valkey.register_script(ATTEMPT_SCRIPT)
        self._renew = valkey.register_script(RENEW_SCRIPT)

    async def create(self, nonce: bytes, code_hash: bytes) -> None:
        """A new challenge with its first code."""
        args: list[str | int] = [code_hash.hex(), _now(), _lifetime()]
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._create(keys=[_key(nonce)], args=args)
        except REDIS_FAILURES as error:
            raise ChallengesUnavailableError from error

    async def attempt(self, nonce: bytes) -> tuple[bytes, int] | None:
        """The code's hash and this attempt's number; None when the challenge is gone."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                answer = await self._attempt(keys=[_key(nonce)])
        except REDIS_FAILURES as error:
            raise ChallengesUnavailableError from error
        if not answer:
            return None
        stored, attempts = answer
        text = stored.decode("ascii") if isinstance(stored, bytes) else str(stored)
        return bytes.fromhex(text), int(attempts)

    async def end(self, nonce: bytes) -> bool:
        """Remove the challenge; True only for the call that removed it."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                return bool(await self._valkey.delete(_key(nonce)))
        except REDIS_FAILURES as error:
            raise ChallengesUnavailableError from error

    async def renew(self, nonce: bytes, code_hash: bytes, pacing: tuple[int, int]) -> Renewal:
        """Replace the code if pacing allows: `pacing` is (interval seconds, max resends)."""
        interval, max_resends = pacing
        args: list[str | int] = [code_hash.hex(), _now(), interval, max_resends, _lifetime()]
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                outcome, wait = await self._renew(keys=[_key(nonce)], args=args)
        except REDIS_FAILURES as error:
            raise ChallengesUnavailableError from error
        return Renewal(int(outcome), int(wait))


def _key(nonce: bytes) -> str:
    return build_key("identity", "email_challenge", hashlib.sha256(nonce).hexdigest())


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def _lifetime() -> int:
    return int(CHALLENGE_LIFETIME.total_seconds())
