import json
import subprocess

# The bonbast CLI performs its own network calls and sets no timeout of its own, so a
# subprocess.run without one blocks until something outside the process intervenes.
#
# That is not hypothetical. Eight scheduled runs between 2026-09-14 and 2026-09-18
# were killed by the GitHub job timeout, each showing a DNS failure on the collector
# immediately before this one and then roughly twenty minutes of silence. A healthy
# run finishes in four. Those eight runs are the missing hourly readings.
#
# The caller already degrades USD/IRR to None on any exception, and TimeoutExpired is
# an Exception, so a timeout here costs one input rather than the entire run. Sixty
# seconds is generous against a call that normally answers in a few, and it leaves the
# rest of the job its full budget.
COLLECT_TIMEOUT_SECONDS = 60


def get_usd_sell_rate() -> int:
    result = subprocess.run(
        ["python", "-m", "bonbast", "export"],
        capture_output=True,
        text=True,
        check=True,
        timeout=COLLECT_TIMEOUT_SECONDS,
    )

    data = json.loads(result.stdout)

    return int(data["USD"]["sell"])
