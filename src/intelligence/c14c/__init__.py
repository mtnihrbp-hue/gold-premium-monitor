"""C.14C Adaptive Intelligence Foundation — diagnostic layer.

Downstream consumer only. No pipeline modification. No adaptation.
"""

from .error_classifier import classify_error, ERROR_CATEGORIES
from .regime_analysis import analyze_regime_performance
from .reliability_analysis import analyze_feature_reliability
from .event_interface import EventInterpreter, StubEventInterpreter
from .intelligence_layer import analyze_forecast_outcome, analyze_historical_batch

__all__ = [
    "classify_error",
    "ERROR_CATEGORIES",
    "analyze_regime_performance",
    "analyze_feature_reliability",
    "EventInterpreter",
    "StubEventInterpreter",
    "analyze_forecast_outcome",
    "analyze_historical_batch",
]
