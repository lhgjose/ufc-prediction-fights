"""Main rating system orchestration."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ..scraper.models import Event, Fight, Fighter
from ..scraper.storage import DataStorage
from .adjustments import apply_chin_degradation, apply_inactivity_decay, get_k_factor_with_recency
from .dimensions import extract_dimension_scores
from .elo import calculate_new_rating, dynamic_k_factor, expected_score, finish_multiplier
from .models import DEFAULT_K_FACTOR, FighterRatings, RatingUpdate, SkillDimension

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RatingSystem:
    """
    Multi-dimensional Elo rating system for UFC fighters.

    Maintains separate ratings for each skill dimension and updates
    them based on fight outcomes and performance.
    """

    def __init__(
        self,
        ratings_dir: Optional[Path] = None,
        data_storage: Optional[DataStorage] = None,
    ):
        """
        Initialize the rating system.

        Args:
            ratings_dir: Directory to store rating files
            data_storage: DataStorage for accessing fight/fighter data
        """
        self.data_storage = data_storage or DataStorage()

        if ratings_dir is None:
            ratings_dir = self.data_storage.data_dir / "ratings"
        self.ratings_dir = ratings_dir
        self.ratings_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of ratings
        self._ratings_cache: dict[str, FighterRatings] = {}

        # Track rating updates for analysis
        self._update_history: list[RatingUpdate] = []

    def get_fighter_ratings(self, fighter_id: str) -> FighterRatings:
        """
        Get ratings for a fighter, creating default if not exists.

        Args:
            fighter_id: Fighter ID

        Returns:
            FighterRatings object
        """
        # Check cache first
        if fighter_id in self._ratings_cache:
            return self._ratings_cache[fighter_id]

        # Try to load from file
        filepath = self.ratings_dir / f"{fighter_id}.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            ratings = FighterRatings.from_dict(data)
            self._ratings_cache[fighter_id] = ratings
            return ratings

        # Create new default ratings
        ratings = FighterRatings(fighter_id=fighter_id)
        self._ratings_cache[fighter_id] = ratings
        return ratings

    def save_fighter_ratings(self, ratings: FighterRatings) -> None:
        """Save fighter ratings to file."""
        filepath = self.ratings_dir / f"{ratings.fighter_id}.json"
        with open(filepath, "w") as f:
            json.dump(ratings.to_dict(), f, indent=2)
        self._ratings_cache[ratings.fighter_id] = ratings

    def save_all_ratings(self) -> None:
        """Save all cached ratings to files."""
        for ratings in self._ratings_cache.values():
            self.save_fighter_ratings(ratings)

    def process_fight(
        self,
        fight: Fight,
        fight_date: date,
        current_date: Optional[date] = None,
        base_k: float = DEFAULT_K_FACTOR,
    ) -> tuple[FighterRatings, FighterRatings]:
        """
        Process a fight and update both fighters' ratings.

        Args:
            fight: Fight data
            fight_date: Date of the fight
            current_date: Current date for recency weighting (default: fight_date)
            base_k: Base K-factor for updates

        Returns:
            Tuple of (fighter1_ratings, fighter2_ratings) after update
        """
        if current_date is None:
            current_date = fight_date

        # Get current ratings
        f1_ratings = self.get_fighter_ratings(fight.fighter1_id)
        f2_ratings = self.get_fighter_ratings(fight.fighter2_id)

        # Extract dimension scores for each fighter
        f1_scores = extract_dimension_scores(
            fight,
            fight.fighter1_id,
            fight.fighter1_stats,
            fight.fighter2_stats,
        )
        f2_scores = extract_dimension_scores(
            fight,
            fight.fighter2_id,
            fight.fighter2_stats,
            fight.fighter1_stats,
        )

        # Update each dimension
        for f1_score, f2_score in zip(f1_scores, f2_scores):
            dim = f1_score.dimension

            # Get current ratings for this dimension
            r1 = f1_ratings.get_rating(dim)
            r2 = f2_ratings.get_rating(dim)

            # Calculate expected scores
            exp1 = expected_score(r1, r2)
            exp2 = 1.0 - exp1

            # Calculate K-factor with adjustments
            k1 = dynamic_k_factor(
                base_k,
                f1_ratings.ratings[dim].games_played,
                r1,
            )
            k2 = dynamic_k_factor(
                base_k,
                f2_ratings.ratings[dim].games_played,
                r2,
            )

            # Apply recency weighting
            k1 = get_k_factor_with_recency(k1, fight_date, current_date)
            k2 = get_k_factor_with_recency(k2, fight_date, current_date)

            # Apply finish multiplier (KO/Sub transfer more rating)
            finish_mult = finish_multiplier(
                fight.method,
                fight.round_finished,
                fight.scheduled_rounds or 3,
            )
            k1 *= finish_mult
            k2 *= finish_mult

            # Weight by dimension score weight
            k1 *= f1_score.weight
            k2 *= f2_score.weight

            # Calculate new ratings
            new_r1 = calculate_new_rating(r1, exp1, f1_score.fighter_score, k1)
            new_r2 = calculate_new_rating(r2, exp2, f2_score.fighter_score, k2)

            # Update ratings
            f1_ratings.update_rating(dim, new_r1, fight_date)
            f2_ratings.update_rating(dim, new_r2, fight_date)

            # Record updates
            self._update_history.append(RatingUpdate(
                fight_id=fight.fight_id,
                fight_date=fight_date,
                fighter_id=fight.fighter1_id,
                opponent_id=fight.fighter2_id,
                dimension=dim,
                old_rating=r1,
                new_rating=new_r1,
                expected_score=exp1,
                actual_score=f1_score.fighter_score,
            ))

        # Update fight counts and last fight date
        f1_ratings.total_fights += 1
        f2_ratings.total_fights += 1
        f1_ratings.last_fight_date = fight_date
        f2_ratings.last_fight_date = fight_date

        # Track KO losses for chin degradation
        method = (fight.method or "").upper()
        if "KO" in method or "TKO" in method:
            if fight.winner_id == fight.fighter1_id:
                f2_ratings.ko_losses += 1
            elif fight.winner_id == fight.fighter2_id:
                f1_ratings.ko_losses += 1

        # Cache updated ratings
        self._ratings_cache[fight.fighter1_id] = f1_ratings
        self._ratings_cache[fight.fighter2_id] = f2_ratings

        return f1_ratings, f2_ratings

    def apply_adjustments(
        self,
        fighter_id: str,
        birth_date: Optional[date] = None,
        current_date: Optional[date] = None,
    ) -> FighterRatings:
        """
        Apply decay and adjustment factors to a fighter's ratings.

        Args:
            fighter_id: Fighter ID
            birth_date: Fighter's date of birth (for age adjustment)
            current_date: Current date

        Returns:
            Updated ratings
        """
        if current_date is None:
            current_date = date.today()

        ratings = self.get_fighter_ratings(fighter_id)

        # Apply inactivity decay
        ratings = apply_inactivity_decay(ratings, current_date)

        # Apply chin degradation
        ratings = apply_chin_degradation(ratings)

        # Note: Age adjustment is applied at prediction time, not stored

        self._ratings_cache[fighter_id] = ratings
        return ratings

    def get_comparison(
        self,
        fighter1_id: str,
        fighter2_id: str,
    ) -> dict:
        """
        Get a comparison of two fighters' ratings.

        Args:
            fighter1_id: First fighter ID
            fighter2_id: Second fighter ID

        Returns:
            Dict with rating comparison data
        """
        r1 = self.get_fighter_ratings(fighter1_id)
        r2 = self.get_fighter_ratings(fighter2_id)

        comparison = {
            "fighter1_id": fighter1_id,
            "fighter2_id": fighter2_id,
            "dimensions": {},
        }

        for dim in SkillDimension:
            rating1 = r1.get_rating(dim)
            rating2 = r2.get_rating(dim)
            diff = rating1 - rating2

            comparison["dimensions"][dim.value] = {
                "fighter1": rating1,
                "fighter2": rating2,
                "difference": diff,
                "advantage": "fighter1" if diff > 0 else "fighter2" if diff < 0 else "even",
            }

        comparison["fighter1_average"] = r1.get_average_rating()
        comparison["fighter2_average"] = r2.get_average_rating()
        comparison["overall_difference"] = (
            comparison["fighter1_average"] - comparison["fighter2_average"]
        )

        return comparison

    def get_update_history(self) -> list[RatingUpdate]:
        """Get the history of rating updates."""
        return self._update_history.copy()

    def clear_cache(self) -> None:
        """Clear the in-memory ratings cache."""
        self._ratings_cache.clear()

    def reset(self) -> None:
        """Reset rating system to initial state (for backtesting)."""
        self._ratings_cache.clear()
        self._update_history.clear()

    def get_all_ratings(self) -> dict[str, FighterRatings]:
        """Get all cached ratings."""
        return self._ratings_cache.copy()


class HistoricalReplay:
    """
    Processor for replaying historical fights to build ratings.

    Processes fights chronologically to establish fighter ratings
    based on their historical performance.
    """

    def __init__(
        self,
        rating_system: RatingSystem,
        data_storage: Optional[DataStorage] = None,
    ):
        """
        Initialize the replay processor.

        Args:
            rating_system: RatingSystem to update
            data_storage: DataStorage for loading fights
        """
        self.rating_system = rating_system
        self.data_storage = data_storage or rating_system.data_storage

    def replay_all(
        self,
        save_interval: int = 100,
        current_date: Optional[date] = None,
    ) -> dict:
        """
        Replay all historical fights in chronological order.

        Args:
            save_interval: Save ratings every N fights
            current_date: Current date for recency weighting

        Returns:
            Dict with replay statistics
        """
        if current_date is None:
            current_date = date.today()

        # Load all events and sort by date
        events = self.data_storage.load_all_events()
        events_with_dates = [(e, e.event_date) for e in events if e.event_date]
        events_with_dates.sort(key=lambda x: x[1])

        logger.info(f"Replaying {len(events_with_dates)} events...")

        fights_processed = 0
        fighters_seen = set()

        for event, event_date in events_with_dates:
            # Load fights for this event
            for fight_id in event.fight_ids:
                fight = self.data_storage.load_fight(fight_id)
                if fight is None:
                    continue

                # Process the fight
                try:
                    self.rating_system.process_fight(
                        fight,
                        fight_date=event_date,
                        current_date=current_date,
                    )
                    fights_processed += 1
                    fighters_seen.add(fight.fighter1_id)
                    fighters_seen.add(fight.fighter2_id)

                    if fights_processed % save_interval == 0:
                        logger.info(f"Processed {fights_processed} fights...")
                        self.rating_system.save_all_ratings()

                except Exception as e:
                    logger.error(f"Error processing fight {fight_id}: {e}")

        # Final save
        self.rating_system.save_all_ratings()

        logger.info(f"Replay complete: {fights_processed} fights, {len(fighters_seen)} fighters")

        return {
            "fights_processed": fights_processed,
            "fighters_rated": len(fighters_seen),
            "events_processed": len(events_with_dates),
        }

    def replay_from_date(
        self,
        start_date: date,
        current_date: Optional[date] = None,
    ) -> dict:
        """
        Replay fights from a specific date onwards.

        Useful for updating ratings after new events.

        Args:
            start_date: Only process fights from this date onwards
            current_date: Current date for recency weighting

        Returns:
            Dict with replay statistics
        """
        if current_date is None:
            current_date = date.today()

        events = self.data_storage.load_all_events()
        events_with_dates = [
            (e, e.event_date)
            for e in events
            if e.event_date and e.event_date >= start_date
        ]
        events_with_dates.sort(key=lambda x: x[1])

        logger.info(f"Replaying {len(events_with_dates)} events from {start_date}...")

        fights_processed = 0

        for event, event_date in events_with_dates:
            for fight_id in event.fight_ids:
                fight = self.data_storage.load_fight(fight_id)
                if fight is None:
                    continue

                try:
                    self.rating_system.process_fight(
                        fight,
                        fight_date=event_date,
                        current_date=current_date,
                    )
                    fights_processed += 1
                except Exception as e:
                    logger.error(f"Error processing fight {fight_id}: {e}")

        self.rating_system.save_all_ratings()

        return {
            "fights_processed": fights_processed,
            "events_processed": len(events_with_dates),
        }
