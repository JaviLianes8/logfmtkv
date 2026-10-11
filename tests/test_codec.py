from __future__ import annotations

from logfmtkv import parse, serialize


def test_parse_simple_pairs() -> None:
    assert parse("level=info count=3") == {"level": "info", "count": "3"}


def test_parse_quoted_value_with_spaces() -> None:
    assert parse('msg="hello world"') == {"msg": "hello world"}


def test_parse_bare_key_is_true() -> None:
    assert parse("verbose level=info") == {"verbose": True, "level": "info"}


def test_parse_unescapes_quote_and_backslash() -> None:
    assert parse(r'msg="a \"b\" \\c"') == {"msg": 'a "b" \\c'}


def test_parse_value_with_equals_sign() -> None:
    assert parse("expr=a=b") == {"expr": "a=b"}


def test_parse_empty_line_is_empty_mapping() -> None:
    assert parse("") == {}
    assert parse("   ") == {}


def test_serialize_quotes_only_when_needed() -> None:
    assert serialize({"level": "info", "msg": "hello world"}) == 'level=info msg="hello world"'


def test_serialize_true_is_bare_flag_and_false_is_omitted() -> None:
    assert serialize({"verbose": True, "quiet": False, "level": "info"}) == "verbose level=info"


def test_serialize_escapes_quote_and_backslash() -> None:
    assert serialize({"msg": 'a "b" \\c'}) == r'msg="a \"b\" \\c"'


def test_round_trip_parse_of_serialize() -> None:
    sample: dict[str, str | bool] = {
        "level": "info",
        "msg": "hello world",
        "expr": "a=b",
        "path": "c:\\tmp",
        "verbose": True,
    }
    assert parse(serialize(sample)) == sample
