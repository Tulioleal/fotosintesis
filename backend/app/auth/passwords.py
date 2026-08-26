from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def hash_token(raw_token: str) -> str:
    """Return a hex SHA-256 digest of the raw recovery token.

    Only the one-way digest is ever persisted or compared; the raw token
    lives only long enough to build the delivery link.
    """
    return sha256(raw_token.encode("utf-8")).hexdigest()
