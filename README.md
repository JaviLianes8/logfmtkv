# logfmtkv

Typed, zero-dependency logfmt codec: parse and serialize key=value log lines in both directions.

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

A bare key with no value parses to `True`. On the way back, `True` becomes a bare flag and
`False` is dropped. Values are quoted only when they contain whitespace, a quote, an equals
sign or a control character, and quotes and backslashes are escaped and restored intact.

## Why

logfmt is a plain, readable log format (`key=value` pairs on one line), but the existing
Python packages for it are stale or ship no type information. logfmtkv is the clean take:
fully typed, zero dependencies, and correct in both directions, so a line you serialize
parses back to the same mapping.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
