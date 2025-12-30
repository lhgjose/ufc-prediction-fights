"""Command-line interface for UFC scraper."""

import argparse
import sys

from .scraper import UFCScraper
from .storage import DataStorage


def main():
    """Run the scraper CLI."""
    parser = argparse.ArgumentParser(description="Scrape UFC data from UFCStats.com")
    parser.add_argument(
        "command",
        choices=["full", "events", "fights", "fighters", "stats"],
        help="Command to run",
    )
    parser.add_argument(
        "--all-time",
        action="store_true",
        help="Include pre-USADA era (before July 2015)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape even if data exists",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--event-id",
        help="Specific event ID to scrape (for 'fights' command)",
    )

    args = parser.parse_args()

    storage = DataStorage()
    scraper = UFCScraper(storage=storage, delay_seconds=args.delay)
    skip_existing = not args.force
    usada_only = not args.all_time

    if args.command == "stats":
        stats = storage.get_stats()
        print(f"Events:   {stats['events']}")
        print(f"Fights:   {stats['fights']}")
        print(f"Fighters: {stats['fighters']}")
        return

    if args.command == "full":
        result = scraper.full_scrape(usada_only=usada_only)
        print(f"Scraped {result['new_events']} events, {result['new_fights']} fights, "
              f"{result['new_fighters']} fighters")
        print(f"Total: {result['total']}")

    elif args.command == "events":
        events = scraper.scrape_all_events(usada_only=usada_only, skip_existing=skip_existing)
        print(f"Scraped {len(events)} events")

    elif args.command == "fights":
        if args.event_id:
            event = storage.load_event(args.event_id)
            if not event:
                print(f"Event {args.event_id} not found. Run 'events' first.")
                sys.exit(1)
            fights = scraper.scrape_fights_for_event(event, skip_existing=skip_existing)
            print(f"Scraped {len(fights)} fights for event {event.name}")
        else:
            # Scrape fights for all events
            total = 0
            for event in storage.load_all_events():
                fights = scraper.scrape_fights_for_event(event, skip_existing=skip_existing)
                total += len(fights)
            print(f"Scraped {total} fights")

    elif args.command == "fighters":
        fighters = scraper.scrape_fighters_from_fights(skip_existing=skip_existing)
        print(f"Scraped {len(fighters)} fighters")


if __name__ == "__main__":
    main()
