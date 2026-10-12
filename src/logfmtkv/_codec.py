"""Parse and serialize logfmt key/value log lines."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal, NamedTuple

from ._encode import encode_pair
from ._errors import LogfmtSyntaxError
from ._scan import Entry, scan

Duplicates = Literal["last", "first", "error"]
_POLICIES = ("last", "first", "error")


class Pair(NamedTuple):
    """One key/value pair of a logfmt line, in line order.

    ``value`` is ``None`` for a bare key (``verbose``) and ``""`` for an explicit empty
    value (``user=``).
    """

    key: str
    value: str | None


def parse(
    line: str, *, strict: bool = False, duplicates: Duplicates = "last"
) -> dict[str, str | bool]:
    """Parse one logfmt line into a mapping.

    A ``key=value`` pair yields a string value, a quoted value is unescaped, ``key=``
    yields ``""`` and a bare key with no ``=`` yields ``True``. Insertion order follows
    the line.

    Args:
        line: One logfmt line. Line breaks inside it count as whitespace.
        strict: Reject anything go-logfmt rejects instead of reading past it.
        duplicates: ``"last"`` keeps the last value of a repeated key, ``"first"``
            the first, and ``"error"`` raises on a repeat.

    Raises:
        LogfmtSyntaxError: In strict mode on malformed input, or on a repeated key
            with ``duplicates="error"``. Lenient parsing of any string never raises.

    >>> parse('level=info msg="hello world" verbose')
    {'level': 'info', 'msg': 'hello world', 'verbose': True}
    """
    return entries_to_dict(scan(line, strict=strict), duplicates, line, 1)


def parse_pairs(line: str, *, strict: bool = False) -> list[Pair]:
    """Parse one logfmt line into ordered pairs, keeping repeated keys.

    >>> parse_pairs("a=1 flag a=")
    [Pair(key='a', value='1'), Pair(key='flag', value=None), Pair(key='a', value='')]
    """
    return [Pair(key, value) for key, value, _ in scan(line, strict=strict)]


def parse_multi(line: str, *, strict: bool = False) -> dict[str, list[str | bool]]:
    """Parse one logfmt line into a mapping of each key to all its values, in order.

    >>> parse_multi("tag=a tag=b ok")
    {'tag': ['a', 'b'], 'ok': [True]}
    """
    result: dict[str, list[str | bool]] = {}
    for key, value, _ in scan(line, strict=strict):
        result.setdefault(key, []).append(True if value is None else value)
    return result


def serialize(mapping: Mapping[str, object], *, strict: bool = False) -> str:
    """Serialize a mapping into a canonical logfmt line.

    ``True`` and ``None`` become a bare key and ``False`` is omitted. Strings are quoted
    only when needed, exactly like go-logfmt. Other values are written by their text
    form: numbers via ``str``, dates and times in ISO 8601, enums by their value, bytes
    as UTF-8, and lists, tuples, sets and mappings as compact JSON. Invalid key
    characters (whitespace, ``=``, ``"``, control characters) are removed.

    Args:
        mapping: Keys to values, written in iteration order.
        strict: Raise instead of repairing: an invalid key character, a non-string key
            or a container value raises :class:`LogfmtEncodeError`.

    Raises:
        LogfmtEncodeError: A key is empty once invalid characters are removed, or
            ``strict`` refuses a key or value.

    >>> serialize({"level": "info", "msg": "hello world", "verbose": True, "quiet": False})
    'level=info msg="hello world" verbose'
    """
    return serialize_pairs(mapping.items(), strict=strict)


def serialize_pairs(pairs: Iterable[tuple[str, object]], *, strict: bool = False) -> str:
    """Serialize ordered ``(key, value)`` pairs, repeated keys included.

    Values follow the same rules as :func:`serialize`, so the output of
    :func:`parse_pairs` (where a bare key has ``None``) writes back unchanged.

    >>> serialize_pairs([("tag", "a"), ("tag", "b c"), ("ok", None)])
    'tag=a tag="b c" ok'
    """
    parts = (encode_pair(key, value, strict) for key, value in pairs)
    return " ".join(part for part in parts if part is not None)


def entries_to_dict(
    entries: list[Entry], duplicates: Duplicates, line: str, lineno: int
) -> dict[str, str | bool]:
    """Fold scanned entries into a dict under a duplicate-key policy."""
    if duplicates not in _POLICIES:
        raise ValueError(f"duplicates must be one of {_POLICIES}, got {duplicates!r}")
    result: dict[str, str | bool] = {}
    for key, value, column in entries:
        if key in result:
            if duplicates == "first":
                continue
            if duplicates == "error":
                raise LogfmtSyntaxError(f"duplicate key {key!r}", column + 1, lineno, line)
        result[key] = True if value is None else value
    return result
