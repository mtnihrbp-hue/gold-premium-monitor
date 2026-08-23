"""C.14C Event Interpreter Interface — structural placeholder.

No LLM integration. No API calls. Architecture boundary only.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class EventInterpreter(ABC):
    """Abstract interface for event interpretation.

    Future implementation may use LLM to convert news events
    into structured analytical context. C.14C reserves this boundary.
    """

    @abstractmethod
    def classify(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a single news event into structured context.

        Args:
            event: dict with keys like title, source, timestamp, content

        Returns:
            dict with structured interpretation
        """
        raise NotImplementedError

    @abstractmethod
    def summarize(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize multiple events into market context.

        Args:
            events: list of event dicts

        Returns:
            dict with summary and sentiment
        """
        raise NotImplementedError


class StubEventInterpreter(EventInterpreter):
    """Minimal non-LLM implementation for testing and structural validation."""

    def classify(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": "UNKNOWN",
            "sentiment": "NEUTRAL",
            "confidence": 0.0,
            "keywords": [],
            "interpreter": "stub",
        }

    def summarize(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "event_count": len(events),
            "overall_sentiment": "NEUTRAL",
            "summary": "No LLM integration available (C.14C placeholder).",
            "interpreter": "stub",
        }
