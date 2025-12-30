"""HTTP client for UFCStats.com scraping."""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://ufcstats.com"

# Default headers to mimic browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class UFCStatsClient:
    """HTTP client with rate limiting for UFCStats.com."""

    def __init__(self, delay_seconds: float = 0.1):
        """Initialize client with rate limiting delay."""
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay_seconds
        self._last_request_time: Optional[float] = None

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str) -> BeautifulSoup:
        """Fetch URL and return parsed BeautifulSoup object."""
        self._rate_limit()
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.content, "lxml")

    def get_events_page(self, page: int = 1) -> BeautifulSoup:
        """Get completed events listing page."""
        url = f"{BASE_URL}/statistics/events/completed?page={page}"
        return self.get(url)

    def get_event_details(self, event_id: str) -> BeautifulSoup:
        """Get single event details page."""
        url = f"{BASE_URL}/event-details/{event_id}"
        return self.get(url)

    def get_fight_details(self, fight_id: str) -> BeautifulSoup:
        """Get single fight details page."""
        url = f"{BASE_URL}/fight-details/{fight_id}"
        return self.get(url)

    def get_fighters_page(self, char: str) -> BeautifulSoup:
        """Get fighters listing by first letter of last name."""
        url = f"{BASE_URL}/statistics/fighters?char={char}&page=all"
        return self.get(url)

    def get_fighter_details(self, fighter_id: str) -> BeautifulSoup:
        """Get single fighter details page."""
        url = f"{BASE_URL}/fighter-details/{fighter_id}"
        return self.get(url)
