"""Tests for the prediction engine."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from ufc_predictor.predictor import (
    FightPredictor,
    Prediction,
    PredictionMethod,
    generate_compact_prediction,
    generate_report,
)
from ufc_predictor.ratings import FighterRatings, RatingSystem, SkillDimension
from ufc_predictor.scraper import DataStorage, Fighter


class TestFightPredictor:
    """Test the FightPredictor class."""

    @pytest.fixture
    def temp_predictor(self):
        """Create a predictor with temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DataStorage(Path(tmpdir))
            rating_system = RatingSystem(
                ratings_dir=Path(tmpdir) / "ratings",
                data_storage=storage,
            )
            predictor = FightPredictor(
                rating_system=rating_system,
                storage=storage,
            )
            yield predictor, storage, rating_system

    def test_predict_with_no_fight_history(self, temp_predictor):
        """Prediction should be refused for fighters with no history."""
        predictor, storage, rating_system = temp_predictor

        # Create fighters with no fight history
        fighter1 = Fighter(fighter_id="f1", name="New Fighter 1")
        fighter2 = Fighter(fighter_id="f2", name="New Fighter 2")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.refused is True
        assert "insufficient" in prediction.refusal_reason.lower()

    def test_predict_with_fight_history(self, temp_predictor):
        """Prediction should work for fighters with history."""
        predictor, storage, rating_system = temp_predictor

        # Create fighters
        fighter1 = Fighter(fighter_id="f1", name="Fighter One")
        fighter2 = Fighter(fighter_id="f2", name="Fighter Two")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        # Give them ratings with fight history
        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 5
        ratings1.update_rating(SkillDimension.KNOCKOUT_POWER, 1700, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 5
        ratings2.update_rating(SkillDimension.KNOCKOUT_POWER, 1400, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.refused is False
        assert prediction.winner_id == "f1"  # Higher rated should win
        assert prediction.method is not None
        assert prediction.round_prediction is not None

    def test_predict_close_fight(self, temp_predictor):
        """Close fights should be marked as such."""
        predictor, storage, rating_system = temp_predictor

        # Create evenly matched fighters
        fighter1 = Fighter(fighter_id="f1", name="Fighter One")
        fighter2 = Fighter(fighter_id="f2", name="Fighter Two")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 5
        for dim in SkillDimension:
            ratings1.update_rating(dim, 1510, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 5
        for dim in SkillDimension:
            ratings2.update_rating(dim, 1490, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.refused is False
        assert prediction.is_close_fight is True

    def test_predict_method_ko(self, temp_predictor):
        """High KO power should predict KO/TKO finish."""
        predictor, storage, rating_system = temp_predictor

        fighter1 = Fighter(fighter_id="f1", name="Power Puncher")
        fighter2 = Fighter(fighter_id="f2", name="Glass Chin")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 10
        ratings1.update_rating(SkillDimension.KNOCKOUT_POWER, 1900, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.STRIKING_VOLUME, 1700, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 10
        ratings2.ko_losses = 4  # Chin is compromised
        ratings2.update_rating(SkillDimension.STRIKING_DEFENSE, 1300, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.method.method == PredictionMethod.KO_TKO

    def test_predict_method_submission(self, temp_predictor):
        """High submission offense should predict submission finish."""
        predictor, storage, rating_system = temp_predictor

        fighter1 = Fighter(fighter_id="f1", name="BJJ Ace")
        fighter2 = Fighter(fighter_id="f2", name="No Ground Game")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 10
        ratings1.update_rating(SkillDimension.SUBMISSION_OFFENSE, 1900, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.WRESTLING_OFFENSE, 1700, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 10
        ratings2.update_rating(SkillDimension.SUBMISSION_DEFENSE, 1200, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.method.method == PredictionMethod.SUBMISSION

    def test_dimension_breakdown(self, temp_predictor):
        """Dimension breakdown should identify advantages."""
        predictor, storage, rating_system = temp_predictor

        fighter1 = Fighter(fighter_id="f1", name="Striker")
        fighter2 = Fighter(fighter_id="f2", name="Wrestler")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 10
        ratings1.update_rating(SkillDimension.KNOCKOUT_POWER, 1800, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.WRESTLING_OFFENSE, 1300, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 10
        ratings2.update_rating(SkillDimension.KNOCKOUT_POWER, 1400, date(2024, 1, 1))
        ratings2.update_rating(SkillDimension.WRESTLING_OFFENSE, 1800, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.dimension_breakdown is not None
        assert SkillDimension.KNOCKOUT_POWER in prediction.dimension_breakdown.fighter1_strengths
        assert SkillDimension.WRESTLING_OFFENSE in prediction.dimension_breakdown.fighter2_strengths

    def test_x_factors_chin_vulnerability(self, temp_predictor):
        """X-factors should note chin vulnerability."""
        predictor, storage, rating_system = temp_predictor

        fighter1 = Fighter(fighter_id="f1", name="Chinny Fighter")
        fighter2 = Fighter(fighter_id="f2", name="Normal Fighter")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 10
        ratings1.ko_losses = 4  # Multiple KO losses
        rating_system.save_fighter_ratings(ratings1)

        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 10
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert any("chin" in factor.lower() for factor in prediction.x_factors)


class TestReportGeneration:
    """Test report generation functions."""

    def test_generate_report_refused(self):
        """Refused predictions should generate appropriate report."""
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            fighter1_name="Fighter One",
            fighter2_name="Fighter Two",
            refused=True,
            refusal_reason="Fighter One has insufficient UFC fight history",
        )

        report = generate_report(prediction)

        assert "Fighter One vs Fighter Two" in report
        assert "REFUSED" in report
        assert "insufficient" in report.lower()

    def test_generate_compact_prediction(self):
        """Compact prediction should be one line."""
        from ufc_predictor.predictor.models import MethodPrediction, RoundPrediction

        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            fighter1_name="Fighter One",
            fighter2_name="Fighter Two",
            winner_id="f1",
            winner_name="Fighter One",
            method=MethodPrediction(
                method=PredictionMethod.KO_TKO,
                confidence="high",
            ),
            round_prediction=RoundPrediction(
                round_number=2,
                is_decision=False,
                scheduled_rounds=3,
            ),
        )

        compact = generate_compact_prediction(prediction)

        assert "Fighter One" in compact
        assert "KO/TKO" in compact
        assert "Rd 2" in compact

    def test_generate_compact_decision(self):
        """Compact prediction should handle decisions."""
        from ufc_predictor.predictor.models import MethodPrediction, RoundPrediction

        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            winner_id="f1",
            winner_name="Fighter One",
            method=MethodPrediction(
                method=PredictionMethod.DECISION,
                confidence="medium",
            ),
            round_prediction=RoundPrediction(
                round_number=None,
                is_decision=True,
                scheduled_rounds=3,
            ),
        )

        compact = generate_compact_prediction(prediction)

        assert "Fighter One" in compact
        assert "Decision" in compact


class TestStyleMatchup:
    """Test style matchup analysis."""

    @pytest.fixture
    def temp_predictor(self):
        """Create a predictor with temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DataStorage(Path(tmpdir))
            rating_system = RatingSystem(
                ratings_dir=Path(tmpdir) / "ratings",
                data_storage=storage,
            )
            predictor = FightPredictor(
                rating_system=rating_system,
                storage=storage,
            )
            yield predictor, storage, rating_system

    def test_striker_vs_grappler_detection(self, temp_predictor):
        """Should detect striker vs grappler matchup."""
        predictor, storage, rating_system = temp_predictor

        fighter1 = Fighter(fighter_id="f1", name="Striker")
        fighter2 = Fighter(fighter_id="f2", name="Grappler")
        storage.save_fighter(fighter1)
        storage.save_fighter(fighter2)

        # Fighter 1 is a striker
        ratings1 = rating_system.get_fighter_ratings("f1")
        ratings1.total_fights = 10
        ratings1.update_rating(SkillDimension.KNOCKOUT_POWER, 1700, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.STRIKING_VOLUME, 1700, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.WRESTLING_OFFENSE, 1300, date(2024, 1, 1))
        ratings1.update_rating(SkillDimension.SUBMISSION_OFFENSE, 1300, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings1)

        # Fighter 2 is a grappler
        ratings2 = rating_system.get_fighter_ratings("f2")
        ratings2.total_fights = 10
        ratings2.update_rating(SkillDimension.KNOCKOUT_POWER, 1300, date(2024, 1, 1))
        ratings2.update_rating(SkillDimension.STRIKING_VOLUME, 1300, date(2024, 1, 1))
        ratings2.update_rating(SkillDimension.WRESTLING_OFFENSE, 1700, date(2024, 1, 1))
        ratings2.update_rating(SkillDimension.SUBMISSION_OFFENSE, 1700, date(2024, 1, 1))
        rating_system.save_fighter_ratings(ratings2)

        prediction = predictor.predict("f1", "f2")

        assert prediction.style_matchup is not None
        assert prediction.style_matchup.striker_vs_grappler is not None
