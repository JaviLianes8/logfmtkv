"""Seeded fuzzing of the round-trip guarantee and of the never-raise promise."""

from __future__ import annotations

import random

import pytest

from logfmtkv import (
    LogfmtEncodeError,
    LogfmtSyntaxError,
    parse,
    parse_pairs,
    serialize,
    serialize_pairs,
)

SPECIAL: list[str] = [
    *' ="\\\t\n\r\x00\x01\x1f\x7fabzu0x9-.:/{}[]',
    "\u00e9",
    "\u0192",
    "\ufffd",
    "\u2028",
    "\u00a0",
    "\U0001f600",
    "null",
    "\\u00e9",
    "\\n",
]
INVALID_KEY = set(' ="\x7f\ufffd') | {chr(c) for c in range(0x21)}
ROUNDS = 400


def _char(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(SPECIAL)
    code = rng.randrange(0x110000)
    return chr(code) if not 0xD800 <= code <= 0xDFFF else "\ufffd"


def _text(rng: random.Random, low: int, high: int) -> str:
    return "".join(_char(rng) for _ in range(rng.randint(low, high)))


def _key(rng: random.Random) -> str:
    key = "".join(c for c in _text(rng, 1, 8) if not INVALID_KEY.intersection(c))
    return key or "k"


def _mapping(rng: random.Random) -> dict[str, str | bool]:
    result: dict[str, str | bool] = {}
    for _ in range(rng.randint(0, 6)):
        result[_key(rng)] = True if rng.random() < 0.15 else _text(rng, 0, 12)
    return result


@pytest.mark.parametrize("seed", range(4))
def test_serialize_then_parse_returns_the_original(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(ROUNDS):
        original = _mapping(rng)
        line = serialize(original)
        assert parse(line) == original
        assert parse(line, strict=True) == original
        assert serialize(parse(line)) == line


@pytest.mark.parametrize("seed", range(4))
def test_ordered_pairs_round_trip_with_duplicates(seed: int) -> None:
    rng = random.Random(1000 + seed)
    for _ in range(ROUNDS):
        keys = [_key(rng) for _ in range(rng.randint(1, 3))]
        pairs = [
            (rng.choice(keys), None if rng.random() < 0.2 else _text(rng, 0, 10))
            for _ in range(rng.randint(0, 6))
        ]
        line = serialize_pairs(pairs)
        assert parse_pairs(line, strict=True) == pairs


@pytest.mark.parametrize("seed", range(4))
def test_lenient_never_raises_and_canonical_output_is_strict_valid(seed: int) -> None:
    rng = random.Random(2000 + seed)
    for _ in range(ROUNDS):
        garbage = _text(rng, 0, 30)
        pairs = parse_pairs(garbage)
        parse(garbage)
        try:
            parse(garbage, strict=True)
        except LogfmtSyntaxError as error:
            assert 1 <= error.pos <= len(garbage) + 1
        try:
            line = serialize_pairs(pairs)
        except LogfmtEncodeError:
            continue
        assert len(parse_pairs(line, strict=True)) == len(pairs)
