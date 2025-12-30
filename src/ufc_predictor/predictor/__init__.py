"""Fight prediction engine."""

from .models import (
    CLOSE_FIGHT_THRESHOLD,
    MIN_FIGHTS_FOR_PREDICTION,
    SIGNIFICANT_ADVANTAGE_THRESHOLD,
    DimensionAdvantage,
    DimensionBreakdown,
    MethodPrediction,
    Prediction,
    PredictionMethod,
    RoundPrediction,
    StyleMatchup,
)
from .predictor import FightPredictor
from .report import generate_compact_prediction, generate_report

__all__ = [
    # Predictor
    "FightPredictor",
    # Models
    "Prediction",
    "PredictionMethod",
    "MethodPrediction",
    "RoundPrediction",
    "DimensionAdvantage",
    "DimensionBreakdown",
    "StyleMatchup",
    # Constants
    "CLOSE_FIGHT_THRESHOLD",
    "SIGNIFICANT_ADVANTAGE_THRESHOLD",
    "MIN_FIGHTS_FOR_PREDICTION",
    # Report
    "generate_report",
    "generate_compact_prediction",
]
