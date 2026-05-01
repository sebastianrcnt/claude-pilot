from __future__ import annotations

import base64
from typing import Any


class XPlaneUnavailableError(RuntimeError):
    pass


class ToLissNotLoadedError(RuntimeError):
    pass


class MappingError(NotImplementedError):
    pass


def decode_toliss_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            raw = base64.b64decode(value, validate=True)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
        except Exception:
            return value.rstrip("\x00").rstrip()
    if isinstance(value, list):
        try:
            raw = bytes(int(item) & 0xFF for item in value)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
        except Exception:
            return ""
    if isinstance(value, bytes):
        return value.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
    return str(value).rstrip("\x00").rstrip()
