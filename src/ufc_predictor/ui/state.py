"""State management and caching for the Streamlit app."""

import streamlit as st

from ufc_predictor.predictor import FightPredictor
from ufc_predictor.ratings import RatingSystem
from ufc_predictor.scraper import DataStorage
from ufc_predictor.tracking import PerformanceTracker


@st.cache_resource
def get_storage() -> DataStorage:
    """Get or create the DataStorage instance."""
    return DataStorage()


@st.cache_resource
def get_rating_system() -> RatingSystem:
    """Get or create the RatingSystem instance."""
    storage = get_storage()
    return RatingSystem(data_storage=storage)


@st.cache_resource
def get_predictor() -> FightPredictor:
    """Get or create the FightPredictor instance."""
    storage = get_storage()
    rating_system = get_rating_system()
    return FightPredictor(rating_system=rating_system, storage=storage)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_fighters_list() -> list[tuple[str, str]]:
    """
    Load list of all fighters for selection.

    Returns:
        List of (fighter_id, fighter_name) tuples sorted by name.
    """
    storage = get_storage()
    fighters = storage.load_all_fighters()

    # Return as list of tuples (id, name) sorted by name
    return sorted(
        [(f.fighter_id, f.name) for f in fighters],
        key=lambda x: x[1].lower(),
    )


@st.cache_data(ttl=300)
def load_events_list() -> list[tuple[str, str, str]]:
    """
    Load list of all events.

    Returns:
        List of (event_id, event_name, event_date) tuples sorted by date descending.
    """
    storage = get_storage()
    events = storage.load_all_events()

    # Sort by date descending (most recent first)
    events_sorted = sorted(
        events,
        key=lambda e: e.event_date or "",
        reverse=True,
    )

    return [
        (e.event_id, e.name, str(e.event_date) if e.event_date else "Unknown")
        for e in events_sorted
    ]


@st.cache_resource
def get_tracker() -> PerformanceTracker:
    """Get or create the PerformanceTracker instance."""
    return PerformanceTracker()
