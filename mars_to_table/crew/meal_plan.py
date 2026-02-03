"""
Mars to Table — Meal Plan System
14-sol rotating meal plan with recipe tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import logging

from ..config import MISSION, FOOD

logger = logging.getLogger(__name__)


class MealSlot(Enum):
    """Meal slots in a day."""
    BREAKFAST = auto()
    LUNCH = auto()
    DINNER = auto()
    SNACK = auto()


class FoodSource(Enum):
    """Source of food ingredients."""
    IN_SITU_CROP = auto()      # Grown on Mars
    IN_SITU_LIVESTOCK = auto() # Eggs, milk, cheese from Mars
    EARTH_SUPPLY = auto()      # Pre-packaged from Earth


@dataclass
class Ingredient:
    """A single ingredient with nutritional info."""
    name: str
    source: FoodSource
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: float = 0.0
    water_content_percent: float = 0.0

    def get_nutrition(self, grams: float) -> Dict[str, float]:
        """Get nutritional values for specified amount."""
        factor = grams / 100
        return {
            "calories": self.calories_per_100g * factor,
            "protein_g": self.protein_per_100g * factor,
            "carbs_g": self.carbs_per_100g * factor,
            "fat_g": self.fat_per_100g * factor,
            "fiber_g": self.fiber_per_100g * factor,
        }


# Common ingredients library
INGREDIENTS: Dict[str, Ingredient] = {
    # Vegetables (in-situ)
    "potato": Ingredient("Potato", FoodSource.IN_SITU_CROP, 77, 2.0, 17.5, 0.1, 2.2, 79),
    "sweet_potato": Ingredient("Sweet Potato", FoodSource.IN_SITU_CROP, 86, 1.6, 20.0, 0.1, 3.0, 77),
    "tomato": Ingredient("Tomato", FoodSource.IN_SITU_CROP, 18, 0.9, 3.9, 0.2, 1.2, 95),
    "lettuce": Ingredient("Lettuce", FoodSource.IN_SITU_CROP, 15, 1.4, 2.9, 0.2, 1.3, 95),
    "spinach": Ingredient("Spinach", FoodSource.IN_SITU_CROP, 23, 2.9, 3.6, 0.4, 2.2, 91),
    "pepper": Ingredient("Bell Pepper", FoodSource.IN_SITU_CROP, 20, 0.9, 4.6, 0.2, 1.7, 92),
    "beans": Ingredient("Beans", FoodSource.IN_SITU_CROP, 31, 1.8, 7.0, 0.1, 2.7, 90),
    "peas": Ingredient("Peas", FoodSource.IN_SITU_CROP, 81, 5.4, 14.5, 0.4, 5.7, 79),
    "soybean": Ingredient("Soybean", FoodSource.IN_SITU_CROP, 147, 12.4, 11.1, 6.4, 4.2, 68),
    "herbs": Ingredient("Fresh Herbs", FoodSource.IN_SITU_CROP, 30, 2.0, 5.0, 0.5, 2.0, 85),

    # Grains (in-situ)
    "flour": Ingredient("Wheat Flour", FoodSource.IN_SITU_CROP, 364, 10.0, 76.0, 1.0, 2.7, 12),
    "bread": Ingredient("Bread", FoodSource.IN_SITU_CROP, 265, 9.0, 49.0, 3.2, 2.7, 36),
    "pasta": Ingredient("Pasta", FoodSource.IN_SITU_CROP, 131, 5.0, 25.0, 1.1, 1.8, 62),
    "rice": Ingredient("Rice", FoodSource.IN_SITU_CROP, 130, 2.7, 28.0, 0.3, 0.4, 68),

    # Livestock products (in-situ)
    "egg": Ingredient("Egg", FoodSource.IN_SITU_LIVESTOCK, 155, 12.6, 1.1, 10.6, 0.0, 75),
    "milk": Ingredient("Goat Milk", FoodSource.IN_SITU_LIVESTOCK, 69, 3.6, 4.5, 4.1, 0.0, 87),
    "cheese": Ingredient("Goat Cheese", FoodSource.IN_SITU_LIVESTOCK, 364, 22.0, 0.1, 30.0, 0.0, 45),
    "yogurt": Ingredient("Yogurt", FoodSource.IN_SITU_LIVESTOCK, 61, 3.5, 4.7, 3.3, 0.0, 88),

    # Earth-supplied
    "olive_oil": Ingredient("Olive Oil", FoodSource.EARTH_SUPPLY, 884, 0.0, 0.0, 100.0, 0.0, 0),
    "salt": Ingredient("Salt", FoodSource.EARTH_SUPPLY, 0, 0.0, 0.0, 0.0, 0.0, 0),
    "spices": Ingredient("Spices", FoodSource.EARTH_SUPPLY, 250, 10.0, 50.0, 5.0, 15.0, 10),
    "protein_powder": Ingredient("Protein Powder", FoodSource.EARTH_SUPPLY, 400, 80.0, 10.0, 5.0, 0.0, 5),
    "dried_fruit": Ingredient("Dried Fruit", FoodSource.EARTH_SUPPLY, 240, 2.0, 64.0, 0.5, 7.0, 20),
    "nuts": Ingredient("Mixed Nuts", FoodSource.EARTH_SUPPLY, 607, 20.0, 21.0, 54.0, 7.0, 4),
    "chocolate": Ingredient("Dark Chocolate", FoodSource.EARTH_SUPPLY, 546, 5.0, 60.0, 31.0, 7.0, 1),
    "coffee": Ingredient("Coffee", FoodSource.EARTH_SUPPLY, 2, 0.1, 0.0, 0.0, 0.0, 99),
    "tea": Ingredient("Tea", FoodSource.EARTH_SUPPLY, 1, 0.0, 0.2, 0.0, 0.0, 99),
}


@dataclass
class Recipe:
    """A recipe with ingredients and portions."""
    name: str
    meal_slot: MealSlot
    servings: int
    ingredients: List[Tuple[str, float]]  # (ingredient_name, grams_per_serving)
    prep_time_minutes: int = 15
    cook_time_minutes: int = 30
    description: str = ""

    def get_nutrition_per_serving(self) -> Dict[str, float]:
        """Calculate nutrition per serving."""
        totals = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
        }

        for ing_name, grams in self.ingredients:
            ing = INGREDIENTS.get(ing_name)
            if ing:
                nutrition = ing.get_nutrition(grams)
                for key in totals:
                    totals[key] += nutrition.get(key, 0)

        return totals

    def get_earth_independence(self) -> float:
        """Calculate percentage of calories from in-situ sources."""
        total_calories = 0.0
        in_situ_calories = 0.0

        for ing_name, grams in self.ingredients:
            ing = INGREDIENTS.get(ing_name)
            if ing:
                cals = ing.get_nutrition(grams)["calories"]
                total_calories += cals
                if ing.source in (FoodSource.IN_SITU_CROP, FoodSource.IN_SITU_LIVESTOCK):
                    in_situ_calories += cals

        return in_situ_calories / total_calories if total_calories > 0 else 0


# Recipe library
RECIPES: Dict[str, Recipe] = {
    # Breakfasts
    "scrambled_eggs": Recipe(
        "Scrambled Eggs with Toast",
        MealSlot.BREAKFAST,
        servings=1,
        ingredients=[
            ("egg", 100),      # 2 eggs
            ("bread", 60),     # 2 slices
            ("tomato", 50),
            ("herbs", 5),
            ("olive_oil", 5),
        ],
        description="Fresh eggs scrambled with herbs, served with toast and tomato"
    ),
    "oatmeal_fruit": Recipe(
        "Oatmeal with Dried Fruit",
        MealSlot.BREAKFAST,
        servings=1,
        ingredients=[
            ("flour", 50),      # Using flour as oat substitute
            ("milk", 200),
            ("dried_fruit", 30),
            ("nuts", 15),
        ],
        description="Warm oatmeal with goat milk, dried fruit and nuts"
    ),
    "potato_hash": Recipe(
        "Potato Hash with Eggs",
        MealSlot.BREAKFAST,
        servings=1,
        ingredients=[
            ("potato", 150),
            ("egg", 50),
            ("pepper", 50),
            ("herbs", 5),
            ("olive_oil", 10),
        ],
        description="Crispy potato hash topped with fried egg"
    ),
    "yogurt_parfait": Recipe(
        "Yogurt Parfait",
        MealSlot.BREAKFAST,
        servings=1,
        ingredients=[
            ("yogurt", 200),
            ("dried_fruit", 40),
            ("nuts", 20),
        ],
        description="Fresh yogurt layered with dried fruit and nuts"
    ),

    # Lunches
    "veggie_wrap": Recipe(
        "Vegetable Wrap",
        MealSlot.LUNCH,
        servings=1,
        ingredients=[
            ("flour", 60),      # Tortilla
            ("beans", 100),
            ("lettuce", 50),
            ("tomato", 50),
            ("cheese", 30),
            ("herbs", 5),
        ],
        description="Fresh vegetable wrap with beans and goat cheese"
    ),
    "potato_soup": Recipe(
        "Creamy Potato Soup",
        MealSlot.LUNCH,
        servings=1,
        ingredients=[
            ("potato", 200),
            ("milk", 150),
            ("herbs", 10),
            ("olive_oil", 10),
        ],
        description="Hearty potato soup with fresh herbs"
    ),
    "grain_bowl": Recipe(
        "Grain Bowl",
        MealSlot.LUNCH,
        servings=1,
        ingredients=[
            ("rice", 150),
            ("beans", 80),
            ("tomato", 50),
            ("spinach", 50),
            ("olive_oil", 10),
        ],
        description="Nutritious grain bowl with vegetables and beans"
    ),
    "egg_salad": Recipe(
        "Egg Salad Sandwich",
        MealSlot.LUNCH,
        servings=1,
        ingredients=[
            ("bread", 80),
            ("egg", 100),
            ("lettuce", 30),
            ("herbs", 5),
            ("olive_oil", 10),
        ],
        description="Classic egg salad on fresh bread"
    ),

    # Dinners
    "pasta_primavera": Recipe(
        "Pasta Primavera",
        MealSlot.DINNER,
        servings=1,
        ingredients=[
            ("pasta", 150),
            ("tomato", 100),
            ("pepper", 50),
            ("spinach", 50),
            ("cheese", 30),
            ("olive_oil", 15),
            ("herbs", 10),
        ],
        description="Pasta with fresh vegetables and goat cheese"
    ),
    "stuffed_potato": Recipe(
        "Stuffed Baked Potato",
        MealSlot.DINNER,
        servings=1,
        ingredients=[
            ("potato", 250),
            ("cheese", 40),
            ("beans", 80),
            ("herbs", 10),
            ("olive_oil", 10),
        ],
        description="Large baked potato stuffed with beans and cheese"
    ),
    "stir_fry": Recipe(
        "Vegetable Stir Fry",
        MealSlot.DINNER,
        servings=1,
        ingredients=[
            ("rice", 150),
            ("soybean", 80),
            ("pepper", 80),
            ("spinach", 50),
            ("olive_oil", 15),
            ("spices", 5),
        ],
        description="Asian-style vegetable stir fry with rice"
    ),
    "bean_stew": Recipe(
        "Hearty Bean Stew",
        MealSlot.DINNER,
        servings=1,
        ingredients=[
            ("beans", 150),
            ("potato", 100),
            ("tomato", 100),
            ("herbs", 10),
            ("bread", 60),
        ],
        description="Warming bean stew with crusty bread"
    ),

    # Snacks
    "cheese_crackers": Recipe(
        "Cheese and Crackers",
        MealSlot.SNACK,
        servings=1,
        ingredients=[
            ("flour", 30),
            ("cheese", 30),
        ],
        description="Fresh cheese with homemade crackers"
    ),
    "trail_mix": Recipe(
        "Trail Mix",
        MealSlot.SNACK,
        servings=1,
        ingredients=[
            ("nuts", 30),
            ("dried_fruit", 30),
            ("chocolate", 10),
        ],
        description="Energy-boosting trail mix"
    ),
}


@dataclass
class DailyMenu:
    """A day's complete menu."""
    sol_number: int
    breakfast: str  # Recipe name
    lunch: str
    dinner: str
    snacks: List[str] = field(default_factory=list)

    def get_total_nutrition(self) -> Dict[str, float]:
        """Get total nutrition for the day."""
        totals = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
        }

        meals = [self.breakfast, self.lunch, self.dinner] + self.snacks
        for meal_name in meals:
            recipe = RECIPES.get(meal_name)
            if recipe:
                nutrition = recipe.get_nutrition_per_serving()
                for key in totals:
                    totals[key] += nutrition.get(key, 0)

        return totals

    def get_earth_independence(self) -> float:
        """Get average Earth independence for the day."""
        total_independence = 0.0
        meal_count = 0

        meals = [self.breakfast, self.lunch, self.dinner] + self.snacks
        for meal_name in meals:
            recipe = RECIPES.get(meal_name)
            if recipe:
                total_independence += recipe.get_earth_independence()
                meal_count += 1

        return total_independence / meal_count if meal_count > 0 else 0


class MealPlanRotation:
    """
    14-sol rotating meal plan.

    Provides variety while maintaining nutritional targets.
    """

    def __init__(self):
        self.rotation_length = 14  # 14-sol cycle
        self.daily_menus: List[DailyMenu] = []
        self.current_sol = 0

    def setup_default_rotation(self):
        """Set up the default 14-sol meal rotation."""
        # Breakfast rotation (4 options)
        breakfasts = ["scrambled_eggs", "oatmeal_fruit", "potato_hash", "yogurt_parfait"]

        # Lunch rotation (4 options)
        lunches = ["veggie_wrap", "potato_soup", "grain_bowl", "egg_salad"]

        # Dinner rotation (4 options)
        dinners = ["pasta_primavera", "stuffed_potato", "stir_fry", "bean_stew"]

        # Create 14-day rotation
        for sol in range(14):
            menu = DailyMenu(
                sol_number=sol + 1,
                breakfast=breakfasts[sol % 4],
                lunch=lunches[sol % 4],
                dinner=dinners[sol % 4],
                snacks=["cheese_crackers" if sol % 2 == 0 else "trail_mix"],
            )
            self.daily_menus.append(menu)

        logger.info(f"Meal plan rotation set up: {self.rotation_length} sols")

    def get_menu_for_sol(self, sol: int) -> DailyMenu:
        """Get the menu for a specific sol."""
        index = (sol - 1) % self.rotation_length
        return self.daily_menus[index]

    def advance_sol(self) -> DailyMenu:
        """Advance to next sol and return its menu."""
        self.current_sol += 1
        return self.get_menu_for_sol(self.current_sol)

    def get_average_nutrition(self) -> Dict[str, float]:
        """Get average daily nutrition across rotation."""
        totals = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
        }

        for menu in self.daily_menus:
            nutrition = menu.get_total_nutrition()
            for key in totals:
                totals[key] += nutrition.get(key, 0)

        for key in totals:
            totals[key] /= len(self.daily_menus)

        return totals

    def get_average_earth_independence(self) -> float:
        """Get average Earth independence across rotation."""
        return sum(m.get_earth_independence() for m in self.daily_menus) / len(self.daily_menus)

    def get_status(self) -> Dict:
        """Get meal plan status."""
        avg_nutrition = self.get_average_nutrition()

        return {
            "rotation_length": self.rotation_length,
            "current_sol": self.current_sol,
            "average_daily_calories": avg_nutrition["calories"],
            "average_daily_protein_g": avg_nutrition["protein_g"],
            "average_daily_carbs_g": avg_nutrition["carbs_g"],
            "average_daily_fat_g": avg_nutrition["fat_g"],
            "average_earth_independence": self.get_average_earth_independence(),
        }


class MealPlan:
    """
    Central meal planning and tracking system.

    Integrates with food production and crew systems.
    """

    def __init__(self):
        self.rotation = MealPlanRotation()
        self.crew_size = MISSION.crew_size

        # Meal service tracking
        self.meals_served_today = {slot: False for slot in MealSlot}
        self.total_calories_served_today = 0.0

        # History
        self.daily_summaries: List[Dict] = []

    def initialize(self):
        """Initialize the meal plan."""
        self.rotation.setup_default_rotation()

    def get_todays_menu(self) -> DailyMenu:
        """Get today's menu."""
        return self.rotation.get_menu_for_sol(self.rotation.current_sol or 1)

    def serve_meal(self, slot: MealSlot) -> Dict:
        """
        Serve a meal to the crew.

        Returns nutritional info for the meal.
        """
        menu = self.get_todays_menu()

        # Get recipe for this slot
        recipe_name = None
        if slot == MealSlot.BREAKFAST:
            recipe_name = menu.breakfast
        elif slot == MealSlot.LUNCH:
            recipe_name = menu.lunch
        elif slot == MealSlot.DINNER:
            recipe_name = menu.dinner
        elif slot == MealSlot.SNACK and menu.snacks:
            recipe_name = menu.snacks[0]

        if not recipe_name:
            return {"error": "No meal found for slot"}

        recipe = RECIPES.get(recipe_name)
        if not recipe:
            return {"error": f"Recipe not found: {recipe_name}"}

        # Calculate nutrition for entire crew
        nutrition_per_serving = recipe.get_nutrition_per_serving()
        total_nutrition = {
            key: value * self.crew_size
            for key, value in nutrition_per_serving.items()
        }

        self.meals_served_today[slot] = True
        self.total_calories_served_today += total_nutrition["calories"]

        logger.info(f"Served {recipe.name} to {self.crew_size} crew "
                   f"({nutrition_per_serving['calories']:.0f} kcal/person)")

        return {
            "recipe_name": recipe.name,
            "meal_slot": slot.name,
            "servings": self.crew_size,
            "nutrition_per_serving": nutrition_per_serving,
            "total_nutrition": total_nutrition,
            "earth_independence": recipe.get_earth_independence(),
        }

    def end_day(self) -> Dict:
        """Process end of day."""
        menu = self.get_todays_menu()
        total_nutrition = menu.get_total_nutrition()

        summary = {
            "sol": self.rotation.current_sol,
            "menu": {
                "breakfast": menu.breakfast,
                "lunch": menu.lunch,
                "dinner": menu.dinner,
                "snacks": menu.snacks,
            },
            "planned_nutrition": total_nutrition,
            "planned_calories_per_person": total_nutrition["calories"],
            "total_calories_for_crew": total_nutrition["calories"] * self.crew_size,
            "calories_actually_served": self.total_calories_served_today,
            "meals_served": {slot.name: served for slot, served in self.meals_served_today.items()},
            "earth_independence": menu.get_earth_independence(),
        }

        self.daily_summaries.append(summary)

        # Reset for next day
        self.meals_served_today = {slot: False for slot in MealSlot}
        self.total_calories_served_today = 0.0

        # Advance to next sol
        self.rotation.advance_sol()

        return summary

    def get_ingredient_requirements(self, sols: int = 1) -> Dict[str, float]:
        """
        Calculate ingredient requirements for specified number of sols.

        Returns dict of ingredient_name -> total grams needed.
        """
        requirements: Dict[str, float] = {}

        for sol_offset in range(sols):
            menu = self.rotation.get_menu_for_sol(self.rotation.current_sol + sol_offset + 1)
            meals = [menu.breakfast, menu.lunch, menu.dinner] + menu.snacks

            for meal_name in meals:
                recipe = RECIPES.get(meal_name)
                if recipe:
                    for ing_name, grams_per_serving in recipe.ingredients:
                        total_grams = grams_per_serving * self.crew_size
                        requirements[ing_name] = requirements.get(ing_name, 0) + total_grams

        return requirements

    def get_status(self) -> Dict:
        """Get current meal plan status."""
        return {
            "crew_size": self.crew_size,
            "rotation_status": self.rotation.get_status(),
            "todays_menu": {
                "breakfast": self.get_todays_menu().breakfast,
                "lunch": self.get_todays_menu().lunch,
                "dinner": self.get_todays_menu().dinner,
            },
            "meals_served_today": {slot.name: served for slot, served in self.meals_served_today.items()},
            "calories_served_today": self.total_calories_served_today,
        }
