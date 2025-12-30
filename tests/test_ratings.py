"""Tests for the rating system."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from ufc_predictor.ratings import (
    DEFAULT_RATING,
    DimensionRating,
    FighterRatings,
    HistoricalReplay,
    RatingSystem,
    SkillDimension,
    calculate_age_factor,
    calculate_chin_degradation,
    calculate_inactivity_decay,
    calculate_new_rating,
    calculate_recency_weight,
    dynamic_k_factor,
    expected_score,
    update_ratings,
    win_probability,
)
from ufc_predictor.scraper import DataStorage, Event, Fight, FightStats


class TestEloFunctions:
    """Test core Elo calculations."""

    def test_expected_score_equal_ratings(self):
        """Equal ratings should give 0.5 expected score."""
        assert expected_score(1500, 1500) == 0.5

    def test_expected_score_higher_rating(self):
        """Higher rating should give higher expected score."""
        exp = expected_score(1600, 1400)
        assert exp > 0.5
        assert exp < 1.0

    def test_expected_score_lower_rating(self):
        """Lower rating should give lower expected score."""
        exp = expected_score(1400, 1600)
        assert exp < 0.5
        assert exp > 0.0

    def test_expected_score_symmetry(self):
        """Expected scores should sum to 1."""
        exp_a = expected_score(1600, 1400)
        exp_b = expected_score(1400, 1600)
        assert abs(exp_a + exp_b - 1.0) < 0.0001

    def test_calculate_new_rating_win(self):
        """Winner's rating should increase."""
        new = calculate_new_rating(1500, 0.5, 1.0, k_factor=32)
        assert new > 1500

    def test_calculate_new_rating_loss(self):
        """Loser's rating should decrease."""
        new = calculate_new_rating(1500, 0.5, 0.0, k_factor=32)
        assert new < 1500

    def test_calculate_new_rating_expected_result(self):
        """Expected result should cause minimal change."""
        # If expected 0.8 and got 0.8 (as a win), small change
        new = calculate_new_rating(1600, 0.76, 1.0, k_factor=32)
        change = new - 1600
        # Change should be relatively small
        assert abs(change) < 16

    def test_update_ratings_zero_sum(self):
        """Rating changes should be approximately zero-sum."""
        r1, r2 = update_ratings(1500, 1500, 1.0, k_factor=32)
        # Winner gains what loser loses
        change1 = r1 - 1500
        change2 = r2 - 1500
        assert abs(change1 + change2) < 0.01

    def test_win_probability(self):
        """Win probability should match expected score."""
        prob = win_probability(1600, 1400)
        exp = expected_score(1600, 1400)
        assert prob == exp

    def test_dynamic_k_factor_new_fighter(self):
        """New fighters should have higher K-factor."""
        k = dynamic_k_factor(32, games_played=3, rating=1500)
        assert k > 32

    def test_dynamic_k_factor_experienced(self):
        """Experienced high-rated fighters should have lower K-factor."""
        k = dynamic_k_factor(32, games_played=50, rating=1900)
        assert k < 32


class TestAdjustments:
    """Test rating adjustments."""

    def test_inactivity_decay_no_decay_recent(self):
        """No decay for recent fighters."""
        last_fight = date(2024, 1, 1)
        current = date(2024, 6, 1)  # 5 months later
        new_rating = calculate_inactivity_decay(1700, last_fight, current)
        assert new_rating == 1700

    def test_inactivity_decay_with_decay(self):
        """Decay after long inactivity."""
        last_fight = date(2022, 1, 1)
        current = date(2024, 6, 1)  # 2.5 years later
        new_rating = calculate_inactivity_decay(1700, last_fight, current)
        assert new_rating < 1700
        assert new_rating > DEFAULT_RATING  # Should decay toward mean but not below

    def test_inactivity_decay_toward_mean(self):
        """Low rating should decay toward mean (upward)."""
        last_fight = date(2022, 1, 1)
        current = date(2024, 6, 1)
        new_rating = calculate_inactivity_decay(1300, last_fight, current)
        assert new_rating > 1300  # Should move toward 1500

    def test_chin_degradation(self):
        """KO losses should cause chin degradation."""
        penalty = calculate_chin_degradation(2)
        assert penalty == 50  # 25 per KO loss

    def test_chin_degradation_capped(self):
        """Chin degradation should be capped."""
        penalty = calculate_chin_degradation(10)
        assert penalty == 100  # Max 100

    def test_age_factor_young(self):
        """Young fighters should have no age penalty."""
        birth = date(1995, 1, 1)
        current = date(2024, 1, 1)  # Age 29
        factor = calculate_age_factor(birth, current)
        assert factor == 1.0

    def test_age_factor_old(self):
        """Older fighters should have age penalty."""
        birth = date(1980, 1, 1)
        current = date(2024, 1, 1)  # Age 44
        factor = calculate_age_factor(birth, current)
        assert factor < 1.0
        assert factor >= 0.9  # Max 10% decline

    def test_recency_weight_recent(self):
        """Recent fights should have high weight."""
        fight_date = date(2024, 1, 1)
        current = date(2024, 2, 1)  # 1 month ago
        weight = calculate_recency_weight(fight_date, current)
        assert weight > 0.9

    def test_recency_weight_old(self):
        """Old fights should have lower weight."""
        fight_date = date(2020, 1, 1)
        current = date(2024, 1, 1)  # 4 years ago
        weight = calculate_recency_weight(fight_date, current)
        assert weight < 0.5
        assert weight >= 0.1  # Minimum weight


class TestFighterRatings:
    """Test FighterRatings model."""

    def test_default_initialization(self):
        """New fighter should have default ratings for all dimensions."""
        ratings = FighterRatings(fighter_id="test123")
        assert len(ratings.ratings) == len(SkillDimension)
        for dim in SkillDimension:
            assert ratings.get_rating(dim) == DEFAULT_RATING

    def test_update_rating(self):
        """Updating a rating should persist."""
        ratings = FighterRatings(fighter_id="test123")
        ratings.update_rating(SkillDimension.KNOCKOUT_POWER, 1600, date(2024, 1, 1))
        assert ratings.get_rating(SkillDimension.KNOCKOUT_POWER) == 1600

    def test_rating_bounds(self):
        """Ratings should be bounded."""
        ratings = FighterRatings(fighter_id="test123")
        ratings.update_rating(SkillDimension.KNOCKOUT_POWER, 3000)
        assert ratings.get_rating(SkillDimension.KNOCKOUT_POWER) <= 2200

        ratings.update_rating(SkillDimension.KNOCKOUT_POWER, 500)
        assert ratings.get_rating(SkillDimension.KNOCKOUT_POWER) >= 1000

    def test_average_rating(self):
        """Average should be correct."""
        ratings = FighterRatings(fighter_id="test123")
        assert ratings.get_average_rating() == DEFAULT_RATING

    def test_serialization(self):
        """Ratings should serialize and deserialize correctly."""
        ratings = FighterRatings(fighter_id="test123")
        ratings.update_rating(SkillDimension.KNOCKOUT_POWER, 1600, date(2024, 1, 1))
        ratings.ko_losses = 2
        ratings.total_fights = 10

        data = ratings.to_dict()
        restored = FighterRatings.from_dict(data)

        assert restored.fighter_id == ratings.fighter_id
        assert restored.get_rating(SkillDimension.KNOCKOUT_POWER) == 1600
        assert restored.ko_losses == 2
        assert restored.total_fights == 10


class TestRatingSystem:
    """Test the main RatingSystem."""

    @pytest.fixture
    def temp_system(self):
        """Create a temporary rating system."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DataStorage(Path(tmpdir))
            system = RatingSystem(ratings_dir=Path(tmpdir) / "ratings", data_storage=storage)
            yield system, storage

    def test_get_new_fighter(self, temp_system):
        """Getting a new fighter should create default ratings."""
        system, _ = temp_system
        ratings = system.get_fighter_ratings("new_fighter")
        assert ratings.fighter_id == "new_fighter"
        assert ratings.get_average_rating() == DEFAULT_RATING

    def test_process_fight(self, temp_system):
        """Processing a fight should update both fighters."""
        system, storage = temp_system

        fight = Fight(
            fight_id="fight1",
            event_id="event1",
            fighter1_id="fighter_a",
            fighter2_id="fighter_b",
            winner_id="fighter_a",
            method="KO/TKO",
            round_finished=2,
        )

        r1, r2 = system.process_fight(fight, fight_date=date(2024, 1, 1))

        # Winner should have higher ratings in relevant dimensions
        assert r1.get_rating(SkillDimension.KNOCKOUT_POWER) > DEFAULT_RATING
        # Loser's KO losses should be tracked
        assert r2.ko_losses == 1

    def test_save_load_ratings(self, temp_system):
        """Ratings should persist to disk."""
        system, _ = temp_system

        ratings = system.get_fighter_ratings("test_fighter")
        ratings.update_rating(SkillDimension.CARDIO, 1700)
        system.save_fighter_ratings(ratings)

        # Clear cache and reload
        system.clear_cache()
        loaded = system.get_fighter_ratings("test_fighter")

        assert loaded.get_rating(SkillDimension.CARDIO) == 1700

    def test_comparison(self, temp_system):
        """Comparison should show dimension-by-dimension breakdown."""
        system, _ = temp_system

        r1 = system.get_fighter_ratings("fighter1")
        r1.update_rating(SkillDimension.KNOCKOUT_POWER, 1700)
        system._ratings_cache["fighter1"] = r1

        r2 = system.get_fighter_ratings("fighter2")
        r2.update_rating(SkillDimension.WRESTLING_OFFENSE, 1700)
        system._ratings_cache["fighter2"] = r2

        comparison = system.get_comparison("fighter1", "fighter2")

        assert comparison["dimensions"]["knockout_power"]["advantage"] == "fighter1"
        assert comparison["dimensions"]["wrestling_offense"]["advantage"] == "fighter2"
