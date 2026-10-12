"""Real log lines from go-logfmt, Heroku, Loki, logrus and slog, asserted pair by pair."""

from __future__ import annotations

from typing import Any

import pytest
from conftest import GOLDEN, as_dict, as_pairs, case_id

from logfmtkv import (
    LogfmtSyntaxError,
    iter_pairs,
    parse,
    parse_pairs,
    serialize,
    serialize_pairs,
)

PARSE = GOLDEN["parse"]
STRICT_SAME = [c for c in PARSE if c["strict"] == "same"]
STRICT_FAIL = [c for c in PARSE if c["strict"] != "same"]


@pytest.mark.parametrize("case", PARSE, ids=case_id)
def test_lenient_pairs_match_the_reference(case: dict[str, Any]) -> None:
    assert parse_pairs(case["line"]) == as_pairs(case["pairs"])
    assert parse(case["line"]) == as_dict(case["pairs"])


@pytest.mark.parametrize("case", STRICT_SAME, ids=case_id)
def test_strict_accepts_what_go_logfmt_accepts(case: dict[str, Any]) -> None:
    assert parse_pairs(case["line"], strict=True) == as_pairs(case["pairs"])


@pytest.mark.parametrize("case", STRICT_FAIL, ids=case_id)
def test_strict_rejects_with_the_reference_message(case: dict[str, Any]) -> None:
    with pytest.raises(LogfmtSyntaxError) as info:
        parse(case["line"], strict=True)
    assert (info.value.msg, info.value.pos) == (case["strict"]["msg"], case["strict"]["pos"])


@pytest.mark.parametrize("case", GOLDEN["strict_errors"], ids=case_id)
def test_go_logfmt_syntax_errors(case: dict[str, Any]) -> None:
    with pytest.raises(LogfmtSyntaxError) as info:
        list(iter_pairs(case["text"], strict=True))
    error = info.value
    assert (error.msg, error.pos, error.lineno) == (case["msg"], case["pos"], case["lineno"])
    assert error.line == case["text"].split("\n")[case["lineno"] - 1]
    if case["pos"] == case["go_pos"]:
        assert str(error) == (
            f"logfmt syntax error at pos {case['go_pos']} on line {case['lineno']}: {case['msg']}"
        )


@pytest.mark.parametrize("case", GOLDEN["strict_errors"], ids=case_id)
def test_lenient_reads_past_what_strict_rejects(case: dict[str, Any]) -> None:
    failing = case["text"].split("\n")[case["lineno"] - 1]
    assert parse_pairs(failing) == as_pairs(case["lenient_pairs"])


@pytest.mark.parametrize("case", GOLDEN["streams"], ids=case_id)
def test_multi_record_streams(case: dict[str, Any]) -> None:
    for strict in (False, True):
        got = list(iter_pairs(case["text"], strict=strict, skip_blank=False))
        assert got == [as_pairs(record) for record in case["records"]]


@pytest.mark.parametrize("case", GOLDEN["canonical"], ids=case_id)
def test_decode_then_encode_is_canonical(case: dict[str, Any]) -> None:
    assert serialize_pairs(parse_pairs(case["line"], strict=True)) == case["want"]
    go_style = [(k, "" if v is None else v) for k, v in parse_pairs(case["line"])]
    assert serialize_pairs(go_style) == case["go_want"]


@pytest.mark.parametrize("case", GOLDEN["encode"], ids=case_id)
def test_encoder_matches_go_logfmt(case: dict[str, Any]) -> None:
    assert serialize({case["key"]: case["value"]}) == case["want"]
    assert serialize_pairs([(case["key"], case["value"])]) == case["want"]


@pytest.mark.parametrize("case", STRICT_SAME, ids=case_id)
def test_real_lines_survive_a_round_trip(case: dict[str, Any]) -> None:
    pairs = parse_pairs(case["line"])
    line = serialize_pairs(pairs)
    assert parse_pairs(line, strict=True) == pairs
    assert serialize_pairs(parse_pairs(line)) == line
