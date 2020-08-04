import asyncio
from typing import Union

def ensure_bytes(v: Union[bytes, str]) -> bytes:
    if not isinstance(v, bytes):
        return bytes(v, encoding='utf8')
    else:
        return v

def prefix_range_end(prefix: Union[bytes, str]) -> bytes:
    """Create a bytestring that can be used as a range_end for a prefix."""
    prefix = ensure_bytes(prefix)
    s = bytearray(prefix)
    for i in reversed(range(len(s))):
        if s[i] < 0xff:
            s[i] = s[i] + 1
            break
    return bytes(s)

