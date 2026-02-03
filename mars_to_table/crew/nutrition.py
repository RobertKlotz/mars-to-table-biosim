"""
Mars to Table — Nutrition Tracking
Calorie, macronutrient, and micronutrient tracking for crew health.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging

from ..config import MISSION

logger = logging.getLogger(__name__)


@dataclass
class MacroNutrients:
    """Macronutrient values."""
    calories: float = 0.0
    protein_g: float = 0.0
    carbohydrates_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0
    water_ml: float = 0.0

    def __add__(self, other: 'MacroNutrients') -> 'MacroNutrients':
        """Add two MacroNutrients together."""
        return MacroNutrients(
            calories=self.calories + other.calories,
            protein_g=self.protein_g + other.protein_g,
            carbohydrates_g=self.carbohydrates_g + other.carbohydrates_g,
            fat_g=self.fat_g + other.fat_g,
            fiber_g=self.fiber_g + other.fiber_g,
            water_ml=self.water_ml + other.water_ml,
        )

    def __mul__(self, factor: float) -> 'MacroNutrients':
        """Multiply all values by a factor."""
        return MacroNutrients(
            calories=self.calories * factor,
            protein_g=self.protein_g * factor,
            carbohydrates_g=self.carbohydrates_g * factor,
            fat_g=self.fat_g * factor,
            fiber_g=self.fiber_g * factor,
            water_ml=self.water_ml * factor,
        )

    @property
    def protein_calories(self) -> float:
        """Calories from protein (4 kcal/g)."""
        return self.protein_g * 4

    @property
    def carb_calories(self) -> float:
        """Calories from carbohydrates (4 kcal/g)."""
        return self.carbohydrates_g * 4

    @property
    def fat_calories(self) -> float:
        """Calories from fat (9 kcal/g)."""
        return self.fat_g * 9

    @property
    def macro_ratio(self) -> Dict[str, float]:
        """Get macronutrient ratio by calories."""
        total = self.protein_calories + self.carb_calories + self.fat_calories
        if total == 0:
            return {"protein": 0, "carbs": 0, "fat": 0}
        return {
            "protein": self.protein_calories / total,
            "carbs": self.carb_calories / total,
            "fat": self.fat_calories / total,
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbohydrates_g": self.carbohydrates_g,
            "fat_g": self.fat_g,
            "fiber_g": self.fiber_g,
            "water_ml": self.water_ml,
            "macro_ratio": self.macro_ratio,
        }


@dataclass
class MicroNutrients:
    """Micronutrient values (vitamins and minerals)."""
    # Vitamins (in mg or mcg as noted)
    vitamin_a_mcg: float = 0.0
    vitamin_c_mg: float = 0.0
    vitamin_d_mcg: float = 0.0
    vitamin_e_mg: float = 0.0
    vitamin_k_mcg: float = 0.0
    vitamin_b1_mg: float = 0.0  # Thiamin
    vitamin_b2_mg: float = 0.0  # Riboflavin
    vitamin_b3_mg: float = 0.0  # Niacin
    vitamin_b6_mg: float = 0.0
    vitamin_b12_mcg: float = 0.0
    folate_mcg: float = 0.0

    # Minerals (in mg)
    calcium_mg: float = 0.0
    iron_mg: float = 0.0
    magnesium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    potassium_mg: float = 0.0
    sodium_mg: float = 0.0
    zinc_mg: float = 0.0

    def __add__(self, other: 'MicroNutrients') -> 'MicroNutrients':
        """Add two MicroNutrients together."""
        return MicroNutrients(
            vitamin_a_mcg=self.vitamin_a_mcg + other.vitamin_a_mcg,
            vitamin_c_mg=self.vitamin_c_mg + other.vitamin_c_mg,
            vitamin_d_mcg=self.vitamin_d_mcg + other.vitamin_d_mcg,
            vitamin_e_mg=self.vitamin_e_mg + other.vitamin_e_mg,
            vitamin_k_mcg=self.vitamin_k_mcg + other.vitamin_k_mcg,
            vitamin_b1_mg=self.vitamin_b1_mg + other.vitamin_b1_mg,
            vitamin_b2_mg=self.vitamin_b2_mg + other.vitamin_b2_mg,
            vitamin_b3_mg=self.vitamin_b3_mg + other.vitamin_b3_mg,
            vitamin_b6_mg=self.vitamin_b6_mg + other.vitamin_b6_mg,
            vitamin_b12_mcg=self.vitamin_b12_mcg + other.vitamin_b12_mcg,
            folate_mcg=self.folate_mcg + other.folate_mcg,
            calcium_mg=self.calcium_mg + other.calcium_mg,
            iron_mg=self.iron_mg + other.iron_mg,
            magnesium_mg=self.magnesium_mg + other.magnesium_mg,
            phosphorus_mg=self.phosphorus_mg + other.phosphorus_mg,
            potassium_mg=self.potassium_mg + other.potassium_mg,
            sodium_mg=self.sodium_mg + other.sodium_mg,
            zinc_mg=self.zinc_mg + other.zinc_mg,
        )


@dataclass
class NutrientRequirements:
    """
    Daily nutrient requirements based on NASA STD-3001.

    Values for active astronaut (moderate activity).
    """
    # Macros
    calories: float = 3035.0
    protein_g: float = 75.0          # ~10% of calories
    carbohydrates_g: float = 400.0   # ~53% of calories
    fat_g: float = 100.0             # ~30% of calories
    fiber_g: float = 30.0
    water_ml: float = 3000.0

    # Vitamins
    vitamin_a_mcg: float = 900.0
    vitamin_c_mg: float = 90.0
    vitamin_d_mcg: float = 20.0
    vitamin_e_mg: float = 15.0
    vitamin_k_mcg: float = 120.0
    vitamin_b1_mg: float = 1.2
    vitamin_b2_mg: float = 1.3
    vitamin_b3_mg: float = 16.0
    vitamin_b6_mg: float = 1.7
    vitamin_b12_mcg: float = 2.4
    folate_mcg: float = 400.0

    # Minerals
    calcium_mg: float = 1200.0   # Higher for bone health in low gravity
    iron_mg: float = 10.0
    magnesium_mg: float = 420.0
    phosphorus_mg: float = 700.0
    potassium_mg: float = 3500.0
    sodium_mg: float = 2300.0    # Upper limit
    zinc_mg: float = 11.0


class NutritionStatus(Enum):
    """Nutritional status categories."""
    OPTIMAL = auto()      # Meeting all requirements
    ADEQUATE = auto()     # Meeting most requirements (>80%)
    MARGINAL = auto()     # Below requirements (60-80%)
    DEFICIENT = auto()    # Significantly below (<60%)
    EXCESS = auto()       # Above safe upper limits


@dataclass
class DailyNutritionLog:
    """Log of nutrition for a single day."""
    sol: int
    macros: MacroNutrients = field(default_factory=MacroNutrients)
    micros: MicroNutrients = field(default_factory=MicroNutrients)

    # Meal breakdown
    breakfast_calories: float = 0.0
    lunch_calories: float = 0.0
    dinner_calories: float = 0.0
    snack_calories: float = 0.0

    # Source tracking
    in_situ_calories: float = 0.0
    earth_supply_calories: float = 0.0

    @property
    def earth_independence(self) -> float:
        """Calculate Earth independence (% calories from in-situ)."""
        total = self.in_situ_calories + self.earth_supply_calories
        return self.in_situ_calories / total if total > 0 else 0


class NutritionTracker:
    """
    Tracks nutrition for the entire crew.

    Monitors:
    - Daily intake vs requirements
    - Macronutrient balance
    - Earth independence
    - Deficiency alerts
    """

    def __init__(self, crew_size: int = None):
        self.crew_size = crew_size or MISSION.crew_size
        self.requirements = NutrientRequirements()

        # Current day tracking
        self.current_sol = 0
        self.current_day_log: Optional[DailyNutritionLog] = None

        # History
        self.daily_logs: List[DailyNutritionLog] = []

        # Aggregate tracking
        self.total_calories_consumed = 0.0
        self.total_in_situ_calories = 0.0
        self.total_earth_calories = 0.0

        # Deficiency tracking (days with <80% of requirement)
        self.deficiency_counts: Dict[str, int] = {
            "calories": 0,
            "protein": 0,
            "calcium": 0,
            "iron": 0,
            "vitamin_c": 0,
            "vitamin_d": 0,
        }

    def start_day(self, sol: int):
        """Start tracking a new day."""
        self.current_sol = sol
        self.current_day_log = DailyNutritionLog(sol=sol)

    def log_meal(self, meal_type: str, macros: MacroNutrients,
                 in_situ_fraction: float = 0.84):
        """
        Log a meal's nutrition.

        Args:
            meal_type: 'breakfast', 'lunch', 'dinner', or 'snack'
            macros: Macronutrient values for the meal (per person)
            in_situ_fraction: Fraction from in-situ sources
        """
        if not self.current_day_log:
            self.start_day(self.current_sol or 1)

        # Scale for crew
        crew_macros = macros * self.crew_size

        # Add to daily totals
        self.current_day_log.macros = self.current_day_log.macros + crew_macros

        # Track by meal type
        if meal_type == "breakfast":
            self.current_day_log.breakfast_calories += crew_macros.calories
        elif meal_type == "lunch":
            self.current_day_log.lunch_calories += crew_macros.calories
        elif meal_type == "dinner":
            self.current_day_log.dinner_calories += crew_macros.calories
        else:
            self.current_day_log.snack_calories += crew_macros.calories

        # Track source
        in_situ = crew_macros.calories * in_situ_fraction
        earth = crew_macros.calories * (1 - in_situ_fraction)
        self.current_day_log.in_situ_calories += in_situ
        self.current_day_log.earth_supply_calories += earth

    def end_day(self) -> Dict:
        """
        End day and generate summary.

        Returns nutritional assessment for the day.
        """
        if not self.current_day_log:
            return {"error": "No day started"}

        log = self.current_day_log
        per_person = log.macros * (1 / self.crew_size)

        # Calculate status for key nutrients
        calorie_ratio = per_person.calories / self.requirements.calories
        protein_ratio = per_person.protein_g / self.requirements.protein_g

        # Determine overall status
        if calorie_ratio >= 0.95 and protein_ratio >= 0.95:
            status = NutritionStatus.OPTIMAL
        elif calorie_ratio >= 0.80 and protein_ratio >= 0.80:
            status = NutritionStatus.ADEQUATE
        elif calorie_ratio >= 0.60 and protein_ratio >= 0.60:
            status = NutritionStatus.MARGINAL
        else:
            status = NutritionStatus.DEFICIENT

        # Track deficiencies
        if calorie_ratio < 0.80:
            self.deficiency_counts["calories"] += 1
        if protein_ratio < 0.80:
            self.deficiency_counts["protein"] += 1

        # Update totals
        self.total_calories_consumed += log.macros.calories
        self.total_in_situ_calories += log.in_situ_calories
        self.total_earth_calories += log.earth_supply_calories

        # Save to history
        self.daily_logs.append(log)

        summary = {
            "sol": log.sol,
            "status": status.name,
            "per_person": {
                "calories": per_person.calories,
                "protein_g": per_person.protein_g,
                "carbs_g": per_person.carbohydrates_g,
                "fat_g": per_person.fat_g,
                "macro_ratio": per_person.macro_ratio,
            },
            "requirements_met": {
                "calories": calorie_ratio,
                "protein": protein_ratio,
            },
            "crew_total": {
                "calories": log.macros.calories,
                "protein_g": log.macros.protein_g,
            },
            "meal_breakdown": {
                "breakfast": log.breakfast_calories,
                "lunch": log.lunch_calories,
                "dinner": log.dinner_calories,
                "snacks": log.snack_calories,
            },
            "earth_independence": log.earth_independence,
        }

        # Reset for next day
        self.current_day_log = None

        return summary

    def get_running_average(self, days: int = 7) -> Dict:
        """Get running average nutrition over recent days."""
        if not self.daily_logs:
            return {}

        recent = self.daily_logs[-days:]
        avg_macros = MacroNutrients()

        for log in recent:
            avg_macros = avg_macros + (log.macros * (1 / len(recent)))

        per_person = avg_macros * (1 / self.crew_size)

        return {
            "days_averaged": len(recent),
            "avg_calories_per_person": per_person.calories,
            "avg_protein_per_person": per_person.protein_g,
            "avg_carbs_per_person": per_person.carbohydrates_g,
            "avg_fat_per_person": per_person.fat_g,
            "avg_macro_ratio": per_person.macro_ratio,
            "calorie_requirement_met": per_person.calories / self.requirements.calories,
        }

    def get_earth_independence(self) -> float:
        """Get overall Earth independence percentage."""
        total = self.total_in_situ_calories + self.total_earth_calories
        return self.total_in_situ_calories / total if total > 0 else 0

    def get_deficiency_alerts(self) -> List[str]:
        """Get list of nutritional deficiency alerts."""
        alerts = []

        if self.deficiency_counts["calories"] >= 3:
            alerts.append(f"WARNING: Calorie deficit for {self.deficiency_counts['calories']} days")

        if self.deficiency_counts["protein"] >= 3:
            alerts.append(f"WARNING: Protein deficit for {self.deficiency_counts['protein']} days")

        return alerts

    def get_status(self) -> Dict:
        """Get current nutrition tracking status."""
        return {
            "crew_size": self.crew_size,
            "current_sol": self.current_sol,
            "total_calories_consumed": self.total_calories_consumed,
            "earth_independence": self.get_earth_independence(),
            "target_earth_independence": MISSION.target_earth_independence,
            "meeting_independence_target": self.get_earth_independence() >= MISSION.min_earth_independence,
            "deficiency_counts": self.deficiency_counts,
            "alerts": self.get_deficiency_alerts(),
            "running_average": self.get_running_average(),
        }

    def generate_report(self) -> Dict:
        """Generate comprehensive nutrition report."""
        if not self.daily_logs:
            return {"error": "No data logged"}

        total_days = len(self.daily_logs)

        # Calculate averages
        total_macros = MacroNutrients()
        for log in self.daily_logs:
            total_macros = total_macros + log.macros

        avg_per_person_per_day = total_macros * (1 / (total_days * self.crew_size))

        return {
            "report_period_sols": total_days,
            "crew_size": self.crew_size,
            "average_daily_per_person": avg_per_person_per_day.to_dict(),
            "requirements": {
                "calories": self.requirements.calories,
                "protein_g": self.requirements.protein_g,
                "carbs_g": self.requirements.carbohydrates_g,
                "fat_g": self.requirements.fat_g,
            },
            "requirement_satisfaction": {
                "calories": avg_per_person_per_day.calories / self.requirements.calories,
                "protein": avg_per_person_per_day.protein_g / self.requirements.protein_g,
                "carbs": avg_per_person_per_day.carbohydrates_g / self.requirements.carbohydrates_g,
                "fat": avg_per_person_per_day.fat_g / self.requirements.fat_g,
            },
            "earth_independence": {
                "achieved": self.get_earth_independence(),
                "target": MISSION.target_earth_independence,
                "minimum_required": MISSION.min_earth_independence,
                "passing": self.get_earth_independence() >= MISSION.min_earth_independence,
            },
            "deficiency_summary": self.deficiency_counts,
            "health_alerts": self.get_deficiency_alerts(),
        }
