"""
Mars to Table — Human Factors Modeling

Crew psychology, morale, and human factors that affect food production:
- Individual crew member psychological profiles
- Team dynamics and interpersonal relationships
- Food satisfaction and dietary variety impacts
- Work performance and productivity
- Stress responses and coping mechanisms
- Long-duration isolation effects
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum, auto
import random
import math
import logging

logger = logging.getLogger(__name__)


class PsychologicalState(Enum):
    """Overall psychological state categories."""
    OPTIMAL = auto()        # 90-100% functioning
    GOOD = auto()           # 75-89%
    ADEQUATE = auto()       # 60-74%
    STRESSED = auto()       # 45-59%
    STRUGGLING = auto()     # 30-44%
    CRITICAL = auto()       # <30%


class StressorType(Enum):
    """Types of stressors affecting crew."""
    ISOLATION = auto()          # Distance from Earth, confinement
    WORKLOAD = auto()           # Task demands
    INTERPERSONAL = auto()      # Crew conflicts
    FOOD_MONOTONY = auto()      # Lack of dietary variety
    FOOD_QUALITY = auto()       # Unpleasant food
    FOOD_SCARCITY = auto()      # Insufficient calories
    SLEEP_DISRUPTION = auto()   # Circadian issues
    ENVIRONMENTAL = auto()      # Habitat conditions
    HEALTH_CONCERN = auto()     # Medical issues
    HOMESICKNESS = auto()       # Missing Earth
    MISSION_STRESS = auto()     # Mission-critical events


class CopingMechanism(Enum):
    """Coping strategies available to crew."""
    SOCIAL_SUPPORT = auto()     # Talking with crewmates
    EXERCISE = auto()           # Physical activity
    RECREATION = auto()         # Entertainment, hobbies
    GARDENING = auto()          # Therapeutic plant care
    COOKING = auto()            # Food preparation as activity
    COMMUNICATION = auto()      # Contact with Earth
    MEDITATION = auto()         # Mindfulness practices
    WORK_FOCUS = auto()         # Immersion in tasks


@dataclass
class MealSatisfaction:
    """Tracks satisfaction from a meal."""
    tick: int
    calories: float
    protein_g: float
    variety_score: float  # 0-1, based on unique ingredients
    taste_score: float    # 0-1, based on preparation/freshness
    cultural_match: float # 0-1, how well it matches preferences
    social_context: float # 0-1, eating with others
    overall_satisfaction: float = 0.0

    def __post_init__(self):
        # Calculate overall satisfaction
        weights = {
            "calories": 0.2,  # Having enough food
            "variety": 0.25,  # Not eating same thing daily
            "taste": 0.25,    # Food tastes good
            "cultural": 0.15, # Familiar/preferred foods
            "social": 0.15,   # Eating together
        }

        calorie_score = min(1.0, self.calories / 2000)  # Based on 2000 cal target

        self.overall_satisfaction = (
            weights["calories"] * calorie_score +
            weights["variety"] * self.variety_score +
            weights["taste"] * self.taste_score +
            weights["cultural"] * self.cultural_match +
            weights["social"] * self.social_context
        )


@dataclass
class CrewMemberPsychology:
    """
    Psychological profile and state for one crew member.

    Based on NASA astronaut selection criteria and long-duration
    mission research (ISS expeditions, HERA studies, Mars-500).
    """
    crew_id: str
    name: str

    # Personality traits (Big Five, 0-1 scale)
    openness: float = 0.7           # Creativity, curiosity
    conscientiousness: float = 0.8  # Organization, discipline
    extraversion: float = 0.5       # Social energy
    agreeableness: float = 0.7      # Cooperation, trust
    neuroticism: float = 0.3        # Emotional instability (lower is better)

    # Current psychological state
    morale: float = 0.85            # Overall well-being (0-1)
    stress_level: float = 0.2       # Current stress (0-1)
    fatigue: float = 0.1            # Accumulated tiredness (0-1)
    food_satisfaction: float = 0.8  # Satisfaction with food (0-1)

    # Performance factors
    work_efficiency: float = 1.0    # Productivity multiplier
    error_rate: float = 0.02        # Chance of errors in tasks

    # Social factors
    team_cohesion: float = 0.8      # Bond with team
    isolation_tolerance: float = 0.7 # Ability to handle confinement

    # Food preferences
    food_preferences: Dict[str, float] = field(default_factory=dict)
    dietary_restrictions: List[str] = field(default_factory=list)

    # History tracking
    meal_history: List[MealSatisfaction] = field(default_factory=list)
    stress_history: List[tuple] = field(default_factory=list)

    # Role in food system
    food_system_role: str = "consumer"  # consumer, gardener, chef, veterinarian

    def get_psychological_state(self) -> PsychologicalState:
        """Determine overall psychological state category."""
        # Combine factors into overall score
        overall = (
            self.morale * 0.35 +
            (1 - self.stress_level) * 0.25 +
            (1 - self.fatigue) * 0.15 +
            self.food_satisfaction * 0.15 +
            self.team_cohesion * 0.10
        )

        if overall >= 0.9:
            return PsychologicalState.OPTIMAL
        elif overall >= 0.75:
            return PsychologicalState.GOOD
        elif overall >= 0.6:
            return PsychologicalState.ADEQUATE
        elif overall >= 0.45:
            return PsychologicalState.STRESSED
        elif overall >= 0.3:
            return PsychologicalState.STRUGGLING
        else:
            return PsychologicalState.CRITICAL

    def get_food_system_productivity(self) -> float:
        """
        Get productivity multiplier for food system tasks.

        Affected by morale, stress, fatigue, and role experience.
        """
        base = self.work_efficiency

        # Morale impact
        if self.morale < 0.5:
            base *= 0.7 + (self.morale * 0.6)

        # Stress impact (high stress reduces performance)
        if self.stress_level > 0.6:
            base *= 1.0 - ((self.stress_level - 0.6) * 0.5)

        # Fatigue impact
        if self.fatigue > 0.7:
            base *= 0.6

        # Role bonus (experienced in food tasks)
        if self.food_system_role in ["gardener", "chef", "veterinarian"]:
            base *= 1.1

        return max(0.3, min(1.2, base))


class CrewPsychologyManager:
    """
    Manages crew psychological states and their impact on food production.

    Key research basis:
    - Mars-500 study findings on crew dynamics
    - ISS expedition psychology data
    - HERA analog mission studies
    - Antarctic winter-over research
    """

    # Isolation effects over time (days into mission)
    ISOLATION_CURVE = {
        0: 0.0,      # Launch excitement
        30: 0.1,     # Novelty wearing off
        90: 0.2,     # Routine setting in
        180: 0.3,    # "Third quarter phenomenon"
        365: 0.35,   # Full year mark
        500: 0.4,    # Mars mission duration
    }

    # Food variety decay rate (days eating same foods)
    VARIETY_DECAY_PER_DAY = 0.005

    def __init__(self, crew_size: int = 15):
        self.crew: Dict[str, CrewMemberPsychology] = {}
        self.crew_size = crew_size
        self.current_tick = 0

        # Food tracking
        self.recent_meals: List[Dict] = []
        self.unique_foods_30_days: set = set()

        # Team dynamics
        self.team_morale = 0.85
        self.interpersonal_tensions: List[Dict] = []

        # Events
        self.psychological_events: List[Dict] = []

    def initialize_crew(self, crew_profiles: Optional[List[Dict]] = None):
        """Initialize crew with psychological profiles."""
        if crew_profiles:
            for profile in crew_profiles:
                self._create_crew_member(**profile)
        else:
            # Generate default diverse crew
            roles = ["commander", "pilot", "engineer", "scientist", "physician",
                    "gardener", "gardener", "gardener", "chef", "veterinarian",
                    "technician", "technician", "scientist", "scientist", "engineer"]

            for i in range(self.crew_size):
                # Generate diverse personality types
                self._create_crew_member(
                    crew_id=f"crew_{i+1:02d}",
                    name=f"Crew Member {i+1}",
                    role=roles[i % len(roles)],
                )

        logger.info(f"Initialized {len(self.crew)} crew members")

    def _create_crew_member(
        self,
        crew_id: str,
        name: str,
        role: str = "consumer",
        personality: Optional[Dict] = None,
    ):
        """Create a crew member with realistic personality."""
        # Generate personality if not provided
        if personality is None:
            # Astronaut selection tends toward these ranges
            personality = {
                "openness": random.gauss(0.7, 0.1),
                "conscientiousness": random.gauss(0.8, 0.08),
                "extraversion": random.gauss(0.55, 0.15),
                "agreeableness": random.gauss(0.7, 0.1),
                "neuroticism": random.gauss(0.25, 0.1),  # Selected for low
            }

        # Clamp values
        for key in personality:
            personality[key] = max(0.1, min(0.95, personality[key]))

        # Map role to food system role
        food_role_map = {
            "gardener": "gardener",
            "chef": "chef",
            "cook": "chef",
            "veterinarian": "veterinarian",
            "biologist": "gardener",
        }
        food_role = food_role_map.get(role.lower(), "consumer")

        crew_member = CrewMemberPsychology(
            crew_id=crew_id,
            name=name,
            openness=personality["openness"],
            conscientiousness=personality["conscientiousness"],
            extraversion=personality["extraversion"],
            agreeableness=personality["agreeableness"],
            neuroticism=personality["neuroticism"],
            food_system_role=food_role,
            isolation_tolerance=0.6 + random.gauss(0.1, 0.05),
        )

        self.crew[crew_id] = crew_member

    def update_tick(
        self,
        tick: int,
        meal_data: Optional[Dict] = None,
        work_demands: float = 0.5,
        environmental_quality: float = 0.8,
    ) -> Dict:
        """
        Update crew psychological states for one tick.

        Args:
            tick: Current simulation tick
            meal_data: Information about the current meal (if meal time)
            work_demands: Current workload level (0-1)
            environmental_quality: Habitat quality (0-1)

        Returns:
            Summary of psychological state changes
        """
        self.current_tick = tick
        mission_day = tick // 24

        events = []
        state_changes = []

        for crew_id, member in self.crew.items():
            # Update isolation effects
            isolation_stress = self._calculate_isolation_stress(mission_day, member)

            # Update based on meal (if provided)
            if meal_data:
                meal_satisfaction = self._process_meal(member, meal_data)
                member.food_satisfaction = (
                    member.food_satisfaction * 0.9 +
                    meal_satisfaction.overall_satisfaction * 0.1
                )

            # Update stress from workload
            workload_stress = work_demands * (1 - member.conscientiousness * 0.3)

            # Update fatigue
            hour_of_day = tick % 24
            if hour_of_day in range(6, 22):  # Waking hours
                member.fatigue += 0.002 * (1 + work_demands)
            else:  # Sleep hours
                member.fatigue = max(0, member.fatigue - 0.02)

            # Combine stressors
            total_stress = (
                isolation_stress * 0.3 +
                workload_stress * 0.3 +
                (1 - member.food_satisfaction) * 0.2 +
                (1 - environmental_quality) * 0.2
            )

            # Apply personality modifiers
            total_stress *= (0.7 + member.neuroticism * 0.6)

            # Apply coping
            coping_reduction = self._apply_coping(member, tick)
            total_stress = max(0, total_stress - coping_reduction)

            # Update stress level (gradual change)
            member.stress_level = member.stress_level * 0.95 + total_stress * 0.05

            # Update morale
            morale_change = self._calculate_morale_change(member)
            member.morale = max(0.1, min(1.0, member.morale + morale_change))

            # Update work efficiency
            state = member.get_psychological_state()
            efficiency_map = {
                PsychologicalState.OPTIMAL: 1.1,
                PsychologicalState.GOOD: 1.0,
                PsychologicalState.ADEQUATE: 0.9,
                PsychologicalState.STRESSED: 0.75,
                PsychologicalState.STRUGGLING: 0.55,
                PsychologicalState.CRITICAL: 0.35,
            }
            member.work_efficiency = efficiency_map.get(state, 0.8)

            # Check for psychological events
            event = self._check_for_events(member, tick)
            if event:
                events.append(event)

            state_changes.append({
                "crew_id": crew_id,
                "state": state.name,
                "morale": member.morale,
                "stress": member.stress_level,
                "efficiency": member.work_efficiency,
            })

        # Update team dynamics
        self._update_team_dynamics()

        return {
            "events": events,
            "state_changes": state_changes,
            "team_morale": self.team_morale,
            "avg_efficiency": sum(m.work_efficiency for m in self.crew.values()) / len(self.crew),
        }

    def _calculate_isolation_stress(self, mission_day: int, member: CrewMemberPsychology) -> float:
        """Calculate stress from isolation based on mission duration."""
        # Interpolate isolation curve
        prev_day = 0
        prev_stress = 0.0

        for day, stress in sorted(self.ISOLATION_CURVE.items()):
            if mission_day <= day:
                # Linear interpolation
                if day == prev_day:
                    base_stress = stress
                else:
                    fraction = (mission_day - prev_day) / (day - prev_day)
                    base_stress = prev_stress + (stress - prev_stress) * fraction
                break
            prev_day = day
            prev_stress = stress
        else:
            base_stress = 0.4  # Max isolation stress

        # Modified by individual tolerance
        return base_stress * (1.0 - member.isolation_tolerance * 0.5)

    def _process_meal(self, member: CrewMemberPsychology, meal_data: Dict) -> MealSatisfaction:
        """Process a meal and calculate satisfaction."""
        # Track unique foods for variety calculation
        foods = meal_data.get("foods", [])
        for food in foods:
            self.unique_foods_30_days.add(food)

        # Decay variety score over time
        days_since_variety = len(member.meal_history) // 3  # ~3 meals per day
        variety_score = max(0.3, 1.0 - days_since_variety * self.VARIETY_DECAY_PER_DAY)

        # Boost variety if new foods
        new_food_bonus = sum(0.05 for f in foods if f not in [
            m.get("food", "") for m in self.recent_meals[-10:]
        ])
        variety_score = min(1.0, variety_score + new_food_bonus)

        # Taste score based on food freshness and preparation
        taste_score = meal_data.get("freshness", 0.7) * meal_data.get("preparation_quality", 0.8)

        # Cultural match based on preferences
        cultural_match = 0.6  # Base score
        for food in foods:
            if food in member.food_preferences:
                cultural_match += member.food_preferences[food] * 0.1

        cultural_match = min(1.0, cultural_match)

        # Social context (eating with others)
        social_context = meal_data.get("social_eating", 0.7)
        if member.extraversion > 0.6:
            social_context *= 1.1  # Extroverts value social meals more

        satisfaction = MealSatisfaction(
            tick=self.current_tick,
            calories=meal_data.get("calories", 600),
            protein_g=meal_data.get("protein_g", 20),
            variety_score=variety_score,
            taste_score=taste_score,
            cultural_match=cultural_match,
            social_context=social_context,
        )

        member.meal_history.append(satisfaction)

        # Limit history size
        if len(member.meal_history) > 100:
            member.meal_history = member.meal_history[-100:]

        return satisfaction

    def _apply_coping(self, member: CrewMemberPsychology, tick: int) -> float:
        """Apply coping mechanisms to reduce stress."""
        coping_effect = 0.0
        hour = tick % 24

        # Exercise (typically morning or evening)
        if hour in [6, 7, 18, 19]:
            coping_effect += 0.01 * (0.5 + member.conscientiousness * 0.5)

        # Social support (depends on team cohesion)
        if member.extraversion > 0.5:
            coping_effect += 0.005 * member.team_cohesion

        # Gardening (for gardeners, very therapeutic)
        if member.food_system_role == "gardener":
            coping_effect += 0.01 * member.openness

        # Cooking (for chefs)
        if member.food_system_role == "chef":
            coping_effect += 0.008

        return coping_effect

    def _calculate_morale_change(self, member: CrewMemberPsychology) -> float:
        """Calculate morale change for a tick."""
        change = 0.0

        # Stress reduces morale
        if member.stress_level > 0.5:
            change -= (member.stress_level - 0.5) * 0.01

        # Food satisfaction affects morale
        if member.food_satisfaction < 0.5:
            change -= (0.5 - member.food_satisfaction) * 0.005
        elif member.food_satisfaction > 0.8:
            change += (member.food_satisfaction - 0.8) * 0.002

        # Team cohesion helps
        if member.team_cohesion > 0.7:
            change += 0.001

        # Natural recovery toward baseline
        if member.morale < 0.7 and member.stress_level < 0.4:
            change += 0.002

        return change

    def _check_for_events(self, member: CrewMemberPsychology, tick: int) -> Optional[Dict]:
        """Check for psychological events requiring intervention."""
        state = member.get_psychological_state()

        # Critical state requires intervention
        if state == PsychologicalState.CRITICAL:
            return {
                "type": "critical_psychology",
                "crew_id": member.crew_id,
                "tick": tick,
                "message": f"{member.name} requires psychological intervention",
                "severity": "critical",
            }

        # Struggling state is a warning
        if state == PsychologicalState.STRUGGLING:
            return {
                "type": "struggling_psychology",
                "crew_id": member.crew_id,
                "tick": tick,
                "message": f"{member.name} showing signs of psychological stress",
                "severity": "warning",
            }

        # Low food satisfaction
        if member.food_satisfaction < 0.3:
            return {
                "type": "food_dissatisfaction",
                "crew_id": member.crew_id,
                "tick": tick,
                "message": f"{member.name} expressing significant food dissatisfaction",
                "severity": "moderate",
            }

        return None

    def _update_team_dynamics(self):
        """Update overall team dynamics."""
        # Average individual morale
        avg_morale = sum(m.morale for m in self.crew.values()) / len(self.crew)

        # Team cohesion affects group morale
        avg_cohesion = sum(m.team_cohesion for m in self.crew.values()) / len(self.crew)

        # Calculate team morale (weighted)
        self.team_morale = avg_morale * 0.7 + avg_cohesion * 0.3

        # Update individual team cohesion based on team morale
        for member in self.crew.values():
            # Gradual convergence toward team average
            member.team_cohesion = member.team_cohesion * 0.99 + avg_cohesion * 0.01

    def get_food_production_modifier(self) -> float:
        """
        Get overall productivity modifier for food production.

        Based on crew psychological state and efficiency.
        """
        # Get gardeners and food workers
        food_workers = [m for m in self.crew.values()
                       if m.food_system_role in ["gardener", "chef", "veterinarian"]]

        if not food_workers:
            # Fall back to team average
            return sum(m.work_efficiency for m in self.crew.values()) / len(self.crew)

        # Weight by role importance
        total_weight = 0
        weighted_efficiency = 0

        for worker in food_workers:
            role_weight = {"gardener": 2.0, "chef": 1.5, "veterinarian": 1.5}.get(
                worker.food_system_role, 1.0
            )
            weighted_efficiency += worker.get_food_system_productivity() * role_weight
            total_weight += role_weight

        return weighted_efficiency / total_weight if total_weight > 0 else 0.8

    def get_dietary_requirements_modifier(self) -> Dict[str, float]:
        """
        Get modifiers for dietary requirements based on psychological state.

        Stressed crew may need more comfort foods, variety, etc.
        """
        avg_stress = sum(m.stress_level for m in self.crew.values()) / len(self.crew)
        avg_morale = sum(m.morale for m in self.crew.values()) / len(self.crew)

        modifiers = {
            "variety_importance": 1.0 + (avg_stress * 0.3),  # More variety when stressed
            "comfort_food_need": 1.0 + (1 - avg_morale) * 0.5,  # More comfort food when low morale
            "calorie_adjustment": 1.0,  # Maintain calorie intake
            "protein_importance": 1.0 + (avg_stress * 0.1),  # Slightly more protein when stressed
        }

        return modifiers

    def get_crew_summary(self) -> Dict:
        """Get summary of crew psychological status."""
        states = {}
        for member in self.crew.values():
            state = member.get_psychological_state()
            states[state.name] = states.get(state.name, 0) + 1

        return {
            "crew_size": len(self.crew),
            "team_morale": self.team_morale,
            "state_distribution": states,
            "avg_morale": sum(m.morale for m in self.crew.values()) / len(self.crew),
            "avg_stress": sum(m.stress_level for m in self.crew.values()) / len(self.crew),
            "avg_food_satisfaction": sum(m.food_satisfaction for m in self.crew.values()) / len(self.crew),
            "avg_efficiency": sum(m.work_efficiency for m in self.crew.values()) / len(self.crew),
            "food_production_modifier": self.get_food_production_modifier(),
            "critical_crew": [m.name for m in self.crew.values()
                            if m.get_psychological_state() == PsychologicalState.CRITICAL],
            "struggling_crew": [m.name for m in self.crew.values()
                               if m.get_psychological_state() == PsychologicalState.STRUGGLING],
        }
