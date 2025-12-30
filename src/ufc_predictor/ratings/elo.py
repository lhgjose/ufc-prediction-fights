"""Core Elo rating calculation functions."""

import math
from typing import Tuple

from .models import DEFAULT_K_FACTOR


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Calculate expected score for player A against player B.

    Uses the standard Elo formula:
    E_A = 1 / (1 + 10^((R_B - R_A) / 400))

    Args:
        rating_a: Rating of player A
        rating_b: Rating of player B

    Returns:
        Expected score for A (between 0 and 1)
    """
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))


def calculate_new_rating(
    rating: float,
    expected: float,
    actual: float,
    k_factor: float = DEFAULT_K_FACTOR,
) -> float:
    """
    Calculate new rating after a game.

    Uses the standard Elo formula:
    R'_A = R_A + K * (S_A - E_A)

    Args:
        rating: Current rating
        expected: Expected score (from expected_score function)
        actual: Actual score (1.0 win, 0.5 draw, 0.0 loss)
        k_factor: K-factor controlling rating volatility

    Returns:
        New rating
    """
    return rating + k_factor * (actual - expected)


def calculate_rating_change(
    rating: float,
    expected: float,
    actual: float,
    k_factor: float = DEFAULT_K_FACTOR,
) -> float:
    """
    Calculate the rating change (delta) from a game.

    Args:
        rating: Current rating
        expected: Expected score
        actual: Actual score
        k_factor: K-factor

    Returns:
        Rating change (can be positive or negative)
    """
    return k_factor * (actual - expected)


def update_ratings(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k_factor: float = DEFAULT_K_FACTOR,
) -> Tuple[float, float]:
    """
    Update ratings for both players after a game.

    Args:
        rating_a: Rating of player A
        rating_b: Rating of player B
        score_a: Score for player A (1.0 win, 0.5 draw, 0.0 loss)
        k_factor: K-factor for both players

    Returns:
        Tuple of (new_rating_a, new_rating_b)
    """
    expected_a = expected_score(rating_a, rating_b)
    expected_b = 1.0 - expected_a  # E_B = 1 - E_A

    score_b = 1.0 - score_a  # S_B = 1 - S_A for zero-sum games

    new_rating_a = calculate_new_rating(rating_a, expected_a, score_a, k_factor)
    new_rating_b = calculate_new_rating(rating_b, expected_b, score_b, k_factor)

    return new_rating_a, new_rating_b


def dynamic_k_factor(
    base_k: float,
    games_played: int,
    rating: float,
    provisional_threshold: int = 10,
    high_rating_threshold: float = 1800.0,
) -> float:
    """
    Calculate dynamic K-factor based on experience and rating.

    Higher K for new fighters (more volatile ratings).
    Lower K for experienced, high-rated fighters (more stable).

    Args:
        base_k: Base K-factor
        games_played: Number of rated games played
        rating: Current rating
        provisional_threshold: Number of games before considered established
        high_rating_threshold: Rating above which K is reduced

    Returns:
        Adjusted K-factor
    """
    k = base_k

    # New fighters get higher K (faster rating adjustment)
    if games_played < provisional_threshold:
        k = base_k * 1.5

    # High-rated fighters get lower K (more stable ratings)
    elif rating > high_rating_threshold:
        k = base_k * 0.75

    return k


def win_probability(rating_a: float, rating_b: float) -> float:
    """
    Calculate win probability for player A.

    This is the same as expected_score but with a clearer name
    for prediction purposes.

    Args:
        rating_a: Rating of player A
        rating_b: Rating of player B

    Returns:
        Probability that A beats B (between 0 and 1)
    """
    return expected_score(rating_a, rating_b)


def rating_difference_to_probability(diff: float) -> float:
    """
    Convert a rating difference to win probability.

    Args:
        diff: Rating difference (R_A - R_B)

    Returns:
        Probability of A winning
    """
    return 1.0 / (1.0 + math.pow(10, -diff / 400.0))


def probability_to_rating_difference(prob: float) -> float:
    """
    Convert win probability to expected rating difference.

    Args:
        prob: Win probability (between 0 and 1, exclusive)

    Returns:
        Expected rating difference
    """
    if prob <= 0 or prob >= 1:
        raise ValueError("Probability must be between 0 and 1 (exclusive)")
    return -400.0 * math.log10((1.0 / prob) - 1.0)
