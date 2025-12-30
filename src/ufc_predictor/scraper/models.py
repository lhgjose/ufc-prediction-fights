"""Data models for UFC scraper."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Fighter:
    """UFC fighter profile."""

    fighter_id: str
    name: str
    nickname: Optional[str] = None
    height_inches: Optional[int] = None
    weight_lbs: Optional[int] = None
    reach_inches: Optional[int] = None
    stance: Optional[str] = None  # Orthodox, Southpaw, Switch
    dob: Optional[date] = None
    gender: Optional[str] = None  # "male" or "female"
    record_wins: int = 0
    record_losses: int = 0
    record_draws: int = 0
    record_nc: int = 0
    slpm: Optional[float] = None  # Significant strikes landed per minute
    str_acc: Optional[float] = None  # Striking accuracy %
    sapm: Optional[float] = None  # Significant strikes absorbed per minute
    str_def: Optional[float] = None  # Striking defense %
    td_avg: Optional[float] = None  # Takedowns per 15 min
    td_acc: Optional[float] = None  # Takedown accuracy %
    td_def: Optional[float] = None  # Takedown defense %
    sub_avg: Optional[float] = None  # Submissions per 15 min


@dataclass
class FightStats:
    """Per-fighter stats for a single fight."""

    fighter_id: str
    knockdowns: int = 0
    sig_strikes_landed: int = 0
    sig_strikes_attempted: int = 0
    total_strikes_landed: int = 0
    total_strikes_attempted: int = 0
    takedowns_landed: int = 0
    takedowns_attempted: int = 0
    sub_attempts: int = 0
    reversals: int = 0
    control_time_seconds: int = 0
    # Per-round breakdown
    round_stats: list[dict] = field(default_factory=list)


@dataclass
class Fight:
    """A single UFC fight."""

    fight_id: str
    event_id: str
    fighter1_id: str
    fighter2_id: str
    winner_id: Optional[str] = None  # None for draw/NC
    weight_class: Optional[str] = None
    is_title_fight: bool = False
    is_main_event: bool = False
    method: Optional[str] = None  # KO/TKO, Submission, Decision, etc.
    method_detail: Optional[str] = None  # Rear Naked Choke, Unanimous, etc.
    round_finished: Optional[int] = None
    time_finished: Optional[str] = None  # "4:32"
    scheduled_rounds: int = 3
    referee: Optional[str] = None
    fighter1_stats: Optional[FightStats] = None
    fighter2_stats: Optional[FightStats] = None


@dataclass
class Event:
    """A UFC event."""

    event_id: str
    name: str
    event_date: Optional[date] = None
    location: Optional[str] = None
    fight_ids: list[str] = field(default_factory=list)
