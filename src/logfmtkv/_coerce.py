"""Optional, lossless coercion of logfmt values into Python scalars."""

from __future__ import annotations

import math
import re

_INT = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
_FLOAT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?\Z")


def coerce(value: str | bool | None) -> str | bool | int | float | None:
    """Turn a parsed value into ``bool``, ``int`` or ``float`` when that loses nothing.

    ``"true"`` and ``"false"`` (lowercase, as Go and slog write them) become booleans,
    canonical decimal integers become ``int`` and finite decimal numbers become
    ``float``. Anything else is returned unchanged, including ``"007"``, ``"-0"``,
    ``"+1"``, ``"1_000"``, ``"8ms"``, ``"nan"`` and the empty string. Booleans and
    ``None`` pass through, so the result of :func:`parse` can be fed in directly.

    >>> [coerce(v) for v in ("200", "1.5", "true", "007", "8ms", True)]
    [200, 1.5, True, '007', '8ms', True]
    """
    if not isinstance(value, str) or isinstance(value, bool):
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        if _INT.match(value):
            return int(value)
        if _FLOAT.match(value) and not value.isdigit() and any(c in value for c in ".eE"):
            number = float(value)
            return number if math.isfinite(number) else value
    except ValueError:
        return value
    return value
