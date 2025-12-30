"""Data models for the rating system."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class SkillDimension(Enum):
    """Skill dimensions for multi-dimensional Elo ratings."""

    KNOCKOUT_POWER = "knockout_power"  # Ability to finish fights via KO/TKO
    STRIKING_VOLUME = "striking_volume"  # Output and pace on the feet
    STRIKING_DEFENSE = "striking_defense"  # Ability to avoid damage
    WRESTLING_OFFENSE = "wrestling_offense"  # Takedown ability
    WRESTLING_DEFENSE = "wrestling_defense"  # Takedown defense
    SUBMISSION_OFFENSE = "submission_offense"  # Ability to submit opponents
    SUBMISSION_DEFENSE = "submission_defense"  # Ability to escape submissions
    CARDIO = "cardio"  # Endurance and late-fight performance
    PRESSURE = "pressure"  # Cage control, clinch work, forward movement
    ADAPTABILITY = "adaptability"  # Fight IQ, adjustments, experience factor


# Default starting rating (like chess Elo)
DEFAULT_RATING = 1500.0

# K-factor for rating updates (higher = more volatile)
DEFAULT_K_FACTOR = 32.0

# Rating floor and ceiling
MIN_RATING = 1000.0
MAX_RATING = 2200.0


@dataclass
class DimensionRating:
    """Rating for a single skill dimension."""

    dimension: SkillDimension
    rating: float = DEFAULT_RATING
    games_played: int = 0  # Number of fights this dimension was updated
    last_updated: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension.value,
            "rating": self.rating,
            "games_played": self.games_played,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DimensionRating":
        return cls(
            dimension=SkillDimension(data["dimension"]),
            rating=data["rating"],
            games_played=data["games_played"],
            last_updated=date.fromisoformat(data["last_updated"]) if data["last_updated"] else None,
        )


@dataclass
class FighterRatings:
    """Complete multi-dimensional ratings for a fighter."""

    fighter_id: str
    ratings: dict[SkillDimension, DimensionRating] = field(default_factory=dict)
    ko_losses: int = 0  # Track for chin degradation
    last_fight_date: Optional[date] = None
    total_fights: int = 0

    def __post_init__(self):
        # Initialize all dimensions with default ratings if not present
        for dim in SkillDimension:
            if dim not in self.ratings:
                self.ratings[dim] = DimensionRating(dimension=dim)

    def get_rating(self, dimension: SkillDimension) -> float:
        """Get rating for a specific dimension."""
        return self.ratings[dimension].rating

    def get_all_ratings(self) -> dict[SkillDimension, float]:
        """Get all ratings as a simple dict."""
        return {dim: r.rating for dim, r in self.ratings.items()}

    def get_average_rating(self) -> float:
        """Get average rating across all dimensions."""
        return sum(r.rating for r in self.ratings.values()) / len(self.ratings)

    def update_rating(
        self,
        dimension: SkillDimension,
        new_rating: float,
        fight_date: Optional[date] = None,
    ) -> None:
        """Update rating for a dimension."""
        self.ratings[dimension].rating = max(MIN_RATING, min(MAX_RATING, new_rating))
        self.ratings[dimension].games_played += 1
        if fight_date:
            self.ratings[dimension].last_updated = fight_date
            self.last_fight_date = fight_date

    def to_dict(self) -> dict:
        return {
            "fighter_id": self.fighter_id,
            "ratings": {dim.value: r.to_dict() for dim, r in self.ratings.items()},
            "ko_losses": self.ko_losses,
            "last_fight_date": self.last_fight_date.isoformat() if self.last_fight_date else None,
            "total_fights": self.total_fights,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FighterRatings":
        ratings = {}
        for dim_str, rating_data in data.get("ratings", {}).items():
            dim = SkillDimension(dim_str)
            ratings[dim] = DimensionRating.from_dict(rating_data)

        instance = cls(
            fighter_id=data["fighter_id"],
            ratings=ratings,
            ko_losses=data.get("ko_losses", 0),
            last_fight_date=(
                date.fromisoformat(data["last_fight_date"]) if data.get("last_fight_date") else None
            ),
            total_fights=data.get("total_fights", 0),
        )
        return instance


@dataclass
class RatingUpdate:
    """Record of a rating update from a fight."""

    fight_id: str
    fight_date: date
    fighter_id: str
    opponent_id: str
    dimension: SkillDimension
    old_rating: float
    new_rating: float
    expected_score: float
    actual_score: float  # 1.0 win, 0.5 draw, 0.0 loss
