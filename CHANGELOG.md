# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Added

- `strict=True` on every reader: accept and reject exactly what go-logfmt does, with its
  messages and positions.
- `LogfmtSyntaxError` (with `msg`, `pos`, `lineno`, `line`), `LogfmtEncodeError` and their
  base `LogfmtError`, a `ValueError`.
- `parse_pairs` and `Pair`: ordered pairs with repeated keys, telling a bare key (`None`)
  from an empty value (`""`).
- `parse(..., duplicates=...)` with the `"last"`, `"first"` and `"error"` policies, typed
  as `Duplicates`, and `parse_multi` for every value of every key.
- `iter_records` and `iter_pairs`: lazy parsing of files, standard input or any iterable
  of lines, with line numbers in errors.
- `serialize_pairs`, `quote_value`, and serialization of any Python value (numbers,
  dates, enums, bytes, exceptions, containers as JSON); `None` writes a bare key.
- `coerce`: lossless conversion of values into `int`, `float` and `bool` (a float only
  when it prints back as the same text).
- The `logfmtkv` command: `to-json`, `from-json`, `fmt` and `check`.
- Golden test vectors from go-logfmt, Heroku, Grafana Loki, logrus and Go's slog.

### Changed

- Output now matches go-logfmt byte for byte: a backslash alone no longer forces
  quoting, other control characters are written as `\u00XX` and the literal text
  `null` is quoted. The one exception is the character after U+FFFD, which logfmtkv
  always escapes.
- Unicode whitespace above U+0020 (such as U+00A0 or U+2028) no longer forces quoting,
  as in go-logfmt. Split records on `\n` only, not with `str.splitlines()`.
- Invalid key characters are removed when writing instead of producing an unparseable
  line.

### Fixed

- Tabs and other control characters now separate pairs.
- `\uXXXX` escapes are decoded, and an unknown escape keeps its backslash.
- A pair with no key (`=value`) is skipped instead of turning its value into a flag.

## [0.1.0]

- Add `parse` to read a logfmt line into a typed mapping, with a bare key yielding `True`.
- Add `serialize` to write a mapping back to a logfmt line, quoting only when needed and
  omitting `False`.
