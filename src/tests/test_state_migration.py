"""Unit tests for state loading and schema migration.

Tests that state.json upgrades gracefully and handles corruption.
"""

import sys
from pathlib import Path
import json
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from persistence import state as state_module


def test_default_state_structure():
    """Default state has all required keys."""
    default = state_module._default_state()
    assert "schema_version" in default
    assert "history" in default
    assert "last_alert" in default
    assert "alert_history" in default
    assert "created_at" in default
    assert default["schema_version"] == 1
    assert default["history"] == []
    assert default["last_alert"] is None
    assert default["alert_history"] == []


def test_load_missing_file():
    """Missing state file returns default state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "nonexistent.json"
        try:
            result = state_module.load_state()
            assert result["history"] == []
            assert result["last_alert"] is None
        finally:
            state_module.STATE_FILE = old_file


def test_load_corrupted_file():
    """Corrupted state file returns default state with warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "state.json"
        state_module.STATE_FILE.write_text("not valid json {")
        try:
            result = state_module.load_state()
            assert result["history"] == []
            assert result["last_alert"] is None
            assert result["schema_version"] == 1
        finally:
            state_module.STATE_FILE = old_file


def test_load_partial_state():
    """Partial state gets missing keys populated with defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "state.json"
        partial = {"history": [{"premium": 1.0}]}
        state_module.STATE_FILE.write_text(json.dumps(partial))
        try:
            result = state_module.load_state()
            assert result["history"] == [{"premium": 1.0}]
            assert result["last_alert"] is None
            assert result["alert_history"] == []
            assert result["schema_version"] == 1
        finally:
            state_module.STATE_FILE = old_file


def test_load_future_schema():
    """Future schema version is preserved, missing keys defaulted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "state.json"
        future = {
            "schema_version": 99,
            "history": [],
            "last_alert": "SELL",
            "alert_history": [],
            "future_field": "should survive",
        }
        state_module.STATE_FILE.write_text(json.dumps(future))
        try:
            result = state_module.load_state()
            assert result["schema_version"] == 99
            assert result["last_alert"] == "SELL"
            assert result["future_field"] == "should survive"
        finally:
            state_module.STATE_FILE = old_file


def test_save_adds_updated_at():
    """save_state adds updated_at timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "state.json"
        try:
            state = state_module._default_state()
            state_module.save_state(state)
            assert state_module.STATE_FILE.exists()
            saved = json.loads(state_module.STATE_FILE.read_text())
            assert "updated_at" in saved
        finally:
            state_module.STATE_FILE = old_file


def test_save_roundtrip():
    """Save and load preserves data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = state_module.STATE_FILE
        state_module.STATE_FILE = Path(tmpdir) / "state.json"
        try:
            state = state_module._default_state()
            state["history"].append({"premium": 2.5, "timestamp": "2026-08-01T12:00:00"})
            state["last_alert"] = "BUY"
            state_module.save_state(state)

            loaded = state_module.load_state()
            assert loaded["history"][0]["premium"] == 2.5
            assert loaded["last_alert"] == "BUY"
        finally:
            state_module.STATE_FILE = old_file


if __name__ == "__main__":
    test_default_state_structure()
    test_load_missing_file()
    test_load_corrupted_file()
    test_load_partial_state()
    test_load_future_schema()
    test_save_adds_updated_at()
    test_save_roundtrip()
    print("All state migration tests passed.")
