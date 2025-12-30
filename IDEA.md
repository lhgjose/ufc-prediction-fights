# UFC Fight Prediction Tool - Specification

## Overview
A personal hobby tool that predicts UFC fight outcomes including the winner, method of victory, and round of finish. Outputs binary picks (no probability percentages) with structured analytical reports.

---

## Data Architecture

### Source
- **Primary**: UFCStats.com (web scraping)
- **Historical depth**: USADA era only (2015-present) - most relevant to current standards
- **Update trigger**: Event-triggered scraping after each UFC event concludes
- **Storage**: Flat files (JSON/CSV) - simple, version controllable
- **Truth handling**: Re-scrape overwrites are the source of truth for NCs and overturned decisions

### Stats to Collect
Pull all available UFCStats data - let feature selection determine what's useful:
- Volume metrics (strikes landed/absorbed, takedowns)
- Accuracy metrics (striking %, TD %, defense %)
- Efficiency ratios (damage per minute, control time)
- Fight-level and career-level aggregates

---

## Rating System

### Core Approach
Elo/Glicko-based system with **separate ratings per skill dimension** (not a single overall rating).

### Skill Dimensions (8-10 axes)
Granular skills including:
- Knockout power
- Volume striking
- Striking defense
- Wrestling offense (takedowns)
- Takedown defense
- Submission offense
- Submission defense
- Cardio/pace
- Cage control/clinch
- Fight IQ/adaptability

### Rating Initialization
**Historical replay**: Process all USADA-era fights chronologically to establish current ratings for all fighters.

### Rating Dynamics
- **Recency weighting**: Recent fights matter more, older fights fade
- **Inactivity decay**: Ratings decay toward average during long layoffs (ring rust)
- **Evolution**: Trust stats to capture style changes naturally (no manual intervention)

---

## Prediction Logic

### Winner Prediction
- Use skill differential across dimensions
- **Stylistic tiebreaker** for close matchups when ratings are similar
- Refuse prediction for debuting fighters with zero UFC stats

### Method Prediction
Predict KO/TKO, Submission, or Decision based on:
- Finish rate histories
- Skill matchup (KO power vs chin, sub offense vs defense)
- Historical method distributions

### Round Prediction
- Model finish probability curves
- **Championship factor**: Apply cardio adjustment for 5-round fights
- Consider historical round distributions by method

### Sparse Data Handling
For fighters with limited history:
- Use proxy features: age, gym affiliation, weight class averages
- **Do not predict** if a fighter has zero UFC fights

---

## Contextual Factors

### Decline Modeling
Apply all of:
- Natural rating decline from losses
- **Chin degradation tracking**: KO losses specifically flagged as potential permanent decline
- **Recent form weighting**: Last 3 fights weighted heavily
- **Age adjustment**: Additional decline factors after 35+

### Fight Context
- **Short-notice penalty**: Preparedness disadvantage for fighters taking short-notice bouts
- **Location factor**: Account for hometown judging bias by venue/commission
- **Size differential**: For weight class moves and catchweights, calculate who has size advantage

### Division Handling
- **Separate models** for men's and women's divisions
- Catchweight/superfight predictions use size advantage calculations

---

## Validation Strategy

### Before Deployment
- Train/test split on historical data
- Time-series cross-validation (walk-forward, respecting temporal order)
- Backtest predictions against historical betting line accuracy

### Ongoing
- **Error analysis**: Categorize why predictions failed (upset, injury, bad data, style mismatch)
- **Feature importance review**: After each card, review which factors drove predictions

---

## User Interface

### Platform
- **Framework**: Streamlit
- **Deployment**: Cloud free tier (Heroku/Render/Railway)
- **Usage pattern**: Fight week only

### Input Methods
1. **Upcoming cards**: Auto-scrape and present scheduled UFC events
2. **Fighter search**: Autocomplete search from fighter database
3. **Hypotheticals**: Support "what if" matchups that may never happen

### Output Display
**Full breakdown** including:
- **Spider/radar chart**: Visual comparison of both fighters across skill dimensions
- **Structured report** with sections:
  - Striking Analysis
  - Grappling Analysis
  - X-Factors (contextual advantages)
  - Prediction (winner, method, round)
- Key stats driving the prediction
- Reasoning narrative (rule-based, analytical style)

### Performance Dashboard
Track prediction history with accuracy breakdowns:
- By weight class
- By method
- By underdog/favorite
- Overall hit rate

---

## Future Enhancements (Not MVP)

These are noted for later but explicitly skipped for initial build:
- Camp/coaching quality tracking
- Sentiment/hype factors (momentum, grudge matches, home crowd)
- Altitude and venue-specific factors
- Integration with regional promotion data (Bellator, PFL, etc.)

---

## Build Priority (All Complete)

1. **Phase 1**: Data pipeline - UFCStats scraper + flat file storage ✓
2. **Phase 2**: Rating system - Multi-dimensional Elo with historical replay ✓
3. **Phase 3**: Prediction engine - Winner/method/round logic ✓
4. **Phase 4**: Web UI - Streamlit app with visualizations ✓
5. **Phase 5**: Performance tracking - Dashboard and validation metrics ✓

---

## Technical Decisions Summary

| Decision | Choice |
|----------|--------|
| Data source | UFCStats.com scraping |
| Storage | Flat files (JSON/CSV) |
| Model type | Multi-dimensional Elo/Glicko |
| Web framework | Streamlit |
| Deployment | Cloud free tier |
| Historical data | USADA era (2015+) |
| Narrative generation | Rule-based templates (no LLM cost) |
| Men's/Women's | Separate models |
| Debut fighters | Refuse prediction |
