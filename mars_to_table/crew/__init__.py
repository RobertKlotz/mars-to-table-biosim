"""
Mars to Table — Crew Package
Crew modeling, meal planning, and nutrition tracking.
"""

from .crew_model import CrewMember, CrewManager, ActivityLevel, CrewRole
from .meal_plan import MealPlan, MealSlot, DailyMenu, MealPlanRotation
from .nutrition import NutritionTracker, NutrientRequirements, MacroNutrients

__all__ = [
    'CrewMember', 'CrewManager', 'ActivityLevel', 'CrewRole',
    'MealPlan', 'MealSlot', 'DailyMenu', 'MealPlanRotation',
    'NutritionTracker', 'NutrientRequirements', 'MacroNutrients',
]
