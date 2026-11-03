"""Identifier generation."""

import os
import time
import uuid


def new_uuid7() -> uuid.UUID:
    """Generate a UUIDv7-compatible identifier on Python 3.12."""
    timestamp_ms = int(time.time() * 1000)
    random_bytes = bytearray(os.urandom(10))
    value = (timestamp_ms << 80) | int.from_bytes(random_bytes, "big")
    value &= ~(0xF << 76)
    value |= 0x7 << 76
    value &= ~(0x3 << 62)
    value |= 0x2 << 62
    return uuid.UUID(int=value)
