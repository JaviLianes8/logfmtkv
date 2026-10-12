# logfmtkv

Typed, zero-dependency logfmt codec: parse and serialize key=value log lines in both
directions, byte-compatible with go-logfmt, with a strict mode, streaming over large
files and a command line tool.

## Install

```
pip install logfmtkv
```

## Usage

```python
from logfmtkv import parse, serialize

parse('level=info msg="hello world" verbose')
# {'level': 'info', 'msg': 'hello world', 'verbose': True}

serialize({"level": "info", "msg": "hello world", "verbose": True, "quiet": False})
# 'level=info msg="hello world" verbose'
```

A bare key with no value parses to `True`. On the way back, `True` (and `None`) becomes a
bare key and `False` is dropped.

## Guide

### The format

A logfmt line is a run of `key=value` pairs separated by whitespace:

```
time="2015-03-26T01:27:38-04:00" level=warning msg="The group's number increased tremendously!" number=122 omg=true
```

- A key is any run of characters other than whitespace, `=` and `"`.
- A value is either bare (no whitespace, `=` or `"`) or double-quoted.
- `key=` is an empty value; `key` alone is a bare key (a flag).
- Any character at or below space separates pairs: spaces, tabs, control bytes.

### Reading

| Function | Returns | Repeated keys |
|---|---|---|
| `parse(line)` | `dict[str, str \| bool]` | last wins (or `duplicates="first"` / `"error"`) |
| `parse_pairs(line)` | `list[Pair]` in line order | all kept |
| `parse_multi(line)` | `dict[str, list[str \| bool]]` | all kept, per key |
| `iter_records(lines)` | an iterator of dicts | as `parse` |
| `iter_pairs(lines)` | an iterator of `list[Pair]` | all kept |

`Pair(key, value)` tells a bare key (`value is None`) from an empty value (`value == ""`):

```python
from logfmtkv import parse_multi, parse_pairs

parse_pairs("tag=a flag user= tag=b")
# [Pair(key='tag', value='a'), Pair(key='flag', value=None),
#  Pair(key='user', value=''), Pair(key='tag', value='b')]

parse_multi("tag=a tag=b")
# {'tag': ['a', 'b']}
```

### Streaming large files

`iter_records` and `iter_pairs` take any iterable of lines (an open file, `sys.stdin`, a
list) or one string holding the whole text. They are lazy, so memory stays flat, and
they strip `\n` and `\r\n`. Records are split on `\n` only.

```python
from logfmtkv import iter_records

with open("app.log", encoding="utf-8", newline="\n") as handle:
    errors = [r for r in iter_records(handle) if r.get("level") == "error"]
```

### Strict and lenient

Every reader is lenient by default and takes `strict=True`.

- **Lenient** never raises. It reads past malformed pairs, keeps `=` and `"` found inside
  bare values, accepts slog's quoted keys and the Go `strconv.Quote` escapes that logrus
  and slog write (`\a \v \xHH \UXXXXXXXX`), keeps an unknown escape verbatim and lets an
  unterminated quote run to the end of the line. A pair with no key (`=value`) or an
  empty key (`""=v`) is skipped.
- **Strict** accepts and rejects exactly what go-logfmt does, with the same messages:

```python
from logfmtkv import LogfmtSyntaxError, parse

try:
    parse('k=b"ar', strict=True)
except LogfmtSyntaxError as error:
    print(error)  # logfmt syntax error at pos 4 on line 1: unexpected '"'
    error.msg, error.pos, error.lineno, error.line  # ("unexpected '\"'", 4, 1, 'k=b"ar')
```

Positions are 1-based character columns (go-logfmt counts bytes, which is the same for
ASCII). In `iter_records` and `iter_pairs`, `lineno` is the line in the stream.

### Escapes

Inside quotes both modes read `\" \\ \/ \' \b \f \n \r \t` and `\uXXXX`, joining UTF-16
surrogate pairs (a lone surrogate becomes U+FFFD). In strict mode, raw control
characters are rejected only in a quoted value that also holds an escape, as go-logfmt
does.

### Writing

`serialize(mapping)` and `serialize_pairs(pairs)` write the canonical form, which is
byte-for-byte what go-logfmt writes for the same string pairs:

- a value is quoted only when it contains a character at or below space, `=`, `"`, DEL
  or U+FFFD, or is the literal text `null`;
- inside quotes `\\ \" \n \r \t` are escaped, other control characters become `\u00XX`;
- backslashes alone do not force quoting (`path=C:\tmp`);
- invalid key characters are removed (`strict=True` raises `LogfmtEncodeError`).

Any Python value is accepted: numbers via `str`, `Decimal`, dates and times in ISO 8601,
enums by their value, bytes as UTF-8, exceptions by their message, and lists, tuples,
sets and dicts as compact JSON. With `strict=True` a container value raises instead.

```python
import datetime
from logfmtkv import serialize, serialize_pairs

serialize({"at": datetime.date(2026, 10, 12), "n": 3, "tags": ["a", "b c"], "ok": True})
# 'at=2026-10-12 n=3 tags="[\\"a\\",\\"b c\\"]" ok'

serialize_pairs([("tag", "a"), ("tag", "b")])
# 'tag=a tag=b'
```

`quote_value(text)` gives the canonical token for one value.

### Round-trip guarantee

For any mapping of valid keys to strings or `True`, `parse(serialize(m)) == m` in both
modes, and serializing a parsed canonical line gives the same line back. Ordered pairs
round-trip through `serialize_pairs` and `parse_pairs`, repeated keys included. A seeded
fuzz test pins this.

### Typed values

`coerce` turns a value into `int`, `float` or `bool` only when nothing is lost:

```python
from logfmtkv import coerce, parse

{k: coerce(v) for k, v in parse("status=200 took=1.5 ok=true id=007").items()}
# {'status': 200, 'took': 1.5, 'ok': True, 'id': '007'}
```

### Where real tools disagree

| Case | go-logfmt | Loki | logfmtkv |
|---|---|---|---|
| bare key `d` | nil value | dropped by default | `True` / `Pair("d", None)` |
| `k=` | nil value | empty | `""` |
| repeated key | all returned | last wins | `parse`: policy; `parse_pairs`: all |
| `foo=bar=buzz` | error | skipped in lenient mode | lenient `"bar=buzz"`, strict error |
| slog quoted key `"a b"=1` | error | error | lenient reads it, strict error |
| writing a bare key | not possible (`d=`) | n/a | bare `d` |

## Command line

```
logfmtkv to-json [FILE] [--strict] [--where KEY[=VALUE]] [--select KEYS] [--coerce]
                        [--duplicates last|first|error|list]
logfmtkv from-json [FILE] [--strict] [--where ...] [--select ...]
logfmtkv fmt [FILE] [--strict] [--where ...] [--select ...]
logfmtkv check [FILE]
```

```
$ echo 'level=info msg="hello world" took=3ms' | logfmtkv to-json
{"level": "info", "msg": "hello world", "took": "3ms"}

$ logfmtkv to-json app.log --where level=error --select time,msg
$ echo '{"level": "info", "msg": "hi there", "ok": true}' | logfmtkv from-json
level=info msg="hi there" ok

$ logfmtkv check app.log
app.log:2:4: unexpected '"'
logfmtkv: 1 of 2 records invalid
```

`FILE` defaults to standard input. Input is UTF-8, one record per line. `--where` is
repeatable and all filters must match; `KEY` alone matches when the key is present.
Errors go to standard error with exit status 1.

## Why

logfmt is a plain, readable log format, but the existing Python packages for it are stale
or ship no type information. logfmtkv is fully typed, has zero dependencies, and is
tested against real lines from go-logfmt, Heroku, Grafana Loki, logrus and Go's slog.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
