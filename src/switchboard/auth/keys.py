import hashlib
import secrets
from typing import NamedTuple

KEY_PREFIX_LENGTH = 8


class GeneratedApiKey(NamedTuple):
    key: str
    key_prefix: str
    key_hash: str


def generate_api_key() -> GeneratedApiKey:
    key = f"sbk_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(key)
    return GeneratedApiKey(key=key, key_prefix=key[:KEY_PREFIX_LENGTH], key_hash=key_hash)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_api_key(key: str, key_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(key), key_hash)