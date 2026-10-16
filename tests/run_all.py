"""Run every unit test file in tests/ and report a consolidated result.

The companion of kpi/run_all.py: each `tests/test_*.py` runs in its own subprocess
against an isolated in-memory database, with UTF-8 forced for the same Windows reason
(status emoji printed after the assertions pass). A file passes when it exits 0; the
files use unittest or a plain runner of their own, so the exit code is the one
contract they share.

Usage:
    python tests/run_all.py
"""

import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
PER_FILE_TIMEOUT_SECONDS = 300


def _child_env():
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


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
        return "TIMEOUT", ""
    output = (completed.stdout or "") + (completed.stderr or "")
    return ("PASS" if completed.returncode == 0 else "FAIL"), output


def main() -> int:
    files = sorted(p for p in TESTS_DIR.glob("test_*.py") if p.is_file())
    if not files:
        print("No test files found.")
        return 1

    failures = []
    for path in files:
        status, output = run_one(path)
        print(f"{path.name:<32} {status}")
        if status != "PASS":
            failures.append((path.name, output))

    print("-" * 45)
    print(f"UNIT TESTS: {len(files) - len(failures)}/{len(files)} files passed")

    for name, output in failures:
        print(f"\n===== {name} =====")
        sys.stdout.flush()
        sys.stdout.buffer.write(output.strip()[-3000:].encode("utf-8", "replace") + b"\n")
        sys.stdout.flush()

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
