"""Typed, zero-dependency logfmt codec: parse and serialize key=value log lines.

Read lines with :func:`parse`, :func:`parse_pairs`, :func:`parse_multi` or stream them
with :func:`iter_records` and :func:`iter_pairs`; write them with :func:`serialize` and
:func:`serialize_pairs`. Every reader takes ``strict=True`` to behave like go-logfmt.
"""

from __future__ import annotations

from ._codec import Duplicates, Pair, parse, parse_multi, parse_pairs, serialize, serialize_pairs
from ._coerce import coerce
from ._errors import LogfmtEncodeError, LogfmtError, LogfmtSyntaxError
from ._escape import quote_value
from ._stream import iter_pairs, iter_records

__version__ = "0.2.0"

__all__ = [
    "Duplicates",
    "LogfmtEncodeError",
    "LogfmtError",
    "LogfmtSyntaxError",
    "Pair",
    "coerce",
    "iter_pairs",
    "iter_records",
    "parse",
    "parse_multi",
    "parse_pairs",
    "quote_value",
    "serialize",
    "serialize_pairs",
]
