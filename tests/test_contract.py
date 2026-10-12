"""The complete promise of every public name, pinned on real golden log lines."""

from __future__ import annotations

import doctest
import importlib
import importlib.resources
import typing

import pytest
from conftest import GOLDEN, REAL_LOG, as_dict, as_pairs

import logfmtkv
from logfmtkv import (
    LogfmtEncodeError,
    LogfmtError,
    LogfmtSyntaxError,
    Pair,
    coerce,
    iter_pairs,
    iter_records,
    parse,
    parse_multi,
    parse_pairs,
    quote_value,
    serialize,
    serialize_pairs,
)

PUBLIC_API: list[str] = [
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
REAL = [c for c in GOLDEN["parse"] if c["strict"] == "same" and c["source"] != "go-logfmt"]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(logfmtkv.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves_and_is_documented() -> None:
    for name in logfmtkv.__all__:
        obj = getattr(logfmtkv, name)
        if name != "Duplicates":
            assert obj.__doc__, name


def test_version_is_a_three_part_string() -> None:
    parts = logfmtkv.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("logfmtkv").joinpath("py.typed").is_file()


def test_docstring_examples_run() -> None:
    modules = ["_codec", "_coerce", "_escape", "_stream"]
    for module in modules:
        result = doctest.testmod(importlib.import_module(f"logfmtkv.{module}"))
        assert result.failed == 0 and result.attempted > 0, module


def test_duplicates_names_the_three_policies() -> None:
    assert typing.get_args(logfmtkv.Duplicates) == ("last", "first", "error")


def test_error_hierarchy_and_encode_errors() -> None:
    assert issubclass(LogfmtError, ValueError)
    assert issubclass(LogfmtSyntaxError, LogfmtError)
    assert issubclass(LogfmtEncodeError, LogfmtError)
    with pytest.raises(LogfmtEncodeError):
        serialize({"= =": "v"})
    with pytest.raises(LogfmtEncodeError):
        serialize_pairs([("bad key", "v")], strict=True)


def test_real_log_file_reads_through_every_reader() -> None:
    expected = [as_dict(c["pairs"]) for c in REAL]
    lines = REAL_LOG.read_text(encoding="utf-8").splitlines(keepends=True)
    assert [c["line"] for c in REAL] == [line.rstrip("\n") for line in lines]
    for strict in (False, True):
        assert list(iter_records(lines, strict=strict)) == expected
        assert list(iter_pairs(lines, strict=strict)) == [as_pairs(c["pairs"]) for c in REAL]
        assert [parse(line, strict=strict) for line in lines] == expected


@pytest.mark.parametrize("case", REAL, ids=lambda c: c["line"][:30])
def test_promise_on_each_real_line(case: dict[str, typing.Any]) -> None:
    line, pairs = case["line"], as_pairs(case["pairs"])
    got = parse_pairs(line)
    assert got == pairs
    assert all(isinstance(pair, Pair) for pair in got)
    assert parse(line) == as_dict(case["pairs"])

    first: dict[str, str | bool] = {}
    multi: dict[str, list[str | bool]] = {}
    for key, value in pairs:
        first.setdefault(key, True if value is None else value)
        multi.setdefault(key, []).append(True if value is None else value)
    assert parse(line, duplicates="first") == first
    assert parse_multi(line) == multi
    if len(multi) == len(pairs):
        assert parse(line, duplicates="error") == first
    else:
        with pytest.raises(LogfmtSyntaxError, match="duplicate key"):
            parse(line, duplicates="error")

    canonical = serialize_pairs(pairs)
    assert parse_pairs(canonical, strict=True) == pairs
    assert serialize_pairs(parse_pairs(canonical)) == canonical
    assert parse(serialize(parse(line))) == parse(line)

    for _, value in pairs:
        if value is not None:
            assert parse_pairs("k=" + quote_value(value), strict=True) == [("k", value)]
            _assert_coerce_is_lossless(value)


def _assert_coerce_is_lossless(text: str) -> None:
    result = coerce(text)
    if isinstance(result, bool):
        assert text in ("true", "false")
    elif isinstance(result, int):
        assert str(result) == text
    elif isinstance(result, float):
        assert float(text) == result
    else:
        assert result == text
