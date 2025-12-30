"""Main scraper orchestration for UFCStats.com."""

import logging
import string
from datetime import date
from typing import Optional

from .client import UFCStatsClient
from .models import Event, Fight, Fighter
from .parsers import (
    parse_event_details,
    parse_events_list,
    parse_fight_details,
    parse_fighter_details,
    parse_fighters_list,
)
from .storage import DataStorage

# USADA era start date (July 1, 2015)
USADA_START_DATE = date(2015, 7, 1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UFCScraper:
    """Main scraper for UFCStats.com data."""

    def __init__(
        self,
        storage: Optional[DataStorage] = None,
        client: Optional[UFCStatsClient] = None,
        delay_seconds: float = 1.0,
    ):
        """Initialize scraper with storage and HTTP client."""
        self.storage = storage or DataStorage()
        self.client = client or UFCStatsClient(delay_seconds=delay_seconds)

    def scrape_all_events(self, usada_only: bool = True, skip_existing: bool = True) -> list[Event]:
        """
        Scrape all completed UFC events.

        Args:
            usada_only: Only scrape events from USADA era (July 2015+)
            skip_existing: Skip events that already exist in storage

        Returns:
            List of scraped Event objects
        """
        logger.info("Fetching events list...")
        events = []
        page = 1

        while True:
            soup = self.client.get_events_page(page)
            event_tuples = parse_events_list(soup)

            if not event_tuples:
                break

            for event_id, event_name, event_date in event_tuples:
                # Filter by USADA era
                if usada_only and event_date and event_date < USADA_START_DATE:
                    logger.info(f"Stopping at pre-USADA event: {event_name} ({event_date})")
                    return events

                # Skip if exists
                if skip_existing and self.storage.event_exists(event_id):
                    logger.debug(f"Skipping existing event: {event_name}")
                    continue

                # Scrape event details
                try:
                    event = self.scrape_event(event_id)
                    events.append(event)
                    logger.info(f"Scraped event: {event.name} ({len(event.fight_ids)} fights)")
                except Exception as e:
                    logger.error(f"Failed to scrape event {event_id}: {e}")

            page += 1

        return events

    def scrape_event(self, event_id: str) -> Event:
        """Scrape a single event and save it."""
        soup = self.client.get_event_details(event_id)
        event = parse_event_details(soup, event_id)
        self.storage.save_event(event)
        return event

    def scrape_fights_for_event(
        self, event: Event, skip_existing: bool = True
    ) -> list[Fight]:
        """
        Scrape all fights for an event.

        Args:
            event: Event object with fight_ids
            skip_existing: Skip fights that already exist in storage

        Returns:
            List of scraped Fight objects
        """
        fights = []

        for fight_id in event.fight_ids:
            if skip_existing and self.storage.fight_exists(fight_id):
                logger.debug(f"Skipping existing fight: {fight_id}")
                continue

            try:
                fight = self.scrape_fight(fight_id, event.event_id)
                fights.append(fight)
                logger.info(f"Scraped fight: {fight.fighter1_id} vs {fight.fighter2_id}")
            except Exception as e:
                logger.error(f"Failed to scrape fight {fight_id}: {e}")

        return fights

    def scrape_fight(self, fight_id: str, event_id: str) -> Fight:
        """Scrape a single fight and save it."""
        soup = self.client.get_fight_details(fight_id)
        fight = parse_fight_details(soup, fight_id, event_id)
        self.storage.save_fight(fight)
        return fight

    def scrape_all_fighters(self, skip_existing: bool = True) -> list[Fighter]:
        """
        Scrape all fighters from A-Z listings.

        Args:
            skip_existing: Skip fighters that already exist in storage

        Returns:
            List of scraped Fighter objects
        """
        fighters = []

        for char in string.ascii_lowercase:
            logger.info(f"Fetching fighters starting with '{char.upper()}'...")
            try:
                soup = self.client.get_fighters_page(char)
                fighter_tuples = parse_fighters_list(soup)

                for fighter_id, fighter_name in fighter_tuples:
                    if skip_existing and self.storage.fighter_exists(fighter_id):
                        logger.debug(f"Skipping existing fighter: {fighter_name}")
                        continue

                    try:
                        fighter = self.scrape_fighter(fighter_id)
                        fighters.append(fighter)
                        logger.info(f"Scraped fighter: {fighter.name}")
                    except Exception as e:
                        logger.error(f"Failed to scrape fighter {fighter_id}: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch fighters for '{char}': {e}")

        return fighters

    def scrape_fighter(self, fighter_id: str) -> Fighter:
        """Scrape a single fighter and save."""
        soup = self.client.get_fighter_details(fighter_id)
        fighter = parse_fighter_details(soup, fighter_id)
        self.storage.save_fighter(fighter)
        return fighter

    def scrape_fighters_from_fights(self, skip_existing: bool = True) -> list[Fighter]:
        """
        Scrape fighters referenced in existing fight data.

        More efficient than scraping all fighters if you only need
        fighters who have actually fought.

        Args:
            skip_existing: Skip fighters that already exist in storage

        Returns:
            List of scraped Fighter objects
        """
        # Get unique fighter IDs from fights
        fighter_ids = set()
        for fight in self.storage.load_all_fights():
            if fight.fighter1_id:
                fighter_ids.add(fight.fighter1_id)
            if fight.fighter2_id:
                fighter_ids.add(fight.fighter2_id)

        logger.info(f"Found {len(fighter_ids)} unique fighters in fight data")

        fighters = []
        for fighter_id in fighter_ids:
            if skip_existing and self.storage.fighter_exists(fighter_id):
                continue

            try:
                fighter = self.scrape_fighter(fighter_id)
                fighters.append(fighter)
                logger.info(f"Scraped fighter: {fighter.name}")
            except Exception as e:
                logger.error(f"Failed to scrape fighter {fighter_id}: {e}")

        return fighters

    def full_scrape(self, usada_only: bool = True) -> dict:
        """
        Perform a full scrape of events, fights, and fighters.

        Args:
            usada_only: Only scrape USADA era (July 2015+)

        Returns:
            Dict with counts of scraped items
        """
        logger.info("Starting full scrape...")

        # 1. Scrape all events
        events = self.scrape_all_events(usada_only=usada_only)
        logger.info(f"Scraped {len(events)} new events")

        # 2. Scrape fights for each event
        all_fights = []
        for event in self.storage.load_all_events():
            fights = self.scrape_fights_for_event(event)
            all_fights.extend(fights)
        logger.info(f"Scraped {len(all_fights)} new fights")

        # 3. Scrape fighters from fights
        fighters = self.scrape_fighters_from_fights()
        logger.info(f"Scraped {len(fighters)} new fighters")

        stats = self.storage.get_stats()
        logger.info(f"Total data: {stats}")

        return {
            "new_events": len(events),
            "new_fights": len(all_fights),
            "new_fighters": len(fighters),
            "total": stats,
        }
