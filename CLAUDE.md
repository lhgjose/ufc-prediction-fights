# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UFC fight prediction tool for personal use. Predicts winner, method of victory (KO/TKO, Submission, Decision), and round of finish. Outputs binary picks with structured analytical reports - no probability percentages.

See `IDEA.md` for the full specification.

## Current Status

All 5 build phases are complete:
- **Phase 1**: Data pipeline (UFCStats scraper) - 5,204 fights, 1,697 fighters, 434 events
- **Phase 2**: Rating system (10-dimensional Elo with historical replay)
- **Phase 3**: Prediction engine (winner/method/round logic)
- **Phase 4**: Streamlit web UI with radar charts and detailed analysis
- **Phase 5**: Performance tracking system with accuracy dashboard

## Development Commands

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/

# Scrape UFC data
ufc-scrape stats              # Show data counts
ufc-scrape full               # Full scrape (events, fights, fighters)
ufc-scrape events             # Scrape events only
ufc-scrape fights             # Scrape fights for all events
ufc-scrape fighters           # Scrape fighters from fight data

# Build ratings from historical data
ufc-ratings replay            # Process all fights chronologically
ufc-ratings stats             # Show top/bottom rated fighters
ufc-ratings show --fighter ID # Show fighter's dimension ratings
ufc-ratings compare --fighter1 ID --fighter2 ID  # Compare two fighters

# Performance tracking
ufc-track stats               # Show prediction accuracy stats
ufc-track report              # Generate full performance report
ufc-track recent              # Show recent predictions
ufc-track sync                # Sync results from scraped fight data

# Run Streamlit app
streamlit run src/ufc_predictor/ui/app.py
```

## Project Structure

```
src/ufc_predictor/
├── scraper/     # UFCStats.com data collection
├── ratings/     # Multi-dimensional Elo system
├── predictor/   # Fight prediction logic
├── tracking/    # Prediction performance tracking
└── ui/          # Streamlit web interface

data/
├── fighters/    # Fighter profiles (JSON)
├── fights/      # Fight records with stats (JSON)
├── events/      # UFC event data (JSON)
├── ratings/     # Fighter skill ratings (JSON)
└── tracking/    # Logged predictions and results (JSON)
```

## Architecture

### Data Layer
- **Source**: UFCStats.com web scraping
- **Scope**: USADA era only (2015-present)
- **Storage**: Flat files (JSON/CSV)
- **Update**: Event-triggered after each UFC card

### Rating System
Multi-dimensional Elo/Glicko with separate ratings per skill axis:
- Knockout power, volume striking, striking defense
- Wrestling offense, takedown defense
- Submission offense, submission defense
- Cardio/pace, cage control, fight IQ

Ratings initialized via historical replay of all USADA-era fights.

### Prediction Engine
- Winner: Skill differential across dimensions, stylistic tiebreaker for close matchups
- Method: Based on finish rates and skill matchups
- Round: Finish probability curves with championship factor for 5-rounders
- Refuses prediction for fighters with zero UFC bouts

### Contextual Adjustments
- Recency weighting and inactivity decay (ring rust)
- Chin degradation tracking (KO losses)
- Age adjustment (35+)
- Short-notice penalty
- Location/judging bias
- Size differential for weight class moves

### UI
- Streamlit web app
- Deploy on cloud free tier (Heroku/Render/Railway)
- Spider/radar charts for skill comparison
- Structured reports (Striking Analysis, Grappling Analysis, X-Factors, Prediction)
- Performance dashboard tracking accuracy

## Build Phases (All Complete)

1. **Data pipeline**: UFCStats scraper + flat file storage ✓
2. **Rating system**: Multi-dimensional Elo with historical replay ✓
3. **Prediction engine**: Winner/method/round logic ✓
4. **Web UI**: Streamlit app with visualizations ✓
5. **Performance tracking**: Dashboard and validation metrics ✓

## Key Technical Decisions

| Area | Decision |
|------|----------|
| Model | Multi-dimensional Elo/Glicko (not ML) |
| Data | UFCStats.com, USADA era (2015+) |
| Storage | Flat files (JSON/CSV) |
| Framework | Streamlit |
| Men's/Women's | Separate models |
| Narratives | Rule-based templates (no LLM) |
| Debut fighters | Refuse prediction |

## Domain Notes

- **USADA era**: UFC's anti-doping partnership started July 2015 - data before this is excluded
- **Championship factor**: 5-round fights need cardio adjustment vs 3-round fights
- **Stylistic matchup**: When ratings are close, use skill-type interactions as tiebreaker (e.g., wrestler vs striker dynamics)
- **Chin degradation**: Fighters who've been KO'd may have permanent decline - track separately from general losses
