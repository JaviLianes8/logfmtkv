# logfmtkv improvement round

A ranked list of substantial, coherent improvements for this round. The point of the
round is real-world interop: logfmt as it is actually written by go-logfmt, Heroku
(brandur.org/logfmt), Grafana Loki, logrus and Go's `log/slog` TextHandler. Every item
is additive: `parse` and `serialize` keep their signatures, and the only changes to
their results are the interop fixes listed below and in the changelog.

## Starting point

Version 0.1.0 exposed two functions. `parse` read one line into a `dict` (bare key ->
`True`, last duplicate wins) and `serialize` wrote a mapping of strings and booleans
back. Gaps found while reading the code against the reference implementations:

- Only a space separated pairs; a tab or other control character was swallowed into a
  value (`a=1\tb=2` gave `{"a": "1\tb=2"}`).
- `\uXXXX` escapes were not decoded and unknown escapes silently lost their backslash.
- `=value` (no key) turned `value` into a bare flag instead of being skipped.
- Keys were written raw, so `serialize({"a b": "x"})` produced an unparseable line.
- Backslashes forced quoting, so output differed from what go-logfmt writes.
- No ordered view, no duplicate policy, no strict mode, no errors with a position, no
  streaming, no handling of non-string values and no command line tool.

## Ranked improvements

1. **Exact quoting and escaping, both ways, pinned to go-logfmt.** The encoder quotes a
   value exactly when go-logfmt does (any byte <= space, `=`, `"`, DEL, U+FFFD) and
   escapes `\\ \" \n \r \t`, other control characters as `\u00XX`. The decoder reads
   `\" \\ \/ \' \b \f \n \r \t \uXXXX` with UTF-16 surrogate pairs. Canonical output is
   byte-for-byte what go-logfmt writes for the same pairs, except that the character
   after U+FFFD is always escaped (go-logfmt copies it raw).

2. **Strict mode matching go-logfmt.** `strict=True` rejects what go-logfmt rejects
   (`=value`, `a==`, `k=b"ar`, quoted keys, unterminated or invalid quoted values,
   keys carrying a replacement character) with the same messages and positions.

3. **Honest errors with a column.** `LogfmtSyntaxError` carries `msg`, `pos` (1-based
   column), `lineno` and the offending `line`, formats like go-logfmt, and pickles.
   `LogfmtEncodeError` reports unrepresentable keys or values. Both derive from
   `LogfmtError`, a `ValueError`.

4. **A lenient mode that never raises and reads more real output.** The default keeps
   parsing past bad pairs like Loki does, separates on any whitespace or control byte,
   accepts slog's quoted keys and the Go `strconv.Quote` escapes (`\a \v \xHH
   \UXXXXXXXX`) that logrus and slog emit, keeps unknown escapes verbatim and treats an
   unterminated quote as running to the end of the line.

5. **Ordered pairs and the bare-key versus empty-value distinction.** `parse_pairs`
   returns a list of `Pair(key, value)` in line order with duplicates intact; a bare key
   has `value=None` while `key=` has `value=""`.

6. **Duplicate-key policy.** `parse(..., duplicates="last" | "first" | "error")` and
   `parse_multi` (every value per key, in order).

7. **Streaming over big files.** `iter_records` and `iter_pairs` consume any iterable of
   lines (an open file, `sys.stdin`, a list) lazily, strip `\n` and `\r\n`, report the
   line number in strict errors and can keep or skip blank lines.

8. **Safe serialization of arbitrary Python values.** `serialize` accepts any value:
   numbers, `Decimal`, `datetime` (ISO 8601), enums (their value), bytes (UTF-8 with
   replacement), exceptions (via `str()`) and containers (compact JSON). `None` and
   `True` write a bare key, `False` is omitted. Invalid key characters are stripped like
   go-logfmt, or rejected with `strict=True`. `serialize_pairs` writes ordered pairs,
   duplicates included. `quote_value` exposes the canonical value quoting.

9. **Round-trip guarantee.** For every mapping of valid keys to strings without lone
   surrogates, or `True`,
   `parse(serialize(m)) == m` in both modes, and `serialize` of a parsed canonical line
   reproduces it exactly. Pinned by a seeded fuzz test.

10. **Typed value coercion helper.** `coerce` turns `"200"`, `"1.5"`, `"true"` into
    `int`, `float` and `bool` only when the result prints back as the same text, and
    leaves everything else (including `"007"`, `"1.50"` and `"8ms"`) untouched, so no
    information is lost.

11. **A command line tool.** `logfmtkv to-json`, `from-json`, `fmt` and `check`: convert
    logfmt to JSON lines and back, canonicalise, filter records with `--where`, pick and
    order fields with `--select`, coerce types, choose the duplicate policy, validate a
    file strictly with `file:line:col` diagnostics. Errors go to stderr with exit 1.

12. **Golden fixtures from real tools.** Test vectors taken from go-logfmt's decoder and
    encoder tests, the Heroku logfmt article, Loki's logfmt parser docs, the logrus
    README and Go's slog tests and docs, each with its source noted, asserted pair by
    pair.

13. **Documentation.** Docstrings on every public name and a README guide covering the
    grammar, both modes, the choices made where tools disagree, and the CLI.

## Where real tools disagree, and the choice made

| Case | go-logfmt | Loki | logrus / slog | logfmtkv lenient | logfmtkv strict |
|---|---|---|---|---|---|
| bare key `d` | key, nil value | dropped unless `--keep-empty` | not emitted | `None` / `True` | `None` / `True` |
| `k=` | key, nil value | empty | `k=` / `k=""` | `""` | `""` |
| duplicates | all returned | last wins | not emitted | pairs keep all, dict per policy | same |
| `=v`, `a==`, `k=b"ar` | error | skipped or kept | not emitted | skipped or kept | error |
| quoted key `"a b"=1` | error | error | slog emits it | accepted | error |
| `\xHH`, `\a`, `\v`, `\U` | error | error | emitted by `%q` | decoded | error |
| unknown escape `\q` | error | error | never emitted | kept verbatim | error |
| non-UTF-8 key | error | error | not emitted | kept | error |

## Out of scope

- No third-party dependencies, no change to the existing return types.
- No guessing of durations or sizes (`8ms`, `20MB`): `coerce` stays lossless.
