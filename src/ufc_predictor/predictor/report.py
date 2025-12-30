"""Report generation for fight predictions."""

from typing import Optional

from ..ratings.models import SkillDimension
from .models import DimensionAdvantage, Prediction, PredictionMethod


def generate_report(prediction: Prediction) -> str:
    """
    Generate a structured text report for a fight prediction.

    Args:
        prediction: The Prediction object to format

    Returns:
        Formatted string report
    """
    if prediction.refused:
        return _generate_refusal_report(prediction)

    lines = []

    # Header
    f1_name = prediction.fighter1_name or prediction.fighter1_id
    f2_name = prediction.fighter2_name or prediction.fighter2_id
    lines.append(f"{'=' * 60}")
    lines.append(f"{f1_name} vs {f2_name}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    # Prediction Summary
    lines.append("PREDICTION")
    lines.append("-" * 40)
    winner_name = prediction.winner_name or prediction.winner_id
    lines.append(f"Winner: {winner_name}")

    if prediction.method:
        method_str = prediction.method.method.value
        lines.append(f"Method: {method_str}")

    if prediction.round_prediction:
        if prediction.round_prediction.is_decision:
            rounds = prediction.round_prediction.scheduled_rounds
            lines.append(f"Round: Goes to decision ({rounds} rounds)")
        else:
            lines.append(f"Round: {prediction.round_prediction.round_number}")

    lines.append("")

    # Striking Analysis
    lines.append("STRIKING ANALYSIS")
    lines.append("-" * 40)
    lines.extend(_generate_striking_analysis(prediction, f1_name, f2_name))
    lines.append("")

    # Grappling Analysis
    lines.append("GRAPPLING ANALYSIS")
    lines.append("-" * 40)
    lines.extend(_generate_grappling_analysis(prediction, f1_name, f2_name))
    lines.append("")

    # Intangibles
    lines.append("INTANGIBLES")
    lines.append("-" * 40)
    lines.extend(_generate_intangibles_analysis(prediction, f1_name, f2_name))
    lines.append("")

    # X-Factors
    if prediction.x_factors:
        lines.append("X-FACTORS")
        lines.append("-" * 40)
        for factor in prediction.x_factors:
            lines.append(f"- {factor}")
        lines.append("")

    # Fight Assessment
    lines.append("FIGHT ASSESSMENT")
    lines.append("-" * 40)
    lines.extend(_generate_fight_assessment(prediction, f1_name, f2_name))

    return "\n".join(lines)


def _generate_refusal_report(prediction: Prediction) -> str:
    """Generate a report for a refused prediction."""
    f1_name = prediction.fighter1_name or prediction.fighter1_id
    f2_name = prediction.fighter2_name or prediction.fighter2_id

    lines = [
        f"{'=' * 60}",
        f"{f1_name} vs {f2_name}",
        f"{'=' * 60}",
        "",
        "PREDICTION REFUSED",
        "-" * 40,
        f"Reason: {prediction.refusal_reason}",
        "",
        "Unable to generate prediction due to insufficient data.",
        "This typically occurs when a fighter is making their UFC debut",
        "or has very limited UFC fight history.",
    ]
    return "\n".join(lines)


def _generate_striking_analysis(
    prediction: Prediction,
    f1_name: str,
    f2_name: str,
) -> list[str]:
    """Generate striking analysis section."""
    lines = []

    if not prediction.dimension_breakdown:
        lines.append("No striking data available")
        return lines

    advantages = {a.dimension: a for a in prediction.dimension_breakdown.advantages}

    # Knockout power comparison
    ko_adv = advantages.get(SkillDimension.KNOCKOUT_POWER)
    if ko_adv:
        lines.append(_format_dimension_comparison(
            "Knockout Power", ko_adv, f1_name, f2_name
        ))

    # Striking volume comparison
    vol_adv = advantages.get(SkillDimension.STRIKING_VOLUME)
    if vol_adv:
        lines.append(_format_dimension_comparison(
            "Striking Volume", vol_adv, f1_name, f2_name
        ))

    # Striking defense comparison
    def_adv = advantages.get(SkillDimension.STRIKING_DEFENSE)
    if def_adv:
        lines.append(_format_dimension_comparison(
            "Striking Defense", def_adv, f1_name, f2_name
        ))

    # Summary
    striking_dims = [
        SkillDimension.KNOCKOUT_POWER,
        SkillDimension.STRIKING_VOLUME,
        SkillDimension.STRIKING_DEFENSE,
    ]
    f1_striking_advs = sum(
        1 for d in striking_dims
        if d in advantages and advantages[d].difference > SIGNIFICANT_THRESHOLD
    )
    f2_striking_advs = sum(
        1 for d in striking_dims
        if d in advantages and advantages[d].difference < -SIGNIFICANT_THRESHOLD
    )

    if f1_striking_advs > f2_striking_advs:
        lines.append(f"Striking Edge: {f1_name}")
    elif f2_striking_advs > f1_striking_advs:
        lines.append(f"Striking Edge: {f2_name}")
    else:
        lines.append("Striking Edge: Even")

    return lines


def _generate_grappling_analysis(
    prediction: Prediction,
    f1_name: str,
    f2_name: str,
) -> list[str]:
    """Generate grappling analysis section."""
    lines = []

    if not prediction.dimension_breakdown:
        lines.append("No grappling data available")
        return lines

    advantages = {a.dimension: a for a in prediction.dimension_breakdown.advantages}

    # Wrestling offense
    wr_off = advantages.get(SkillDimension.WRESTLING_OFFENSE)
    if wr_off:
        lines.append(_format_dimension_comparison(
            "Wrestling Offense", wr_off, f1_name, f2_name
        ))

    # Wrestling defense
    wr_def = advantages.get(SkillDimension.WRESTLING_DEFENSE)
    if wr_def:
        lines.append(_format_dimension_comparison(
            "Takedown Defense", wr_def, f1_name, f2_name
        ))

    # Submission offense
    sub_off = advantages.get(SkillDimension.SUBMISSION_OFFENSE)
    if sub_off:
        lines.append(_format_dimension_comparison(
            "Submission Threat", sub_off, f1_name, f2_name
        ))

    # Submission defense
    sub_def = advantages.get(SkillDimension.SUBMISSION_DEFENSE)
    if sub_def:
        lines.append(_format_dimension_comparison(
            "Submission Defense", sub_def, f1_name, f2_name
        ))

    # Grappling summary
    grappling_dims = [
        SkillDimension.WRESTLING_OFFENSE,
        SkillDimension.WRESTLING_DEFENSE,
        SkillDimension.SUBMISSION_OFFENSE,
        SkillDimension.SUBMISSION_DEFENSE,
    ]
    f1_grappling_advs = sum(
        1 for d in grappling_dims
        if d in advantages and advantages[d].difference > SIGNIFICANT_THRESHOLD
    )
    f2_grappling_advs = sum(
        1 for d in grappling_dims
        if d in advantages and advantages[d].difference < -SIGNIFICANT_THRESHOLD
    )

    if f1_grappling_advs > f2_grappling_advs:
        lines.append(f"Grappling Edge: {f1_name}")
    elif f2_grappling_advs > f1_grappling_advs:
        lines.append(f"Grappling Edge: {f2_name}")
    else:
        lines.append("Grappling Edge: Even")

    return lines


def _generate_intangibles_analysis(
    prediction: Prediction,
    f1_name: str,
    f2_name: str,
) -> list[str]:
    """Generate intangibles analysis section."""
    lines = []

    if not prediction.dimension_breakdown:
        lines.append("No intangibles data available")
        return lines

    advantages = {a.dimension: a for a in prediction.dimension_breakdown.advantages}

    # Cardio
    cardio = advantages.get(SkillDimension.CARDIO)
    if cardio:
        lines.append(_format_dimension_comparison(
            "Cardio/Endurance", cardio, f1_name, f2_name
        ))

    # Pressure
    pressure = advantages.get(SkillDimension.PRESSURE)
    if pressure:
        lines.append(_format_dimension_comparison(
            "Pressure/Cage Control", pressure, f1_name, f2_name
        ))

    # Adaptability/Fight IQ
    adapt = advantages.get(SkillDimension.ADAPTABILITY)
    if adapt:
        lines.append(_format_dimension_comparison(
            "Fight IQ", adapt, f1_name, f2_name
        ))

    return lines


def _generate_fight_assessment(
    prediction: Prediction,
    f1_name: str,
    f2_name: str,
) -> list[str]:
    """Generate overall fight assessment."""
    lines = []

    winner = prediction.winner_name or prediction.winner_id

    if prediction.is_close_fight:
        lines.append("This is a closely matched fight that could go either way.")
        lines.append(f"The edge goes to {winner} based on stylistic factors.")
    else:
        diff = abs(prediction.rating_differential)
        if diff > 150:
            lines.append(f"{winner} is a significant favorite in this matchup.")
        elif diff > 75:
            lines.append(f"{winner} holds clear advantages in this fight.")
        else:
            lines.append(f"{winner} has a slight edge in this contest.")

    # Method commentary
    if prediction.method:
        method = prediction.method.method
        if method == PredictionMethod.KO_TKO:
            lines.append(f"Look for {winner} to find the finish on the feet.")
        elif method == PredictionMethod.SUBMISSION:
            lines.append(f"The ground game favors {winner} - submission is the likely path.")
        else:
            lines.append("Expect this one to go the distance.")

    return lines


def _format_dimension_comparison(
    label: str,
    adv: "DimensionAdvantage",
    f1_name: str,
    f2_name: str,
) -> str:
    """Format a single dimension comparison line."""
    diff = adv.difference
    if abs(diff) < 25:
        assessment = "Even"
        leader = ""
    elif diff > 0:
        leader = f1_name
        if diff > 100:
            assessment = "Strong advantage"
        elif diff > 50:
            assessment = "Clear advantage"
        else:
            assessment = "Slight edge"
    else:
        leader = f2_name
        if diff < -100:
            assessment = "Strong advantage"
        elif diff < -50:
            assessment = "Clear advantage"
        else:
            assessment = "Slight edge"

    if leader:
        return f"{label}: {leader} ({assessment})"
    return f"{label}: {assessment}"


# Threshold for "significant" advantage in report
SIGNIFICANT_THRESHOLD = 50


def generate_compact_prediction(prediction: Prediction) -> str:
    """Generate a one-line prediction summary."""
    if prediction.refused:
        return f"REFUSED: {prediction.refusal_reason}"

    winner = prediction.winner_name or prediction.winner_id

    if prediction.method and prediction.round_prediction:
        method = prediction.method.method.value
        if prediction.round_prediction.is_decision:
            return f"{winner} via {method}"
        else:
            round_num = prediction.round_prediction.round_number
            return f"{winner} via {method} (Rd {round_num})"

    return f"{winner}"
