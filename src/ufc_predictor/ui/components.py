"""UI components for the Streamlit app."""

from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from ufc_predictor.predictor.models import Prediction, PredictionMethod
from ufc_predictor.ratings.models import SkillDimension
from ufc_predictor.scraper.models import Fighter
from ufc_predictor.tracking.models import LoggedPrediction, PerformanceStats
from ufc_predictor.ui.state import get_rating_system


def render_fighter_selector(
    fighters: list[tuple[str, str]],
    key: str,
    label: str,
) -> Optional[str]:
    """
    Render a fighter selection dropdown.

    Args:
        fighters: List of (fighter_id, fighter_name) tuples
        key: Unique key for the widget
        label: Label to display

    Returns:
        Selected fighter ID or None
    """
    # Create options dict for selectbox
    options = {name: fid for fid, name in fighters}
    names = [""] + sorted(options.keys())

    selected_name = st.selectbox(
        label,
        options=names,
        key=key,
        help="Search by typing fighter name",
    )

    if selected_name:
        return options[selected_name]
    return None


def render_fighter_card(fighter: Optional[Fighter], corner: str = "red"):
    """
    Render a fighter info card.

    Args:
        fighter: Fighter object
        corner: "red" or "blue"
    """
    if not fighter:
        st.warning("Fighter not found")
        return

    color = "#ff4444" if corner == "red" else "#4444ff"

    st.markdown(
        f'<p class="fighter-name" style="color: {color}">{fighter.name}</p>',
        unsafe_allow_html=True,
    )

    if fighter.nickname:
        st.caption(f'"{fighter.nickname}"')

    # Stats in columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Record", f"{fighter.record_wins}-{fighter.record_losses}-{fighter.record_draws}")

    with col2:
        if fighter.height_inches:
            feet = fighter.height_inches // 12
            inches = fighter.height_inches % 12
            st.metric("Height", f"{feet}'{inches}\"")
        else:
            st.metric("Height", "N/A")

    with col3:
        if fighter.reach_inches:
            st.metric("Reach", f'{fighter.reach_inches}"')
        else:
            st.metric("Reach", "N/A")

    # Career stats
    with st.expander("Career Statistics"):
        stats_col1, stats_col2 = st.columns(2)

        with stats_col1:
            st.markdown("**Striking**")
            st.write(f"SLpM: {fighter.slpm or 'N/A'}")
            st.write(f"Str. Acc: {_format_pct(fighter.str_acc)}")
            st.write(f"SApM: {fighter.sapm or 'N/A'}")
            st.write(f"Str. Def: {_format_pct(fighter.str_def)}")

        with stats_col2:
            st.markdown("**Grappling**")
            st.write(f"TD Avg: {fighter.td_avg or 'N/A'}")
            st.write(f"TD Acc: {_format_pct(fighter.td_acc)}")
            st.write(f"TD Def: {_format_pct(fighter.td_def)}")
            st.write(f"Sub Avg: {fighter.sub_avg or 'N/A'}")


def _format_pct(value: Optional[float]) -> str:
    """Format a percentage value."""
    if value is None:
        return "N/A"
    return f"{value * 100:.0f}%"


def render_prediction_result(
    prediction: Prediction,
    fighter1: Fighter,
    fighter2: Fighter,
):
    """Render the prediction result."""
    if prediction.refused:
        st.error(f"**Prediction Refused:** {prediction.refusal_reason}")
        return

    winner_name = prediction.winner_name or prediction.winner_id
    is_fighter1_winner = prediction.winner_id == prediction.fighter1_id
    winner_color = "#ff4444" if is_fighter1_winner else "#4444ff"

    # Winner announcement
    st.markdown(
        f"""
        <div class="prediction-winner" style="background-color: {winner_color}22; border: 2px solid {winner_color}">
            🏆 {winner_name} 🏆
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Method and round
    col1, col2, col3 = st.columns(3)

    with col1:
        if prediction.method:
            method_str = prediction.method.method.value
            st.metric("Method", method_str)

    with col2:
        if prediction.round_prediction:
            if prediction.round_prediction.is_decision:
                round_str = f"Decision ({prediction.round_prediction.scheduled_rounds} rds)"
            else:
                round_str = f"Round {prediction.round_prediction.round_number}"
            st.metric("Round", round_str)

    with col3:
        fight_type = "Close Fight" if prediction.is_close_fight else "Clear Edge"
        st.metric("Fight Type", fight_type)

    # X-Factors
    if prediction.x_factors:
        st.markdown("**X-Factors:**")
        for factor in prediction.x_factors:
            st.markdown(f"- {factor}")


def render_radar_chart(
    prediction: Prediction,
    fighter1: Fighter,
    fighter2: Fighter,
):
    """Render a radar chart comparing fighter skills."""
    rating_system = get_rating_system()

    ratings1 = rating_system.get_fighter_ratings(prediction.fighter1_id)
    ratings2 = rating_system.get_fighter_ratings(prediction.fighter2_id)

    # Dimension labels (shortened for display)
    dimension_labels = {
        SkillDimension.KNOCKOUT_POWER: "KO Power",
        SkillDimension.STRIKING_VOLUME: "Volume",
        SkillDimension.STRIKING_DEFENSE: "Strike Def",
        SkillDimension.WRESTLING_OFFENSE: "Wrestling",
        SkillDimension.WRESTLING_DEFENSE: "TD Def",
        SkillDimension.SUBMISSION_OFFENSE: "Sub Off",
        SkillDimension.SUBMISSION_DEFENSE: "Sub Def",
        SkillDimension.CARDIO: "Cardio",
        SkillDimension.PRESSURE: "Pressure",
        SkillDimension.ADAPTABILITY: "Fight IQ",
    }

    categories = list(dimension_labels.values())
    dimensions = list(dimension_labels.keys())

    # Get ratings (normalize to 0-100 scale for visualization)
    def normalize(rating: float) -> float:
        # Ratings typically range 1000-2200, normalize to 0-100
        return max(0, min(100, (rating - 1000) / 12))

    values1 = [normalize(ratings1.get_rating(dim)) for dim in dimensions]
    values2 = [normalize(ratings2.get_rating(dim)) for dim in dimensions]

    # Close the radar chart
    categories_closed = categories + [categories[0]]
    values1_closed = values1 + [values1[0]]
    values2_closed = values2 + [values2[0]]

    fig = go.Figure()

    # Fighter 1 (Red)
    fig.add_trace(
        go.Scatterpolar(
            r=values1_closed,
            theta=categories_closed,
            fill="toself",
            name=fighter1.name if fighter1 else prediction.fighter1_id,
            line_color="#ff4444",
            fillcolor="rgba(255, 68, 68, 0.3)",
        )
    )

    # Fighter 2 (Blue)
    fig.add_trace(
        go.Scatterpolar(
            r=values2_closed,
            theta=categories_closed,
            fill="toself",
            name=fighter2.name if fighter2 else prediction.fighter2_id,
            line_color="#4444ff",
            fillcolor="rgba(68, 68, 255, 0.3)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10),
            ),
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=80, r=80, t=40, b=80),
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_dimension_breakdown(
    prediction: Prediction,
    fighter1: Fighter,
    fighter2: Fighter,
):
    """Render detailed dimension breakdown."""
    if not prediction.dimension_breakdown:
        st.info("No detailed breakdown available")
        return

    f1_name = fighter1.name if fighter1 else prediction.fighter1_id
    f2_name = fighter2.name if fighter2 else prediction.fighter2_id

    # Create tabs for different analysis sections
    tab1, tab2, tab3 = st.tabs(["Striking", "Grappling", "Intangibles"])

    advantages = {a.dimension: a for a in prediction.dimension_breakdown.advantages}

    with tab1:
        _render_dimension_row(
            "Knockout Power",
            advantages.get(SkillDimension.KNOCKOUT_POWER),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Striking Volume",
            advantages.get(SkillDimension.STRIKING_VOLUME),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Striking Defense",
            advantages.get(SkillDimension.STRIKING_DEFENSE),
            f1_name,
            f2_name,
        )

    with tab2:
        _render_dimension_row(
            "Wrestling Offense",
            advantages.get(SkillDimension.WRESTLING_OFFENSE),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Takedown Defense",
            advantages.get(SkillDimension.WRESTLING_DEFENSE),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Submission Offense",
            advantages.get(SkillDimension.SUBMISSION_OFFENSE),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Submission Defense",
            advantages.get(SkillDimension.SUBMISSION_DEFENSE),
            f1_name,
            f2_name,
        )

    with tab3:
        _render_dimension_row(
            "Cardio",
            advantages.get(SkillDimension.CARDIO),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Pressure/Cage Control",
            advantages.get(SkillDimension.PRESSURE),
            f1_name,
            f2_name,
        )
        _render_dimension_row(
            "Fight IQ",
            advantages.get(SkillDimension.ADAPTABILITY),
            f1_name,
            f2_name,
        )


def _render_dimension_row(
    label: str,
    advantage,
    f1_name: str,
    f2_name: str,
):
    """Render a single dimension comparison row."""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])

    with col1:
        st.write(f"**{label}**")

    if advantage is None:
        with col2:
            st.write("N/A")
        with col3:
            st.write("N/A")
        with col4:
            st.write("Even")
        return

    diff = advantage.difference

    with col2:
        st.write(f"{advantage.fighter1_rating:.0f}")

    with col3:
        st.write(f"{advantage.fighter2_rating:.0f}")

    with col4:
        if abs(diff) < 25:
            st.markdown('<span class="even">Even</span>', unsafe_allow_html=True)
        elif diff > 0:
            if diff > 100:
                st.markdown(f'<span class="advantage">{f1_name} +++</span>', unsafe_allow_html=True)
            elif diff > 50:
                st.markdown(f'<span class="advantage">{f1_name} ++</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="advantage">{f1_name} +</span>', unsafe_allow_html=True)
        else:
            if diff < -100:
                st.markdown(f'<span class="advantage">{f2_name} +++</span>', unsafe_allow_html=True)
            elif diff < -50:
                st.markdown(f'<span class="advantage">{f2_name} ++</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="advantage">{f2_name} +</span>', unsafe_allow_html=True)


def render_performance_stats(stats: PerformanceStats):
    """Render performance statistics dashboard."""
    st.subheader("Prediction Performance")

    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Predictions", stats.total_predictions)

    with col2:
        st.metric("Resolved", stats.resolved_predictions)

    with col3:
        st.metric("Pending", stats.pending_predictions)

    with col4:
        st.metric(
            "Winner Accuracy",
            f"{stats.winner_accuracy:.1f}%",
            delta=None,
        )

    if stats.resolved_predictions > 0:
        # Accuracy breakdown
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Winner Prediction**")
            st.write(f"Correct: {stats.winner_correct}")
            st.write(f"Incorrect: {stats.winner_incorrect}")
            st.progress(stats.winner_accuracy / 100 if stats.winner_accuracy else 0)

        with col2:
            st.markdown("**Method Prediction**")
            st.write(f"Correct: {stats.method_correct}")
            st.write(f"Incorrect: {stats.method_incorrect}")
            st.progress(stats.method_accuracy / 100 if stats.method_accuracy else 0)

        with col3:
            st.markdown("**Round Prediction**")
            st.write(f"Correct: {stats.round_correct}")
            st.write(f"Incorrect: {stats.round_incorrect}")
            st.progress(stats.round_accuracy / 100 if stats.round_accuracy else 0)

        # Method breakdown
        with st.expander("Breakdown by Method"):
            method_col1, method_col2, method_col3 = st.columns(3)

            with method_col1:
                st.markdown("**KO/TKO**")
                st.write(f"{stats.ko_correct}/{stats.ko_predictions} correct")

            with method_col2:
                st.markdown("**Submission**")
                st.write(f"{stats.submission_correct}/{stats.submission_predictions} correct")

            with method_col3:
                st.markdown("**Decision**")
                st.write(f"{stats.decision_correct}/{stats.decision_predictions} correct")

        # Favorite/Underdog breakdown
        with st.expander("Favorite vs Underdog"):
            fav_col1, fav_col2 = st.columns(2)

            with fav_col1:
                st.markdown("**Favorite Picks**")
                st.write(f"{stats.favorite_correct}/{stats.favorite_predictions} correct")

            with fav_col2:
                st.markdown("**Underdog Picks**")
                st.write(f"{stats.underdog_correct}/{stats.underdog_predictions} correct")

            st.write(f"Upsets predicted: {stats.upsets_predicted}")
            st.write(f"Upsets missed: {stats.upsets_missed}")


def render_recent_predictions(predictions: list[LoggedPrediction]):
    """Render list of recent predictions."""
    if not predictions:
        st.info("No predictions logged yet.")
        return

    st.subheader(f"Recent Predictions ({len(predictions)})")

    for pred in predictions:
        f1_name = pred.fighter1_name or pred.fighter1_id
        f2_name = pred.fighter2_name or pred.fighter2_id

        winner_name = (
            pred.fighter1_name
            if pred.predicted_winner_id == pred.fighter1_id
            else pred.fighter2_name
        )
        winner_name = winner_name or pred.predicted_winner_id

        method = pred.predicted_method or "N/A"
        round_str = f"Round {pred.predicted_round}" if pred.predicted_round else "Decision"

        timestamp = (
            pred.prediction_timestamp.strftime("%Y-%m-%d %H:%M")
            if pred.prediction_timestamp
            else "N/A"
        )

        with st.container():
            st.markdown(f"**{f1_name} vs {f2_name}**")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"Pick: {winner_name}")

            with col2:
                st.write(f"Method: {method}")

            with col3:
                st.write(f"{round_str}")

            if pred.event_name:
                st.caption(f"{pred.event_name} | {timestamp}")
            else:
                st.caption(timestamp)

            st.divider()
