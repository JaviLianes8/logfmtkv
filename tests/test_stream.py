"""Streaming, duplicate policies, ordered pairs and error positions."""

from __future__ import annotations

import io
import pickle
from collections.abc import Iterator

import pytest
from conftest import REAL_LOG

from logfmtkv import (
    LogfmtError,
    LogfmtSyntaxError,
    Pair,
    iter_pairs,
    iter_records,
    parse,
    parse_multi,
    parse_pairs,
)


def test_iter_records_reads_an_open_file_lazily() -> None:
    with REAL_LOG.open(encoding="utf-8", newline="\n") as handle:
        records = iter_records(handle, strict=True)
        assert isinstance(records, Iterator)
        first = next(records)
        assert first["at"] == "info" and first["bytes"] == "1653"
        assert sum(1 for _ in records) == 15


def test_crlf_and_blank_lines() -> None:
    stream = io.StringIO("a=1\r\n\r\n  \n b=2\r\n", newline="")
    assert list(iter_records(stream)) == [{"a": "1"}, {"b": "2"}]
    assert list(iter_records(["a=1\r\n", "\n"], skip_blank=False)) == [{"a": "1"}, {}]


def test_a_whole_text_string_is_split_on_newlines_only() -> None:
    assert list(iter_records("a=1\nb=x\u2028y\n")) == [{"a": "1"}, {"b": "x\u2028y"}]


def test_strict_stream_errors_carry_the_line_number() -> None:
    with pytest.raises(LogfmtSyntaxError) as info:
        list(iter_records(["a=1\n", "\n", "b==2\n"], strict=True))
    assert (info.value.lineno, info.value.pos, info.value.line) == (3, 3, "b==2")


def test_duplicate_policies() -> None:
    line = "a=1 b=2 a=3 a"
    assert parse(line) == {"a": True, "b": "2"}
    assert parse(line, duplicates="first") == {"a": "1", "b": "2"}
    assert parse_multi(line) == {"a": ["1", "3", True], "b": ["2"]}
    with pytest.raises(LogfmtSyntaxError, match="duplicate key 'a'") as info:
        parse(line, duplicates="error")
    assert info.value.pos == 9
    with pytest.raises(LogfmtSyntaxError) as info:
        list(iter_records(["x=1\n", "a=1 a=2\n"], duplicates="error"))
    assert (info.value.lineno, info.value.pos) == (2, 5)


def test_unknown_duplicate_policy_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="duplicates must be one of"):
        parse("a=1", duplicates="list")  # type: ignore[arg-type]


def test_pairs_tell_bare_keys_from_empty_values() -> None:
    assert parse_pairs('flag empty= quoted=""') == [
        Pair("flag", None),
        Pair("empty", ""),
        Pair("quoted", ""),
    ]
    assert list(iter_pairs(["a=1 a\n"])) == [[Pair("a", "1"), Pair("a", None)]]


def test_whitespace_and_control_bytes_separate_pairs() -> None:
    assert parse("a=1\tb=2\x1ec=3\nd=4") == {"a": "1", "b": "2", "c": "3", "d": "4"}


def test_errors_are_value_errors_that_pickle() -> None:
    error = LogfmtSyntaxError("unexpected '='", 3, 7, "a==")
    assert isinstance(error, LogfmtError) and isinstance(error, ValueError)
    clone = pickle.loads(pickle.dumps(error))
    assert (clone.msg, clone.pos, clone.lineno, clone.line) == ("unexpected '='", 3, 7, "a==")
    assert str(clone) == "logfmt syntax error at pos 3 on line 7: unexpected '='"
