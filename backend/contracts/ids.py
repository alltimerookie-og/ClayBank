"""UUIDv7 + ISO-8601 UTC helpers (contract: UUIDv7 ids, Z timestamps)."""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone


def now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_uuid7() -> str:
    """Random UUIDv7 (RFC 9562): 48-bit ms timestamp + ver 7 + rand."""
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = bytearray(os.urandom(10))
    b = bytearray(16)
    b[0:6] = ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand[0] & 0x0F)
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)
    b[9:16] = rand[3:10]
    return str(uuid.UUID(bytes=bytes(b)))
