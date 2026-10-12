"""Quoting and escaping rules, both directions, strict and lenient."""

from __future__ import annotations

import pytest

from logfmtkv import LogfmtSyntaxError, parse, quote_value


@pytest.mark.parametrize(
    ("text", "token"),
    [
        ("plain", "plain"),
        ("", ""),
        ("a b", '"a b"'),
        ("tab\there", '"tab\\there"'),
        ("new\nline", '"new\\nline"'),
        ("cr\rx", '"cr\\rx"'),
        ('say "hi"', '"say \\"hi\\""'),
        ("C:\\tmp", "C:\\tmp"),
        ("a=b", '"a=b"'),
        ("\x01", '"\\u0001"'),
        ("\x1b[0m", '"\\u001b[0m"'),
        ("\x7f", '"\\u007f"'),
        ("\ud800", '"\\ufffd"'),
        ("null", '"null"'),
        ("nullable", "nullable"),
        ("caf\u00e9", "caf\u00e9"),
        ("\U0001f600", "\U0001f600"),
        ("\u00a0", "\u00a0"),
    ],
)
def test_quote_value(text: str, token: str) -> None:
    assert quote_value(text) == token


@pytest.mark.parametrize(
    ("body", "value"),
    [
        ('\\"', '"'),
        ("\\\\", "\\"),
        ("\\/", "/"),
        ("\\'", "'"),
        ("\\b\\f\\n\\r\\t", "\b\f\n\r\t"),
        ("\\u00e9", "\u00e9"),
        ("\\u00E9", "\u00e9"),
        ("\\ud83d\\ude00", "\U0001f600"),
        ("\\ud83dx", "\ufffdx"),
        ("\\ude00", "\ufffd"),
        ("\\ud83d\\u0041", "\ufffdA"),
    ],
)
def test_escapes_both_modes_read(body: str, value: str) -> None:
    line = f'k="{body}"'
    assert parse(line) == {"k": value}
    assert parse(line, strict=True) == {"k": value}


@pytest.mark.parametrize(
    ("body", "value"),
    [
        ("\\a\\v", "\a\v"),
        ("\\x00y", "\x00y"),
        ("\\x41", "A"),
        ("\\xe2\\x82\\xac", "\u20ac"),
        ("\\xff", "\ufffd"),
        ("\\U0001F600", "\U0001f600"),
        ("\\q", "\\q"),
        ("\\u12", "\\u12"),
        ("\\uzzzz", "\\uzzzz"),
        ("\\U0011FFFF", "\\U0011FFFF"),
        ("\\UD800DC00", "\\UD800DC00"),
        ("\\x4", "\\x4"),
        ("tail\\", "tail\\"),
    ],
)
def test_go_quote_escapes_lenient_only(body: str, value: str) -> None:
    line = f'k="{body}"' if not body.endswith("\\") else f'k="{body}'
    assert parse(line) == {"k": value}
    with pytest.raises(LogfmtSyntaxError):
        parse(line, strict=True)


def test_strict_keeps_raw_control_characters_when_no_escape_is_present() -> None:
    # go-logfmt only validates the body of a quoted value that contains an escape.
    assert parse('k="a\tb"', strict=True) == {"k": "a\tb"}
    with pytest.raises(LogfmtSyntaxError, match="invalid quoted value"):
        parse('k="a\tb\\n"', strict=True)


def test_escapes_written_by_quote_value_read_back_exactly() -> None:
    text = 'q" b\\ \n\r\t\x00\x1f\x7f end'
    assert parse("k=" + quote_value(text), strict=True) == {"k": text}
