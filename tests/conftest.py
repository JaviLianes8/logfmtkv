"""Shared access to the hand-written golden fixtures (syntax probes and app-style lines)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN: dict[str, Any] = json.loads((FIXTURES / "golden.json").read_text(encoding="utf-8"))
REAL_LOG = FIXTURES / "real.log"


def as_pairs(raw: list[list[Any]]) -> list[tuple[str, str | None]]:
    """Turn fixture ``[[key, value], ...]`` lists into ``(key, value)`` tuples."""
    return [(key, value) for key, value in raw]


def as_dict(raw: list[list[Any]]) -> dict[str, str | bool]:
    """Fold fixture pairs into the mapping :func:`logfmtkv.parse` promises (last wins)."""
    result: dict[str, str | bool] = {}
    for key, value in raw:
        result[key] = True if value is None else value
    return result


def case_id(case: dict[str, Any]) -> str:
    """A short readable pytest id for a fixture case."""
    text = case.get("line", case.get("text", case.get("value", "")))
    return f"{case['source']}:{str(text)[:40]!r}"
