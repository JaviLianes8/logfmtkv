"""Quoting and unquoting of logfmt values, in strict and lenient flavours."""

from __future__ import annotations

import re

_STRICT_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "'": "'",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_LENIENT_ESCAPES = {**_STRICT_ESCAPES, "a": "\a", "v": "\v"}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_NEEDS_QUOTE = re.compile('[\\x00-\\x20="\\x7f\\ufffd\\ud800-\\udfff]')
_TO_ESCAPE = re.compile('[\\x00-\\x1f"\\\\\\x7f\\ufffd\\ud800-\\udfff]')
_NAMED = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def quote_value(text: str) -> str:
    """Return ``text`` as a logfmt value token, quoted only when needed.

    The rule is go-logfmt's: quote when the text contains a character at or below space,
    ``=``, ``"``, DEL or U+FFFD, and quote the literal text ``null`` so it is never read
    as a missing value. Inside quotes ``\\ " \\n \\r \\t`` get short escapes,
    other control characters become ``\\u00XX`` and U+FFFD or a lone surrogate becomes
    ``\\ufffd``. The empty string stays empty (``key=``).

    >>> quote_value("hello world")
    '"hello world"'
    >>> quote_value("C:\\\\tmp")
    'C:\\\\tmp'
    """
    if text != "null" and not _NEEDS_QUOTE.search(text):
        return text
    return '"' + _TO_ESCAPE.sub(_escape_char, text) + '"'


def _escape_char(match: re.Match[str]) -> str:
    char = match.group()
    named = _NAMED.get(char)
    if named is not None:
        return named
    if char < " " or char == "\x7f":
        return f"\\u{ord(char):04x}"
    return "\\ufffd"


def find_closing_quote(line: str, start: int) -> tuple[int, bool]:
    """Find the quote closing the one at ``start``.

    Returns the index of the closing quote (``-1`` when unterminated) and whether a
    backslash escape was seen on the way.
    """
    i, n, escaped = start + 1, len(line), False
    while i < n:
        char = line[i]
        if char == "\\":
            escaped = True
            i += 2
            continue
        if char == '"':
            return i, escaped
        i += 1
    return -1, escaped


def _hex(text: str, start: int, width: int) -> int:
    digits = text[start : start + width]
    if len(digits) != width or not all(c in _HEX_DIGITS for c in digits):
        return -1
    return int(digits, 16)


def _read_u4(body: str, i: int) -> tuple[str, int]:
    """Decode ``\\uXXXX`` at ``i`` (a valid escape), joining a surrogate pair."""
    code = _hex(body, i + 2, 4)
    i += 6
    if not 0xD800 <= code <= 0xDFFF:
        return chr(code), i
    low = _hex(body, i + 2, 4) if body.startswith("\\u", i) else -1
    if code < 0xDC00 and 0xDC00 <= low <= 0xDFFF:
        return chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)), i + 6
    return "\ufffd", i


def decode_strict(body: str) -> str | None:
    """Unescape a quoted body exactly as go-logfmt does, or return ``None`` if invalid."""
    out: list[str] = []
    i, n = 0, len(body)
    while i < n:
        char = body[i]
        if char == "\\":
            esc = body[i + 1] if i + 1 < n else ""
            if esc and esc in _STRICT_ESCAPES:
                out.append(_STRICT_ESCAPES[esc])
                i += 2
            elif esc == "u" and _hex(body, i + 2, 4) >= 0:
                text, i = _read_u4(body, i)
                out.append(text)
            else:
                return None
            continue
        if char == '"' or char < " ":
            return None
        out.append("\ufffd" if "\ud800" <= char <= "\udfff" else char)
        i += 1
    return "".join(out)


def decode_lenient(body: str) -> str:
    """Unescape a quoted body, also reading Go ``%q`` escapes, never failing.

    Beyond the strict set this reads ``\\a \\v \\xHH \\UXXXXXXXX``; runs of ``\\xHH``
    are decoded as UTF-8 bytes. An unknown or malformed escape is kept verbatim.
    """
    if "\\" not in body:
        return body
    out: list[str] = []
    i, n = 0, len(body)
    while i < n:
        char = body[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        esc = body[i + 1] if i + 1 < n else ""
        if esc and esc in _LENIENT_ESCAPES:
            out.append(_LENIENT_ESCAPES[esc])
            i += 2
        elif esc == "u" and _hex(body, i + 2, 4) >= 0:
            text, i = _read_u4(body, i)
            out.append(text)
        elif esc == "U" and _valid_scalar(_hex(body, i + 2, 8)):
            out.append(chr(_hex(body, i + 2, 8)))
            i += 10
        elif esc == "x" and _hex(body, i + 2, 2) >= 0:
            text, i = _read_bytes(body, i)
            out.append(text)
        else:
            out.append("\\" + esc)
            i += 1 + len(esc)
    return "".join(out)


def _valid_scalar(code: int) -> bool:
    return 0 <= code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF


def _read_bytes(body: str, i: int) -> tuple[str, int]:
    raw = bytearray()
    while body.startswith("\\x", i) and (byte := _hex(body, i + 2, 2)) >= 0:
        raw.append(byte)
        i += 4
    return raw.decode("utf-8", "replace"), i
