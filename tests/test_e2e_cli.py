"""Real end-to-end test: build a wheel, install it, drive the installed script.

No mocks. The project is built into a wheel, the wheel is installed into a throwaway
virtual environment, and the real ``logfmtkv`` executable is run over ``subprocess``
on the golden log file and on hand-made input. Stdout, stderr and exit codes are the
real ones.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import venv
from pathlib import Path

import pytest
from conftest import GOLDEN, REAL_LOG, as_dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL = [c for c in GOLDEN["parse"] if c["strict"] == "same" and c["source"] != "go-logfmt"]


def _exe(env_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return env_dir / "Scripts" / f"{name}.exe"
    return env_dir / "bin" / name


@pytest.fixture(scope="module")
def cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a wheel, install it into a fresh venv and return the console script path."""
    work = tmp_path_factory.mktemp("logfmtkv-e2e")
    env_dir = work / "venv"
    venv.create(env_dir, with_pip=True)
    python = _exe(env_dir, "python")
    wheels = work / "wheels"
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-q",
            "-w",
            str(wheels),
            str(PROJECT_ROOT),
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    (wheel,) = wheels.glob("logfmtkv-*.whl")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "-q", str(wheel)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    script = _exe(env_dir, "logfmtkv")
    assert script.is_file(), f"console script was not installed at {script}"
    return script


def _run(cli: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(cli), *args], input=stdin.encode(), capture_output=True, timeout=60, check=False
    )


def test_installed_script_converts_the_real_log(cli: Path) -> None:
    result = _run(cli, "to-json", "--strict", str(REAL_LOG))
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.decode().splitlines()]
    assert rows == [as_dict(c["pairs"]) for c in REAL]


def test_installed_script_round_trips_through_json(cli: Path) -> None:
    as_json = _run(cli, "to-json", str(REAL_LOG)).stdout.decode()
    back = _run(cli, "from-json", stdin=as_json)
    assert back.returncode == 0
    again = _run(cli, "to-json", "--strict", stdin=back.stdout.decode())
    assert again.stdout.decode() == as_json
    canonical = _run(cli, "fmt", str(REAL_LOG)).stdout
    assert _run(cli, "fmt", stdin=canonical.decode()).stdout == canonical
    check = _run(cli, "check", stdin=canonical.decode())
    assert check.returncode == 0
    assert check.stdout.decode() == "<stdin>: 16 records ok\n"


def test_installed_script_filters_and_selects(cli: Path) -> None:
    result = _run(cli, "to-json", str(REAL_LOG), "-w", "animal=orca", "-s", "msg,size", "--coerce")
    assert result.returncode == 0
    assert result.stdout.decode() == '{"msg": "The ice breaks!", "size": 9009}\n'


def test_installed_script_handles_utf8_from_stdin(cli: Path) -> None:
    result = _run(cli, "fmt", stdin='msg="caf\u00e9 \u00fcber"  ok\n')
    assert (result.returncode, result.stderr) == (0, b"")
    assert result.stdout.decode("utf-8") == 'msg="caf\u00e9 \u00fcber" ok\n'


def test_installed_script_reports_errors_on_stderr(cli: Path) -> None:
    result = _run(cli, "check", stdin='a=1\nk=b"ar\n')
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr.decode().splitlines() == [
        "<stdin>:2:4: unexpected '\"'",
        "logfmtkv: 1 of 2 records invalid",
    ]
    missing = _run(cli, "to-json", "no-such-file.log")
    assert missing.returncode == 1 and b"no-such-file.log" in missing.stderr


def test_installed_script_exits_quietly_when_the_reader_stops(cli: Path) -> None:
    big = "".join(f'n={i} msg="line {i}"\n' for i in range(200_000))
    proc = subprocess.Popen(
        [str(cli), "fmt"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    stdin = proc.stdin

    def feed() -> None:
        try:
            stdin.write(big.encode())
            stdin.close()
        except OSError:
            pass

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    assert proc.stdout.readline() == b'n=0 msg="line 0"\n'
    proc.stdout.close()
    stderr = proc.stderr.read()
    assert proc.wait(timeout=60) == 0
    writer.join(timeout=60)
    assert b"Traceback" not in stderr and b"Exception ignored" not in stderr


def test_installed_script_help_has_runnable_examples(cli: Path) -> None:
    result = _run(cli, "--help")
    assert result.returncode == 0
    text = result.stdout.decode()
    assert "examples:" in text
    example = 'level=info msg="hello world" took=3ms'
    assert example in text
    converted = _run(cli, "to-json", stdin=example + "\n")
    assert converted.stdout == b'{"level": "info", "msg": "hello world", "took": "3ms"}\n'
