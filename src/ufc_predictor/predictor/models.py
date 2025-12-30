"""Data models for fight predictions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..ratings.models import SkillDimension


class PredictionMethod(Enum):
    """How the fight is predicted to end."""

    KO_TKO = "KO/TKO"
    SUBMISSION = "Submission"
    DECISION = "Decision"


@dataclass
class DimensionAdvantage:
    """Advantage breakdown for a single skill dimension."""

    dimension: SkillDimension
    fighter1_rating: float
    fighter2_rating: float
    difference: float  # Positive = fighter1 advantage
    significant: bool  # True if difference > threshold


@dataclass
class MethodPrediction:
    """Predicted method of victory."""

    method: PredictionMethod
    confidence: str  # "high", "medium", "low" - internal use only, not shown to user


@dataclass
class RoundPrediction:
    """Predicted round of finish."""

    round_number: Optional[int]  # None for decision
    is_decision: bool
    scheduled_rounds: int  # 3 or 5


@dataclass
class StyleMatchup:
    """Stylistic matchup analysis."""

    striker_vs_grappler: Optional[str]  # Which fighter, if applicable
    pressure_dynamic: str  # "fighter1_pressures", "fighter2_pressures", "neutral"
    cardio_factor: str  # "fighter1_advantage", "fighter2_advantage", "even"
    experience_edge: Optional[str]  # Which fighter has more experience


@dataclass
class DimensionBreakdown:
    """Complete dimension-by-dimension analysis."""

    advantages: list[DimensionAdvantage]
    fighter1_strengths: list[SkillDimension]
    fighter2_strengths: list[SkillDimension]
    key_dimensions: list[SkillDimension]  # Most impactful for this matchup


@dataclass
class Prediction:
    """Complete fight prediction."""

    fighter1_id: str
    fighter2_id: str
    fighter1_name: Optional[str] = None
    fighter2_name: Optional[str] = None

    # Core predictions
    winner_id: str = ""
    winner_name: Optional[str] = None
    method: Optional[MethodPrediction] = None
    round_prediction: Optional[RoundPrediction] = None

    # Analysis
    dimension_breakdown: Optional[DimensionBreakdown] = None
    style_matchup: Optional[StyleMatchup] = None

    # Ratings summary
    fighter1_avg_rating: float = 0.0
    fighter2_avg_rating: float = 0.0
    rating_differential: float = 0.0  # Positive = fighter1 favored

    # Metadata
    is_close_fight: bool = False  # True if within margin
    refused: bool = False  # True if prediction refused (e.g., debut fighter)
    refusal_reason: Optional[str] = None

    # X-factors (special considerations)
    x_factors: list[str] = field(default_factory=list)


@dataclass
class FightCard:
    """A collection of predictions for an event."""

    event_name: str
    event_date: Optional[str] = None
    predictions: list[Prediction] = field(default_factory=list)


# Thresholds for prediction logic
CLOSE_FIGHT_THRESHOLD = 50.0  # Rating difference below this = close fight
SIGNIFICANT_ADVANTAGE_THRESHOLD = 75.0  # Dimension advantage to be "significant"
MIN_FIGHTS_FOR_PREDICTION = 1  # Minimum UFC fights to make prediction


# Weight class categories for separate modeling
MENS_WEIGHT_CLASSES = [
    "Flyweight",
    "Bantamweight",
    "Featherweight",
    "Lightweight",
    "Welterweight",
    "Middleweight",
    "Light Heavyweight",
    "Heavyweight",
]

WOMENS_WEIGHT_CLASSES = [
    "Women's Strawweight",
    "Women's Flyweight",
    "Women's Bantamweight",
    "Women's Featherweight",
]
