# UFC Fight Prediction Tool

A UFC fight prediction tool using multi-dimensional Elo ratings. Predicts winner, method of victory (KO/TKO, Submission, Decision), and round of finish.

**Live App:** https://ufc-prediction-fights-production.up.railway.app

## Features

- **Fighter Comparison**: Side-by-side radar charts comparing 10 skill dimensions
- **Win Prediction**: Binary pick based on Elo rating differentials
- **Method Prediction**: KO/TKO, Submission, or Decision
- **Round Prediction**: When the fight will end (with championship 5-round factor)
- **Historical Data**: 5,200+ fights, 1,600+ fighters from USADA era (2015+)

## Skill Dimensions

The rating system tracks 10 dimensions for each fighter:

| Dimension | Description |
|-----------|-------------|
| Knockout Power | Ability to finish fights via strikes |
| Striking Volume | Output and pace on the feet |
| Striking Defense | Ability to avoid damage |
| Wrestling Offense | Takedown ability |
| Wrestling Defense | Takedown prevention |
| Submission Offense | Ability to submit opponents |
| Submission Defense | Ability to escape submissions |
| Cardio | Endurance over rounds |
| Pressure | Cage cutting and forward movement |
| Adaptability | Fight IQ and adjustments |

## Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the app
streamlit run src/ufc_predictor/ui/app.py

# CLI tools
ufc-scrape stats              # Show data counts
ufc-scrape upcoming           # Show upcoming UFC events
ufc-ratings stats --gender male --min-fights 5  # Top rated fighters
ufc-ratings show --fighter ID # Show fighter ratings
```

## Data Pipeline

```bash
# Full scrape from UFCStats.com
ufc-scrape full

# Rebuild ratings from historical fights
ufc-ratings replay
```

## Project Structure

```
src/ufc_predictor/
├── scraper/     # UFCStats.com data collection
├── ratings/     # Multi-dimensional Elo system
├── predictor/   # Fight prediction logic
├── tracking/    # Prediction logging & accuracy
└── ui/          # Streamlit web interface

data/
├── fighters/    # Fighter profiles (JSON)
├── fights/      # Fight records with stats (JSON)
├── events/      # UFC event data (JSON)
└── ratings/     # Fighter skill ratings (JSON)
```

## Tech Stack

- **Data**: UFCStats.com web scraping
- **Ratings**: Multi-dimensional Elo with K-factor adjustments
- **UI**: Streamlit + Plotly radar charts
- **Deployment**: Railway

## Accuracy

Based on backtesting against historical fights:
- **Winner prediction**: ~72%
- **Method prediction**: ~58%

---

Built for personal use. Data from UFCStats.com.
