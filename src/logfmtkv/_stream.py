"""Lazy, line-by-line parsing of logfmt streams of any size."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from ._codec import Duplicates, Pair, entries_to_dict
from ._scan import Entry, is_blank, scan


def iter_pairs(
    lines: Iterable[str], *, strict: bool = False, skip_blank: bool = True
) -> Iterator[list[Pair]]:
    """Yield the ordered pairs of every record in a stream of lines, lazily.

    ``lines`` is any iterable of lines (an open text file, ``sys.stdin``, a list) or a
    single string holding the whole text, which is split on ``\\n``. A trailing ``\\n``
    or ``\\r\\n`` is removed from each line. Records are split on ``\\n`` only, never on
    other Unicode line separators, matching go-logfmt.

    Args:
        lines: The input lines.
        strict: Parse each line in strict mode.
        skip_blank: Skip lines holding only whitespace (the default); when False they
            yield an empty record, as go-logfmt does.

    Raises:
        LogfmtSyntaxError: In strict mode, with ``lineno`` set to the 1-based line.
    """
    for _, entries in _entries_with_text(lines, strict, skip_blank):
        yield [Pair(key, value) for key, value, _ in entries]


def iter_records(
    lines: Iterable[str],
    *,
    strict: bool = False,
    duplicates: Duplicates = "last",
    skip_blank: bool = True,
) -> Iterator[dict[str, str | bool]]:
    """Yield every record of a stream of lines as a mapping, lazily.

    Each line is read like :func:`parse` (bare key -> ``True``) under the given
    ``duplicates`` policy; ``lines`` and ``skip_blank`` work as in :func:`iter_pairs`.
    Memory use stays flat however large the input is.

    Raises:
        LogfmtSyntaxError: In strict mode or with ``duplicates="error"``, with
            ``lineno`` set to the 1-based line.

    >>> list(iter_records(["a=1 b=2\\n", "\\n", "c=\\"x y\\"\\n"]))
    [{'a': '1', 'b': '2'}, {'c': 'x y'}]
    """
    for (lineno, line), entries in _entries_with_text(lines, strict, skip_blank):
        yield entries_to_dict(entries, duplicates, line, lineno)


def _entries_with_text(
    lines: Iterable[str], strict: bool, skip_blank: bool
) -> Iterator[tuple[tuple[int, str], list[Entry]]]:
    for lineno, raw in enumerate(_split(lines), start=1):
        line = _chomp(raw)
        if skip_blank and is_blank(line):
            continue
        yield (lineno, line), scan(line, strict=strict, lineno=lineno)


def _split(lines: Iterable[str]) -> Iterable[str]:
    if not isinstance(lines, str):
        return lines
    parts = lines.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _chomp(line: str) -> str:
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line
