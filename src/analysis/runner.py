"""Analysis Wing Scheduled Runner — PRE-SP-C.13

Thin execution wrapper for scheduled analysis windows.
Delegates collection and calculation to main.py.
Ensures idempotent, window-gated execution.
"""

import os
import sys

from analysis.scheduler import should_run_analysis


def run_scheduled_analysis():
    """Execute the analysis wing within the scheduled window."""
    from main import main, load_config

    config = load_config()

    if not should_run_analysis(config=config):
        print("Analysis window closed — skipping scheduled run")
        return 0

    os.environ["SCHEDULED_RUN"] = "true"
    main()
    return 0


def run_analysis_for_snapshot(snapshot_id=None, config=None):
    """Backward-compatible Analysis Wing entry point.

    The current C.13 architecture builds analysis from the latest persisted
    market state rather than requiring a snapshot ID argument. The optional
    snapshot_id is retained for callers from earlier phase contracts.
    """
    from analysis.snapshot_builder import build_analysis_snapshot
    return build_analysis_snapshot(config=config)


if __name__ == "__main__":
    sys.exit(run_scheduled_analysis())
