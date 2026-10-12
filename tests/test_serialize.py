"""Serialization of keys, flags and arbitrary Python values."""

from __future__ import annotations

import datetime
import decimal
import enum
import uuid

import pytest

from logfmtkv import LogfmtEncodeError, parse, serialize, serialize_pairs


class Color(enum.Enum):
    RED = "red"


class Level(enum.IntEnum):
    WARN = 30


class Broken:
    def __str__(self) -> str:
        raise RuntimeError("boom")


UTC = datetime.timezone.utc


@pytest.mark.parametrize(
    ("value", "token"),
    [
        (3, "3"),
        (-4, "-4"),
        (1.5, "1.5"),
        (decimal.Decimal("1.10"), "1.10"),
        (datetime.datetime(2009, 11, 10, 23, 0, tzinfo=UTC), "2009-11-10T23:00:00+00:00"),
        (datetime.date(2026, 10, 12), "2026-10-12"),
        (Color.RED, "red"),
        (Level.WARN, "30"),
        (b"caf\xc3\xa9", "caf\u00e9"),
        (b"\xbd", '"\\ufffd"'),
        (ValueError("bad thing"), '"bad thing"'),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        ([1, "a b"], '"[1,\\"a b\\"]"'),
        ({"x": 1}, '"{\\"x\\":1}"'),
        ((1, 2), "[1,2]"),
        ({7}, "[7]"),
        ([Color.RED, datetime.date(2026, 1, 2)], '"[\\"red\\",\\"2026-01-02\\"]"'),
        (Broken(), '"<unprintable Broken: RuntimeError>"'),
    ],
)
def test_values_have_a_safe_text_form(value: object, token: str) -> None:
    assert serialize({"k": value}) == f"k={token}"


def test_flags_none_and_false() -> None:
    assert serialize({"a": True, "b": None, "c": False, "d": "x"}) == "a b d=x"
    assert parse(serialize({"a": True})) == {"a": True}


def test_invalid_key_characters_are_stripped() -> None:
    assert serialize({"a b": 1, 'q"=x': 2, "t\tab": 3, "del\x7f": 4}) == "ab=1 qx=2 tab=3 del=4"


@pytest.mark.parametrize("key", ["", " ", "==", '"', "\ufffd"])
def test_key_with_nothing_left_raises(key: str) -> None:
    with pytest.raises(LogfmtEncodeError):
        serialize({key: "v"})


@pytest.mark.parametrize("key", ["a b", "a=b", 'a"', "a\x00"])
def test_strict_refuses_invalid_key_characters(key: str) -> None:
    with pytest.raises(LogfmtEncodeError, match="invalid character"):
        serialize({key: "v"}, strict=True)


def test_strict_refuses_containers_and_unprintable_values() -> None:
    with pytest.raises(LogfmtEncodeError, match="unsupported value type list"):
        serialize({"k": [1]}, strict=True)
    with pytest.raises(LogfmtEncodeError, match="no text form"):
        serialize({"k": Broken()}, strict=True)


def test_non_string_keys() -> None:
    assert serialize_pairs([(1, "v")]) == "1=v"  # type: ignore[list-item]
    with pytest.raises(LogfmtEncodeError, match="key must be a str"):
        serialize_pairs([(1, "v")], strict=True)  # type: ignore[list-item]


def test_circular_container_falls_back_to_its_repr() -> None:
    loop: list[object] = []
    loop.append(loop)
    assert serialize({"k": loop}) == "k=[[...]]"


def test_serialize_pairs_keeps_order_and_duplicates() -> None:
    assert serialize_pairs([("b", 1), ("a", "x y"), ("b", None), ("c", False)]) == 'b=1 a="x y" b'


def test_empty_inputs() -> None:
    assert serialize({}) == ""
    assert serialize_pairs([]) == ""
