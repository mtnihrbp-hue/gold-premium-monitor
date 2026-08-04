"""Sprint 1 KPI checker.

Validates the Neon PostgreSQL persistence layer against real credentials.

Usage:
    set DATABASE_URL=postgresql://user:pass@host/db
    python -c "import sys; sys.path.insert(0, 'src'); from kpi.sprint_01_kpi import run_kpi; run_kpi()"
"""

import sys

sys.path.insert(0, "src")

from datetime import datetime

from sqlalchemy import text

from database.connection import get_engine, init_db
from database.repository import (
    save_market_snapshot,
    get_latest_market_snapshot,
    get_snapshots,
)
import database.repository as repo


def _banner():
    print("=" * 50)
    print("Sprint 1 KPI Report")
    print("=" * 50)


def _check_connection():
    try:
        engine = get_engine()
        if engine is None:
            raise RuntimeError("DATABASE_URL not set")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection: PASS")
        return True
    except Exception as e:
        print(f"Database connection: FAIL ({e})")
        return False


def _check_tables():
    try:
        init_db()
        print("Tables created: PASS")
        return True
    except Exception as e:
        print(f"Tables created: FAIL ({e})")
        return False


def _check_insert():
    try:
        now = datetime.now()
        sid = save_market_snapshot(
            timestamp=now,
            fair_price=187448499,
            premium_percent=-2.76,
            world_gold_usd=4080.70,
            usd_irr=190500,
            signal="BUY",
            confidence=None,
            platform_prices=[
                {
                    "platform_name": "Taline",
                    "price_irr": 182270000,
                    "change_irr": -970000,
                },
            ],
        )
        print(f"Insert test: PASS (id={sid})")
        return True
    except Exception as e:
        print(f"Insert test: FAIL ({e})")
        return False


def _check_read():
    try:
        latest = get_latest_market_snapshot()
        assert latest is not None
        assert float(latest.premium_percent) == -2.76
        print("Read test: PASS")
        return True
    except Exception as e:
        print(f"Read test: FAIL ({e})")
        return False


def _check_failure_handling():
    try:
        # Patch the get_session that repository actually uses
        orig = repo.get_session
        repo.get_session = lambda: None

        result = get_latest_market_snapshot()
        snapshots = get_snapshots(days=7)

        # Restore
        repo.get_session = orig

        assert result is None
        assert snapshots == []
        print("Failure handling: PASS")
        return True
    except Exception as e:
        print(f"Failure handling: FAIL ({e})")
        return False


def run_kpi():
    _banner()
    results = [
        _check_connection(),
        _check_tables(),
        _check_insert(),
        _check_read(),
        _check_failure_handling(),
    ]
    print("-" * 50)
    if all(results):
        print("Overall: SPRINT 1 COMPLETE")
    else:
        print("Overall: SPRINT 1 INCOMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    run_kpi()
