"""The command line tool, driven in-process over real files."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from conftest import GOLDEN, REAL_LOG, as_dict

from logfmtkv._cli import main

REAL = [c for c in GOLDEN["parse"] if c["strict"] == "same" and c["source"] != "go-logfmt"]


def _write(tmp_path: Path, text: str, name: str = "in.log") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return str(path)


def _run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_to_json_over_the_real_log(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _run(capsys, "to-json", str(REAL_LOG), "--strict")
    assert (code, err) == (0, "")
    assert [json.loads(line) for line in out.splitlines()] == [as_dict(c["pairs"]) for c in REAL]


def test_to_json_filters_selects_and_coerces(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = _write(tmp_path, "level=info n=1\r\nlevel=error n=2 msg=x ok\n\nlevel=error\n")
    code, out, _ = _run(capsys, "to-json", path, "-w", "level=error", "-w", "n", "-s", "n,msg")
    assert (code, out) == (0, '{"n": "2", "msg": "x"}\n')
    code, out, _ = _run(capsys, "to-json", path, "--coerce", "--where", "ok")
    assert out == '{"level": "error", "n": 2, "msg": "x", "ok": true}\n'


def test_to_json_duplicate_policies(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = _write(tmp_path, "tag=a tag=b n=1 n=2\n")
    assert _run(capsys, "to-json", path)[1] == '{"tag": "b", "n": "2"}\n'
    assert _run(capsys, "to-json", path, "--duplicates", "first")[1] == '{"tag": "a", "n": "1"}\n'
    out = _run(capsys, "to-json", path, "--duplicates", "list", "--coerce")[1]
    assert out == '{"tag": ["a", "b"], "n": [1, 2]}\n'
    code, out, err = _run(capsys, "to-json", path, "--duplicates", "error")
    assert (code, out) == (1, "")
    assert err == f"logfmtkv: {path}:1:7: duplicate key 'tag'\n"


def test_from_json(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    rows = '{"level": "info", "msg": "hi there", "n": 3, "ok": true, "no": false, "x": null}\n'
    path = _write(tmp_path, rows + '{"level": "debug", "tags": ["a", "b c"]}\n')
    code, out, err = _run(capsys, "from-json", path)
    assert (code, err) == (0, "")
    assert out == 'level=info msg="hi there" n=3 ok x\nlevel=debug tags="[\\"a\\",\\"b c\\"]"\n'
    assert _run(capsys, "from-json", path, "-w", "n=3", "-s", "msg")[1] == 'msg="hi there"\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{bad\n", "in.log:1:2: invalid JSON"),
        ("[1, 2]\n", "in.log:1: expected a JSON object per line"),
        ('{"a b": 1}\n', "in.log:1: invalid character in key"),
    ],
)
def test_from_json_errors(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str, message: str
) -> None:
    path = _write(tmp_path, text)
    code, out, err = _run(capsys, "from-json", path, "--strict")
    assert (code, out) == (1, "")
    assert message in err


def test_fmt_canonicalises(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = _write(tmp_path, 'b="bar"  a="x y"\tflag c="C:\\\\tmp" b=2\n')
    assert _run(capsys, "fmt", path)[1] == 'b=bar a="x y" flag c=C:\\tmp b=2\n'
    assert _run(capsys, "fmt", path, "-s", "b,flag")[1] == "b=bar b=2 flag\n"
    assert _run(capsys, "fmt", path, "-w", "b=nope")[1] == ""


def test_fmt_reports_a_key_that_cannot_be_written(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, _, err = _run(capsys, "fmt", _write(tmp_path, '"=="=1\n'))
    assert code == 1 and "in.log:1: key '=='" in err


def test_check(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, out, err = _run(capsys, "check", str(REAL_LOG))
    assert (code, err) == (0, "") and out.endswith("real.log: 16 records ok\n")
    path = _write(tmp_path, 'a=1\nk=b"ar\n\nx="open\n')
    code, out, err = _run(capsys, "check", path)
    assert (code, out) == (1, "")
    assert err.splitlines() == [
        f"{path}:2:4: unexpected '\"'",
        f"{path}:4:8: unterminated quoted value",
        "logfmtkv: 2 of 3 records invalid",
    ]


def test_strict_read_errors_carry_file_line_and_column(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = _write(tmp_path, "ok=1\na==\n")
    code, out, err = _run(capsys, "to-json", path, "--strict")
    assert (code, out) == (1, '{"ok": "1"}\n')
    assert err == f"logfmtkv: {path}:2:3: unexpected '='\n"


def test_reads_standard_input(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    stdin = io.TextIOWrapper(io.BytesIO('msg="caf\u00e9 ok"\n'.encode()), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    code, out, _ = _run(capsys, "to-json")
    assert (code, out) == (0, '{"msg": "caf\u00e9 ok"}\n')


@pytest.mark.parametrize(
    "args",
    [["to-json", "missing.log"], ["to-json", "-w", "=x"], ["nope"], [], ["to-json", "--bogus"]],
)
def test_usage_and_file_errors_exit_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, args: list[str]
) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(tmp_path)
        try:
            code = main(args)
        except SystemExit as exit_:
            code = int(exit_.code or 0)
    out, err = capsys.readouterr()
    assert (code, out) == (1, "")
    assert err.strip()


def test_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert "examples:" in out and "logfmtkv to-json app.log" in out
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.startswith("logfmtkv 0.2.0")
