"""Core prediction logic for UFC fights."""

from typing import Optional

from ..ratings.models import FighterRatings, SkillDimension
from ..ratings.system import RatingSystem
from ..scraper.models import Fighter
from ..scraper.storage import DataStorage
from .models import (
    CLOSE_FIGHT_THRESHOLD,
    MIN_FIGHTS_FOR_PREDICTION,
    SIGNIFICANT_ADVANTAGE_THRESHOLD,
    DimensionAdvantage,
    DimensionBreakdown,
    MethodPrediction,
    Prediction,
    PredictionMethod,
    RoundPrediction,
    StyleMatchup,
)


class FightPredictor:
    """Predicts UFC fight outcomes based on multi-dimensional ratings."""

    def __init__(
        self,
        rating_system: Optional[RatingSystem] = None,
        storage: Optional[DataStorage] = None,
    ):
        """Initialize predictor with rating system and storage."""
        self.storage = storage or DataStorage()
        self.rating_system = rating_system or RatingSystem(data_storage=self.storage)

    def predict(
        self,
        fighter1_id: str,
        fighter2_id: str,
        scheduled_rounds: int = 3,
        is_title_fight: bool = False,
    ) -> Prediction:
        """
        Generate a complete fight prediction.

        Args:
            fighter1_id: First fighter's ID
            fighter2_id: Second fighter's ID
            scheduled_rounds: Number of scheduled rounds (3 or 5)
            is_title_fight: Whether this is a title fight

        Returns:
            Complete Prediction object
        """
        # Load fighter info
        fighter1 = self.storage.load_fighter(fighter1_id)
        fighter2 = self.storage.load_fighter(fighter2_id)

        # Load ratings
        ratings1 = self.rating_system.get_fighter_ratings(fighter1_id)
        ratings2 = self.rating_system.get_fighter_ratings(fighter2_id)

        # Create base prediction
        prediction = Prediction(
            fighter1_id=fighter1_id,
            fighter2_id=fighter2_id,
            fighter1_name=fighter1.name if fighter1 else None,
            fighter2_name=fighter2.name if fighter2 else None,
            fighter1_avg_rating=ratings1.get_average_rating(),
            fighter2_avg_rating=ratings2.get_average_rating(),
        )

        # Check if we can make a prediction
        refusal = self._check_refusal(ratings1, ratings2, fighter1, fighter2)
        if refusal:
            prediction.refused = True
            prediction.refusal_reason = refusal
            return prediction

        # Calculate rating differential
        prediction.rating_differential = (
            prediction.fighter1_avg_rating - prediction.fighter2_avg_rating
        )

        # Analyze dimensions
        prediction.dimension_breakdown = self._analyze_dimensions(ratings1, ratings2)

        # Analyze style matchup
        prediction.style_matchup = self._analyze_style_matchup(ratings1, ratings2)

        # Determine if close fight
        prediction.is_close_fight = (
            abs(prediction.rating_differential) < CLOSE_FIGHT_THRESHOLD
        )

        # Predict winner
        prediction.winner_id = self._predict_winner(
            fighter1_id, fighter2_id, ratings1, ratings2, prediction
        )
        prediction.winner_name = (
            fighter1.name if prediction.winner_id == fighter1_id else fighter2.name
            if fighter1 and fighter2 else None
        )

        # Predict method
        prediction.method = self._predict_method(
            prediction.winner_id,
            fighter1_id,
            fighter2_id,
            ratings1,
            ratings2,
            prediction,
        )

        # Predict round
        prediction.round_prediction = self._predict_round(
            prediction.method,
            ratings1,
            ratings2,
            scheduled_rounds,
            is_title_fight,
        )

        # Generate X-factors
        prediction.x_factors = self._generate_x_factors(
            ratings1, ratings2, fighter1, fighter2, prediction
        )

        return prediction

    def _check_refusal(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        fighter1: Optional[Fighter],
        fighter2: Optional[Fighter],
    ) -> Optional[str]:
        """Check if prediction should be refused."""
        if ratings1.total_fights < MIN_FIGHTS_FOR_PREDICTION:
            name = fighter1.name if fighter1 else ratings1.fighter_id
            return f"{name} has insufficient UFC fight history for prediction"

        if ratings2.total_fights < MIN_FIGHTS_FOR_PREDICTION:
            name = fighter2.name if fighter2 else ratings2.fighter_id
            return f"{name} has insufficient UFC fight history for prediction"

        return None

    def _analyze_dimensions(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
    ) -> DimensionBreakdown:
        """Analyze dimension-by-dimension advantages."""
        advantages = []
        fighter1_strengths = []
        fighter2_strengths = []

        for dim in SkillDimension:
            r1 = ratings1.get_rating(dim)
            r2 = ratings2.get_rating(dim)
            diff = r1 - r2
            significant = abs(diff) >= SIGNIFICANT_ADVANTAGE_THRESHOLD

            advantages.append(
                DimensionAdvantage(
                    dimension=dim,
                    fighter1_rating=r1,
                    fighter2_rating=r2,
                    difference=diff,
                    significant=significant,
                )
            )

            if significant:
                if diff > 0:
                    fighter1_strengths.append(dim)
                else:
                    fighter2_strengths.append(dim)

        # Determine key dimensions for this matchup
        key_dimensions = self._identify_key_dimensions(ratings1, ratings2)

        return DimensionBreakdown(
            advantages=advantages,
            fighter1_strengths=fighter1_strengths,
            fighter2_strengths=fighter2_strengths,
            key_dimensions=key_dimensions,
        )

    def _identify_key_dimensions(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
    ) -> list[SkillDimension]:
        """Identify which dimensions will be most impactful for this matchup."""
        key_dims = []

        # If one fighter has strong wrestling, TD defense becomes key
        wrestling_off_diff = (
            ratings1.get_rating(SkillDimension.WRESTLING_OFFENSE)
            - ratings2.get_rating(SkillDimension.WRESTLING_OFFENSE)
        )
        if abs(wrestling_off_diff) > 50:
            key_dims.append(SkillDimension.WRESTLING_DEFENSE)
            key_dims.append(SkillDimension.WRESTLING_OFFENSE)

        # If both are strikers, striking dimensions are key
        avg_wrestling = (
            ratings1.get_rating(SkillDimension.WRESTLING_OFFENSE)
            + ratings2.get_rating(SkillDimension.WRESTLING_OFFENSE)
        ) / 2
        if avg_wrestling < 1550:  # Both relatively low wrestling
            key_dims.append(SkillDimension.KNOCKOUT_POWER)
            key_dims.append(SkillDimension.STRIKING_DEFENSE)

        # If one has high submission offense, sub defense is key
        sub_off_max = max(
            ratings1.get_rating(SkillDimension.SUBMISSION_OFFENSE),
            ratings2.get_rating(SkillDimension.SUBMISSION_OFFENSE),
        )
        if sub_off_max > 1600:
            key_dims.append(SkillDimension.SUBMISSION_DEFENSE)

        # Cardio is always relevant for 5-round fights
        key_dims.append(SkillDimension.CARDIO)

        return list(set(key_dims))  # Remove duplicates

    def _analyze_style_matchup(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
    ) -> StyleMatchup:
        """Analyze stylistic matchup between fighters."""
        # Determine striker vs grappler dynamic
        striker_vs_grappler = None
        striking1 = (
            ratings1.get_rating(SkillDimension.KNOCKOUT_POWER)
            + ratings1.get_rating(SkillDimension.STRIKING_VOLUME)
        ) / 2
        grappling1 = (
            ratings1.get_rating(SkillDimension.WRESTLING_OFFENSE)
            + ratings1.get_rating(SkillDimension.SUBMISSION_OFFENSE)
        ) / 2
        striking2 = (
            ratings2.get_rating(SkillDimension.KNOCKOUT_POWER)
            + ratings2.get_rating(SkillDimension.STRIKING_VOLUME)
        ) / 2
        grappling2 = (
            ratings2.get_rating(SkillDimension.WRESTLING_OFFENSE)
            + ratings2.get_rating(SkillDimension.SUBMISSION_OFFENSE)
        ) / 2

        # Check for clear striker vs grappler
        if striking1 > grappling1 + 50 and grappling2 > striking2 + 50:
            striker_vs_grappler = "fighter1_striker"
        elif striking2 > grappling2 + 50 and grappling1 > striking1 + 50:
            striker_vs_grappler = "fighter2_striker"

        # Pressure dynamic
        pressure1 = ratings1.get_rating(SkillDimension.PRESSURE)
        pressure2 = ratings2.get_rating(SkillDimension.PRESSURE)
        if pressure1 > pressure2 + 50:
            pressure_dynamic = "fighter1_pressures"
        elif pressure2 > pressure1 + 50:
            pressure_dynamic = "fighter2_pressures"
        else:
            pressure_dynamic = "neutral"

        # Cardio factor
        cardio1 = ratings1.get_rating(SkillDimension.CARDIO)
        cardio2 = ratings2.get_rating(SkillDimension.CARDIO)
        if cardio1 > cardio2 + 50:
            cardio_factor = "fighter1_advantage"
        elif cardio2 > cardio1 + 50:
            cardio_factor = "fighter2_advantage"
        else:
            cardio_factor = "even"

        # Experience edge
        experience_edge = None
        if ratings1.total_fights > ratings2.total_fights + 5:
            experience_edge = "fighter1"
        elif ratings2.total_fights > ratings1.total_fights + 5:
            experience_edge = "fighter2"

        return StyleMatchup(
            striker_vs_grappler=striker_vs_grappler,
            pressure_dynamic=pressure_dynamic,
            cardio_factor=cardio_factor,
            experience_edge=experience_edge,
        )

    def _predict_winner(
        self,
        fighter1_id: str,
        fighter2_id: str,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        prediction: Prediction,
    ) -> str:
        """Predict the winner of the fight."""
        # Start with overall rating differential
        score = prediction.rating_differential

        # Apply stylistic adjustments for close fights
        if prediction.is_close_fight and prediction.style_matchup:
            score += self._apply_style_adjustments(
                ratings1, ratings2, prediction.style_matchup
            )

        # Tiebreaker: experience
        if abs(score) < 10:
            if ratings1.total_fights > ratings2.total_fights:
                score += 5
            elif ratings2.total_fights > ratings1.total_fights:
                score -= 5

        return fighter1_id if score >= 0 else fighter2_id

    def _apply_style_adjustments(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        style: StyleMatchup,
    ) -> float:
        """Apply stylistic adjustments for close fights."""
        adjustment = 0.0

        # Striker vs grappler: check if grappler can get it down
        if style.striker_vs_grappler == "fighter1_striker":
            # Fighter 1 is striker, fighter 2 is grappler
            # Check TDD of striker vs wrestling of grappler
            tdd = ratings1.get_rating(SkillDimension.WRESTLING_DEFENSE)
            wrestling = ratings2.get_rating(SkillDimension.WRESTLING_OFFENSE)
            if tdd > wrestling:
                adjustment += 20  # Striker can keep it standing
            else:
                adjustment -= 20  # Grappler can get it down

        elif style.striker_vs_grappler == "fighter2_striker":
            tdd = ratings2.get_rating(SkillDimension.WRESTLING_DEFENSE)
            wrestling = ratings1.get_rating(SkillDimension.WRESTLING_OFFENSE)
            if tdd > wrestling:
                adjustment -= 20
            else:
                adjustment += 20

        # Pressure fighter advantage in close fights
        if style.pressure_dynamic == "fighter1_pressures":
            adjustment += 10
        elif style.pressure_dynamic == "fighter2_pressures":
            adjustment -= 10

        return adjustment

    def _predict_method(
        self,
        winner_id: str,
        fighter1_id: str,
        fighter2_id: str,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        prediction: Prediction,
    ) -> MethodPrediction:
        """Predict the method of victory."""
        winner_ratings = ratings1 if winner_id == fighter1_id else ratings2
        loser_ratings = ratings2 if winner_id == fighter1_id else ratings1

        # Calculate finish potential scores
        ko_score = self._calculate_ko_potential(winner_ratings, loser_ratings)
        sub_score = self._calculate_sub_potential(winner_ratings, loser_ratings)
        decision_score = self._calculate_decision_potential(
            winner_ratings, loser_ratings, prediction.is_close_fight
        )

        # Determine method based on highest score
        scores = {
            PredictionMethod.KO_TKO: ko_score,
            PredictionMethod.SUBMISSION: sub_score,
            PredictionMethod.DECISION: decision_score,
        }
        method = max(scores, key=scores.get)

        # Determine confidence
        sorted_scores = sorted(scores.values(), reverse=True)
        gap = sorted_scores[0] - sorted_scores[1]
        if gap > 30:
            confidence = "high"
        elif gap > 15:
            confidence = "medium"
        else:
            confidence = "low"

        return MethodPrediction(method=method, confidence=confidence)

    def _calculate_ko_potential(
        self,
        winner: FighterRatings,
        loser: FighterRatings,
    ) -> float:
        """Calculate KO/TKO finish potential."""
        score = 0.0

        # Winner's knockout power (primary factor)
        ko_power = winner.get_rating(SkillDimension.KNOCKOUT_POWER)
        score += (ko_power - 1500) * 0.7  # Increased weight

        # Loser's chin vulnerability
        chin_rating = loser.get_rating(SkillDimension.STRIKING_DEFENSE)
        chin_penalty = loser.ko_losses * 20  # Increased penalty per KO loss
        score += (1500 - chin_rating) * 0.4 + chin_penalty

        # Volume striking contributes to TKO potential
        volume = winner.get_rating(SkillDimension.STRIKING_VOLUME)
        score += (volume - 1500) * 0.25

        # Pressure creates more KO opportunities
        pressure = winner.get_rating(SkillDimension.PRESSURE)
        score += (pressure - 1500) * 0.15

        return score

    def _calculate_sub_potential(
        self,
        winner: FighterRatings,
        loser: FighterRatings,
    ) -> float:
        """Calculate submission finish potential."""
        score = 0.0

        # Winner's submission offense (primary factor)
        sub_off = winner.get_rating(SkillDimension.SUBMISSION_OFFENSE)
        score += (sub_off - 1500) * 0.8  # Increased weight

        # Loser's submission defense
        sub_def = loser.get_rating(SkillDimension.SUBMISSION_DEFENSE)
        score += (1500 - sub_def) * 0.5  # Increased weight

        # Wrestling offense helps get to position
        wrestling = winner.get_rating(SkillDimension.WRESTLING_OFFENSE)
        score += (wrestling - 1500) * 0.3

        # Loser's weak takedown defense creates more sub opportunities
        td_def = loser.get_rating(SkillDimension.WRESTLING_DEFENSE)
        score += (1500 - td_def) * 0.2

        return score

    def _calculate_decision_potential(
        self,
        winner: FighterRatings,
        loser: FighterRatings,
        is_close_fight: bool,
    ) -> float:
        """Calculate decision potential."""
        score = 20.0  # Reduced base decision score

        # Close fights more likely to go to decision
        if is_close_fight:
            score += 30

        # Good cardio increases decision likelihood
        cardio_winner = winner.get_rating(SkillDimension.CARDIO)
        cardio_loser = loser.get_rating(SkillDimension.CARDIO)
        avg_cardio = (cardio_winner + cardio_loser) / 2
        score += (avg_cardio - 1500) * 0.25

        # Good defense on both sides increases decision likelihood
        strike_def_winner = winner.get_rating(SkillDimension.STRIKING_DEFENSE)
        strike_def_loser = loser.get_rating(SkillDimension.STRIKING_DEFENSE)
        avg_strike_def = (strike_def_winner + strike_def_loser) / 2
        score += (avg_strike_def - 1500) * 0.35

        # High submission defense on loser decreases sub finish likelihood
        sub_def_loser = loser.get_rating(SkillDimension.SUBMISSION_DEFENSE)
        score += (sub_def_loser - 1500) * 0.2

        # Low KO power from winner increases decision likelihood
        ko_power = winner.get_rating(SkillDimension.KNOCKOUT_POWER)
        score += (1500 - ko_power) * 0.2

        # Good chin on loser (low KO losses) increases decision likelihood
        if loser.ko_losses == 0:
            score += 15
        elif loser.ko_losses == 1:
            score += 5

        return score

    def _predict_round(
        self,
        method: MethodPrediction,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        scheduled_rounds: int,
        is_title_fight: bool,
    ) -> RoundPrediction:
        """Predict the round of finish."""
        if method.method == PredictionMethod.DECISION:
            return RoundPrediction(
                round_number=None,
                is_decision=True,
                scheduled_rounds=scheduled_rounds,
            )

        # Calculate finish timing based on style
        early_finish_score = 0.0

        # High KO power = earlier finish
        max_ko_power = max(
            ratings1.get_rating(SkillDimension.KNOCKOUT_POWER),
            ratings2.get_rating(SkillDimension.KNOCKOUT_POWER),
        )
        early_finish_score += (max_ko_power - 1500) * 0.3

        # Poor cardio = earlier finish
        min_cardio = min(
            ratings1.get_rating(SkillDimension.CARDIO),
            ratings2.get_rating(SkillDimension.CARDIO),
        )
        early_finish_score += (1500 - min_cardio) * 0.2

        # High pressure = earlier finish
        max_pressure = max(
            ratings1.get_rating(SkillDimension.PRESSURE),
            ratings2.get_rating(SkillDimension.PRESSURE),
        )
        early_finish_score += (max_pressure - 1500) * 0.15

        # Convert score to round prediction
        if early_finish_score > 40:
            round_num = 1
        elif early_finish_score > 20:
            round_num = 2
        elif early_finish_score > 0:
            round_num = 3
        elif scheduled_rounds == 5:
            round_num = 4
        else:
            round_num = 3

        # Cap at scheduled rounds
        round_num = min(round_num, scheduled_rounds)

        return RoundPrediction(
            round_number=round_num,
            is_decision=False,
            scheduled_rounds=scheduled_rounds,
        )

    def _generate_x_factors(
        self,
        ratings1: FighterRatings,
        ratings2: FighterRatings,
        fighter1: Optional[Fighter],
        fighter2: Optional[Fighter],
        prediction: Prediction,
    ) -> list[str]:
        """Generate X-factor notes for the prediction."""
        x_factors = []

        # Chin concerns
        if ratings1.ko_losses >= 3:
            name = fighter1.name if fighter1 else "Fighter 1"
            x_factors.append(f"{name} has shown chin vulnerability ({ratings1.ko_losses} KO losses)")
        if ratings2.ko_losses >= 3:
            name = fighter2.name if fighter2 else "Fighter 2"
            x_factors.append(f"{name} has shown chin vulnerability ({ratings2.ko_losses} KO losses)")

        # Experience gap
        if prediction.style_matchup and prediction.style_matchup.experience_edge:
            edge = prediction.style_matchup.experience_edge
            name = (
                fighter1.name if edge == "fighter1" and fighter1
                else fighter2.name if edge == "fighter2" and fighter2
                else edge
            )
            x_factors.append(f"{name} holds significant experience advantage")

        # Cardio concerns in 5-round fights
        if prediction.round_prediction and prediction.round_prediction.scheduled_rounds == 5:
            if prediction.style_matchup and prediction.style_matchup.cardio_factor != "even":
                if prediction.style_matchup.cardio_factor == "fighter1_advantage":
                    name = fighter1.name if fighter1 else "Fighter 1"
                else:
                    name = fighter2.name if fighter2 else "Fighter 2"
                x_factors.append(f"{name} has cardio edge in championship rounds")

        # Striker vs grappler dynamic
        if prediction.style_matchup and prediction.style_matchup.striker_vs_grappler:
            if "striker" in prediction.style_matchup.striker_vs_grappler:
                x_factors.append("Classic striker vs grappler matchup - where the fight takes place will be decisive")

        return x_factors
