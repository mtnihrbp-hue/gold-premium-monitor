"""The Telegram worker's behaviour (src/worker/telegram-trigger.js), run in Node with fake GitHub, Telegram and KV:
a request without Telegram's secret header is refused, a command is dispatched at most once a minute, GitHub's
error text is escaped (the external audit's A1; SP_D_HANDOFF.md section 52). Imported as a module, which also
checks its syntax (node --check passes any file with `export`, src/worker/README.md). Skipped without Node.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "..", "src", "worker", "telegram-trigger.js")


def test_worker_behaviour():
    node = shutil.which("node")
    if not node:
        print("SKIP: test_worker_behaviour (no node)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([node, os.path.join(HERE, "worker_behaviour.mjs"), WORKER, os.path.join(tmp, "w.mjs")],
                           capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "all checks passed" in r.stdout, r.stdout + r.stderr
    print("PASS: test_worker_behaviour")


if __name__ == "__main__":
    try:
        test_worker_behaviour()
    except AssertionError as e:
        print(f"FAIL: test_worker_behaviour\n{e}")
        sys.exit(1)
    print("\n1 passed, 0 failed out of 1")
