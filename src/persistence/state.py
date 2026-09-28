import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path("state.json")


def _default_state():
    return {
        "schema_version": 1,
        "history": [],
        "last_alert": None,
        "alert_history": [],
        "last_recap_date": None,
        "created_at": datetime.utcnow().isoformat(),
    }


def load_state():
    if not STATE_FILE.exists():
        return _default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(f"WARNING: State file corrupted. Using new state. ({e})")
        return _default_state()

    state.setdefault("schema_version", 1)
    state.setdefault("history", [])
    state.setdefault("last_alert", None)
    state.setdefault("alert_history", [])
    state.setdefault("last_recap_date", None)

    return state


def save_state(state):
    state["updated_at"] = datetime.utcnow().isoformat()

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
