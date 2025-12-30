"""Data storage utilities for JSON flat files."""

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Optional

from .models import Event, Fight, FightStats, Fighter

# Default data directory (relative to project root)
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


class DateEncoder(json.JSONEncoder):
    """JSON encoder that handles date objects."""

    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def _date_decoder(dct: dict) -> dict:
    """Decode ISO date strings back to date objects."""
    for key in ["event_date", "dob"]:
        if key in dct and dct[key] is not None:
            try:
                dct[key] = date.fromisoformat(dct[key])
            except (ValueError, TypeError):
                pass
    return dct


class DataStorage:
    """Handles reading/writing UFC data to JSON files."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize storage with data directory."""
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.fighters_dir = self.data_dir / "fighters"
        self.fights_dir = self.data_dir / "fights"
        self.events_dir = self.data_dir / "events"

        # Ensure directories exist
        for dir_path in [self.fighters_dir, self.fights_dir, self.events_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Fighters
    # -------------------------------------------------------------------------

    def save_fighter(self, fighter: Fighter) -> Path:
        """Save fighter to JSON file."""
        filepath = self.fighters_dir / f"{fighter.fighter_id}.json"
        with open(filepath, "w") as f:
            json.dump(asdict(fighter), f, cls=DateEncoder, indent=2)
        return filepath

    def load_fighter(self, fighter_id: str) -> Optional[Fighter]:
        """Load fighter from JSON file."""
        filepath = self.fighters_dir / f"{fighter_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f, object_hook=_date_decoder)
        return Fighter(**data)

    def load_all_fighters(self) -> list[Fighter]:
        """Load all fighters from data directory."""
        fighters = []
        for filepath in self.fighters_dir.glob("*.json"):
            with open(filepath) as f:
                data = json.load(f, object_hook=_date_decoder)
            fighters.append(Fighter(**data))
        return fighters

    def fighter_exists(self, fighter_id: str) -> bool:
        """Check if fighter data exists."""
        return (self.fighters_dir / f"{fighter_id}.json").exists()

    # -------------------------------------------------------------------------
    # Fights
    # -------------------------------------------------------------------------

    def save_fight(self, fight: Fight) -> Path:
        """Save fight to JSON file."""
        filepath = self.fights_dir / f"{fight.fight_id}.json"
        data = asdict(fight)
        # Handle nested FightStats
        if fight.fighter1_stats:
            data["fighter1_stats"] = asdict(fight.fighter1_stats)
        if fight.fighter2_stats:
            data["fighter2_stats"] = asdict(fight.fighter2_stats)
        with open(filepath, "w") as f:
            json.dump(data, f, cls=DateEncoder, indent=2)
        return filepath

    def load_fight(self, fight_id: str) -> Optional[Fight]:
        """Load fight from JSON file."""
        filepath = self.fights_dir / f"{fight_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f, object_hook=_date_decoder)
        # Reconstruct FightStats objects
        if data.get("fighter1_stats"):
            data["fighter1_stats"] = FightStats(**data["fighter1_stats"])
        if data.get("fighter2_stats"):
            data["fighter2_stats"] = FightStats(**data["fighter2_stats"])
        return Fight(**data)

    def load_all_fights(self) -> list[Fight]:
        """Load all fights from data directory."""
        fights = []
        for filepath in self.fights_dir.glob("*.json"):
            fight = self.load_fight(filepath.stem)
            if fight:
                fights.append(fight)
        return fights

    def fight_exists(self, fight_id: str) -> bool:
        """Check if fight data exists."""
        return (self.fights_dir / f"{fight_id}.json").exists()

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def save_event(self, event: Event) -> Path:
        """Save event to JSON file."""
        filepath = self.events_dir / f"{event.event_id}.json"
        with open(filepath, "w") as f:
            json.dump(asdict(event), f, cls=DateEncoder, indent=2)
        return filepath

    def load_event(self, event_id: str) -> Optional[Event]:
        """Load event from JSON file."""
        filepath = self.events_dir / f"{event_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f, object_hook=_date_decoder)
        return Event(**data)

    def load_all_events(self) -> list[Event]:
        """Load all events from data directory."""
        events = []
        for filepath in self.events_dir.glob("*.json"):
            with open(filepath) as f:
                data = json.load(f, object_hook=_date_decoder)
            events.append(Event(**data))
        return events

    def event_exists(self, event_id: str) -> bool:
        """Check if event data exists."""
        return (self.events_dir / f"{event_id}.json").exists()

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get counts of stored data."""
        return {
            "fighters": len(list(self.fighters_dir.glob("*.json"))),
            "fights": len(list(self.fights_dir.glob("*.json"))),
            "events": len(list(self.events_dir.glob("*.json"))),
        }
