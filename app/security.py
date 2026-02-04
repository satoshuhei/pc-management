from __future__ import annotations

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_passcode(passcode: str) -> str:
    return pwd_context.hash(passcode)


def verify_passcode(passcode: str, passcode_hash: str) -> bool:
    return pwd_context.verify(passcode, passcode_hash)
