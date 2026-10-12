"""Record filtering (``--where``) and field selection (``--select``) for the CLI."""

from __future__ import annotations

from typing import Any

from ._encode import value_text

Filter = tuple[str, str | None]


class CliError(Exception):
    """A failure reported on standard error with exit status 1."""


def matches(pairs: list[tuple[str, object]], filters: list[Filter]) -> bool:
    """True when every filter is met by at least one pair of the record."""
    return all(any(_hit(k, v, f) for k, v in pairs) for f in filters)


def _hit(key: str, value: object, wanted: Filter) -> bool:
    """``KEY`` matches any value; ``KEY=VALUE`` compares the value's text.

    A JSON boolean compares as ``true`` or ``false``; a bare logfmt key has no text and
    only matches ``KEY``.
    """
    if key != wanted[0]:
        return False
    if wanted[1] is None:
        return True
    if value is None:
        return False
    if isinstance(value, bool):
        return wanted[1] == ("true" if value else "false")
    return value_text(value, False, key) == wanted[1]


def parse_filters(raw: list[str]) -> list[Filter]:
    """Turn ``--where`` arguments into ``(key, value or None)`` filters."""
    result: list[Filter] = []
    for item in raw:
        key, sep, value = item.partition("=")
        if not key:
            raise CliError(f"invalid --where {item!r}: expected KEY or KEY=VALUE")
        result.append((key, value if sep else None))
    return result


def parse_keys(raw: str | None) -> list[str] | None:
    """Turn a ``--select`` list into unique keys, in the order given."""
    if raw is None:
        return None
    return list(dict.fromkeys(key for key in (part.strip() for part in raw.split(",")) if key))


def select(record: dict[str, Any], keys: list[str] | None) -> dict[str, Any]:
    """Keep only the selected keys of a mapping, in selection order."""
    return record if keys is None else {k: record[k] for k in keys if k in record}


def select_pairs(
    pairs: list[tuple[str, str | None]], keys: list[str] | None
) -> list[tuple[str, str | None]]:
    """Keep only the selected keys of ordered pairs, grouped in selection order."""
    if keys is None:
        return pairs
    return [pair for key in keys for pair in pairs if pair[0] == key]
