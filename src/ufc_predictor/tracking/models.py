"""Data models for performance tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PredictionOutcome(Enum):
    """Outcome of a prediction."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PENDING = "pending"  # Fight hasn't happened yet
    CANCELLED = "cancelled"  # Fight was cancelled
    NO_CONTEST = "no_contest"  # Fight ended in NC


@dataclass
class LoggedPrediction:
    """A logged prediction for tracking."""

    # Identifiers
    prediction_id: str  # Unique ID for this prediction
    fight_id: Optional[str] = None  # UFC fight ID (if known)
    event_name: Optional[str] = None

    # Fighters
    fighter1_id: str = ""
    fighter2_id: str = ""
    fighter1_name: Optional[str] = None
    fighter2_name: Optional[str] = None

    # Predictions
    predicted_winner_id: str = ""
    predicted_method: Optional[str] = None  # "KO/TKO", "Submission", "Decision"
    predicted_round: Optional[int] = None  # None for decision

    # Metadata
    prediction_timestamp: Optional[datetime] = None
    scheduled_rounds: int = 3
    is_title_fight: bool = False
    confidence_notes: Optional[str] = None  # e.g., "close fight"

    # Ratings at time of prediction
    fighter1_avg_rating: float = 0.0
    fighter2_avg_rating: float = 0.0
    rating_differential: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "prediction_id": self.prediction_id,
            "fight_id": self.fight_id,
            "event_name": self.event_name,
            "fighter1_id": self.fighter1_id,
            "fighter2_id": self.fighter2_id,
            "fighter1_name": self.fighter1_name,
            "fighter2_name": self.fighter2_name,
            "predicted_winner_id": self.predicted_winner_id,
            "predicted_method": self.predicted_method,
            "predicted_round": self.predicted_round,
            "prediction_timestamp": (
                self.prediction_timestamp.isoformat() if self.prediction_timestamp else None
            ),
            "scheduled_rounds": self.scheduled_rounds,
            "is_title_fight": self.is_title_fight,
            "confidence_notes": self.confidence_notes,
            "fighter1_avg_rating": self.fighter1_avg_rating,
            "fighter2_avg_rating": self.fighter2_avg_rating,
            "rating_differential": self.rating_differential,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LoggedPrediction":
        """Create from dictionary."""
        timestamp = data.get("prediction_timestamp")
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            prediction_id=data["prediction_id"],
            fight_id=data.get("fight_id"),
            event_name=data.get("event_name"),
            fighter1_id=data.get("fighter1_id", ""),
            fighter2_id=data.get("fighter2_id", ""),
            fighter1_name=data.get("fighter1_name"),
            fighter2_name=data.get("fighter2_name"),
            predicted_winner_id=data.get("predicted_winner_id", ""),
            predicted_method=data.get("predicted_method"),
            predicted_round=data.get("predicted_round"),
            prediction_timestamp=timestamp,
            scheduled_rounds=data.get("scheduled_rounds", 3),
            is_title_fight=data.get("is_title_fight", False),
            confidence_notes=data.get("confidence_notes"),
            fighter1_avg_rating=data.get("fighter1_avg_rating", 0.0),
            fighter2_avg_rating=data.get("fighter2_avg_rating", 0.0),
            rating_differential=data.get("rating_differential", 0.0),
        )


@dataclass
class ActualResult:
    """Actual result of a fight."""

    fight_id: str
    actual_winner_id: Optional[str] = None  # None for draw/NC
    actual_method: Optional[str] = None  # "KO/TKO", "Submission", "Decision"
    actual_round: Optional[int] = None
    is_draw: bool = False
    is_no_contest: bool = False
    result_timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "fight_id": self.fight_id,
            "actual_winner_id": self.actual_winner_id,
            "actual_method": self.actual_method,
            "actual_round": self.actual_round,
            "is_draw": self.is_draw,
            "is_no_contest": self.is_no_contest,
            "result_timestamp": (
                self.result_timestamp.isoformat() if self.result_timestamp else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActualResult":
        """Create from dictionary."""
        timestamp = data.get("result_timestamp")
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            fight_id=data["fight_id"],
            actual_winner_id=data.get("actual_winner_id"),
            actual_method=data.get("actual_method"),
            actual_round=data.get("actual_round"),
            is_draw=data.get("is_draw", False),
            is_no_contest=data.get("is_no_contest", False),
            result_timestamp=timestamp,
        )


@dataclass
class PredictionResult:
    """Result of comparing a prediction to actual outcome."""

    prediction: LoggedPrediction
    actual: Optional[ActualResult] = None

    # Outcomes
    winner_correct: Optional[bool] = None
    method_correct: Optional[bool] = None
    round_correct: Optional[bool] = None  # Within 1 round counts as correct
    outcome: PredictionOutcome = PredictionOutcome.PENDING


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""

    # Counts
    total_predictions: int = 0
    resolved_predictions: int = 0  # Predictions with known outcomes
    pending_predictions: int = 0

    # Winner accuracy
    winner_correct: int = 0
    winner_incorrect: int = 0
    winner_accuracy: float = 0.0

    # Method accuracy (only for correct winner predictions)
    method_correct: int = 0
    method_incorrect: int = 0
    method_accuracy: float = 0.0

    # Round accuracy (only for correct method predictions that weren't decisions)
    round_correct: int = 0  # Within 1 round
    round_incorrect: int = 0
    round_accuracy: float = 0.0

    # By method type
    ko_predictions: int = 0
    ko_correct: int = 0
    submission_predictions: int = 0
    submission_correct: int = 0
    decision_predictions: int = 0
    decision_correct: int = 0

    # By favorite/underdog
    favorite_predictions: int = 0  # Predicted the favorite (higher rated)
    favorite_correct: int = 0
    underdog_predictions: int = 0  # Predicted the underdog
    underdog_correct: int = 0

    # Upset tracking
    upsets_predicted: int = 0  # Correctly predicted underdog wins
    upsets_missed: int = 0  # Favorite predicted but underdog won

    def calculate_percentages(self) -> None:
        """Calculate accuracy percentages."""
        if self.winner_correct + self.winner_incorrect > 0:
            self.winner_accuracy = (
                self.winner_correct / (self.winner_correct + self.winner_incorrect) * 100
            )

        if self.method_correct + self.method_incorrect > 0:
            self.method_accuracy = (
                self.method_correct / (self.method_correct + self.method_incorrect) * 100
            )

        if self.round_correct + self.round_incorrect > 0:
            self.round_accuracy = (
                self.round_correct / (self.round_correct + self.round_incorrect) * 100
            )
