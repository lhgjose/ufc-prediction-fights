"""Multi-dimensional Elo rating system."""

from .adjustments import (
    apply_age_adjustment,
    apply_chin_degradation,
    apply_inactivity_decay,
    calculate_age_factor,
    calculate_chin_degradation,
    calculate_inactivity_decay,
    calculate_recency_weight,
)
from .dimensions import DimensionScore, extract_dimension_scores
from .elo import (
    calculate_new_rating,
    calculate_rating_change,
    dynamic_k_factor,
    expected_score,
    update_ratings,
    win_probability,
)
from .models import (
    DEFAULT_K_FACTOR,
    DEFAULT_RATING,
    DimensionRating,
    FighterRatings,
    RatingUpdate,
    SkillDimension,
)
from .system import HistoricalReplay, RatingSystem

__all__ = [
    # Models
    "SkillDimension",
    "DimensionRating",
    "FighterRatings",
    "RatingUpdate",
    "DEFAULT_RATING",
    "DEFAULT_K_FACTOR",
    # Elo functions
    "expected_score",
    "calculate_new_rating",
    "calculate_rating_change",
    "update_ratings",
    "dynamic_k_factor",
    "win_probability",
    # Dimensions
    "DimensionScore",
    "extract_dimension_scores",
    # Adjustments
    "calculate_inactivity_decay",
    "apply_inactivity_decay",
    "calculate_chin_degradation",
    "apply_chin_degradation",
    "calculate_age_factor",
    "apply_age_adjustment",
    "calculate_recency_weight",
    # System
    "RatingSystem",
    "HistoricalReplay",
]
