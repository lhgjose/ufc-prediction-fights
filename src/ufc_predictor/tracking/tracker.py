"""Performance tracker for predictions."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..predictor.models import Prediction
from ..scraper.storage import DataStorage
from .models import (
    ActualResult,
    LoggedPrediction,
    PerformanceStats,
    PredictionOutcome,
    PredictionResult,
)


class PerformanceTracker:
    """Tracks prediction performance over time."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize tracker with data directory."""
        if data_dir is None:
            data_dir = DataStorage().data_dir
        self.data_dir = data_dir
        self.tracking_dir = data_dir / "tracking"
        self.predictions_file = self.tracking_dir / "predictions.json"
        self.results_file = self.tracking_dir / "results.json"

        # Ensure directory exists
        self.tracking_dir.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._predictions: dict[str, LoggedPrediction] = {}
        self._results: dict[str, ActualResult] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load existing predictions and results from disk."""
        if self.predictions_file.exists():
            with open(self.predictions_file) as f:
                data = json.load(f)
                for pred_data in data:
                    pred = LoggedPrediction.from_dict(pred_data)
                    self._predictions[pred.prediction_id] = pred

        if self.results_file.exists():
            with open(self.results_file) as f:
                data = json.load(f)
                for result_data in data:
                    result = ActualResult.from_dict(result_data)
                    self._results[result.fight_id] = result

    def _save_predictions(self) -> None:
        """Save predictions to disk."""
        data = [p.to_dict() for p in self._predictions.values()]
        with open(self.predictions_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_results(self) -> None:
        """Save results to disk."""
        data = [r.to_dict() for r in self._results.values()]
        with open(self.results_file, "w") as f:
            json.dump(data, f, indent=2)

    def log_prediction(
        self,
        prediction: Prediction,
        event_name: Optional[str] = None,
        fight_id: Optional[str] = None,
    ) -> LoggedPrediction:
        """
        Log a prediction for tracking.

        Args:
            prediction: The Prediction object to log
            event_name: Name of the event
            fight_id: UFC fight ID if known

        Returns:
            The LoggedPrediction that was created
        """
        if prediction.refused:
            raise ValueError("Cannot log a refused prediction")

        pred_id = str(uuid.uuid4())[:8]

        logged = LoggedPrediction(
            prediction_id=pred_id,
            fight_id=fight_id,
            event_name=event_name,
            fighter1_id=prediction.fighter1_id,
            fighter2_id=prediction.fighter2_id,
            fighter1_name=prediction.fighter1_name,
            fighter2_name=prediction.fighter2_name,
            predicted_winner_id=prediction.winner_id,
            predicted_method=(
                prediction.method.method.value if prediction.method else None
            ),
            predicted_round=(
                prediction.round_prediction.round_number
                if prediction.round_prediction and not prediction.round_prediction.is_decision
                else None
            ),
            prediction_timestamp=datetime.now(),
            scheduled_rounds=(
                prediction.round_prediction.scheduled_rounds
                if prediction.round_prediction
                else 3
            ),
            confidence_notes="close fight" if prediction.is_close_fight else None,
            fighter1_avg_rating=prediction.fighter1_avg_rating,
            fighter2_avg_rating=prediction.fighter2_avg_rating,
            rating_differential=prediction.rating_differential,
        )

        self._predictions[pred_id] = logged
        self._save_predictions()

        return logged

    def record_result(
        self,
        fight_id: str,
        winner_id: Optional[str],
        method: Optional[str],
        round_num: Optional[int] = None,
        is_draw: bool = False,
        is_no_contest: bool = False,
    ) -> ActualResult:
        """
        Record the actual result of a fight.

        Args:
            fight_id: The fight ID
            winner_id: ID of the winner (None for draw/NC)
            method: Method of victory
            round_num: Round of finish (None for decision)
            is_draw: Whether the fight was a draw
            is_no_contest: Whether the fight was a no contest

        Returns:
            The ActualResult that was created
        """
        result = ActualResult(
            fight_id=fight_id,
            actual_winner_id=winner_id,
            actual_method=method,
            actual_round=round_num,
            is_draw=is_draw,
            is_no_contest=is_no_contest,
            result_timestamp=datetime.now(),
        )

        self._results[fight_id] = result
        self._save_results()

        return result

    def record_result_from_fight(self, fight) -> Optional[ActualResult]:
        """
        Record result from a Fight object (from scraper).

        Args:
            fight: Fight object from scraper

        Returns:
            The ActualResult, or None if fight has no result
        """
        if fight.winner_id is None and fight.method not in ["Draw", "NC"]:
            return None

        # Normalize method
        method = fight.method
        if method:
            if "Decision" in method:
                method = "Decision"
            elif "KO" in method or "TKO" in method:
                method = "KO/TKO"
            elif "Sub" in method:
                method = "Submission"

        return self.record_result(
            fight_id=fight.fight_id,
            winner_id=fight.winner_id,
            method=method,
            round_num=fight.round_finished if method != "Decision" else None,
            is_draw=fight.method == "Draw" if fight.method else False,
            is_no_contest="NC" in (fight.method or ""),
        )

    def evaluate_prediction(self, prediction_id: str) -> Optional[PredictionResult]:
        """
        Evaluate a single prediction against actual result.

        Args:
            prediction_id: ID of the prediction to evaluate

        Returns:
            PredictionResult or None if prediction not found
        """
        if prediction_id not in self._predictions:
            return None

        pred = self._predictions[prediction_id]
        result = PredictionResult(prediction=pred)

        # Find matching result by fight_id or fighter IDs
        actual = None
        if pred.fight_id and pred.fight_id in self._results:
            actual = self._results[pred.fight_id]
        else:
            # Try to find by fighter IDs
            for r in self._results.values():
                # Would need to load fight to check fighter IDs
                pass

        if actual is None:
            result.outcome = PredictionOutcome.PENDING
            return result

        result.actual = actual

        # Handle special cases
        if actual.is_no_contest:
            result.outcome = PredictionOutcome.NO_CONTEST
            return result

        if actual.is_draw:
            result.outcome = PredictionOutcome.INCORRECT
            result.winner_correct = False
            return result

        # Check winner
        result.winner_correct = pred.predicted_winner_id == actual.actual_winner_id

        if result.winner_correct:
            result.outcome = PredictionOutcome.CORRECT

            # Check method
            if pred.predicted_method and actual.actual_method:
                result.method_correct = pred.predicted_method == actual.actual_method

                # Check round (within 1 round counts)
                if (
                    result.method_correct
                    and pred.predicted_round is not None
                    and actual.actual_round is not None
                ):
                    result.round_correct = abs(
                        pred.predicted_round - actual.actual_round
                    ) <= 1
        else:
            result.outcome = PredictionOutcome.INCORRECT

        return result

    def get_all_results(self) -> list[PredictionResult]:
        """Evaluate all predictions and return results."""
        results = []
        for pred_id in self._predictions:
            result = self.evaluate_prediction(pred_id)
            if result:
                results.append(result)
        return results

    def calculate_stats(self) -> PerformanceStats:
        """Calculate aggregate performance statistics."""
        stats = PerformanceStats()
        results = self.get_all_results()

        stats.total_predictions = len(results)

        for result in results:
            pred = result.prediction

            if result.outcome == PredictionOutcome.PENDING:
                stats.pending_predictions += 1
                continue

            if result.outcome in [PredictionOutcome.CANCELLED, PredictionOutcome.NO_CONTEST]:
                continue

            stats.resolved_predictions += 1

            # Track favorite/underdog
            is_favorite_pick = pred.rating_differential >= 0
            if is_favorite_pick:
                stats.favorite_predictions += 1
            else:
                stats.underdog_predictions += 1

            # Winner accuracy
            if result.winner_correct:
                stats.winner_correct += 1
                if is_favorite_pick:
                    stats.favorite_correct += 1
                else:
                    stats.underdog_correct += 1
                    stats.upsets_predicted += 1

                # Method accuracy
                if result.method_correct is True:
                    stats.method_correct += 1
                elif result.method_correct is False:
                    stats.method_incorrect += 1

                # Round accuracy
                if result.round_correct is True:
                    stats.round_correct += 1
                elif result.round_correct is False:
                    stats.round_incorrect += 1

            else:
                stats.winner_incorrect += 1
                if is_favorite_pick:
                    stats.upsets_missed += 1

            # Track by method
            if pred.predicted_method == "KO/TKO":
                stats.ko_predictions += 1
                if result.winner_correct and result.method_correct:
                    stats.ko_correct += 1
            elif pred.predicted_method == "Submission":
                stats.submission_predictions += 1
                if result.winner_correct and result.method_correct:
                    stats.submission_correct += 1
            elif pred.predicted_method == "Decision":
                stats.decision_predictions += 1
                if result.winner_correct and result.method_correct:
                    stats.decision_correct += 1

        stats.calculate_percentages()
        return stats

    def get_recent_predictions(self, limit: int = 10) -> list[LoggedPrediction]:
        """Get most recent predictions."""
        sorted_preds = sorted(
            self._predictions.values(),
            key=lambda p: p.prediction_timestamp or datetime.min,
            reverse=True,
        )
        return sorted_preds[:limit]

    def generate_report(self) -> str:
        """Generate a text report of performance statistics."""
        stats = self.calculate_stats()

        lines = [
            "=" * 50,
            "PREDICTION PERFORMANCE REPORT",
            "=" * 50,
            "",
            f"Total Predictions: {stats.total_predictions}",
            f"Resolved: {stats.resolved_predictions}",
            f"Pending: {stats.pending_predictions}",
            "",
            "WINNER ACCURACY",
            "-" * 30,
            f"Correct: {stats.winner_correct}",
            f"Incorrect: {stats.winner_incorrect}",
            f"Accuracy: {stats.winner_accuracy:.1f}%",
            "",
            "METHOD ACCURACY (when winner correct)",
            "-" * 30,
            f"Correct: {stats.method_correct}",
            f"Incorrect: {stats.method_incorrect}",
            f"Accuracy: {stats.method_accuracy:.1f}%",
            "",
            "ROUND ACCURACY (within 1 round)",
            "-" * 30,
            f"Correct: {stats.round_correct}",
            f"Incorrect: {stats.round_incorrect}",
            f"Accuracy: {stats.round_accuracy:.1f}%",
            "",
            "BY METHOD TYPE",
            "-" * 30,
            f"KO/TKO: {stats.ko_correct}/{stats.ko_predictions}",
            f"Submission: {stats.submission_correct}/{stats.submission_predictions}",
            f"Decision: {stats.decision_correct}/{stats.decision_predictions}",
            "",
            "FAVORITE vs UNDERDOG",
            "-" * 30,
            f"Favorite picks: {stats.favorite_correct}/{stats.favorite_predictions}",
            f"Underdog picks: {stats.underdog_correct}/{stats.underdog_predictions}",
            f"Upsets predicted: {stats.upsets_predicted}",
            f"Upsets missed: {stats.upsets_missed}",
        ]

        return "\n".join(lines)
