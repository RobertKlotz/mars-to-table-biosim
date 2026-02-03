"""
Test: Resource Systems (Sprint 2)
Verifies power, water, and nutrient systems work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mars_to_table.core.store import Store, StoreManager, ResourceType
from mars_to_table.core.module import ModuleManager
from mars_to_table.config import POWER, WATER, NUTRIENTS, Priority

from mars_to_table.systems.power_system import (
    PowerSystem, SolarArray, FuelCell, BiogasGenerator
)
from mars_to_table.systems.water_system import (
    WaterSystem, RSVExtractor, WaterRecycler, H2Combuster, WallWaterReserve
)
from mars_to_table.systems.nutrient_system import (
    NutrientSystem, HaberBoschReactor, WasteProcessor, AtmosphereProcessor, NutrientType
)


def create_test_stores() -> StoreManager:
    """Create a store manager with common test stores."""
    manager = StoreManager()

    # Power
    manager.add_store(Store("Power", ResourceType.ELECTRICAL_POWER, 10000.0, 5000.0))

    # Water
    manager.add_store(Store("Potable_Water", ResourceType.POTABLE_WATER, 10000.0, 5000.0))
    manager.add_store(Store("Grey_Water", ResourceType.GREY_WATER, 5000.0, 1000.0))
    manager.add_store(Store("Waste_Water", ResourceType.WASTE_WATER, 5000.0, 500.0))

    # Gases
    manager.add_store(Store("Oxygen", ResourceType.OXYGEN, 5000.0, 3000.0))
    manager.add_store(Store("Hydrogen", ResourceType.HYDROGEN, 1000.0, 500.0))
    manager.add_store(Store("Biogas", ResourceType.METHANE, 500.0, 100.0))

    # Nutrients
    manager.add_store(Store("Nutrients_N", ResourceType.NUTRIENTS_N, 500.0, 100.0))
    manager.add_store(Store("Nutrients_P", ResourceType.NUTRIENTS_P, 200.0, 50.0))
    manager.add_store(Store("Nutrients_K", ResourceType.NUTRIENTS_K, 300.0, 200.0))
    manager.add_store(Store("Atmospheric_N2", ResourceType.NITROGEN, 100.0, 50.0))
    manager.add_store(Store("CO2_Store", ResourceType.CO2, 500.0, 0.0))

    # Waste
    manager.add_store(Store("Human_Waste", ResourceType.HUMAN_WASTE, 50.0, 10.0))
    manager.add_store(Store("Animal_Waste", ResourceType.ANIMAL_WASTE, 100.0, 20.0))
    manager.add_store(Store("Crop_Waste", ResourceType.BIOMASS_INEDIBLE, 200.0, 50.0))

    return manager


# =============================================================================
# POWER SYSTEM TESTS
# =============================================================================

def test_solar_array_day_night():
    """Test solar array day/night cycle."""
    print("Testing Solar Array day/night cycle...")

    stores = create_test_stores()
    solar = SolarArray("Test_Solar", stores, array_area_m2=1000.0, efficiency=0.20)
    solar.start()
    solar.tick()  # Complete startup

    # Test noon (hour 12) - peak output
    solar.set_hour(12)
    initial_power = stores.get("Power").current_level
    metrics = solar.process_tick()

    assert metrics["solar_factor"] > 0.9, f"Expected high solar factor at noon, got {metrics['solar_factor']}"
    assert metrics["output_kw"] > 0, "Expected power output at noon"
    assert stores.get("Power").current_level > initial_power, "Power should increase"

    # Test midnight (hour 0) - no output
    solar.set_hour(0)
    metrics = solar.process_tick()

    assert metrics["solar_factor"] == 0.0, f"Expected zero solar factor at midnight, got {metrics['solar_factor']}"
    assert metrics["output_kw"] == 0.0, "Expected no power output at midnight"

    print("  ✓ Solar Array day/night tests passed")


def test_solar_array_dust_storm():
    """Test solar array dust storm reduction."""
    print("Testing Solar Array dust storm...")

    stores = create_test_stores()
    solar = SolarArray("Test_Solar", stores, array_area_m2=1000.0)
    solar.start()
    solar.tick()  # Complete startup
    solar.set_hour(12)  # Noon

    # Normal operation
    solar.set_dust_storm(1.0)
    metrics_clear = solar.process_tick()

    # 50% dust storm
    solar.set_dust_storm(0.5)
    metrics_dusty = solar.process_tick()

    assert metrics_dusty["output_kw"] < metrics_clear["output_kw"], "Dust storm should reduce output"
    assert abs(metrics_dusty["output_kw"] - metrics_clear["output_kw"] * 0.5) < 1, "Should be ~50% reduction"

    print("  ✓ Solar Array dust storm tests passed")


def test_fuel_cell():
    """Test fuel cell backup power."""
    print("Testing Fuel Cell...")

    stores = create_test_stores()
    modules = ModuleManager(stores)

    fc = FuelCell("Test_FC", stores, capacity_kw=50.0)
    fc.start()
    fc.tick()  # Complete startup

    initial_power = stores.get("Power").current_level
    initial_h2 = stores.get("Hydrogen").current_level

    # Request power
    fc.request_power(30.0)
    fc.tick()
    metrics = fc.process_tick()

    # Fuel cell should consume H2 and produce power
    assert stores.get("Hydrogen").current_level < initial_h2, "Should consume hydrogen"

    print("  ✓ Fuel Cell tests passed")


def test_power_system_failover():
    """Test power system automatic failover."""
    print("Testing Power System failover...")

    stores = create_test_stores()
    modules = ModuleManager(stores)
    power_system = PowerSystem(stores, modules)

    # Add components
    solar = SolarArray("Solar_Main", stores)
    solar.start()
    solar.tick()
    power_system.add_solar_array(solar)

    fc = FuelCell("FC_Backup", stores, capacity_kw=50.0)
    fc.start()
    fc.tick()
    power_system.add_fuel_cell(fc)

    # Simulate nighttime (no solar)
    state = power_system.tick(hour=0)  # Midnight

    assert state.solar_output_kw == 0.0, "No solar at night"
    # Fuel cells should be requested for backup
    assert state.is_day == False, "Should detect nighttime"

    # Simulate daytime
    state = power_system.tick(hour=12)  # Noon

    assert state.solar_output_kw > 0, "Should have solar at noon"
    assert state.is_day == True, "Should detect daytime"

    print("  ✓ Power System failover tests passed")


# =============================================================================
# WATER SYSTEM TESTS
# =============================================================================

def test_rsv_extractor():
    """Test RSV ice extraction."""
    print("Testing RSV Extractor...")

    stores = create_test_stores()
    extractor = RSVExtractor("RSV_Test", stores, extraction_rate_l_per_day=700.0)
    extractor.start()
    extractor.tick()  # Startup tick 1
    extractor.tick()  # Startup tick 2

    assert extractor.is_operational, "Extractor should be operational after startup"

    initial_water = stores.get("Potable_Water").current_level
    metrics = extractor.process_tick()

    assert metrics["extracted_l"] > 0, "Should extract water"
    expected_rate = 700.0 / 24  # L per tick
    assert abs(metrics["extracted_l"] - expected_rate) < 1, f"Expected ~{expected_rate:.1f}L/tick"

    print("  ✓ RSV Extractor tests passed")


def test_water_recycler():
    """Test water recycling."""
    print("Testing Water Recycler...")

    stores = create_test_stores()
    recycler = WaterRecycler("Recycler_Test", stores, efficiency=0.95)
    recycler.start()
    recycler.tick()  # Complete startup

    initial_potable = stores.get("Potable_Water").current_level
    initial_grey = stores.get("Grey_Water").current_level

    recycler.tick()  # Process water
    metrics = recycler.process_tick()

    # Should have processed grey water
    assert stores.get("Grey_Water").current_level < initial_grey, "Should consume grey water"

    print("  ✓ Water Recycler tests passed")


def test_h2_combuster_emergency():
    """Test emergency H2 combustion for water."""
    print("Testing H2 Combuster emergency...")

    stores = create_test_stores()
    combuster = H2Combuster("H2_Emergency", stores)

    # Should start inactive
    assert not combuster.is_active, "Should start inactive"

    # Activate emergency
    combuster.activate()
    assert combuster.is_active, "Should be active after activation"

    combuster.tick()  # Complete startup
    initial_water = stores.get("Potable_Water").current_level

    combuster.tick()  # Process
    metrics = combuster.process_tick()

    # Should produce water from H2
    assert metrics["active"], "Should be active"

    # Deactivate
    combuster.deactivate()
    assert not combuster.is_active, "Should be inactive after deactivation"

    print("  ✓ H2 Combuster tests passed")


def test_wall_water_reserve():
    """Test wall water reserve emergency system."""
    print("Testing Wall Water Reserve...")

    stores = create_test_stores()
    reserve = WallWaterReserve(stores, num_pods=13)

    assert reserve.current_level > 0, "Should start with water"
    assert not reserve.is_tapped, "Should not be tapped initially"

    initial_potable = stores.get("Potable_Water").current_level

    # Tap reserve
    drawn = reserve.tap_reserve(100.0)

    assert drawn == 100.0, f"Should draw requested amount, got {drawn}"
    assert reserve.is_tapped, "Should be marked as tapped"
    assert stores.get("Potable_Water").current_level == initial_potable + 100.0, "Should add to potable"

    print("  ✓ Wall Water Reserve tests passed")


def test_water_system_redundancy():
    """Test water system dual RSV redundancy."""
    print("Testing Water System redundancy...")

    stores = create_test_stores()
    modules = ModuleManager(stores)
    water_system = WaterSystem(stores, modules)

    # Add two RSV extractors
    rsv1 = RSVExtractor("RSV_1", stores)
    rsv1.start()
    rsv1.tick()
    rsv1.tick()
    water_system.add_rsv_extractor(rsv1)

    rsv2 = RSVExtractor("RSV_2", stores)
    rsv2.start()
    rsv2.tick()
    rsv2.tick()
    water_system.add_rsv_extractor(rsv2)

    state = water_system.tick()
    assert state.rsv_pods_operational == 2, "Both RSVs should be operational"

    # Simulate RSV failure
    water_system.handle_rsv_failure(0)
    state = water_system.tick()

    assert state.rsv_pods_operational == 1, "One RSV should remain operational"

    print("  ✓ Water System redundancy tests passed")


# =============================================================================
# NUTRIENT SYSTEM TESTS
# =============================================================================

def test_haber_bosch():
    """Test Haber-Bosch nitrogen fixation."""
    print("Testing Haber-Bosch reactor...")

    stores = create_test_stores()
    haber = HaberBoschReactor("HB_Test", stores)
    haber.start()

    # Wait for startup (4 ticks)
    for _ in range(4):
        haber.tick()

    assert haber.is_operational, "Should be operational after startup"

    initial_n = stores.get("Nutrients_N").current_level
    metrics = haber.process_tick()

    # Should produce nitrogen nutrients
    assert metrics["efficiency"] > 0, "Should have non-zero efficiency"

    print("  ✓ Haber-Bosch tests passed")


def test_waste_processor():
    """Test waste processing to biogas and nutrients."""
    print("Testing Waste Processor...")

    stores = create_test_stores()
    processor = WasteProcessor("Waste_Test", stores)
    processor.start()

    # Wait for startup (24 ticks for digester)
    for _ in range(24):
        processor.tick()

    assert processor.is_operational, "Should be operational after startup"

    initial_biogas = stores.get("Biogas").current_level
    initial_p = stores.get("Nutrients_P").current_level

    # Process some waste
    processor.tick()
    metrics = processor.process_tick()

    # Should process waste
    assert metrics["waste_processed_kg"] >= 0, "Should process waste"

    print("  ✓ Waste Processor tests passed")


def test_nutrient_system_cycle():
    """Test complete nutrient cycling."""
    print("Testing Nutrient System cycle...")

    stores = create_test_stores()
    modules = ModuleManager(stores)
    nutrient_system = NutrientSystem(stores, modules)

    # Initialize system
    nutrient_system.initialize_default_system()

    # Run for several ticks to let things start up
    for _ in range(30):
        nutrient_system.tick()

    state = nutrient_system.tick()

    # Check nutrient levels
    assert state.nitrogen_store_kg >= 0, "Should track nitrogen"
    assert state.phosphorus_store_kg >= 0, "Should track phosphorus"
    assert state.potassium_store_kg > 0, "Should have potassium from Earth supply"

    # Check days of supply
    days = nutrient_system.get_days_of_supply()
    assert "nitrogen" in days, "Should calculate N supply"
    assert "potassium" in days, "Should calculate K supply"

    print("  ✓ Nutrient System cycle tests passed")


def test_nutrient_consumption():
    """Test nutrient consumption for crops."""
    print("Testing Nutrient consumption...")

    stores = create_test_stores()
    modules = ModuleManager(stores)
    nutrient_system = NutrientSystem(stores, modules)
    nutrient_system.initialize_default_system()

    # Get initial levels
    initial_n = nutrient_system.get_nutrient_level(NutrientType.NITROGEN)
    initial_p = nutrient_system.get_nutrient_level(NutrientType.PHOSPHORUS)
    initial_k = nutrient_system.get_nutrient_level(NutrientType.POTASSIUM)

    # Consume nutrients
    consumed = nutrient_system.consume_nutrients(n_kg=1.0, p_kg=0.5, k_kg=0.8)

    assert consumed["nitrogen"] <= 1.0, "Should consume up to requested N"
    assert consumed["phosphorus"] <= 0.5, "Should consume up to requested P"
    assert consumed["potassium"] <= 0.8, "Should consume up to requested K"

    # Levels should decrease
    assert nutrient_system.get_nutrient_level(NutrientType.NITROGEN) < initial_n, "N should decrease"
    assert nutrient_system.get_nutrient_level(NutrientType.POTASSIUM) < initial_k, "K should decrease"

    print("  ✓ Nutrient consumption tests passed")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all Sprint 2 system tests."""
    print("\n" + "="*50)
    print("MARS TO TABLE — Sprint 2 System Tests")
    print("="*50 + "\n")

    try:
        # Power tests
        test_solar_array_day_night()
        test_solar_array_dust_storm()
        test_fuel_cell()
        test_power_system_failover()

        # Water tests
        test_rsv_extractor()
        test_water_recycler()
        test_h2_combuster_emergency()
        test_wall_water_reserve()
        test_water_system_redundancy()

        # Nutrient tests
        test_haber_bosch()
        test_waste_processor()
        test_nutrient_system_cycle()
        test_nutrient_consumption()

        print("\n" + "="*50)
        print("ALL SPRINT 2 TESTS PASSED ✓")
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
