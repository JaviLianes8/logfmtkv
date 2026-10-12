"""The ``logfmtkv`` command line tool."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from . import __version__
from ._cli_cmds import run
from ._cli_filters import CliError

_EPILOG = """\
examples:
  echo 'level=info msg="hello world" took=3ms' | logfmtkv to-json
  logfmtkv to-json app.log --where level=error --select time,msg
  logfmtkv to-json app.log --coerce --duplicates list
  echo '{"level": "info", "msg": "hi there", "ok": true}' | logfmtkv from-json
  logfmtkv fmt app.log --where user_id=1234 --select msg,status
  logfmtkv check app.log

FILE defaults to standard input; '-' also means standard input. Input is read as
UTF-8, one record per line. Errors go to standard error and exit with status 1.
"""

_FILTER_HELP = "keep records where KEY equals VALUE, or where KEY is present (repeatable)"
_SELECT_HELP = "comma-separated keys to keep, written in this order"


class _Parser(argparse.ArgumentParser):
    """An argument parser that reports usage errors with exit status 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``logfmtkv`` command."""
    parser = _Parser(
        prog="logfmtkv",
        description="Convert, filter, canonicalise and validate logfmt (key=value) lines.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    to_json = _add(sub, "to-json", "convert logfmt lines to JSON lines")
    _add_reading(to_json)
    to_json.add_argument(
        "--duplicates",
        choices=["last", "first", "error", "list"],
        default="last",
        help="policy for a repeated key; 'list' writes every value in a JSON array",
    )
    to_json.add_argument(
        "--coerce", action="store_true", help="write integers, floats and true/false as JSON"
    )

    from_json = _add(sub, "from-json", "convert JSON lines (one object each) to logfmt")
    from_json.add_argument("--strict", action="store_true", help="reject invalid keys")
    _add_filters(from_json)

    fmt = _add(sub, "fmt", "rewrite logfmt lines in canonical form")
    _add_reading(fmt)

    _add(sub, "check", "validate logfmt lines strictly; report file:line:col per error")
    return parser


def _add(sub: argparse._SubParsersAction[_Parser], name: str, text: str) -> argparse.ArgumentParser:
    command = sub.add_parser(name, help=text, description=text)
    command.add_argument("file", nargs="?", default="-", metavar="FILE", help="input file")
    return command


def _add_reading(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--strict", action="store_true", help="fail on input go-logfmt would reject"
    )
    _add_filters(command)


def _add_filters(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "-w", "--where", action="append", default=[], metavar="KEY[=VALUE]", help=_FILTER_HELP
    )
    command.add_argument("-s", "--select", metavar="KEYS", help=_SELECT_HELP)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except CliError as exc:
        print(f"logfmtkv: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
