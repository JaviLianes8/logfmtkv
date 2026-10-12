"""The work behind each ``logfmtkv`` subcommand."""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import IO, Any, cast

from ._cli_filters import CliError, Filter, matches, parse_filters, parse_keys, select, select_pairs
from ._codec import Duplicates, entries_to_dict, serialize_pairs
from ._coerce import coerce
from ._encode import encode_key
from ._errors import LogfmtEncodeError, LogfmtSyntaxError
from ._scan import Entry, is_blank, scan


def run(args: argparse.Namespace) -> int:
    """Dispatch to the chosen subcommand and return the exit status."""
    out = _stdout()
    check = args.command == "check"
    filters = [] if check else parse_filters(args.where)
    keys = None if check else parse_keys(args.select)
    with _open(args.file) as stream:
        name = "<stdin>" if args.file == "-" else args.file
        lines = _numbered(stream)
        if check:
            return _check(lines, name, out)
        if args.command == "from-json":
            return _from_json(lines, name, out, filters, keys, args.strict)
        for lineno, entries in _scanned(lines, name, args.strict):
            if not matches([(k, v) for k, v, _ in entries], filters):
                continue
            if args.command == "fmt":
                pairs = [(k, v) for k, v, _ in entries if args.strict or _writable(k)]
                try:
                    out.write(serialize_pairs(select_pairs(pairs, keys)) + "\n")
                except LogfmtEncodeError as exc:
                    raise CliError(f"{name}:{lineno}: {exc}") from exc
            else:
                record = _to_record(entries, args.duplicates, name, lineno, args.coerce)
                out.write(json.dumps(select(record, keys), ensure_ascii=False) + "\n")
    out.flush()
    return 0


def _to_record(
    entries: list[Entry], policy: str, name: str, lineno: int, coerced: bool
) -> dict[str, Any]:
    if policy == "list":
        multi: dict[str, list[Any]] = {}
        for key, value, _ in entries:
            multi.setdefault(key, []).append(True if value is None else value)
        if coerced:
            return {k: [coerce(v) for v in vs] for k, vs in multi.items()}
        return dict(multi)
    try:
        record = entries_to_dict(entries, cast(Duplicates, policy), "", lineno)
    except LogfmtSyntaxError as exc:
        raise CliError(f"{name}:{exc.lineno}:{exc.pos}: {exc.msg}") from exc
    return {k: coerce(v) for k, v in record.items()} if coerced else dict(record)


def _from_json(
    lines: Iterator[tuple[int, str]],
    name: str,
    out: IO[str],
    filters: list[Filter],
    keys: list[str] | None,
    strict: bool,
) -> int:
    for lineno, line in lines:
        if is_blank(line):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CliError(f"{name}:{lineno}:{exc.colno}: invalid JSON: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise CliError(f"{name}:{lineno}: expected a JSON object per line")
        if not matches(list(record.items()), filters):
            continue
        try:
            out.write(serialize_pairs(select(record, keys).items(), strict=strict) + "\n")
        except LogfmtEncodeError as exc:
            raise CliError(f"{name}:{lineno}: {exc}") from exc
    out.flush()
    return 0


def _check(lines: Iterator[tuple[int, str]], name: str, out: IO[str]) -> int:
    records, failures = 0, 0
    for lineno, line in lines:
        if is_blank(line):
            continue
        records += 1
        try:
            scan(line, strict=True, lineno=lineno)
        except LogfmtSyntaxError as exc:
            failures += 1
            print(f"{name}:{exc.lineno}:{exc.pos}: {exc.msg}", file=sys.stderr)
    if failures:
        print(f"logfmtkv: {failures} of {records} records invalid", file=sys.stderr)
        return 1
    out.write(f"{name}: {records} records ok\n")
    out.flush()
    return 0


def _scanned(
    lines: Iterator[tuple[int, str]], name: str, strict: bool
) -> Iterator[tuple[int, list[Entry]]]:
    for lineno, line in lines:
        if is_blank(line):
            continue
        try:
            yield lineno, scan(line, strict=strict, lineno=lineno)
        except LogfmtSyntaxError as exc:
            raise CliError(f"{name}:{exc.lineno}:{exc.pos}: {exc.msg}") from exc


def _numbered(stream: IO[str]) -> Iterator[tuple[int, str]]:
    for lineno, raw in enumerate(stream, start=1):
        yield lineno, raw.rstrip("\n").removesuffix("\r")


def _writable(key: str) -> bool:
    """Lenient fmt drops a pair whose key has no character logfmt can write."""
    try:
        encode_key(key, False)
    except LogfmtEncodeError:
        return False
    return True


@contextmanager
def _open(path: str) -> Iterator[IO[str]]:
    if path == "-":
        with _decoded(sys.stdin.buffer, "<stdin>") as stdin:
            yield stdin
        return
    try:
        # Opened outside ``with`` so only the open itself maps OSError to CliError.
        raw = open(path, "rb")  # noqa: SIM115
    except OSError as exc:
        raise CliError(f"{path}: {exc.strerror or exc}") from exc
    with raw, _decoded(raw, path) as stream:
        yield stream


@contextmanager
def _decoded(raw: IO[bytes], name: str) -> Iterator[IO[str]]:
    """Read UTF-8 (an optional BOM is dropped); refuse UTF-16 instead of garbling it."""
    peek = getattr(raw, "peek", None)
    head = peek(4)[:4] if peek is not None else b""
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise CliError(f"{name}: UTF-16 input is not supported; convert it to UTF-8")
    stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="\n")
    try:
        yield stream
    finally:
        with suppress(ValueError, OSError):
            stream.detach()


def _stdout() -> IO[str]:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    return sys.stdout
