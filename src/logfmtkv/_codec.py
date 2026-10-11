"""Parse and serialize logfmt key/value log lines."""

from __future__ import annotations

import re
from collections.abc import Mapping

_NEEDS_QUOTE = re.compile(r'[\s="\\\x00-\x1f]')
_UNESCAPE = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}


def parse(line: str) -> dict[str, str | bool]:
    """Parse one logfmt line into a mapping.

    A ``key=value`` pair yields a string value, a quoted value is unescaped, and a bare
    key with no ``=`` yields ``True``.
    """
    result: dict[str, str | bool] = {}
    i, n = 0, len(line)
    while i < n:
        while i < n and line[i] == " ":
            i += 1
        if i >= n:
            break
        start = i
        while i < n and line[i] not in " =":
            i += 1
        key = line[start:i]
        if not key:
            i += 1
            continue
        if i < n and line[i] == "=":
            value, i = _read_value(line, i + 1)
            result[key] = value
        else:
            result[key] = True
    return result


def serialize(mapping: Mapping[str, str | bool]) -> str:
    """Serialize a mapping into a logfmt line.

    ``True`` becomes a bare flag, ``False`` is omitted, and a string value is quoted only
    when it contains whitespace, a quote, an equals sign or a control character.
    """
    parts: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, bool):
            if value:
                parts.append(key)
            continue
        parts.append(f"{key}={_quote(value)}")
    return " ".join(parts)


def _read_value(line: str, i: int) -> tuple[str, int]:
    if i < len(line) and line[i] == '"':
        return _read_quoted(line, i + 1)
    start = i
    while i < len(line) and line[i] != " ":
        i += 1
    return line[start:i], i


def _read_quoted(line: str, i: int) -> tuple[str, int]:
    out: list[str] = []
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n:
            out.append(_UNESCAPE.get(line[i + 1], line[i + 1]))
            i += 2
            continue
        if c == '"':
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


def _quote(value: str) -> str:
    if not _NEEDS_QUOTE.search(value):
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'
