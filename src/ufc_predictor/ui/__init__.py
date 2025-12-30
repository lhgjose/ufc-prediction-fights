"""Streamlit web UI."""

from .state import get_predictor, get_rating_system, get_storage, load_fighters_list

__all__ = [
    "get_storage",
    "get_rating_system",
    "get_predictor",
    "load_fighters_list",
]
