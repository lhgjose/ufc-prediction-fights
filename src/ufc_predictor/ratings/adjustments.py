"""Rating adjustments: decay, chin degradation, age factors."""

import math
from datetime import date
from typing import Optional

from .models import DEFAULT_RATING, FighterRatings, SkillDimension


# Inactivity decay settings
DECAY_START_MONTHS = 12  # Start decay after 12 months of inactivity
DECAY_RATE_PER_MONTH = 0.005  # 0.5% decay per month toward mean
MAX_DECAY_MONTHS = 36  # Cap decay at 36 months

# Chin degradation settings
CHIN_DEGRADATION_PER_KO = 25  # Rating points lost per KO loss
CHIN_MAX_DEGRADATION = 100  # Maximum total degradation from KO losses

# Age adjustment settings
AGE_DECLINE_START = 35  # Start age decline at 35
AGE_DECLINE_RATE = 0.01  # 1% per year after 35
AGE_MAX_DECLINE = 0.10  # Maximum 10% decline from age


def calculate_inactivity_decay(
    rating: float,
    last_fight_date: Optional[date],
    current_date: date,
    target_rating: float = DEFAULT_RATING,
) -> float:
    """
    Calculate rating decay due to inactivity.

    Ratings decay toward the mean (target_rating) when a fighter
    hasn't competed for a long time.

    Args:
        rating: Current rating
        last_fight_date: Date of last fight
        current_date: Current date for comparison
        target_rating: Rating to decay toward (default: 1500)

    Returns:
        New rating after decay
    """
    if last_fight_date is None:
        return rating

    # Calculate months since last fight
    days_inactive = (current_date - last_fight_date).days
    months_inactive = days_inactive / 30.44  # Average days per month

    if months_inactive < DECAY_START_MONTHS:
        return rating

    # Calculate decay months (capped)
    decay_months = min(months_inactive - DECAY_START_MONTHS, MAX_DECAY_MONTHS)

    # Decay toward target rating
    decay_factor = 1.0 - (DECAY_RATE_PER_MONTH * decay_months)
    decay_factor = max(0.5, decay_factor)  # Cap at 50% decay

    # Move toward target
    diff = rating - target_rating
    new_rating = target_rating + (diff * decay_factor)

    return new_rating


def apply_inactivity_decay(
    ratings: FighterRatings,
    current_date: date,
) -> FighterRatings:
    """
    Apply inactivity decay to all dimensions of a fighter's ratings.

    Args:
        ratings: Fighter's current ratings
        current_date: Current date

    Returns:
        Updated ratings with decay applied
    """
    if ratings.last_fight_date is None:
        return ratings

    for dim in SkillDimension:
        current = ratings.get_rating(dim)
        decayed = calculate_inactivity_decay(
            current,
            ratings.last_fight_date,
            current_date,
        )
        if decayed != current:
            ratings.ratings[dim].rating = decayed

    return ratings


def calculate_chin_degradation(ko_losses: int) -> float:
    """
    Calculate rating penalty for chin degradation due to KO losses.

    Fighters who have been knocked out may have reduced ability
    to take damage in future fights.

    Args:
        ko_losses: Number of KO/TKO losses

    Returns:
        Rating penalty to apply to striking defense
    """
    degradation = ko_losses * CHIN_DEGRADATION_PER_KO
    return min(degradation, CHIN_MAX_DEGRADATION)


def apply_chin_degradation(
    ratings: FighterRatings,
) -> FighterRatings:
    """
    Apply chin degradation penalty to striking defense rating.

    Args:
        ratings: Fighter's current ratings

    Returns:
        Updated ratings with chin degradation applied
    """
    if ratings.ko_losses == 0:
        return ratings

    penalty = calculate_chin_degradation(ratings.ko_losses)
    current = ratings.get_rating(SkillDimension.STRIKING_DEFENSE)

    # Apply penalty but don't go below minimum
    new_rating = max(1000.0, current - penalty)
    ratings.ratings[SkillDimension.STRIKING_DEFENSE].rating = new_rating

    return ratings


def calculate_age_factor(
    birth_date: Optional[date],
    current_date: date,
) -> float:
    """
    Calculate age-based adjustment factor.

    Fighters over 35 may experience declining physical attributes.

    Args:
        birth_date: Fighter's date of birth
        current_date: Current date

    Returns:
        Multiplier for ratings (1.0 = no adjustment, <1.0 = decline)
    """
    if birth_date is None:
        return 1.0

    age = (current_date - birth_date).days / 365.25

    if age < AGE_DECLINE_START:
        return 1.0

    years_over = age - AGE_DECLINE_START
    decline = min(years_over * AGE_DECLINE_RATE, AGE_MAX_DECLINE)

    return 1.0 - decline


def apply_age_adjustment(
    ratings: FighterRatings,
    birth_date: Optional[date],
    current_date: date,
    dimensions: Optional[list[SkillDimension]] = None,
) -> FighterRatings:
    """
    Apply age-based adjustment to physical skill dimensions.

    Args:
        ratings: Fighter's current ratings
        birth_date: Fighter's date of birth
        current_date: Current date
        dimensions: Which dimensions to adjust (default: physical ones)

    Returns:
        Updated ratings with age adjustment
    """
    if birth_date is None:
        return ratings

    factor = calculate_age_factor(birth_date, current_date)
    if factor >= 1.0:
        return ratings

    # Default: adjust physical dimensions only
    if dimensions is None:
        dimensions = [
            SkillDimension.KNOCKOUT_POWER,
            SkillDimension.STRIKING_VOLUME,
            SkillDimension.CARDIO,
            SkillDimension.WRESTLING_OFFENSE,
        ]

    for dim in dimensions:
        current = ratings.get_rating(dim)
        # Adjust toward mean based on age factor
        diff = current - DEFAULT_RATING
        adjusted = DEFAULT_RATING + (diff * factor)
        ratings.ratings[dim].rating = adjusted

    return ratings


def calculate_recency_weight(
    fight_date: date,
    current_date: date,
    half_life_days: int = 365,
) -> float:
    """
    Calculate recency weight for a fight using exponential decay.

    More recent fights have more weight in determining current skill.

    Args:
        fight_date: Date of the fight
        current_date: Current date
        half_life_days: Days until weight is halved (default: 1 year)

    Returns:
        Weight between 0 and 1
    """
    days_ago = (current_date - fight_date).days
    if days_ago <= 0:
        return 1.0

    # Exponential decay with half-life
    decay_constant = math.log(2) / half_life_days
    weight = math.exp(-decay_constant * days_ago)

    return max(0.1, weight)  # Minimum weight of 10%


def get_k_factor_with_recency(
    base_k: float,
    fight_date: date,
    current_date: date,
) -> float:
    """
    Adjust K-factor based on fight recency.

    During historical replay, older fights should have somewhat
    less impact on current ratings.

    Args:
        base_k: Base K-factor
        fight_date: Date of the fight
        current_date: Date we're calculating ratings for

    Returns:
        Adjusted K-factor
    """
    recency = calculate_recency_weight(fight_date, current_date)

    # Scale K-factor by recency, but keep minimum of 50% K
    return base_k * max(0.5, recency)
