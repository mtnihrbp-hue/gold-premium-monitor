"""Run every KPI suite and report a consolidated result.

Executes each `kpi/kpi_*.py` in a subprocess against an isolated in-memory
database so no KPI run can reach production Neon.

UTF-8 output is forced for the child processes because the KPI scripts print
status emoji. Under the Windows console default codepage those raise
UnicodeEncodeError *after* the assertions have already passed, which reports a
passing suite as a failure.

Usage:
    python kpi/run_all.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path

KPI_DIR = Path(__file__).resolve().parent
REPO_ROOT = KPI_DIR.parent
PER_FILE_TIMEOUT_SECONDS = 300

RESULT_PATTERN = re.compile(r"(?:Result:|KPI RESULT:)\s*(\d+/\d+)")


def _natural_key(path: Path):
    """Sort c2 before c10 rather than lexicographically."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name)]


def _child_env():
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _extract_score(output: str) -> str:
    matches = RESULT_PATTERN.findall(output)
    return matches[-1] if matches else ""


def run_one(path: Path):
    try:
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(REPO_ROOT),
            env=_child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PER_FILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", "", ""
    output = (completed.stdout or "") + (completed.stderr or "")
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return status, _extract_score(output), output


def main() -> int:
    kpi_files = sorted(
        (p for p in KPI_DIR.glob("kpi_*.py") if p.is_file()),
        key=_natural_key,
    )
    if not kpi_files:
        print("No KPI files found.")
        return 1

    failures = []
    for path in kpi_files:
        status, score, output = run_one(path)
        print(f"{path.name:<30} {status:<8} {score}")
        if status != "PASS":
            failures.append((path.name, output))

    passed = len(kpi_files) - len(failures)
    print("-" * 55)
    print(f"KPI SUITE: {passed}/{len(kpi_files)} files passed")

    for name, output in failures:
        print(f"\n===== {name} =====")
        # Written through a byte stream rather than print(). The child is forced to
        # UTF-8, but the parent console is cp1252 on Windows, so printing a failure
        # report containing an emoji raised UnicodeEncodeError -- the suite named the
        # failing file and then crashed before saying what the failure was.
        sys.stdout.flush()
        sys.stdout.buffer.write(
            output.strip()[-3000:].encode("utf-8", "replace") + b"\n")
        sys.stdout.flush()

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
