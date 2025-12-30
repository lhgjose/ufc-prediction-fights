"""Command-line interface for performance tracking."""

import argparse

from .tracker import PerformanceTracker


def main():
    """Run the tracking CLI."""
    parser = argparse.ArgumentParser(description="UFC prediction performance tracking")
    parser.add_argument(
        "command",
        choices=["stats", "report", "recent", "sync"],
        help="Command to run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent predictions to show (default: 10)",
    )

    args = parser.parse_args()
    tracker = PerformanceTracker()

    if args.command == "stats":
        stats = tracker.calculate_stats()
        print(f"Total predictions: {stats.total_predictions}")
        print(f"Resolved: {stats.resolved_predictions}")
        print(f"Pending: {stats.pending_predictions}")
        print()
        print(f"Winner accuracy: {stats.winner_accuracy:.1f}%")
        print(f"Method accuracy: {stats.method_accuracy:.1f}%")
        print(f"Round accuracy: {stats.round_accuracy:.1f}%")

    elif args.command == "report":
        print(tracker.generate_report())

    elif args.command == "recent":
        predictions = tracker.get_recent_predictions(args.limit)
        if not predictions:
            print("No predictions logged yet.")
            return

        print(f"Recent {len(predictions)} predictions:")
        print("-" * 60)
        for pred in predictions:
            f1 = pred.fighter1_name or pred.fighter1_id
            f2 = pred.fighter2_name or pred.fighter2_id
            winner = pred.fighter1_name if pred.predicted_winner_id == pred.fighter1_id else pred.fighter2_name
            winner = winner or pred.predicted_winner_id

            method = pred.predicted_method or "N/A"
            round_str = f"Rd {pred.predicted_round}" if pred.predicted_round else "Dec"

            timestamp = pred.prediction_timestamp.strftime("%Y-%m-%d %H:%M") if pred.prediction_timestamp else "N/A"

            print(f"{f1} vs {f2}")
            print(f"  Prediction: {winner} via {method} ({round_str})")
            print(f"  Logged: {timestamp}")
            if pred.event_name:
                print(f"  Event: {pred.event_name}")
            print()

    elif args.command == "sync":
        # Sync results from scraped fight data
        from ..scraper import DataStorage

        storage = DataStorage()
        fights = storage.load_all_fights()

        synced = 0
        for fight in fights:
            if fight.winner_id or fight.method in ["Draw", "NC"]:
                result = tracker.record_result_from_fight(fight)
                if result:
                    synced += 1

        print(f"Synced {synced} fight results from scraped data.")


if __name__ == "__main__":
    main()
