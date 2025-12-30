"""Command-line interface for rating system."""

import argparse
import json
from datetime import date

from ..scraper.storage import DataStorage
from .models import SkillDimension
from .system import HistoricalReplay, RatingSystem


def main():
    """Run the rating system CLI."""
    parser = argparse.ArgumentParser(description="UFC fighter rating system")
    parser.add_argument(
        "command",
        choices=["replay", "show", "compare", "stats"],
        help="Command to run",
    )
    parser.add_argument(
        "--fighter",
        help="Fighter ID for 'show' command",
    )
    parser.add_argument(
        "--fighter1",
        help="First fighter ID for 'compare' command",
    )
    parser.add_argument(
        "--fighter2",
        help="Second fighter ID for 'compare' command",
    )
    parser.add_argument(
        "--save-interval",
        type=int,
        default=100,
        help="Save ratings every N fights during replay (default: 100)",
    )
    parser.add_argument(
        "--gender",
        choices=["male", "female", "all"],
        default="all",
        help="Filter by gender for 'stats' command (default: all)",
    )
    parser.add_argument(
        "--min-fights",
        type=int,
        default=5,
        help="Minimum UFC fights for 'stats' command (default: 5)",
    )

    args = parser.parse_args()

    storage = DataStorage()
    rating_system = RatingSystem(data_storage=storage)

    if args.command == "replay":
        print("Starting historical replay...")
        replay = HistoricalReplay(rating_system, storage)
        result = replay.replay_all(save_interval=args.save_interval)
        print(f"Processed {result['fights_processed']} fights")
        print(f"Rated {result['fighters_rated']} fighters")
        print(f"From {result['events_processed']} events")

    elif args.command == "show":
        if not args.fighter:
            print("Error: --fighter required for 'show' command")
            return

        ratings = rating_system.get_fighter_ratings(args.fighter)
        fighter = storage.load_fighter(args.fighter)
        fighter_name = fighter.name if fighter else args.fighter

        print(f"Fighter: {fighter_name}")
        print(f"ID: {args.fighter}")
        print(f"Total fights: {ratings.total_fights}")
        print(f"KO losses: {ratings.ko_losses}")
        print(f"Last fight: {ratings.last_fight_date}")
        print(f"Average rating: {ratings.get_average_rating():.1f}")
        print("\nDimension ratings:")
        for dim in SkillDimension:
            r = ratings.ratings[dim]
            print(f"  {dim.value:20s}: {r.rating:7.1f} ({r.games_played} games)")

    elif args.command == "compare":
        if not args.fighter1 or not args.fighter2:
            print("Error: --fighter1 and --fighter2 required for 'compare' command")
            return

        fighter1 = storage.load_fighter(args.fighter1)
        fighter2 = storage.load_fighter(args.fighter2)
        f1_name = fighter1.name if fighter1 else args.fighter1
        f2_name = fighter2.name if fighter2 else args.fighter2

        comparison = rating_system.get_comparison(args.fighter1, args.fighter2)
        print(f"Fighter 1: {f1_name} (avg: {comparison['fighter1_average']:.1f})")
        print(f"Fighter 2: {f2_name} (avg: {comparison['fighter2_average']:.1f})")
        print(f"Overall difference: {comparison['overall_difference']:+.1f}")
        print("\nDimension breakdown:")
        for dim, data in comparison["dimensions"].items():
            diff = data["difference"]
            adv = "=" if data["advantage"] == "even" else ("1" if diff > 0 else "2")
            print(f"  {dim:20s}: {data['fighter1']:7.1f} vs {data['fighter2']:7.1f} ({diff:+6.1f}) [{adv}]")

    elif args.command == "stats":
        # Show overall rating system stats
        from pathlib import Path

        ratings_dir = storage.data_dir / "ratings"
        if not ratings_dir.exists():
            print("No ratings data found. Run 'replay' first.")
            return

        # Load all fighters for name lookup and gender filtering
        all_fighters = {f.fighter_id: f for f in storage.load_all_fighters()}

        rating_files = list(ratings_dir.glob("*.json"))
        print(f"Total rated fighters: {len(rating_files)}")

        if rating_files:
            # Load all and show distribution
            all_ratings = []
            for f in rating_files:
                with open(f) as fp:
                    data = json.load(fp)

                fighter_id = data["fighter_id"]
                total_fights = data["total_fights"]

                # Apply minimum fights filter
                if total_fights < args.min_fights:
                    continue

                # Apply gender filter
                fighter = all_fighters.get(fighter_id)
                if args.gender != "all" and fighter:
                    if fighter.gender != args.gender:
                        continue

                avg = sum(
                    r["rating"] for r in data["ratings"].values()
                ) / len(data["ratings"])

                fighter_name = fighter.name if fighter else fighter_id
                all_ratings.append((fighter_id, fighter_name, avg, total_fights))

            all_ratings.sort(key=lambda x: x[2], reverse=True)

            gender_label = f" ({args.gender})" if args.gender != "all" else ""
            print(f"\nFiltered fighters{gender_label}: {len(all_ratings)} (min {args.min_fights} fights)")

            print(f"\nTop 10 rated fighters{gender_label}:")
            for fighter_id, name, avg, fights in all_ratings[:10]:
                print(f"  {name:<25s} {avg:7.1f} ({fights} fights)")

            print(f"\nBottom 10 rated fighters{gender_label}:")
            for fighter_id, name, avg, fights in all_ratings[-10:]:
                print(f"  {name:<25s} {avg:7.1f} ({fights} fights)")


if __name__ == "__main__":
    main()
