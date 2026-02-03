"""
Test: Food Production Systems (Sprint 3)
Verifies food PODs, fodder, grain, and livestock work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mars_to_table.core.store import Store, StoreManager, ResourceType
from mars_to_table.core.module import ModuleManager
from mars_to_table.config import FOOD, LIVESTOCK, Priority

from mars_to_table.systems.food_pod import (
    FoodPOD, FoodPODManager, CropType, CropSpec, CropBed, CROP_SPECS, GrowthStage
)
from mars_to_table.systems.fodder_pod import (
    FodderPOD, FodderType, FODDER_SPECS
)
from mars_to_table.systems.grain_pod import (
    GrainPOD, GrainMill, GrainType, GRAIN_SPECS
)
from mars_to_table.systems.livestock_pod import (
    LivestockPOD, GoatHerd, ChickenFlock, AnimalType, AnimalState
)


def create_test_stores() -> StoreManager:
    """Create a store manager with test stores for food production."""
    manager = StoreManager()

    # Power
    manager.add_store(Store("Power", ResourceType.ELECTRICAL_POWER, 10000.0, 5000.0))

    # Water
    manager.add_store(Store("Potable_Water", ResourceType.POTABLE_WATER, 50000.0, 30000.0))

    # Gases
    manager.add_store(Store("Oxygen", ResourceType.OXYGEN, 10000.0, 5000.0))
    manager.add_store(Store("CO2_Store", ResourceType.CO2, 1000.0, 500.0))

    # Nutrients
    manager.add_store(Store("Nutrients_N", ResourceType.NUTRIENTS_N, 500.0, 200.0))
    manager.add_store(Store("Nutrients_P", ResourceType.NUTRIENTS_P, 200.0, 100.0))
    manager.add_store(Store("Nutrients_K", ResourceType.NUTRIENTS_K, 300.0, 200.0))

    # Food storage
    manager.add_store(Store("Food_Storage", ResourceType.BIOMASS_EDIBLE, 5000.0, 0.0))
    manager.add_store(Store("Fodder_Storage", ResourceType.FODDER, 1000.0, 200.0))
    manager.add_store(Store("Flour_Storage", ResourceType.GRAIN_FLOUR, 500.0, 0.0))
    manager.add_store(Store("Grain_Storage", ResourceType.BIOMASS_EDIBLE, 500.0, 0.0))

    # Livestock products
    manager.add_store(Store("Milk_Storage", ResourceType.MILK, 100.0, 0.0))
    manager.add_store(Store("Egg_Storage", ResourceType.EGGS, 50.0, 0.0))
    manager.add_store(Store("Cheese_Storage", ResourceType.CHEESE, 50.0, 0.0))

    # Waste
    manager.add_store(Store("Crop_Waste", ResourceType.BIOMASS_INEDIBLE, 500.0, 0.0))
    manager.add_store(Store("Animal_Waste", ResourceType.ANIMAL_WASTE, 200.0, 0.0))

    return manager


# =============================================================================
# FOOD POD TESTS
# =============================================================================

def test_crop_specs():
    """Test crop specifications are properly defined."""
    print("Testing Crop Specifications...")

    assert len(CROP_SPECS) >= 9, f"Expected at least 9 crop types, got {len(CROP_SPECS)}"

    for crop_type, spec in CROP_SPECS.items():
        assert spec.growth_cycle_days > 0, f"{crop_type}: Invalid growth cycle"
        assert spec.yield_kg_per_m2 > 0, f"{crop_type}: Invalid yield"
        assert spec.calorie_density_kcal_per_kg > 0, f"{crop_type}: Invalid calorie density"
        assert spec.yield_per_day > 0, f"{crop_type}: yield_per_day should be positive"

    # Check potato specifically
    potato = CROP_SPECS[CropType.POTATO]
    assert potato.growth_cycle_days == 120, f"Potato cycle should be 120 days, got {potato.growth_cycle_days}"
    assert potato.calorie_density_kcal_per_kg == 770, f"Potato calories should be 770"

    print("  ✓ Crop Specifications tests passed")


def test_crop_bed_growth():
    """Test crop bed growth progression."""
    print("Testing Crop Bed growth...")

    spec = CROP_SPECS[CropType.LETTUCE]  # Fast growing
    bed = CropBed(
        bed_id="test_bed",
        area_m2=10.0,
        crop_spec=spec,
        planted_tick=0
    )

    # Check initial state
    assert bed.growth_progress == 0.0
    assert bed.current_stage == GrowthStage.GERMINATION
    assert not bed.is_ready_to_harvest()

    # Simulate growth (45 day cycle for lettuce = 45*24 = 1080 ticks)
    bed.update_stage(current_tick=540)  # Half cycle
    assert bed.growth_progress == 0.5, f"Expected 50% progress, got {bed.growth_progress}"
    # At 50% progress, should be in FLOWERING stage (0.5-0.75 range)
    assert bed.current_stage == GrowthStage.FLOWERING

    # Complete growth
    bed.update_stage(current_tick=1080)
    assert bed.growth_progress == 1.0
    assert bed.is_ready_to_harvest()
    assert bed.current_stage == GrowthStage.HARVEST

    # Simulate water received during growth cycle
    expected_water = spec.water_l_per_m2_per_day * 10.0 * spec.growth_cycle_days
    bed.water_received = expected_water  # Full water

    # Test harvest
    yield_kg = bed.harvest(current_tick=1080)
    assert yield_kg > 0, "Should produce yield"
    expected_yield = spec.yield_kg_per_m2 * 10.0  # 10 m²
    assert abs(yield_kg - expected_yield) < 0.1, f"Expected ~{expected_yield}kg, got {yield_kg}kg"

    # After harvest, should reset
    assert bed.growth_progress == 0.0
    assert bed.total_harvests == 1

    print("  ✓ Crop Bed growth tests passed")


def test_food_pod_basic():
    """Test basic food POD operations."""
    print("Testing Food POD basic operations...")

    stores = create_test_stores()
    pod = FoodPOD("Test_Food_POD_1", pod_number=1, store_manager=stores, growing_area_m2=100.0)

    assert pod.total_area_m2 == 100.0
    assert pod.pod_number == 1

    # Setup default allocation
    pod.setup_default_allocation()
    assert len(pod.beds) > 0, "Should have growing beds"

    total_bed_area = sum(b.area_m2 for b in pod.beds)
    assert abs(total_bed_area - 100.0) < 1.0, f"Bed area should sum to ~100, got {total_bed_area}"

    print("  ✓ Food POD basic tests passed")


def test_food_pod_production():
    """Test food POD water consumption and oxygen production."""
    print("Testing Food POD production...")

    stores = create_test_stores()
    modules = ModuleManager(stores)

    pod = FoodPOD("Test_Food_POD", pod_number=1, store_manager=stores, growing_area_m2=100.0)
    pod.setup_default_allocation()
    pod.start()
    pod.tick()  # Complete startup

    initial_water = stores.get("Potable_Water").current_level
    initial_o2 = stores.get("Oxygen").current_level

    # Run a few ticks
    for _ in range(10):
        pod.tick()
        metrics = pod.process_tick()

    # Should consume water
    assert stores.get("Potable_Water").current_level < initial_water, "Should consume water"

    # Should produce oxygen
    assert stores.get("Oxygen").current_level > initial_o2, "Should produce oxygen"

    # Should report expected production
    assert metrics["expected_yield_per_day_kg"] > 0, "Should have expected yield"
    assert metrics["expected_calories_per_day"] > 0, "Should have expected calories"

    print("  ✓ Food POD production tests passed")


def test_food_pod_manager():
    """Test food POD manager coordinating multiple PODs."""
    print("Testing Food POD Manager...")

    stores = create_test_stores()
    modules = ModuleManager(stores)
    manager = FoodPODManager(stores, modules)

    # Initialize 3 test PODs
    manager.initialize_default_pods(num_pods=3)

    assert len(manager.pods) == 3
    assert manager.get_total_growing_area() == 3 * FOOD.growing_area_per_pod_m2

    # Check expected production
    expected = manager.get_expected_daily_production()
    assert expected["yield_kg"] > 0
    assert expected["calories"] > 0

    print("  ✓ Food POD Manager tests passed")


# =============================================================================
# FODDER POD TESTS
# =============================================================================

def test_fodder_specs():
    """Test fodder specifications."""
    print("Testing Fodder Specifications...")

    assert len(FODDER_SPECS) >= 5, f"Expected at least 5 fodder types"

    for fodder_type, spec in FODDER_SPECS.items():
        assert spec.growth_cycle_days > 0
        assert spec.yield_kg_per_m2 > 0
        assert spec.dry_matter_fraction > 0 and spec.dry_matter_fraction < 1
        assert spec.protein_percent > 0

    # Check barley grass (fast growing)
    barley = FODDER_SPECS[FodderType.BARLEY_GRASS]
    assert barley.growth_cycle_days == 7, "Barley grass should be 7 day cycle"

    print("  ✓ Fodder Specifications tests passed")


def test_fodder_pod():
    """Test fodder POD operations."""
    print("Testing Fodder POD...")

    stores = create_test_stores()
    pod = FodderPOD("Test_Fodder_POD", stores, growing_area_m2=100.0)
    pod.setup_default_allocation()
    pod.start()
    pod.tick()  # Complete startup

    assert len(pod.beds) > 0, "Should have fodder beds"
    assert pod.daily_target_kg > 0, "Should have production target"

    # Run some ticks
    for _ in range(10):
        pod.tick()
        metrics = pod.process_tick()

    assert "daily_yield_kg" in metrics
    assert "avg_health" in metrics
    assert metrics["avg_health"] > 0

    print("  ✓ Fodder POD tests passed")


# =============================================================================
# GRAIN POD TESTS
# =============================================================================

def test_grain_specs():
    """Test grain specifications."""
    print("Testing Grain Specifications...")

    assert len(GRAIN_SPECS) >= 4, f"Expected at least 4 grain types"

    for grain_type, spec in GRAIN_SPECS.items():
        assert spec.growth_cycle_days > 0
        assert spec.yield_kg_per_m2 > 0
        assert spec.flour_conversion > 0 and spec.flour_conversion <= 1
        assert spec.calorie_density_kcal_per_kg > 3000, "Grains should be calorie dense"

    # Check wheat
    wheat = GRAIN_SPECS[GrainType.WHEAT]
    assert wheat.flour_conversion == 0.72, "Wheat flour conversion should be 72%"

    print("  ✓ Grain Specifications tests passed")


def test_grain_pod():
    """Test grain POD operations."""
    print("Testing Grain POD...")

    stores = create_test_stores()
    pod = GrainPOD("Test_Grain_POD", stores, growing_area_m2=100.0)
    pod.setup_default_allocation()
    pod.start()
    pod.tick()  # Complete startup

    assert len(pod.beds) > 0, "Should have grain beds"
    assert pod.mill is not None, "Should have grain mill"
    assert pod.daily_target_flour_kg > 0, "Should have flour target"

    # Run some ticks
    for _ in range(10):
        pod.tick()
        metrics = pod.process_tick()

    assert "daily_flour_kg" in metrics
    assert metrics["avg_health"] > 0

    status = pod.get_status()
    assert "beds_by_grain" in status
    assert status["expected_daily_flour_kg"] > 0

    print("  ✓ Grain POD tests passed")


# =============================================================================
# LIVESTOCK POD TESTS
# =============================================================================

def test_goat_herd():
    """Test goat herd operations."""
    print("Testing Goat Herd...")

    herd = GoatHerd()
    herd.initialize_herd(num_does=6, num_bucks=1)

    assert herd.total_goats == 7
    assert len(herd.does) == 6
    assert len(herd.bucks) == 1
    assert herd.lactating_does == 6  # All start lactating

    # Test feed requirement
    feed_req = herd.get_daily_feed_requirement()
    expected_feed = 7 * LIVESTOCK.goat_feed_kg_per_day
    assert abs(feed_req - expected_feed) < 0.1, f"Expected {expected_feed}kg feed, got {feed_req}"

    # Test milk production with full resources
    milk = herd.produce_milk(feed_available_kg=20.0, water_available_l=50.0)
    expected_milk = 6 * LIVESTOCK.milk_per_doe_l_per_day
    assert milk > 0, "Should produce milk"
    assert abs(milk - expected_milk) < 1.0, f"Expected ~{expected_milk}L, got {milk}L"

    print("  ✓ Goat Herd tests passed")


def test_chicken_flock():
    """Test chicken flock operations."""
    print("Testing Chicken Flock...")

    flock = ChickenFlock()
    flock.initialize_flock(num_hens=20, num_roosters=2)

    assert flock.total_birds == 22
    assert len(flock.hens) == 20
    assert flock.productive_hens == 20  # All start healthy

    # Test feed requirement
    feed_req = flock.get_daily_feed_requirement()
    expected_feed = 22 * LIVESTOCK.chicken_feed_kg_per_day
    assert abs(feed_req - expected_feed) < 0.1

    # Test egg production (probabilistic, so check range)
    # Run multiple times for statistical check
    total_eggs = 0
    for _ in range(10):
        eggs = flock.produce_eggs(feed_available_kg=5.0, water_available_l=10.0)
        total_eggs += eggs

    avg_eggs = total_eggs / 10
    expected_eggs = 20 * LIVESTOCK.eggs_per_hen_per_day
    # Allow wide range due to randomness
    assert 5 < avg_eggs < 25, f"Expected ~{expected_eggs} eggs/day, got avg {avg_eggs}"

    print("  ✓ Chicken Flock tests passed")


def test_livestock_pod():
    """Test livestock POD operations."""
    print("Testing Livestock POD...")

    stores = create_test_stores()
    pod = LivestockPOD("Test_Livestock_POD", stores)
    pod.initialize_livestock()
    pod.start()
    pod.tick()  # Complete startup

    assert pod.goat_herd.total_goats > 0
    assert pod.chicken_flock.total_birds > 0

    # Test feed/water requirements
    feed_req = pod.get_feed_requirement()
    assert feed_req > 0, "Should have feed requirement"

    water_req = pod.get_water_requirement()
    assert water_req > 0, "Should have water requirement"

    # Run 24 ticks (one day) to trigger production
    for i in range(24):
        pod.tick()
        metrics = pod.process_tick()

    # Check production occurred
    assert pod.daily_milk_l > 0 or pod.total_milk_l > 0, "Should produce milk"
    assert pod.daily_eggs >= 0, "Should track eggs"

    status = pod.get_status()
    assert "goat_herd" in status
    assert "chicken_flock" in status
    assert status["daily_calories"] >= 0

    print("  ✓ Livestock POD tests passed")


def test_livestock_resource_stress():
    """Test livestock under resource stress."""
    print("Testing Livestock resource stress...")

    stores = create_test_stores()
    # Reduce fodder to stress animals
    stores.get("Fodder_Storage").current_level = 10.0  # Very low

    pod = LivestockPOD("Stressed_Livestock_POD", stores)
    pod.initialize_livestock()
    pod.start()
    pod.tick()

    # Run several days
    for _ in range(48):  # 2 days
        pod.tick()
        pod.process_tick()

    # Health should decrease under stress
    avg_goat_health = sum(g.health for g in pod.goat_herd.does) / len(pod.goat_herd.does)
    assert avg_goat_health < 1.0, "Goat health should decrease under feed stress"

    print("  ✓ Livestock resource stress tests passed")


# =============================================================================
# INTEGRATION TEST
# =============================================================================

def test_food_system_integration():
    """Test integrated food production chain."""
    print("Testing Food System integration...")

    stores = create_test_stores()
    modules = ModuleManager(stores)

    # Set up fodder POD to feed livestock
    fodder_pod = FodderPOD("Fodder_POD", stores, growing_area_m2=100.0)
    fodder_pod.setup_default_allocation()
    fodder_pod.start()
    modules.add_module(fodder_pod)

    # Set up livestock POD
    livestock_pod = LivestockPOD("Livestock_POD", stores)
    livestock_pod.initialize_livestock()
    livestock_pod.start()
    modules.add_module(livestock_pod)

    # Run for a simulated day
    for tick in range(24):
        fodder_pod.tick()
        fodder_pod.process_tick()

        livestock_pod.tick()
        livestock_pod.process_tick()

    # Check fodder was produced
    fodder_level = stores.get("Fodder_Storage").current_level
    assert fodder_level > 0, "Fodder should be produced"

    # Check livestock products were produced
    milk_level = stores.get("Milk_Storage").current_level
    egg_level = stores.get("Egg_Storage").current_level

    # At least one product should be produced
    assert milk_level > 0 or egg_level > 0, "Should produce milk or eggs"

    print("  ✓ Food System integration tests passed")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all Sprint 3 food production tests."""
    print("\n" + "="*50)
    print("MARS TO TABLE — Sprint 3 Food Production Tests")
    print("="*50 + "\n")

    try:
        # Crop/Food POD tests
        test_crop_specs()
        test_crop_bed_growth()
        test_food_pod_basic()
        test_food_pod_production()
        test_food_pod_manager()

        # Fodder tests
        test_fodder_specs()
        test_fodder_pod()

        # Grain tests
        test_grain_specs()
        test_grain_pod()

        # Livestock tests
        test_goat_herd()
        test_chicken_flock()
        test_livestock_pod()
        test_livestock_resource_stress()

        # Integration test
        test_food_system_integration()

        print("\n" + "="*50)
        print("ALL SPRINT 3 TESTS PASSED ✓")
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
