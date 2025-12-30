"""Streamlit web application for UFC fight predictions."""

import sys
from pathlib import Path

# Add src to path for imports when running directly
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st

from ufc_predictor.ui.components import (
    render_dimension_breakdown,
    render_fighter_card,
    render_fighter_selector,
    render_performance_stats,
    render_prediction_result,
    render_radar_chart,
    render_recent_predictions,
)
from ufc_predictor.ui.state import (
    get_predictor,
    get_storage,
    get_tracker,
    load_events_list,
    load_fighters_list,
)


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="UFC Fight Predictor",
        page_icon="🥊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown(
        """
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            text-align: center;
            padding: 1rem 0;
        }
        .prediction-winner {
            font-size: 1.8rem;
            font-weight: bold;
            text-align: center;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        .fighter-name {
            font-size: 1.5rem;
            font-weight: bold;
        }
        .stat-label {
            color: #888;
            font-size: 0.9rem;
        }
        .advantage {
            color: #00cc00;
            font-weight: bold;
        }
        .disadvantage {
            color: #cc0000;
        }
        .even {
            color: #888;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header
    st.markdown('<p class="main-header">🥊 UFC Fight Predictor</p>', unsafe_allow_html=True)

    # Initialize tracker early for sidebar stats
    tracker = get_tracker()

    # Sidebar
    with st.sidebar:
        st.header("Settings")
        scheduled_rounds = st.selectbox(
            "Scheduled Rounds",
            options=[3, 5],
            index=0,
            help="Select 5 for main events and title fights",
        )
        is_title_fight = st.checkbox("Title Fight", value=False)

        st.divider()
        st.header("Performance")
        stats = tracker.calculate_stats()
        if stats.total_predictions > 0:
            st.metric("Total Predictions", stats.total_predictions)
            st.metric("Winner Accuracy", f"{stats.winner_accuracy:.1f}%")
            if st.button("View Full Stats"):
                st.session_state["show_stats"] = True
        else:
            st.info("No predictions logged yet.")

        st.divider()
        st.header("About")
        st.markdown(
            """
            This tool predicts UFC fight outcomes using a multi-dimensional
            Elo rating system. Each fighter is rated across 10 skill dimensions.

            **Predictions include:**
            - Winner
            - Method (KO/TKO, Submission, Decision)
            - Round (for finishes)

            **Note:** Predictions are refused for fighters with no UFC history.
            """
        )

    # Load data
    storage = get_storage()
    predictor = get_predictor()
    fighters = load_fighters_list()
    events = load_events_list()

    if not fighters:
        st.warning(
            "No fighter data found. Please run the scraper first:\n\n"
            "```bash\nufc-scrape full\nufc-ratings replay\n```"
        )
        return

    # Fighter selection
    st.subheader("Select Fighters")
    col1, col2 = st.columns(2)

    with col1:
        fighter1_id = render_fighter_selector(fighters, key="fighter1", label="Fighter 1 (Red Corner)")

    with col2:
        fighter2_id = render_fighter_selector(fighters, key="fighter2", label="Fighter 2 (Blue Corner)")

    # Validate selection
    if not fighter1_id or not fighter2_id:
        st.info("Select two fighters to generate a prediction.")
        return

    if fighter1_id == fighter2_id:
        st.error("Please select two different fighters.")
        return

    # Load fighter data
    fighter1 = storage.load_fighter(fighter1_id)
    fighter2 = storage.load_fighter(fighter2_id)

    # Display fighter cards
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        render_fighter_card(fighter1, corner="red")

    with col2:
        render_fighter_card(fighter2, corner="blue")

    # Generate prediction button
    st.divider()
    if st.button("🎯 Generate Prediction", type="primary", use_container_width=True):
        with st.spinner("Analyzing matchup..."):
            prediction = predictor.predict(
                fighter1_id,
                fighter2_id,
                scheduled_rounds=scheduled_rounds,
                is_title_fight=is_title_fight,
            )

        # Store prediction in session state (use different keys to avoid widget conflict)
        st.session_state["prediction"] = prediction
        st.session_state["pred_fighter1"] = fighter1
        st.session_state["pred_fighter2"] = fighter2

    # Display prediction if available
    if "prediction" in st.session_state:
        prediction = st.session_state["prediction"]
        fighter1 = st.session_state["pred_fighter1"]
        fighter2 = st.session_state["pred_fighter2"]

        st.divider()

        # Prediction result
        render_prediction_result(prediction, fighter1, fighter2)

        if not prediction.refused:
            # Radar chart comparison
            st.divider()
            st.subheader("Skill Comparison")
            render_radar_chart(prediction, fighter1, fighter2)

            # Dimension breakdown
            st.divider()
            st.subheader("Detailed Analysis")
            render_dimension_breakdown(prediction, fighter1, fighter2)

            # Log prediction button
            st.divider()
            col1, col2 = st.columns([3, 1])

            with col1:
                event_options = [""] + [f"{name} ({date})" for _, name, date in events]
                event_names = {f"{name} ({date})": eid for eid, name, date in events}
                selected_event = st.selectbox(
                    "Event (optional)",
                    options=event_options,
                    key="log_event",
                    help="Select event to associate with this prediction",
                )

            with col2:
                st.write("")  # Spacer
                st.write("")
                if st.button("Log Prediction", type="secondary"):
                    event_name = None
                    if selected_event and selected_event in event_names:
                        # Extract just the event name without date
                        event_name = selected_event.rsplit(" (", 1)[0]

                    logged = tracker.log_prediction(prediction, event_name=event_name)
                    st.success(f"Prediction logged (ID: {logged.prediction_id})")
                    st.session_state["prediction_logged"] = logged.prediction_id

    # Show full stats modal
    if st.session_state.get("show_stats"):
        st.divider()
        full_stats = tracker.calculate_stats()
        render_performance_stats(full_stats)
        if st.button("Hide Stats"):
            st.session_state["show_stats"] = False

    # Recent predictions section
    st.divider()
    recent = tracker.get_recent_predictions(5)
    if recent:
        with st.expander("Recent Predictions", expanded=False):
            render_recent_predictions(recent)


if __name__ == "__main__":
    main()
