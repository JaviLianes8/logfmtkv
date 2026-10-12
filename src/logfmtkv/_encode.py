"""Turn keys and arbitrary Python values into logfmt tokens."""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Mapping
from enum import Enum

from ._errors import LogfmtEncodeError
from ._escape import quote_value

_BAD_KEY_CHARS = re.compile('[\\x00-\\x20="\\x7f\\ufffd\\ud800-\\udfff]')
_CONTAINERS = (Mapping, list, tuple, set, frozenset)


def encode_pair(key: object, value: object, strict: bool) -> str | None:
    """Return ``key=value``, a bare ``key`` for True/None, or None to omit (False)."""
    if value is False:
        return None
    name = encode_key(key, strict)
    if value is True or value is None:
        return name
    return f"{name}={quote_value(value_text(value, strict, name))}"


def encode_key(key: object, strict: bool) -> str:
    """Return a valid logfmt key, stripping invalid characters unless ``strict``."""
    if not isinstance(key, str):
        if strict:
            raise LogfmtEncodeError(f"key must be a str, got {type(key).__name__}")
        key = _safe_str(key)
    if strict and _BAD_KEY_CHARS.search(key):
        raise LogfmtEncodeError(f"invalid character in key {key!r}")
    cleaned = _BAD_KEY_CHARS.sub("", key)
    if not cleaned:
        raise LogfmtEncodeError(f"key {key!r} is empty once invalid characters are removed")
    return cleaned


def value_text(value: object, strict: bool, key: str = "") -> str:
    """Return the text form of a non-flag value (before quoting)."""
    if isinstance(value, str):
        return value
    if isinstance(value, Enum):
        return value_text(value.value, strict, key)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", "replace")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, _CONTAINERS):
        if strict:
            raise LogfmtEncodeError(
                f"unsupported value type {type(value).__name__} for key {key!r}"
            )
        return _to_json(value)
    if strict:
        try:
            return str(value)
        except Exception as exc:
            raise LogfmtEncodeError(f"value for key {key!r} has no text form") from exc
    return _safe_str(value)


def _to_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    except (TypeError, ValueError):
        return _safe_str(value)


def _json_default(obj: object) -> object:
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return bytes(obj).decode("utf-8", "replace")
    return _safe_str(obj)


def _safe_str(obj: object) -> str:
    try:
        return str(obj)
    except Exception as exc:
        return f"<unprintable {type(obj).__name__}: {type(exc).__name__}>"
