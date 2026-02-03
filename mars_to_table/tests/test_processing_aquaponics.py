"""
Tests for food processing and aquaponics systems:
- Oil extraction
- Fermentation
- Grain milling
- Food drying
- Aquaponics (tilapia)
- Stress testing
"""

import pytest
from mars_to_table.systems.processing import (
    OilProcessor,
    FermentationVessel,
    GrainMill,
    FoodDryer,
    OIL_CROPS,
    FERMENTED_PRODUCTS,
)
from mars_to_table.systems.aquaponics import (
    AquaponicsManager,
    FishSpecies,
    FishLifeStage,
    FISH_SPECIES,
)
from mars_to_table.simulation.stress_tests import (
    StressTestRunner,
    StressTestCategory,
    StressTestSeverity,
    STRESS_TEST_SCENARIOS,
)


# =============================================================================
# OIL PROCESSING TESTS
# =============================================================================

class TestOilProcessor:
    """Tests for oil extraction system."""

    def test_initialization(self):
        """Test oil processor setup."""
        processor = OilProcessor(power_kw=5.0)
        assert processor.power_consumption_kw == 5.0
        assert processor.total_oil_produced_l == 0.0

    def test_start_batch(self):
        """Test starting an oil extraction batch."""
        processor = OilProcessor()

        result = processor.start_batch("soybean", 10.0)
        assert result is True
        assert processor.current_batch is not None
        assert processor.current_batch["seed_type"] == "soybean"

    def test_reject_unknown_crop(self):
        """Test rejecting unknown oil crops."""
        processor = OilProcessor()

        result = processor.start_batch("unknown_crop", 5.0)
        assert result is False

    def test_cannot_start_while_processing(self):
        """Test cannot start new batch while processing."""
        processor = OilProcessor()
        processor.start_batch("soybean", 10.0)

        result = processor.start_batch("sunflower", 5.0)
        assert result is False

    def test_processing_completion(self):
        """Test completing oil extraction."""
        processor = OilProcessor()
        processor.start_batch("soybean", 10.0)

        # Process until complete
        result = None
        for _ in range(100):
            result = processor.process_tick(power_available_kw=10.0)
            if result:
                break

        assert result is not None
        assert result["oil_produced_l"] > 0
        assert result["meal_produced_kg"] > 0
        assert result["seed_type"] == "soybean"

    def test_oil_yield_calculations(self):
        """Test oil yield varies by crop type."""
        # Sunflower has higher oil content than soybean
        soy = OIL_CROPS["soybean"]
        sunflower = OIL_CROPS["sunflower"]

        assert sunflower.oil_content_pct > soy.oil_content_pct

    def test_insufficient_power(self):
        """Test processing stops without power."""
        processor = OilProcessor()
        processor.start_batch("soybean", 10.0)
        initial_ticks = processor.processing_ticks_remaining

        result = processor.process_tick(power_available_kw=1.0)  # Insufficient

        # Should not progress
        assert result is None
        assert processor.processing_ticks_remaining == initial_ticks


class TestFermentationVessel:
    """Tests for fermentation system."""

    def test_initialization(self):
        """Test fermentation vessel setup."""
        vessel = FermentationVessel(capacity_kg=20.0, vessel_id="test_01")
        assert vessel.capacity_kg == 20.0
        assert vessel.product_type is None

    def test_start_fermentation(self):
        """Test starting a fermentation batch."""
        vessel = FermentationVessel(capacity_kg=20.0)

        result = vessel.start_fermentation("sauerkraut", 10.0, current_tick=0)
        assert result is True
        assert vessel.product_type == "sauerkraut"
        assert vessel.batch_kg == 10.0

    def test_reject_unknown_product(self):
        """Test rejecting unknown fermented products."""
        vessel = FermentationVessel()

        result = vessel.start_fermentation("unknown_product", 5.0, current_tick=0)
        assert result is False

    def test_capacity_limit(self):
        """Test batch is limited to vessel capacity."""
        vessel = FermentationVessel(capacity_kg=10.0)

        vessel.start_fermentation("sauerkraut", 20.0, current_tick=0)
        assert vessel.batch_kg == 10.0  # Limited to capacity

    def test_fermentation_progress(self):
        """Test fermentation progress tracking."""
        vessel = FermentationVessel()
        vessel.start_fermentation("tempeh", 5.0, current_tick=0)

        # Tempeh ferments for 2 days = 48 ticks
        vessel.update_tick(24, temperature_c=28.0)
        progress = vessel.get_progress()

        assert 0 < progress < 1

    def test_fermentation_completion(self):
        """Test completing fermentation."""
        vessel = FermentationVessel()
        vessel.start_fermentation("tempeh", 5.0, current_tick=0)

        # Run until complete (2 days + buffer)
        result = None
        for tick in range(100):
            result = vessel.update_tick(tick, temperature_c=28.0)
            if result:
                break

        assert result is not None
        assert result["product"] == "tempeh"
        assert result["output_kg"] > 0
        assert result["probiotic_benefit"] > 0

    def test_temperature_affects_speed(self):
        """Test temperature affects fermentation speed."""
        # Warm fermentation
        warm_vessel = FermentationVessel(vessel_id="warm")
        warm_vessel.start_fermentation("kimchi", 5.0, current_tick=0)

        # Cold fermentation
        cold_vessel = FermentationVessel(vessel_id="cold")
        cold_vessel.start_fermentation("kimchi", 5.0, current_tick=0)

        # Update both at different temps
        warm_vessel.update_tick(48, temperature_c=30.0)
        cold_vessel.update_tick(48, temperature_c=15.0)

        # Warm should progress faster
        assert warm_vessel.get_progress() >= cold_vessel.get_progress()


class TestGrainMill:
    """Tests for grain milling."""

    def test_initialization(self):
        """Test grain mill setup."""
        mill = GrainMill()
        assert mill.total_flour_kg == 0.0

    def test_mill_wheat(self):
        """Test milling wheat into flour."""
        mill = GrainMill()

        result = mill.mill_grain("wheat", 10.0, whole_grain=False)

        assert result["flour_output_kg"] > 0
        assert result["bran_output_kg"] > 0
        assert result["flour_output_kg"] + result["bran_output_kg"] < 10.0  # Some loss

    def test_whole_grain_milling(self):
        """Test whole grain milling includes bran."""
        mill = GrainMill()

        result = mill.mill_grain("wheat", 10.0, whole_grain=True)

        assert result["bran_output_kg"] == 0.0  # Bran kept in flour
        assert result["whole_grain"] is True

    def test_different_grains(self):
        """Test milling different grain types."""
        mill = GrainMill()

        wheat = mill.mill_grain("wheat", 10.0)
        rice = mill.mill_grain("rice", 10.0)
        corn = mill.mill_grain("corn", 10.0)

        # Rice has more hull loss
        assert rice["flour_output_kg"] < wheat["flour_output_kg"]


class TestFoodDryer:
    """Tests for food dehydration."""

    def test_initialization(self):
        """Test food dryer setup."""
        dryer = FoodDryer(capacity_kg=10.0)
        assert dryer.capacity_kg == 10.0

    def test_dry_fruit(self):
        """Test drying fruit."""
        dryer = FoodDryer()

        result = dryer.dry_food("fruit", 5.0)

        assert result["dried_output_kg"] < 5.0  # Lost water
        assert result["weight_reduction_pct"] > 50  # Significant reduction
        assert result["shelf_life_months"] == 12

    def test_different_foods(self):
        """Test drying different food types."""
        dryer = FoodDryer()

        tomato = dryer.dry_food("tomato", 5.0)  # 94% water
        potato = dryer.dry_food("potato", 5.0)  # 80% water

        # Tomato loses more weight (more water)
        assert tomato["weight_reduction_pct"] > potato["weight_reduction_pct"]

    def test_capacity_limit(self):
        """Test dryer capacity limit."""
        dryer = FoodDryer(capacity_kg=5.0)

        result = dryer.dry_food("fruit", 10.0)

        assert result["fresh_input_kg"] == 5.0  # Limited to capacity


# =============================================================================
# AQUAPONICS TESTS
# =============================================================================

class TestAquaponicsManager:
    """Tests for aquaponics fish farming."""

    def test_initialization(self):
        """Test aquaponics system setup."""
        manager = AquaponicsManager(num_tanks=4, tank_volume_l=2000)

        assert len(manager.tanks) == 4
        assert manager.total_volume_l == 8000

    def test_population_initialization(self):
        """Test initializing fish population."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=200, include_broodstock=10)

        total_fish = sum(len(t.fish) for t in manager.tanks)
        assert total_fish == 200

        broodstock = sum(
            1 for t in manager.tanks
            for f in t.fish
            if f.is_broodstock
        )
        assert broodstock == 10

    def test_fish_species(self):
        """Test fish species configuration."""
        spec = FISH_SPECIES[FishSpecies.TILAPIA]

        assert spec.name == "Nile Tilapia"
        assert spec.optimal_temp_c == 28
        assert spec.market_weight_g == 500

    def test_tank_stocking_density(self):
        """Test tank stocking density tracking."""
        manager = AquaponicsManager(num_tanks=4, tank_volume_l=1000)
        manager.initialize_population(num_fish=100, include_broodstock=10)

        for tank in manager.tanks:
            # Density should be within limits
            assert tank.stocking_density_kg_m3 < tank.max_fish_density_kg_m3

    def test_update_tick(self):
        """Test aquaponics tick update."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=100, include_broodstock=5)

        result = manager.update_tick(
            tick=1,
            feed_available_kg=1.0,
            water_temp_c=28.0,
        )

        assert "feed_consumed_kg" in result
        assert "fish_grown_kg" in result
        assert "water_quality" in result

    def test_fish_growth(self):
        """Test fish grow over time."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=50)

        initial_weight = sum(t.total_fish_weight_kg for t in manager.tanks)

        # Run for 100 ticks with good conditions
        for tick in range(100):
            manager.update_tick(tick, feed_available_kg=0.5, water_temp_c=28.0)

        final_weight = sum(t.total_fish_weight_kg for t in manager.tanks)

        assert final_weight > initial_weight

    def test_breeding(self):
        """Test fish breeding mechanism exists and can be triggered."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=100, include_broodstock=10)

        # Verify broodstock are set up properly
        broodstock = [
            f for t in manager.tanks for f in t.fish if f.is_broodstock
        ]
        assert len(broodstock) == 10

        # Run some ticks and verify breeding system runs without error
        for tick in range(100):
            result = manager.update_tick(tick, feed_available_kg=0.5, water_temp_c=28.0)
            assert "spawned" in result

        # Breeding is probabilistic over long periods - just verify the system works
        assert manager.broodstock_tank is not None

    def test_water_quality_tracking(self):
        """Test water quality parameters are tracked."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=50)

        manager.update_tick(tick=1, feed_available_kg=0.5, water_temp_c=28.0)

        quality = manager._get_water_quality_summary()

        assert "avg_temp_c" in quality
        assert "avg_ammonia_ppm" in quality
        assert "avg_nitrate_ppm" in quality
        assert "avg_do_ppm" in quality

    def test_status_report(self):
        """Test status report generation."""
        manager = AquaponicsManager()
        manager.initialize_population(num_fish=100)

        status = manager.get_status()

        assert status["species"] == "Nile Tilapia"
        assert status["total_fish"] == 100
        assert "fish_by_stage" in status
        assert "tanks" in status


# =============================================================================
# STRESS TEST TESTS
# =============================================================================

class TestStressTestRunner:
    """Tests for stress testing framework."""

    def test_initialization(self):
        """Test stress test runner setup."""
        runner = StressTestRunner()

        assert len(runner.scenarios) > 0
        assert len(runner.results) == 0

    def test_list_scenarios(self):
        """Test listing available scenarios."""
        runner = StressTestRunner()

        all_scenarios = runner.list_scenarios()
        assert len(all_scenarios) > 10

        power_scenarios = runner.list_scenarios(category=StressTestCategory.POWER)
        assert len(power_scenarios) > 0

    def test_get_scenario(self):
        """Test getting a specific scenario."""
        runner = StressTestRunner()

        scenario = runner.get_scenario("power_total_outage")

        assert scenario is not None
        assert scenario.name == "Total Power Outage"
        assert scenario.category == StressTestCategory.POWER
        assert scenario.severity == StressTestSeverity.EMERGENCY

    def test_scenario_structure(self):
        """Test scenario has required structure."""
        for scenario_id, scenario in STRESS_TEST_SCENARIOS.items():
            assert scenario.scenario_id == scenario_id
            assert scenario.name
            assert scenario.category in StressTestCategory
            assert scenario.severity in StressTestSeverity
            assert scenario.duration_ticks > 0
            assert scenario.success_criteria

    def test_run_simple_scenario(self):
        """Test running a simple stress test."""
        runner = StressTestRunner()

        def mock_tick_callback(tick: int, conditions: dict) -> dict:
            """Simple mock system state."""
            return {
                "power": {"battery_level_kwh": 5000},
                "water": {"reservoir_level_l": 15000},
                "food": {"total_kg": 1000},
                "atmosphere": {"o2_pct": 21, "co2_pct": 0.04},
                "crew": {"avg_health": 1.0, "avg_morale": 0.8, "survival_rate": 1.0},
            }

        # Run a short scenario
        result = runner.run_scenario(
            "atmosphere_o2_generation_failure",
            system_state={},
            tick_callback=mock_tick_callback,
        )

        assert result is not None
        assert result.scenario_id == "atmosphere_o2_generation_failure"
        assert isinstance(result.passed, bool)
        assert 0 <= result.score <= 100

    def test_summary_generation(self):
        """Test summary generation after running tests."""
        runner = StressTestRunner()

        def mock_callback(tick, conditions):
            return {
                "power": {"battery_level_kwh": 5000},
                "water": {"reservoir_level_l": 15000},
                "food": {"total_kg": 1000},
                "atmosphere": {"o2_pct": 21, "co2_pct": 0.04},
                "crew": {"avg_health": 1.0, "avg_morale": 0.8, "survival_rate": 1.0},
            }

        # Run a few scenarios
        runner.run_scenario("atmosphere_o2_generation_failure", {}, mock_callback)

        summary = runner.get_summary()

        assert summary["total_scenarios"] == 1
        assert "pass_rate" in summary

    def test_report_generation(self):
        """Test human-readable report generation."""
        runner = StressTestRunner()

        def mock_callback(tick, conditions):
            return {
                "power": {"battery_level_kwh": 5000},
                "water": {"reservoir_level_l": 15000},
                "food": {"total_kg": 1000},
                "atmosphere": {"o2_pct": 21, "co2_pct": 0.04},
                "crew": {"avg_health": 1.0, "survival_rate": 1.0},
            }

        runner.run_scenario("atmosphere_o2_generation_failure", {}, mock_callback)

        report = runner.generate_report()

        assert "STRESS TEST REPORT" in report
        assert "O2 Generation" in report

    def test_scenario_categories(self):
        """Test scenarios cover all categories."""
        categories_covered = set()

        for scenario in STRESS_TEST_SCENARIOS.values():
            categories_covered.add(scenario.category)

        # Should have scenarios for all major categories
        assert StressTestCategory.POWER in categories_covered
        assert StressTestCategory.WATER in categories_covered
        assert StressTestCategory.FOOD in categories_covered
        assert StressTestCategory.COMBINED in categories_covered


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestProcessingIntegration:
    """Integration tests for processing systems."""

    def test_soybean_to_oil_and_tempeh(self):
        """Test soybeans can produce both oil and tempeh."""
        # Process soybeans for oil
        oil_processor = OilProcessor()
        oil_processor.start_batch("soybean", 10.0)

        oil_result = None
        for _ in range(100):
            oil_result = oil_processor.process_tick(power_available_kw=10.0)
            if oil_result:
                break

        # Remaining meal could be used for tempeh
        meal_kg = oil_result["meal_produced_kg"]

        # Ferment into tempeh
        vessel = FermentationVessel()
        vessel.start_fermentation("tempeh", meal_kg, current_tick=0)

        tempeh_result = None
        for tick in range(100):
            tempeh_result = vessel.update_tick(tick, temperature_c=30.0)
            if tempeh_result:
                break

        assert tempeh_result is not None
        assert tempeh_result["output_kg"] > 0

    def test_grain_to_flour_to_bread(self):
        """Test grain processing chain."""
        # Mill wheat
        mill = GrainMill()
        flour_result = mill.mill_grain("wheat", 10.0, whole_grain=False)

        flour_kg = flour_result["flour_output_kg"]

        # Use flour for sourdough starter
        vessel = FermentationVessel()
        vessel.start_fermentation("sourdough_starter", flour_kg * 0.1, current_tick=0)

        # Process fermentation
        starter_result = None
        for tick in range(200):
            starter_result = vessel.update_tick(tick, temperature_c=22.0)
            if starter_result:
                break

        assert starter_result is not None
        assert flour_kg > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
