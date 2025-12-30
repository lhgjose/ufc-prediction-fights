"""Tests for UFC scraper module."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from ufc_predictor.scraper import DataStorage, Event, Fight, FightStats, Fighter
from ufc_predictor.scraper.parsers import (
    _parse_height,
    _parse_percentage,
    _parse_reach,
    _parse_record,
    _parse_weight,
)


class TestParsers:
    """Test parsing utility functions."""

    def test_parse_height(self):
        assert _parse_height("6' 4\"") == 76
        assert _parse_height("5' 11\"") == 71
        assert _parse_height("--") is None
        assert _parse_height("") is None

    def test_parse_weight(self):
        assert _parse_weight("185 lbs.") == 185
        assert _parse_weight("265 lbs") == 265
        assert _parse_weight("--") is None

    def test_parse_reach(self):
        assert _parse_reach("84\"") == 84
        assert _parse_reach("72") == 72
        assert _parse_reach("--") is None

    def test_parse_percentage(self):
        assert _parse_percentage("52%") == 0.52
        assert _parse_percentage("100%") == 1.0
        assert _parse_percentage("--") is None

    def test_parse_record(self):
        assert _parse_record("22-5-0") == (22, 5, 0, 0)
        assert _parse_record("15-3-1") == (15, 3, 1, 0)
        assert _parse_record("20-6-0 (1 NC)") == (20, 6, 0, 1)
        assert _parse_record("") == (0, 0, 0, 0)


class TestDataStorage:
    """Test data storage operations."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield DataStorage(Path(tmpdir))

    def test_save_load_fighter(self, temp_storage):
        fighter = Fighter(
            fighter_id="abc123",
            name="Test Fighter",
            nickname="The Test",
            height_inches=72,
            weight_lbs=185,
            reach_inches=76,
            stance="Orthodox",
            dob=date(1990, 5, 15),
            record_wins=20,
            record_losses=5,
            record_draws=0,
            slpm=4.5,
            str_acc=0.52,
        )

        temp_storage.save_fighter(fighter)
        loaded = temp_storage.load_fighter("abc123")

        assert loaded is not None
        assert loaded.fighter_id == fighter.fighter_id
        assert loaded.name == fighter.name
        assert loaded.dob == fighter.dob
        assert loaded.slpm == fighter.slpm

    def test_save_load_event(self, temp_storage):
        event = Event(
            event_id="event123",
            name="UFC 300",
            event_date=date(2024, 4, 13),
            location="Las Vegas, Nevada",
            fight_ids=["fight1", "fight2", "fight3"],
        )

        temp_storage.save_event(event)
        loaded = temp_storage.load_event("event123")

        assert loaded is not None
        assert loaded.event_id == event.event_id
        assert loaded.name == event.name
        assert loaded.event_date == event.event_date
        assert loaded.fight_ids == event.fight_ids

    def test_save_load_fight(self, temp_storage):
        stats1 = FightStats(
            fighter_id="fighter1",
            knockdowns=1,
            sig_strikes_landed=87,
            sig_strikes_attempted=150,
        )
        stats2 = FightStats(
            fighter_id="fighter2",
            knockdowns=0,
            sig_strikes_landed=45,
            sig_strikes_attempted=98,
        )

        fight = Fight(
            fight_id="fight123",
            event_id="event123",
            fighter1_id="fighter1",
            fighter2_id="fighter2",
            winner_id="fighter1",
            weight_class="Middleweight",
            is_title_fight=True,
            method="KO/TKO",
            round_finished=3,
            time_finished="4:32",
            scheduled_rounds=5,
            fighter1_stats=stats1,
            fighter2_stats=stats2,
        )

        temp_storage.save_fight(fight)
        loaded = temp_storage.load_fight("fight123")

        assert loaded is not None
        assert loaded.fight_id == fight.fight_id
        assert loaded.winner_id == fight.winner_id
        assert loaded.fighter1_stats.knockdowns == 1
        assert loaded.fighter2_stats.sig_strikes_landed == 45

    def test_get_stats(self, temp_storage):
        # Empty initially
        stats = temp_storage.get_stats()
        assert stats["fighters"] == 0
        assert stats["fights"] == 0
        assert stats["events"] == 0

        # Add some data
        temp_storage.save_fighter(Fighter(fighter_id="f1", name="Fighter 1"))
        temp_storage.save_fighter(Fighter(fighter_id="f2", name="Fighter 2"))
        temp_storage.save_event(Event(event_id="e1", name="Event 1"))

        stats = temp_storage.get_stats()
        assert stats["fighters"] == 2
        assert stats["events"] == 1

    def test_exists_methods(self, temp_storage):
        assert not temp_storage.fighter_exists("nonexistent")
        assert not temp_storage.event_exists("nonexistent")
        assert not temp_storage.fight_exists("nonexistent")

        temp_storage.save_fighter(Fighter(fighter_id="f1", name="Test"))
        assert temp_storage.fighter_exists("f1")
