"""Errors raised by logfmtkv."""

from __future__ import annotations


class LogfmtError(ValueError):
    """Base class for every error raised by logfmtkv.

    It derives from :class:`ValueError`, so existing ``except ValueError`` handlers keep
    working.
    """


class LogfmtSyntaxError(LogfmtError):
    """A logfmt line that strict parsing rejects.

    Attributes:
        msg: What went wrong, worded like go-logfmt (for example ``unexpected '='``).
        pos: 1-based column of the problem, counted in characters.
        lineno: 1-based line number (``1`` for a single parsed line).
        line: The offending line, without its line ending.
    """

    def __init__(self, msg: str, pos: int, lineno: int = 1, line: str = "") -> None:
        self.msg = msg
        self.pos = pos
        self.lineno = lineno
        self.line = line
        super().__init__(f"logfmt syntax error at pos {pos} on line {lineno}: {msg}")

    def __reduce__(self) -> tuple[type[LogfmtSyntaxError], tuple[str, int, int, str]]:
        return (type(self), (self.msg, self.pos, self.lineno, self.line))


class LogfmtEncodeError(LogfmtError):
    """A key or value that cannot be written as logfmt.

    Raised for a key that is empty once invalid characters are removed, and in strict
    mode for any invalid key character or a value with no faithful text form.
    """
