import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path("state.json")


def load_state():
    if not STATE_FILE.exists():
        return None

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(data):
    data["timestamp"] = datetime.now().isoformat()

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
