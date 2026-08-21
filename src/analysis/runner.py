"""Analysis Wing Scheduled Runner — PRE-SP-C.13

Thin execution wrapper for scheduled analysis windows.
Delegates collection and calculation to main.py.
Ensures idempotent, window-gated execution.
"""

import os
import sys

from analysis.scheduler import should_run_analysis, generate_source_run_id


def run_scheduled_analysis():
    """Execute the analysis wing within the scheduled window.

    Idempotent: duplicate invocations at the same time produce
    the same source_run_id and are deduplicated by the repository.
    """
    # Import here to avoid circular dependency at module load
    from main import main, load_config

    config = load_config()

    if not should_run_analysis(config=config):
        print("Analysis window closed — skipping scheduled run")
        return 0

    # Set scheduled flag for main() behavior (daily recap vs manual update)
    os.environ["SCHEDULED_RUN"] = "true"

    # Main handles collection, calculation, SP-A decision, alerts,
    # and (C.13) triggers build_analysis_snapshot() after market state save
    main()

    return 0


if __name__ == "__main__":
    sys.exit(run_scheduled_analysis())
