"""Skill dimension extraction and scoring from fight data."""

from dataclasses import dataclass
from typing import Optional

from ..scraper.models import Fight, FightStats
from .models import SkillDimension


@dataclass
class DimensionScore:
    """Score for a dimension in a specific fight."""

    dimension: SkillDimension
    fighter_score: float  # 0.0 to 1.0, how well fighter performed in this dimension
    weight: float = 1.0  # How much to weight this dimension in the update


def _safe_ratio(numerator: int, denominator: int, default: float = 0.5) -> float:
    """Safely calculate a ratio, returning default if denominator is 0."""
    if denominator == 0:
        return default
    return numerator / denominator


def extract_dimension_scores(
    fight: Fight,
    fighter_id: str,
    fighter_stats: Optional[FightStats],
    opponent_stats: Optional[FightStats],
) -> list[DimensionScore]:
    """
    Extract dimension-specific scores from a fight.

    Each score represents how well the fighter performed in that dimension,
    relative to their opponent. Scores are 0.0-1.0 where:
    - 1.0 = dominant performance
    - 0.5 = even
    - 0.0 = dominated

    Args:
        fight: The fight data
        fighter_id: ID of the fighter we're scoring
        fighter_stats: Stats for the fighter (may be None)
        opponent_stats: Stats for the opponent (may be None)

    Returns:
        List of dimension scores
    """
    scores = []
    is_winner = fight.winner_id == fighter_id
    base_score = 1.0 if is_winner else 0.0

    # If no detailed stats, use simplified scoring based on outcome
    if fighter_stats is None or opponent_stats is None:
        return _scores_from_outcome_only(fight, fighter_id, is_winner)

    # KNOCKOUT_POWER: Based on KO/TKO wins and knockdowns
    ko_score = _calculate_ko_power_score(fight, fighter_id, is_winner, fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.KNOCKOUT_POWER, ko_score))

    # STRIKING_VOLUME: Based on significant strikes landed
    volume_score = _calculate_striking_volume_score(fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.STRIKING_VOLUME, volume_score))

    # STRIKING_DEFENSE: Based on strikes absorbed vs attempted against
    defense_score = _calculate_striking_defense_score(fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.STRIKING_DEFENSE, defense_score))

    # WRESTLING_OFFENSE: Based on takedowns landed
    td_offense_score = _calculate_wrestling_offense_score(fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.WRESTLING_OFFENSE, td_offense_score))

    # WRESTLING_DEFENSE: Based on opponent's takedown success rate
    td_defense_score = _calculate_wrestling_defense_score(fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.WRESTLING_DEFENSE, td_defense_score))

    # SUBMISSION_OFFENSE: Based on sub attempts and submission wins
    sub_offense_score = _calculate_submission_offense_score(
        fight, fighter_id, is_winner, fighter_stats, opponent_stats
    )
    scores.append(DimensionScore(SkillDimension.SUBMISSION_OFFENSE, sub_offense_score))

    # SUBMISSION_DEFENSE: Based on escaping opponent's sub attempts
    sub_defense_score = _calculate_submission_defense_score(
        fight, fighter_id, is_winner, opponent_stats
    )
    scores.append(DimensionScore(SkillDimension.SUBMISSION_DEFENSE, sub_defense_score))

    # CARDIO: Based on performance in later rounds (if available)
    cardio_score = _calculate_cardio_score(fight, is_winner, fighter_stats)
    scores.append(DimensionScore(SkillDimension.CARDIO, cardio_score))

    # PRESSURE: Based on control time and overall dominance
    pressure_score = _calculate_pressure_score(fighter_stats, opponent_stats)
    scores.append(DimensionScore(SkillDimension.PRESSURE, pressure_score))

    # ADAPTABILITY: Based on winning close fights, comebacks, experience
    adaptability_score = _calculate_adaptability_score(fight, is_winner)
    scores.append(DimensionScore(SkillDimension.ADAPTABILITY, adaptability_score))

    return scores


def _scores_from_outcome_only(
    fight: Fight,
    fighter_id: str,
    is_winner: bool,
) -> list[DimensionScore]:
    """Generate scores when we only have outcome data, no detailed stats."""
    scores = []
    base = 0.7 if is_winner else 0.3  # Moderate adjustment based on outcome

    # Give more weight to relevant dimensions based on method
    method = (fight.method or "").upper()

    for dim in SkillDimension:
        weight = 0.5  # Lower weight when we don't have stats
        score = base

        if "KO" in method or "TKO" in method:
            if dim == SkillDimension.KNOCKOUT_POWER:
                score = 1.0 if is_winner else 0.0
                weight = 1.0
            elif dim == SkillDimension.STRIKING_DEFENSE:
                score = 0.0 if not is_winner else 0.7
                weight = 0.8

        elif "SUB" in method:
            if dim == SkillDimension.SUBMISSION_OFFENSE:
                score = 1.0 if is_winner else 0.0
                weight = 1.0
            elif dim == SkillDimension.SUBMISSION_DEFENSE:
                score = 0.0 if not is_winner else 0.7
                weight = 0.8

        elif "DEC" in method:
            # Decision implies went the distance
            if dim == SkillDimension.CARDIO:
                score = 0.6 if is_winner else 0.4
                weight = 0.7

        scores.append(DimensionScore(dim, score, weight))

    return scores


def _calculate_ko_power_score(
    fight: Fight,
    fighter_id: str,
    is_winner: bool,
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate knockout power score."""
    method = (fight.method or "").upper()

    # Big bonus for KO/TKO win
    if is_winner and ("KO" in method or "TKO" in method):
        return 1.0

    # Penalty for being KO'd
    if not is_winner and ("KO" in method or "TKO" in method):
        return 0.0

    # Otherwise, base on knockdowns
    kd_landed = fighter_stats.knockdowns
    kd_received = opponent_stats.knockdowns

    if kd_landed > kd_received:
        return 0.7 + min(0.2, kd_landed * 0.1)
    elif kd_landed < kd_received:
        return 0.3 - min(0.2, kd_received * 0.1)
    else:
        return 0.5


def _calculate_striking_volume_score(
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate striking volume score based on significant strikes landed."""
    f_landed = fighter_stats.sig_strikes_landed
    o_landed = opponent_stats.sig_strikes_landed
    total = f_landed + o_landed

    if total == 0:
        return 0.5

    # Score based on share of strikes landed
    share = f_landed / total
    # Scale to 0.2-0.8 range, then adjust based on dominance
    return 0.2 + (share * 0.6) + (0.2 if share > 0.6 else 0.0)


def _calculate_striking_defense_score(
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate striking defense score."""
    # Defense is about how many of opponent's strikes were avoided
    opp_attempted = opponent_stats.sig_strikes_attempted
    opp_landed = opponent_stats.sig_strikes_landed

    if opp_attempted == 0:
        return 0.5

    defense_rate = 1.0 - (opp_landed / opp_attempted)
    # Scale: 50% defense = 0.5 score, 70% = 0.7, etc.
    return max(0.1, min(0.9, defense_rate))


def _calculate_wrestling_offense_score(
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate wrestling offense score based on takedowns."""
    td_landed = fighter_stats.takedowns_landed
    td_attempted = fighter_stats.takedowns_attempted
    opp_td_landed = opponent_stats.takedowns_landed

    # Takedown success rate
    success_rate = _safe_ratio(td_landed, td_attempted, 0.0)

    # Compare to opponent
    total_td = td_landed + opp_td_landed
    if total_td == 0:
        # No takedowns in fight - neutral
        return 0.5

    td_share = td_landed / total_td

    # Combine success rate and share
    return (success_rate * 0.4) + (td_share * 0.6)


def _calculate_wrestling_defense_score(
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate wrestling defense score."""
    opp_td_landed = opponent_stats.takedowns_landed
    opp_td_attempted = opponent_stats.takedowns_attempted

    if opp_td_attempted == 0:
        # Opponent didn't try takedowns - slightly positive
        return 0.55

    defense_rate = 1.0 - _safe_ratio(opp_td_landed, opp_td_attempted, 0.0)
    return max(0.1, min(0.9, defense_rate))


def _calculate_submission_offense_score(
    fight: Fight,
    fighter_id: str,
    is_winner: bool,
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate submission offense score."""
    method = (fight.method or "").upper()

    # Big bonus for submission win
    if is_winner and "SUB" in method:
        return 1.0

    # Base on sub attempts
    sub_attempts = fighter_stats.sub_attempts
    opp_sub_attempts = opponent_stats.sub_attempts

    if sub_attempts == 0 and opp_sub_attempts == 0:
        return 0.5

    total = sub_attempts + opp_sub_attempts
    share = sub_attempts / total if total > 0 else 0.5

    return 0.3 + (share * 0.4)


def _calculate_submission_defense_score(
    fight: Fight,
    fighter_id: str,
    is_winner: bool,
    opponent_stats: FightStats,
) -> float:
    """Calculate submission defense score."""
    method = (fight.method or "").upper()

    # Getting submitted is worst case
    if not is_winner and "SUB" in method:
        return 0.0

    # Surviving sub attempts is good
    opp_sub_attempts = opponent_stats.sub_attempts
    if opp_sub_attempts == 0:
        return 0.55  # No sub threats - slightly positive

    # More sub attempts survived = better defense
    return min(0.9, 0.5 + (opp_sub_attempts * 0.1))


def _calculate_cardio_score(
    fight: Fight,
    is_winner: bool,
    fighter_stats: FightStats,
) -> float:
    """Calculate cardio score based on late-fight performance."""
    scheduled = fight.scheduled_rounds
    finished_round = fight.round_finished

    # If fight went to decision, both fighters showed cardio
    if fight.method and "DEC" in fight.method.upper():
        return 0.65 if is_winner else 0.45

    # Early finish
    if finished_round and finished_round <= 2:
        if is_winner:
            return 0.55  # Finished early, cardio untested
        else:
            return 0.4  # Got finished early

    # Late finish (round 3+)
    if finished_round and finished_round >= 3:
        if is_winner:
            return 0.75  # Strong late
        else:
            return 0.35  # Faded

    return 0.5


def _calculate_pressure_score(
    fighter_stats: FightStats,
    opponent_stats: FightStats,
) -> float:
    """Calculate pressure score based on control time and output."""
    f_control = fighter_stats.control_time_seconds
    o_control = opponent_stats.control_time_seconds
    total_control = f_control + o_control

    control_share = 0.5
    if total_control > 0:
        control_share = f_control / total_control

    # Also factor in total strikes as pressure indicator
    f_total = fighter_stats.total_strikes_landed
    o_total = opponent_stats.total_strikes_landed
    total_strikes = f_total + o_total

    strike_share = 0.5
    if total_strikes > 0:
        strike_share = f_total / total_strikes

    # Weight control more heavily
    return (control_share * 0.6) + (strike_share * 0.4)


def _calculate_adaptability_score(
    fight: Fight,
    is_winner: bool,
) -> float:
    """Calculate adaptability/fight IQ score."""
    method = (fight.method or "").upper()

    # Decision wins show adaptability (outpointed opponent)
    if is_winner and "DEC" in method:
        if "SPLIT" in method:
            return 0.7  # Close fight, showed ability to edge it
        return 0.65

    # Finishing fights also shows adaptability
    if is_winner:
        return 0.6

    # Losses
    if "DEC" in method:
        if "SPLIT" in method:
            return 0.45  # Close loss
        return 0.4

    return 0.35  # Got finished
