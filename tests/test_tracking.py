"""Tests for the performance tracking system."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from ufc_predictor.predictor.models import (
    MethodPrediction,
    Prediction,
    PredictionMethod,
    RoundPrediction,
)
from ufc_predictor.tracking import (
    ActualResult,
    LoggedPrediction,
    PerformanceStats,
    PerformanceTracker,
)
from ufc_predictor.tracking.models import PredictionOutcome


class TestLoggedPrediction:
    """Test LoggedPrediction model."""

    def test_to_dict_and_from_dict(self):
        """Serialization should round-trip correctly."""
        pred = LoggedPrediction(
            prediction_id="abc123",
            fight_id="fight1",
            event_name="UFC 300",
            fighter1_id="f1",
            fighter2_id="f2",
            fighter1_name="Fighter One",
            fighter2_name="Fighter Two",
            predicted_winner_id="f1",
            predicted_method="KO/TKO",
            predicted_round=2,
            prediction_timestamp=datetime(2024, 1, 15, 12, 0, 0),
            scheduled_rounds=3,
            fighter1_avg_rating=1600.0,
            fighter2_avg_rating=1500.0,
            rating_differential=100.0,
        )

        data = pred.to_dict()
        restored = LoggedPrediction.from_dict(data)

        assert restored.prediction_id == pred.prediction_id
        assert restored.fighter1_name == pred.fighter1_name
        assert restored.predicted_method == pred.predicted_method
        assert restored.predicted_round == pred.predicted_round
        assert restored.rating_differential == pred.rating_differential


class TestActualResult:
    """Test ActualResult model."""

    def test_to_dict_and_from_dict(self):
        """Serialization should round-trip correctly."""
        result = ActualResult(
            fight_id="fight1",
            actual_winner_id="f1",
            actual_method="KO/TKO",
            actual_round=2,
            result_timestamp=datetime(2024, 1, 15, 14, 0, 0),
        )

        data = result.to_dict()
        restored = ActualResult.from_dict(data)

        assert restored.fight_id == result.fight_id
        assert restored.actual_winner_id == result.actual_winner_id
        assert restored.actual_method == result.actual_method
        assert restored.actual_round == result.actual_round


class TestPerformanceTracker:
    """Test PerformanceTracker class."""

    @pytest.fixture
    def temp_tracker(self):
        """Create a tracker with temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(data_dir=Path(tmpdir))
            yield tracker

    def test_log_prediction(self, temp_tracker):
        """Logging a prediction should store it."""
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            fighter1_name="Fighter One",
            fighter2_name="Fighter Two",
            winner_id="f1",
            winner_name="Fighter One",
            fighter1_avg_rating=1600.0,
            fighter2_avg_rating=1500.0,
            rating_differential=100.0,
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

        logged = temp_tracker.log_prediction(prediction, event_name="UFC 300")

        assert logged.prediction_id is not None
        assert logged.fighter1_name == "Fighter One"
        assert logged.predicted_winner_id == "f1"
        assert logged.predicted_method == "KO/TKO"
        assert logged.predicted_round == 2
        assert logged.event_name == "UFC 300"

    def test_record_result(self, temp_tracker):
        """Recording a result should store it."""
        result = temp_tracker.record_result(
            fight_id="fight1",
            winner_id="f1",
            method="KO/TKO",
            round_num=2,
        )

        assert result.fight_id == "fight1"
        assert result.actual_winner_id == "f1"
        assert result.actual_method == "KO/TKO"

    def test_evaluate_correct_prediction(self, temp_tracker):
        """Correct prediction should be marked as correct."""
        # Log prediction
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            winner_id="f1",
            method=MethodPrediction(method=PredictionMethod.KO_TKO, confidence="high"),
            round_prediction=RoundPrediction(round_number=2, is_decision=False, scheduled_rounds=3),
        )
        logged = temp_tracker.log_prediction(prediction, fight_id="fight1")

        # Record matching result
        temp_tracker.record_result(
            fight_id="fight1",
            winner_id="f1",
            method="KO/TKO",
            round_num=2,
        )

        # Evaluate
        result = temp_tracker.evaluate_prediction(logged.prediction_id)

        assert result.outcome == PredictionOutcome.CORRECT
        assert result.winner_correct is True
        assert result.method_correct is True
        assert result.round_correct is True

    def test_evaluate_wrong_winner(self, temp_tracker):
        """Wrong winner prediction should be marked as incorrect."""
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            winner_id="f1",  # Predicted f1
            method=MethodPrediction(method=PredictionMethod.KO_TKO, confidence="high"),
            round_prediction=RoundPrediction(round_number=2, is_decision=False, scheduled_rounds=3),
        )
        logged = temp_tracker.log_prediction(prediction, fight_id="fight1")

        # f2 actually won
        temp_tracker.record_result(
            fight_id="fight1",
            winner_id="f2",
            method="Submission",
            round_num=3,
        )

        result = temp_tracker.evaluate_prediction(logged.prediction_id)

        assert result.outcome == PredictionOutcome.INCORRECT
        assert result.winner_correct is False

    def test_evaluate_round_within_one(self, temp_tracker):
        """Round prediction within 1 round should be correct."""
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            winner_id="f1",
            method=MethodPrediction(method=PredictionMethod.KO_TKO, confidence="high"),
            round_prediction=RoundPrediction(round_number=2, is_decision=False, scheduled_rounds=3),
        )
        logged = temp_tracker.log_prediction(prediction, fight_id="fight1")

        # Actual round was 3 (within 1 of predicted 2)
        temp_tracker.record_result(
            fight_id="fight1",
            winner_id="f1",
            method="KO/TKO",
            round_num=3,
        )

        result = temp_tracker.evaluate_prediction(logged.prediction_id)

        assert result.round_correct is True

    def test_calculate_stats(self, temp_tracker):
        """Stats calculation should be accurate."""
        # Log 3 predictions
        for i in range(3):
            prediction = Prediction(
                fighter1_id=f"f{i}a",
                fighter2_id=f"f{i}b",
                winner_id=f"f{i}a",
                fighter1_avg_rating=1600.0,
                fighter2_avg_rating=1500.0,
                rating_differential=100.0,
                method=MethodPrediction(method=PredictionMethod.DECISION, confidence="medium"),
                round_prediction=RoundPrediction(round_number=None, is_decision=True, scheduled_rounds=3),
            )
            temp_tracker.log_prediction(prediction, fight_id=f"fight{i}")

        # Record results: 2 correct, 1 incorrect
        temp_tracker.record_result("fight0", winner_id="f0a", method="Decision")  # Correct
        temp_tracker.record_result("fight1", winner_id="f1a", method="Decision")  # Correct
        temp_tracker.record_result("fight2", winner_id="f2b", method="KO/TKO", round_num=1)  # Wrong

        stats = temp_tracker.calculate_stats()

        assert stats.total_predictions == 3
        assert stats.resolved_predictions == 3
        assert stats.winner_correct == 2
        assert stats.winner_incorrect == 1
        assert stats.winner_accuracy == pytest.approx(66.67, rel=0.01)

    def test_persistence(self, temp_tracker):
        """Data should persist across tracker instances."""
        # Log a prediction
        prediction = Prediction(
            fighter1_id="f1",
            fighter2_id="f2",
            winner_id="f1",
            method=MethodPrediction(method=PredictionMethod.KO_TKO, confidence="high"),
            round_prediction=RoundPrediction(round_number=2, is_decision=False, scheduled_rounds=3),
        )
        logged = temp_tracker.log_prediction(prediction, event_name="Test Event")

        # Create new tracker with same directory
        new_tracker = PerformanceTracker(data_dir=temp_tracker.data_dir)

        # Should have the prediction
        recent = new_tracker.get_recent_predictions(10)
        assert len(recent) == 1
        assert recent[0].prediction_id == logged.prediction_id


class TestPerformanceStats:
    """Test PerformanceStats calculations."""

    def test_calculate_percentages(self):
        """Percentages should calculate correctly."""
        stats = PerformanceStats(
            winner_correct=8,
            winner_incorrect=2,
            method_correct=6,
            method_incorrect=2,
            round_correct=4,
            round_incorrect=2,
        )

        stats.calculate_percentages()

        assert stats.winner_accuracy == 80.0
        assert stats.method_accuracy == 75.0
        assert stats.round_accuracy == pytest.approx(66.67, rel=0.01)

    def test_zero_division_safe(self):
        """Should handle zero counts without error."""
        stats = PerformanceStats()
        stats.calculate_percentages()

        assert stats.winner_accuracy == 0.0
        assert stats.method_accuracy == 0.0
        assert stats.round_accuracy == 0.0
