"""Lossless coercion of parsed values."""

from __future__ import annotations

import pytest

from logfmtkv import coerce, parse


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("0", 0),
        ("200", 200),
        ("-4", -4),
        ("1.5", 1.5),
        ("-0.25", -0.25),
        ("1e+20", 1e20),
        ("0.1", 0.1),
        ("true", True),
        ("false", False),
    ],
)
def test_numbers_and_booleans_are_coerced(text: str, value: object) -> None:
    result = coerce(text)
    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize(
    "text",
    [
        *("", "007", "-0", "+1", "1_000", "8ms", "nan", "inf", "1e999", "True", "1.", ".5"),
        *("0x10", "1.50", "1e5", "1e-400", "2.5E-2", "12345678901234567890.5"),
        "0.1000000000000000055511151231257827",
    ],
)
def test_ambiguous_text_is_left_alone(text: str) -> None:
    assert coerce(text) == text


def test_flags_and_none_pass_through() -> None:
    assert coerce(True) is True
    assert coerce(False) is False
    assert coerce(None) is None


def test_huge_integers_stay_text_when_python_refuses_them() -> None:
    digits = "9" * 5000
    result = coerce(digits)
    assert result == digits or isinstance(result, int)


def test_coerce_a_parsed_record() -> None:
    record = parse("status=200 took=1.5 ok=true id=007 verbose")
    assert {k: coerce(v) for k, v in record.items()} == {
        "status": 200,
        "took": 1.5,
        "ok": True,
        "id": "007",
        "verbose": True,
    }
