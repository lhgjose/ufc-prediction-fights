"""Backtesting script to measure prediction accuracy on historical fights."""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ufc_predictor.predictor import FightPredictor
from ufc_predictor.ratings import RatingSystem
from ufc_predictor.scraper import DataStorage


@dataclass
class BacktestResult:
    """Results from backtesting."""

    total_fights: int = 0
    predicted_fights: int = 0
    skipped_fights: int = 0  # Debut fighters, etc.

    # Winner accuracy
    winner_correct: int = 0
    winner_incorrect: int = 0

    # Method accuracy (when winner correct)
    method_correct: int = 0
    method_incorrect: int = 0

    # Round accuracy (when method correct and not decision)
    round_correct: int = 0  # Within 1 round
    round_incorrect: int = 0

    # By method type
    ko_predictions: int = 0
    ko_correct: int = 0
    sub_predictions: int = 0
    sub_correct: int = 0
    dec_predictions: int = 0
    dec_correct: int = 0

    # Favorite/underdog
    favorite_picks: int = 0
    favorite_correct: int = 0
    underdog_picks: int = 0
    underdog_correct: int = 0

    # Detailed results
    results: list = field(default_factory=list)

    @property
    def winner_accuracy(self) -> float:
        total = self.winner_correct + self.winner_incorrect
        return (self.winner_correct / total * 100) if total > 0 else 0.0

    @property
    def method_accuracy(self) -> float:
        total = self.method_correct + self.method_incorrect
        return (self.method_correct / total * 100) if total > 0 else 0.0

    @property
    def round_accuracy(self) -> float:
        total = self.round_correct + self.round_incorrect
        return (self.round_correct / total * 100) if total > 0 else 0.0


def normalize_method(method: Optional[str]) -> Optional[str]:
    """Normalize method string for comparison."""
    if not method:
        return None
    method = method.upper()
    if "KO" in method or "TKO" in method:
        return "KO/TKO"
    if "SUB" in method:
        return "Submission"
    if "DEC" in method:
        return "Decision"
    return method


def run_backtest(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    verbose: bool = False,
) -> BacktestResult:
    """
    Run backtest on historical fights.

    This replays fights chronologically, making predictions before each fight
    and updating ratings after.

    Args:
        start_date: Only include fights after this date (YYYY-MM-DD)
        end_date: Only include fights before this date (YYYY-MM-DD)
        limit: Maximum number of fights to test
        verbose: Print details for each fight

    Returns:
        BacktestResult with accuracy metrics
    """
    from datetime import date as date_type

    storage = DataStorage()
    rating_system = RatingSystem(data_storage=storage)
    predictor = FightPredictor(rating_system=rating_system, storage=storage)

    # Parse date strings
    start_dt = date_type.fromisoformat(start_date) if start_date else None
    end_dt = date_type.fromisoformat(end_date) if end_date else None

    # Load all events and sort by date
    events = storage.load_all_events()
    events_sorted = sorted(events, key=lambda e: e.event_date or date_type.min)

    # Filter by date range
    if start_dt:
        events_sorted = [e for e in events_sorted if e.event_date and e.event_date >= start_dt]
    if end_dt:
        events_sorted = [e for e in events_sorted if e.event_date and e.event_date <= end_dt]

    result = BacktestResult()
    fights_tested = 0

    # Reset rating system for clean replay
    rating_system.reset()

    for event in events_sorted:
        if limit and fights_tested >= limit:
            break

        # Load fights for this event using fight_ids from event
        for fight_id in event.fight_ids:
            fight = storage.load_fight(fight_id)
            if fight is None:
                continue
            if limit and fights_tested >= limit:
                break

            result.total_fights += 1

            # Skip fights without a winner (draws, NCs)
            if not fight.winner_id:
                result.skipped_fights += 1
                continue

            # Make prediction BEFORE updating ratings
            try:
                prediction = predictor.predict(
                    fight.fighter1_id,
                    fight.fighter2_id,
                    scheduled_rounds=fight.scheduled_rounds or 3,
                )
            except Exception as e:
                if verbose:
                    print(f"Error predicting {fight.fighter1_id} vs {fight.fighter2_id}: {e}")
                result.skipped_fights += 1
                # Still update ratings
                rating_system.process_fight(fight, fight_date=event.event_date)
                continue

            if prediction.refused:
                result.skipped_fights += 1
                # Still update ratings
                rating_system.process_fight(fight, fight_date=event.event_date)
                continue

            result.predicted_fights += 1
            fights_tested += 1

            # Check winner
            winner_correct = prediction.winner_id == fight.winner_id

            if winner_correct:
                result.winner_correct += 1
            else:
                result.winner_incorrect += 1

            # Track favorite/underdog
            is_favorite_pick = (prediction.rating_differential or 0) >= 0
            if is_favorite_pick:
                result.favorite_picks += 1
                if winner_correct:
                    result.favorite_correct += 1
            else:
                result.underdog_picks += 1
                if winner_correct:
                    result.underdog_correct += 1

            # Check method (only if winner correct)
            if winner_correct and prediction.method:
                pred_method = prediction.method.method.value
                actual_method = normalize_method(fight.method)

                method_correct = pred_method == actual_method
                if method_correct:
                    result.method_correct += 1
                else:
                    result.method_incorrect += 1

                # Track by method type
                if pred_method == "KO/TKO":
                    result.ko_predictions += 1
                    if method_correct:
                        result.ko_correct += 1
                elif pred_method == "Submission":
                    result.sub_predictions += 1
                    if method_correct:
                        result.sub_correct += 1
                elif pred_method == "Decision":
                    result.dec_predictions += 1
                    if method_correct:
                        result.dec_correct += 1

                # Check round (only if method correct and not decision)
                if method_correct and prediction.round_prediction and not prediction.round_prediction.is_decision:
                    pred_round = prediction.round_prediction.round_number
                    actual_round = fight.round_finished

                    if pred_round and actual_round:
                        round_correct = abs(pred_round - actual_round) <= 1
                        if round_correct:
                            result.round_correct += 1
                        else:
                            result.round_incorrect += 1

            # Store detailed result
            result.results.append({
                "event": event.name,
                "date": str(event.event_date),
                "fighter1": fight.fighter1_id,
                "fighter2": fight.fighter2_id,
                "predicted_winner": prediction.winner_id,
                "actual_winner": fight.winner_id,
                "winner_correct": winner_correct,
                "predicted_method": prediction.method.method.value if prediction.method else None,
                "actual_method": normalize_method(fight.method),
            })

            if verbose:
                status = "✓" if winner_correct else "✗"
                print(f"{status} {event.name}: {fight.fighter1_id[:8]} vs {fight.fighter2_id[:8]} - "
                      f"Predicted: {prediction.winner_id[:8]}, Actual: {fight.winner_id[:8]}")

            # Update ratings with actual result
            rating_system.process_fight(fight, fight_date=event.event_date)

    return result


def print_report(result: BacktestResult):
    """Print backtest report."""
    print("=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print()
    print(f"Total fights analyzed: {result.total_fights}")
    print(f"Fights predicted: {result.predicted_fights}")
    print(f"Fights skipped: {result.skipped_fights} (debuts, draws, NCs)")
    print()
    print("-" * 40)
    print("WINNER ACCURACY")
    print("-" * 40)
    print(f"Correct: {result.winner_correct}")
    print(f"Incorrect: {result.winner_incorrect}")
    print(f"Accuracy: {result.winner_accuracy:.1f}%")
    print()
    print("-" * 40)
    print("METHOD ACCURACY (when winner correct)")
    print("-" * 40)
    print(f"Correct: {result.method_correct}")
    print(f"Incorrect: {result.method_incorrect}")
    print(f"Accuracy: {result.method_accuracy:.1f}%")
    print()
    print("-" * 40)
    print("ROUND ACCURACY (within 1 round, when method correct)")
    print("-" * 40)
    print(f"Correct: {result.round_correct}")
    print(f"Incorrect: {result.round_incorrect}")
    print(f"Accuracy: {result.round_accuracy:.1f}%")
    print()
    print("-" * 40)
    print("BY METHOD TYPE")
    print("-" * 40)
    print(f"KO/TKO: {result.ko_correct}/{result.ko_predictions} "
          f"({result.ko_correct/result.ko_predictions*100:.1f}%)" if result.ko_predictions else "KO/TKO: 0/0")
    print(f"Submission: {result.sub_correct}/{result.sub_predictions} "
          f"({result.sub_correct/result.sub_predictions*100:.1f}%)" if result.sub_predictions else "Submission: 0/0")
    print(f"Decision: {result.dec_correct}/{result.dec_predictions} "
          f"({result.dec_correct/result.dec_predictions*100:.1f}%)" if result.dec_predictions else "Decision: 0/0")
    print()
    print("-" * 40)
    print("FAVORITE vs UNDERDOG")
    print("-" * 40)
    fav_acc = result.favorite_correct / result.favorite_picks * 100 if result.favorite_picks else 0
    dog_acc = result.underdog_correct / result.underdog_picks * 100 if result.underdog_picks else 0
    print(f"Favorite picks: {result.favorite_correct}/{result.favorite_picks} ({fav_acc:.1f}%)")
    print(f"Underdog picks: {result.underdog_correct}/{result.underdog_picks} ({dog_acc:.1f}%)")
    print()


def main():
    """Run backtest from command line."""
    parser = argparse.ArgumentParser(description="Backtest UFC fight predictions")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="Max fights to test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each prediction")

    args = parser.parse_args()

    print("Running backtest...")
    print()

    result = run_backtest(
        start_date=args.start,
        end_date=args.end,
        limit=args.limit,
        verbose=args.verbose,
    )

    print_report(result)


if __name__ == "__main__":
    main()
