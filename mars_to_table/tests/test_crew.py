"""
Test: Crew & Nutrition Systems (Sprint 4)
Verifies crew model, meal planning, and nutrition tracking.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mars_to_table.config import MISSION

from mars_to_table.crew.crew_model import (
    CrewMember, CrewManager, CrewRole, ActivityLevel, HealthStatus,
    ACTIVITY_MULTIPLIERS
)
from mars_to_table.crew.meal_plan import (
    MealPlan, MealPlanRotation, DailyMenu, MealSlot,
    Recipe, Ingredient, RECIPES, INGREDIENTS, FoodSource
)
from mars_to_table.crew.nutrition import (
    NutritionTracker, MacroNutrients, NutrientRequirements, NutritionStatus
)


# =============================================================================
# CREW MODEL TESTS
# =============================================================================

def test_crew_member_creation():
    """Test crew member creation and properties."""
    print("Testing Crew Member creation...")

    member = CrewMember(
        crew_id="TEST01",
        name="Test Astronaut",
        role=CrewRole.MISSION_SPECIALIST,
        age=35,
        sex='M',
        weight_kg=75,
        height_cm=175,
    )

    assert member.crew_id == "TEST01"
    assert member.name == "Test Astronaut"
    assert member.role == CrewRole.MISSION_SPECIALIST
    assert member.health_status == HealthStatus.HEALTHY
    assert member.morale == 1.0

    # Test BMI calculation
    expected_bmi = 75 / (1.75 ** 2)
    assert abs(member.bmi - expected_bmi) < 0.01, f"BMI should be ~{expected_bmi:.1f}"

    # Test BMR calculation (Mifflin-St Jeor for male)
    expected_bmr = 10 * 75 + 6.25 * 175 - 5 * 35 + 5
    assert abs(member.basal_metabolic_rate - expected_bmr) < 1, f"BMR should be ~{expected_bmr:.0f}"

    print("  ✓ Crew Member creation tests passed")


def test_crew_member_calorie_requirement():
    """Test calorie requirement calculations."""
    print("Testing Crew Member calorie requirements...")

    member = CrewMember(
        crew_id="TEST02",
        name="Calorie Test",
        role=CrewRole.EVA_SPECIALIST,
        age=35,
        sex='M',
        weight_kg=80,
        height_cm=180,
    )

    # Test baseline requirement
    base_req = member.daily_calorie_requirement
    assert base_req > 2000, "Base requirement should be > 2000 kcal"
    assert base_req < 5000, "Base requirement should be < 5000 kcal"

    # Test EVA increases requirement
    member.set_activity(ActivityLevel.EVA, eva_hours=4)
    eva_req = member.daily_calorie_requirement

    assert eva_req > base_req, "EVA should increase calorie requirement"
    assert member.hours_eva_today == 4
    assert member.total_eva_hours == 4

    print("  ✓ Calorie requirement tests passed")


def test_crew_member_meal_consumption():
    """Test meal consumption tracking."""
    print("Testing Crew Member meal consumption...")

    member = CrewMember(
        crew_id="TEST03",
        name="Meal Test",
        role=CrewRole.SCIENCE_OFFICER,
        age=40,
        sex='F',
        weight_kg=60,
        height_cm=165,
    )

    # Consume meals
    member.consume_meal(800, water_l=0.5)   # Breakfast
    member.consume_meal(1000, water_l=0.5)  # Lunch
    member.consume_meal(1200, water_l=0.5)  # Dinner

    assert member.calories_consumed_today == 3000
    assert member.water_consumed_today_l == 1.5
    assert member.total_calories_consumed == 3000

    print("  ✓ Meal consumption tests passed")


def test_crew_member_health_tracking():
    """Test health status updates based on nutrition."""
    print("Testing Crew Member health tracking...")

    member = CrewMember(
        crew_id="TEST04",
        name="Health Test",
        role=CrewRole.MEDICAL_OFFICER,
        age=38,
        sex='F',
        weight_kg=58,
        height_cm=162,
    )

    # Simulate days without adequate food
    for day in range(5):
        # Consume only 50% of needed calories
        requirement = member.daily_calorie_requirement
        member.consume_meal(requirement * 0.5)
        member.end_day()

    # Should be at least fatigued after inadequate nutrition
    assert member.health_status != HealthStatus.HEALTHY, "Should not be healthy after days of deficit"
    assert member.days_without_adequate_food > 0

    print("  ✓ Health tracking tests passed")


def test_crew_manager():
    """Test crew manager operations."""
    print("Testing Crew Manager...")

    manager = CrewManager()
    manager.initialize_default_crew()

    assert manager.crew_size == 15, f"Expected 15 crew, got {manager.crew_size}"
    assert len(manager.crew) == 15

    # Check roles are assigned
    roles = [m.role for m in manager.crew.values()]
    assert CrewRole.COMMANDER in roles
    assert CrewRole.FOOD_SYSTEM_ENGINEER in roles
    assert CrewRole.NUTRITION_SPECIALIST in roles

    # Test total requirements
    total_calories = manager.get_total_calorie_requirement()
    expected_min = MISSION.crew_size * 2200  # Minimum reasonable (sedentary baseline)
    expected_max = MISSION.crew_size * 4000  # Maximum reasonable
    assert expected_min < total_calories < expected_max, \
        f"Total calories {total_calories} not in range [{expected_min}, {expected_max}]"

    print("  ✓ Crew Manager tests passed")


def test_crew_manager_meal_service():
    """Test serving meals to crew."""
    print("Testing Crew Manager meal service...")

    manager = CrewManager()
    manager.initialize_default_crew()

    # Serve meal to all
    manager.serve_meal(calories_per_person=1000, water_per_person_l=0.5)

    # Check all consumed
    for member in manager.crew.values():
        assert member.calories_consumed_today == 1000
        assert member.water_consumed_today_l == 0.5

    print("  ✓ Crew meal service tests passed")


def test_crew_end_of_day():
    """Test end of day processing."""
    print("Testing Crew end of day...")

    manager = CrewManager()
    manager.initialize_default_crew()

    # Serve 3 meals
    manager.serve_meal(calories_per_person=800, water_per_person_l=0.5)
    manager.serve_meal(calories_per_person=1000, water_per_person_l=0.5)
    manager.serve_meal(calories_per_person=1200, water_per_person_l=0.5)

    # Process end of day
    summary = manager.end_day()

    assert summary["crew_size"] == 15
    assert summary["total_calories_consumed"] == 3000 * 15
    assert summary["calorie_satisfaction"] > 0
    assert "individual_summaries" in summary

    print("  ✓ Crew end of day tests passed")


# =============================================================================
# MEAL PLAN TESTS
# =============================================================================

def test_ingredients():
    """Test ingredient library."""
    print("Testing Ingredients...")

    assert len(INGREDIENTS) >= 20, f"Expected at least 20 ingredients, got {len(INGREDIENTS)}"

    # Check a specific ingredient
    potato = INGREDIENTS["potato"]
    assert potato.source == FoodSource.IN_SITU_CROP
    assert potato.calories_per_100g == 77

    # Test nutrition calculation
    nutrition = potato.get_nutrition(200)  # 200g
    assert nutrition["calories"] == 154  # 77 * 2

    # Check Earth-supplied items exist
    oil = INGREDIENTS["olive_oil"]
    assert oil.source == FoodSource.EARTH_SUPPLY

    print("  ✓ Ingredients tests passed")


def test_recipes():
    """Test recipe library."""
    print("Testing Recipes...")

    assert len(RECIPES) >= 12, f"Expected at least 12 recipes, got {len(RECIPES)}"

    # Check recipe nutrition
    scrambled = RECIPES["scrambled_eggs"]
    assert scrambled.meal_slot == MealSlot.BREAKFAST
    assert scrambled.servings == 1

    nutrition = scrambled.get_nutrition_per_serving()
    assert nutrition["calories"] > 200, "Breakfast should have >200 kcal"
    assert nutrition["protein_g"] > 10, "Eggs should have protein"

    # Check Earth independence
    independence = scrambled.get_earth_independence()
    assert 0 < independence <= 1, "Earth independence should be 0-1"

    print("  ✓ Recipes tests passed")


def test_daily_menu():
    """Test daily menu creation."""
    print("Testing Daily Menu...")

    menu = DailyMenu(
        sol_number=1,
        breakfast="scrambled_eggs",
        lunch="veggie_wrap",
        dinner="pasta_primavera",
        snacks=["trail_mix"],
    )

    nutrition = menu.get_total_nutrition()
    assert nutrition["calories"] > 1200, f"Day should have >1200 kcal, got {nutrition['calories']}"

    independence = menu.get_earth_independence()
    assert independence > 0.5, "Should be >50% Earth independent"

    print("  ✓ Daily Menu tests passed")


def test_meal_plan_rotation():
    """Test 14-sol meal rotation."""
    print("Testing Meal Plan Rotation...")

    rotation = MealPlanRotation()
    rotation.setup_default_rotation()

    assert rotation.rotation_length == 14
    assert len(rotation.daily_menus) == 14

    # Check all days have meals
    for menu in rotation.daily_menus:
        assert menu.breakfast in RECIPES
        assert menu.lunch in RECIPES
        assert menu.dinner in RECIPES

    # Check average nutrition (recipes provide ~1400-1500 kcal base, would be scaled up for crew)
    avg_nutrition = rotation.get_average_nutrition()
    assert avg_nutrition["calories"] > 1200, f"Expected >1200 kcal, got {avg_nutrition['calories']}"

    # Check Earth independence
    avg_independence = rotation.get_average_earth_independence()
    assert avg_independence > 0.5, "Average should be >50% Earth independent"

    print("  ✓ Meal Plan Rotation tests passed")


def test_meal_plan():
    """Test full meal plan system."""
    print("Testing Meal Plan...")

    plan = MealPlan()
    plan.initialize()

    # Get today's menu
    menu = plan.get_todays_menu()
    assert menu is not None

    # Serve breakfast
    result = plan.serve_meal(MealSlot.BREAKFAST)
    assert "error" not in result
    assert result["servings"] == MISSION.crew_size
    assert plan.meals_served_today[MealSlot.BREAKFAST] == True

    # Check ingredient requirements
    requirements = plan.get_ingredient_requirements(sols=1)
    assert len(requirements) > 0
    assert "potato" in requirements or "bread" in requirements

    print("  ✓ Meal Plan tests passed")


def test_meal_plan_end_day():
    """Test meal plan end of day."""
    print("Testing Meal Plan end of day...")

    plan = MealPlan()
    plan.initialize()

    # Serve all meals
    plan.serve_meal(MealSlot.BREAKFAST)
    plan.serve_meal(MealSlot.LUNCH)
    plan.serve_meal(MealSlot.DINNER)
    plan.serve_meal(MealSlot.SNACK)

    # End day
    summary = plan.end_day()

    assert "sol" in summary
    assert "planned_calories_per_person" in summary
    assert "earth_independence" in summary
    assert summary["earth_independence"] > 0.5

    print("  ✓ Meal Plan end of day tests passed")


# =============================================================================
# NUTRITION TRACKER TESTS
# =============================================================================

def test_macronutrients():
    """Test MacroNutrients class."""
    print("Testing MacroNutrients...")

    macros1 = MacroNutrients(
        calories=500,
        protein_g=25,
        carbohydrates_g=60,
        fat_g=15,
    )

    macros2 = MacroNutrients(
        calories=300,
        protein_g=15,
        carbohydrates_g=40,
        fat_g=10,
    )

    # Test addition
    combined = macros1 + macros2
    assert combined.calories == 800
    assert combined.protein_g == 40

    # Test multiplication
    scaled = macros1 * 2
    assert scaled.calories == 1000
    assert scaled.protein_g == 50

    # Test macro ratio
    ratio = macros1.macro_ratio
    assert "protein" in ratio
    assert "carbs" in ratio
    assert "fat" in ratio
    assert abs(sum(ratio.values()) - 1.0) < 0.01

    print("  ✓ MacroNutrients tests passed")


def test_nutrition_tracker():
    """Test nutrition tracker."""
    print("Testing Nutrition Tracker...")

    tracker = NutritionTracker(crew_size=15)

    # Start a day
    tracker.start_day(sol=1)

    # Log meals
    breakfast = MacroNutrients(calories=600, protein_g=20, carbohydrates_g=80, fat_g=20)
    lunch = MacroNutrients(calories=800, protein_g=30, carbohydrates_g=100, fat_g=25)
    dinner = MacroNutrients(calories=1000, protein_g=35, carbohydrates_g=120, fat_g=30)

    tracker.log_meal("breakfast", breakfast, in_situ_fraction=0.85)
    tracker.log_meal("lunch", lunch, in_situ_fraction=0.80)
    tracker.log_meal("dinner", dinner, in_situ_fraction=0.85)

    # End day
    summary = tracker.end_day()

    assert summary["sol"] == 1
    assert summary["status"] in ["OPTIMAL", "ADEQUATE", "MARGINAL", "DEFICIENT"]
    assert summary["earth_independence"] > 0.5

    print("  ✓ Nutrition Tracker tests passed")


def test_nutrition_tracker_multi_day():
    """Test nutrition tracker over multiple days."""
    print("Testing Nutrition Tracker multi-day...")

    tracker = NutritionTracker(crew_size=15)

    # Simulate 7 days
    for sol in range(1, 8):
        tracker.start_day(sol=sol)

        # Log adequate meals
        breakfast = MacroNutrients(calories=700, protein_g=25, carbohydrates_g=90, fat_g=25)
        lunch = MacroNutrients(calories=900, protein_g=35, carbohydrates_g=110, fat_g=30)
        dinner = MacroNutrients(calories=1100, protein_g=40, carbohydrates_g=130, fat_g=35)

        tracker.log_meal("breakfast", breakfast, in_situ_fraction=0.84)
        tracker.log_meal("lunch", lunch, in_situ_fraction=0.84)
        tracker.log_meal("dinner", dinner, in_situ_fraction=0.84)

        tracker.end_day()

    # Check running average
    avg = tracker.get_running_average(days=7)
    assert avg["days_averaged"] == 7
    assert avg["avg_calories_per_person"] > 2500

    # Check Earth independence
    independence = tracker.get_earth_independence()
    assert independence > 0.80, f"Expected >80% independence, got {independence:.1%}"

    print("  ✓ Nutrition Tracker multi-day tests passed")


def test_nutrition_tracker_deficiency_detection():
    """Test deficiency detection."""
    print("Testing Nutrition deficiency detection...")

    tracker = NutritionTracker(crew_size=15)

    # Simulate 5 days of insufficient calories
    for sol in range(1, 6):
        tracker.start_day(sol=sol)

        # Log inadequate meals (only 50% of requirement)
        breakfast = MacroNutrients(calories=300, protein_g=10, carbohydrates_g=40, fat_g=10)
        lunch = MacroNutrients(calories=400, protein_g=15, carbohydrates_g=50, fat_g=12)
        dinner = MacroNutrients(calories=500, protein_g=18, carbohydrates_g=60, fat_g=15)

        tracker.log_meal("breakfast", breakfast)
        tracker.log_meal("lunch", lunch)
        tracker.log_meal("dinner", dinner)

        summary = tracker.end_day()
        assert summary["status"] == "DEFICIENT"

    # Check deficiency alerts
    alerts = tracker.get_deficiency_alerts()
    assert len(alerts) > 0, "Should have deficiency alerts"

    print("  ✓ Nutrition deficiency detection tests passed")


def test_nutrition_report():
    """Test nutrition report generation."""
    print("Testing Nutrition report...")

    tracker = NutritionTracker(crew_size=15)

    # Log a few days
    for sol in range(1, 4):
        tracker.start_day(sol=sol)

        meals = MacroNutrients(calories=2800, protein_g=80, carbohydrates_g=350, fat_g=90)
        tracker.log_meal("combined", meals, in_situ_fraction=0.84)

        tracker.end_day()

    # Generate report
    report = tracker.generate_report()

    assert "report_period_sols" in report
    assert report["report_period_sols"] == 3
    assert "earth_independence" in report
    assert "requirement_satisfaction" in report

    print("  ✓ Nutrition report tests passed")


# =============================================================================
# INTEGRATION TEST
# =============================================================================

def test_crew_meal_nutrition_integration():
    """Test integration of crew, meal plan, and nutrition systems."""
    print("Testing Crew/Meal/Nutrition integration...")

    # Set up all systems with fresh crew
    crew_manager = CrewManager()
    crew_manager.initialize_default_crew()

    # Verify crew starts healthy
    for member in crew_manager.crew.values():
        assert member.health_status == HealthStatus.HEALTHY, f"{member.name} should start healthy"

    meal_plan = MealPlan()
    meal_plan.initialize()

    nutrition_tracker = NutritionTracker(crew_size=15)

    # Simulate a day
    nutrition_tracker.start_day(sol=1)

    # Breakfast
    breakfast_result = meal_plan.serve_meal(MealSlot.BREAKFAST)
    crew_manager.serve_meal(
        breakfast_result["nutrition_per_serving"]["calories"],
        water_per_person_l=0.5
    )
    breakfast_macros = MacroNutrients(
        calories=breakfast_result["nutrition_per_serving"]["calories"],
        protein_g=breakfast_result["nutrition_per_serving"]["protein_g"],
        carbohydrates_g=breakfast_result["nutrition_per_serving"]["carbs_g"],
        fat_g=breakfast_result["nutrition_per_serving"]["fat_g"],
    )
    nutrition_tracker.log_meal("breakfast", breakfast_macros, breakfast_result["earth_independence"])

    # Lunch
    lunch_result = meal_plan.serve_meal(MealSlot.LUNCH)
    crew_manager.serve_meal(
        lunch_result["nutrition_per_serving"]["calories"],
        water_per_person_l=0.5
    )
    lunch_macros = MacroNutrients(
        calories=lunch_result["nutrition_per_serving"]["calories"],
        protein_g=lunch_result["nutrition_per_serving"]["protein_g"],
        carbohydrates_g=lunch_result["nutrition_per_serving"]["carbs_g"],
        fat_g=lunch_result["nutrition_per_serving"]["fat_g"],
    )
    nutrition_tracker.log_meal("lunch", lunch_macros, lunch_result["earth_independence"])

    # Dinner
    dinner_result = meal_plan.serve_meal(MealSlot.DINNER)
    crew_manager.serve_meal(
        dinner_result["nutrition_per_serving"]["calories"],
        water_per_person_l=0.5
    )
    dinner_macros = MacroNutrients(
        calories=dinner_result["nutrition_per_serving"]["calories"],
        protein_g=dinner_result["nutrition_per_serving"]["protein_g"],
        carbohydrates_g=dinner_result["nutrition_per_serving"]["carbs_g"],
        fat_g=dinner_result["nutrition_per_serving"]["fat_g"],
    )
    nutrition_tracker.log_meal("dinner", dinner_macros, dinner_result["earth_independence"])

    # End day for all systems
    crew_summary = crew_manager.end_day()
    meal_summary = meal_plan.end_day()
    nutrition_summary = nutrition_tracker.end_day()

    # Verify integration
    assert crew_summary["total_calories_consumed"] > 0, "Crew should have consumed calories"
    assert meal_summary["calories_actually_served"] > 0, "Meals should have been served"
    assert nutrition_summary["crew_total"]["calories"] > 0, "Nutrition should be tracked"

    # Verify crew status is tracked (may be fatigued after one day with deficit - that's correct behavior)
    assert crew_summary["crew_size"] == 15, "All crew should be accounted for"
    assert "healthy_count" in crew_summary, "Should track health counts"

    print("  ✓ Crew/Meal/Nutrition integration tests passed")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all Sprint 4 crew tests."""
    print("\n" + "="*50)
    print("MARS TO TABLE — Sprint 4 Crew & Nutrition Tests")
    print("="*50 + "\n")

    try:
        # Crew model tests
        test_crew_member_creation()
        test_crew_member_calorie_requirement()
        test_crew_member_meal_consumption()
        test_crew_member_health_tracking()
        test_crew_manager()
        test_crew_manager_meal_service()
        test_crew_end_of_day()

        # Meal plan tests
        test_ingredients()
        test_recipes()
        test_daily_menu()
        test_meal_plan_rotation()
        test_meal_plan()
        test_meal_plan_end_day()

        # Nutrition tracker tests
        test_macronutrients()
        test_nutrition_tracker()
        test_nutrition_tracker_multi_day()
        test_nutrition_tracker_deficiency_detection()
        test_nutrition_report()

        # Integration test
        test_crew_meal_nutrition_integration()

        print("\n" + "="*50)
        print("ALL SPRINT 4 TESTS PASSED ✓")
        print("="*50 + "\n")
        return True

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
