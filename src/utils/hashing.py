import hashlib
from typing import Iterable


def hash_bytes(data: bytes, algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


def hash_chunks(chunks: Iterable[bytes], algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    for chunk in chunks:
        h.update(chunk)
    return h.hexdigest()
