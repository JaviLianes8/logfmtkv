"""The logfmt tokenizer: one line in, ordered ``(key, value, column)`` entries out."""

from __future__ import annotations

from ._errors import LogfmtSyntaxError
from ._escape import decode_lenient, decode_strict, find_closing_quote

# key, value (None for a bare key), 0-based column where the key starts
Entry = tuple[str, str | None, int]


def scan(line: str, *, strict: bool = False, lineno: int = 1) -> list[Entry]:
    """Tokenize one line. Lenient scanning never raises; strict follows go-logfmt."""
    if strict:
        return _scan_strict(line, lineno)
    return _scan_lenient(line)


def is_blank(line: str) -> bool:
    """Return True when the line holds only whitespace and control characters."""
    return all(char <= " " for char in line)


def invalid_key(key: str) -> bool:
    """Return True for a key go-logfmt rejects: one carrying U+FFFD or a lone surrogate."""
    return any(char == "\ufffd" or "\ud800" <= char <= "\udfff" for char in key)


def _scan_lenient(line: str) -> list[Entry]:
    out: list[Entry] = []
    i, n = 0, len(line)
    while True:
        while i < n and line[i] <= " ":
            i += 1
        if i >= n:
            return out
        start = i
        if line[i] == '"':
            key, i = _lenient_quoted(line, i)
        else:
            while i < n and line[i] > " " and line[i] != "=":
                i += 1
            key = line[start:i]
        value: str | None = None
        if i < n and line[i] == "=":
            value, i = _lenient_value(line, i + 1)
        if key:
            out.append((key, value, start))


def _lenient_quoted(line: str, i: int) -> tuple[str, int]:
    close, _ = find_closing_quote(line, i)
    if close < 0:
        return decode_lenient(line[i + 1 :]), len(line)
    return decode_lenient(line[i + 1 : close]), close + 1


def _lenient_value(line: str, i: int) -> tuple[str, int]:
    n = len(line)
    if i >= n or line[i] <= " ":
        return "", i
    if line[i] == '"':
        return _lenient_quoted(line, i)
    start = i
    while i < n and line[i] > " ":
        i += 1
    return line[start:i], i


def _scan_strict(line: str, lineno: int) -> list[Entry]:
    out: list[Entry] = []
    i, n = 0, len(line)

    def fail(msg: str, pos: int) -> LogfmtSyntaxError:
        return LogfmtSyntaxError(msg, pos, lineno, line)

    while True:
        while i < n and line[i] <= " ":
            i += 1
        if i >= n:
            return out
        start = i
        while i < n and line[i] != "=" and line[i] > " ":
            if line[i] == '"':
                raise fail("unexpected '\"'", i + 1)
            i += 1
        key = line[start:i]
        if invalid_key(key):
            raise fail("invalid key", i + 1)
        if i >= n or line[i] != "=":
            out.append((key, None, start))
            continue
        if not key:
            raise fail("unexpected '='", i + 1)
        i += 1
        if i >= n or line[i] <= " ":
            out.append((key, "", start))
            continue
        if line[i] == '"':
            close, escaped = find_closing_quote(line, i)
            if close < 0:
                raise fail("unterminated quoted value", n + 1)
            value = decode_strict(line[i + 1 : close]) if escaped else line[i + 1 : close]
            if value is None:
                raise fail("invalid quoted value", close + 2)
            out.append((key, value, start))
            i = close + 1
            continue
        value_start = i
        while i < n and line[i] > " ":
            if line[i] in '="':
                raise fail(f"unexpected {line[i]!r}", i + 1)
            i += 1
        out.append((key, line[value_start:i], start))
