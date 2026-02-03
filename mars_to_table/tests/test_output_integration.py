"""
Mars to Table — Sprint 6 Tests
Output & Integration Testing

Tests for:
- Metrics collection and analysis
- BioSim XML generation
- BioSim REST client (mock)
- Mission evaluation
"""

import sys
import os
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mars_to_table.config import MISSION, POWER, WATER, FOOD, LIVESTOCK

# Import Sprint 6 modules
from mars_to_table.simulation.metrics import (
    MetricCategory,
    FoodProductionMetrics,
    ResourceMetrics,
    SystemMetrics,
    CrewMetrics,
    MissionMetrics,
    MetricsCollector,
    MissionEvaluator,
)

from mars_to_table.biosim.xml_generator import (
    BioSimXMLGenerator,
    ModuleConfig,
    StoreConfig,
    CrewConfig,
    SimulationConfig,
)

from mars_to_table.biosim.client import (
    BioSimClient,
    BioSimSession,
    MockBioSimClient,
    ConnectionError,
    SimulationError,
)


# =============================================================================
# METRICS TESTS
# =============================================================================

def test_food_production_metrics():
    """Test food production metrics tracking."""
    print("Testing Food Production Metrics...")

    metrics = FoodProductionMetrics()

    # Simulate production
    metrics.vegetables_kg = 100.0
    metrics.potatoes_kg = 50.0
    metrics.flour_kg = 30.0
    metrics.milk_liters = 40.0
    metrics.eggs_count = 85.0
    metrics.cheese_kg = 2.0

    metrics.calories_produced = 50000.0
    metrics.calories_from_earth = 10000.0

    # Test calculations
    total_food = metrics.total_food_kg()
    assert total_food > 0, "Should have positive food production"

    ei_ratio = metrics.earth_independence_ratio()
    assert 0 < ei_ratio < 1, f"Earth independence ratio should be 0-1, got {ei_ratio}"
    assert abs(ei_ratio - 0.833) < 0.01, f"Expected ~83.3% EI, got {ei_ratio * 100:.1f}%"

    print(f"  ✓ Food metrics: {total_food:.1f} kg, {ei_ratio * 100:.1f}% EI")


def test_resource_metrics():
    """Test resource metrics tracking."""
    print("Testing Resource Metrics...")

    metrics = ResourceMetrics()

    # Simulate resource usage
    metrics.power_generated_kwh = 1000.0
    metrics.power_consumed_kwh = 850.0
    metrics.power_from_solar_kwh = 800.0
    metrics.power_from_fuel_cells_kwh = 200.0

    metrics.water_extracted_liters = 500.0
    metrics.water_consumed_liters = 400.0
    metrics.water_recycled_liters = 380.0

    metrics.hydrogen_consumed_kg = 10.0
    metrics.hydrogen_remaining_kg = 490.0

    # Test calculations
    power_eff = metrics.power_efficiency()
    assert 0 < power_eff <= 1, f"Power efficiency should be 0-1, got {power_eff}"
    assert abs(power_eff - 0.85) < 0.01

    water_recycling = metrics.water_recycling_rate()
    assert 0 < water_recycling <= 1

    print(f"  ✓ Resource metrics: {power_eff * 100:.1f}% power efficiency")


def test_system_metrics():
    """Test system metrics tracking."""
    print("Testing System Metrics...")

    metrics = SystemMetrics()

    metrics.total_modules = 20
    metrics.operational_modules = 18
    metrics.degraded_modules = 1
    metrics.failed_modules = 1

    metrics.total_ticks = 1000
    metrics.ticks_nominal = 950
    metrics.ticks_degraded = 40
    metrics.ticks_emergency = 10

    metrics.total_events = 10
    metrics.events_successfully_handled = 8

    # Test calculations
    operational_ratio = metrics.operational_ratio()
    assert operational_ratio == 0.9, f"Expected 90% operational, got {operational_ratio * 100}%"

    uptime = metrics.uptime_ratio()
    assert uptime == 0.95, f"Expected 95% uptime, got {uptime * 100}%"

    print(f"  ✓ System metrics: {operational_ratio * 100:.0f}% operational, {uptime * 100:.0f}% uptime")


def test_crew_metrics():
    """Test crew metrics tracking."""
    print("Testing Crew Metrics...")

    metrics = CrewMetrics()

    metrics.crew_size = 15
    metrics.crew_healthy = 14
    metrics.crew_fatigued = 1
    metrics.crew_ill = 0

    metrics.avg_calories_received = 2800.0
    metrics.avg_calories_required = 3035.0
    metrics.nutrition_deficit_days = 3

    # Test calculations
    health_ratio = metrics.health_ratio()
    assert abs(health_ratio - 0.933) < 0.01

    nutrition = metrics.nutrition_adequacy()
    assert 0 < nutrition < 1
    assert abs(nutrition - 0.923) < 0.01

    print(f"  ✓ Crew metrics: {health_ratio * 100:.1f}% healthy, {nutrition * 100:.1f}% nutrition")


def test_mission_metrics():
    """Test mission metrics tracking."""
    print("Testing Mission Metrics...")

    metrics = MissionMetrics()

    metrics.current_sol = 250
    metrics.total_sols = 500
    metrics.earth_independence_achieved = 0.84
    metrics.earth_independence_target = 0.84
    metrics.crew_survival_rate = 1.0

    # Test calculations
    progress = metrics.progress_ratio()
    assert progress == 0.5

    margin = metrics.earth_independence_margin()
    assert abs(margin) < 0.01  # Achieved equals target

    print(f"  ✓ Mission metrics: {progress * 100:.0f}% progress, {margin * 100:+.0f}% EI margin")


def test_metrics_collector():
    """Test MetricsCollector aggregation."""
    print("Testing Metrics Collector...")

    collector = MetricsCollector()

    # Update various metrics
    collector.update_food_metrics(
        vegetables_kg=10.0,
        flour_kg=5.0,
        milk_l=8.0,
        eggs=17.0,
        calories_produced=5000.0,
        calories_from_earth=1000.0,
    )

    collector.update_resource_metrics(
        power_generated=100.0,
        power_consumed=85.0,
        water_extracted=50.0,
        water_consumed=40.0,
        h2_remaining=480.0,
    )

    collector.update_crew_metrics(
        healthy=15,
        calories_received=2900.0,
        calories_required=3035.0,
    )

    collector.update_system_metrics(
        total_modules=20,
        operational=18,
        events_today=1,
        events_handled=1,
    )

    # Get summary
    summary = collector.get_summary()

    assert "mission" in summary
    assert "food_production" in summary
    assert "resources" in summary
    assert "crew" in summary
    assert "system" in summary

    # Get detailed report
    report = collector.get_detailed_report()

    assert "earth_independence" in report
    assert "food_production" in report
    assert "resources" in report

    print(f"  ✓ Metrics collector: {len(summary)} categories tracked")


def test_metrics_export():
    """Test metrics export to JSON and CSV."""
    print("Testing Metrics Export...")

    collector = MetricsCollector()

    # Add some data
    collector.update_food_metrics(calories_produced=10000, calories_from_earth=2000)
    collector.update_resource_metrics(power_generated=500, power_consumed=400)

    # Record some sol history
    collector.record_sol_end(1, {})
    collector.mission.current_sol = 1

    # Export to temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_path = f.name

    collector.export_json(json_path)
    assert os.path.exists(json_path)

    # Verify JSON content
    import json
    with open(json_path) as f:
        data = json.load(f)
    assert "food_production" in data
    assert "resources" in data

    os.unlink(json_path)

    print("  ✓ Metrics export working")


def test_mission_evaluator():
    """Test mission success evaluation."""
    print("Testing Mission Evaluator...")

    collector = MetricsCollector()

    # Set up successful mission metrics
    collector.mission.current_sol = 500
    collector.mission.earth_independence_achieved = 0.84
    collector.crew.crew_size = 15
    collector.crew.crew_healthy = 15
    collector.crew.avg_calories_received = 3000
    collector.crew.avg_calories_required = 3035
    collector.system.total_ticks = 12000
    collector.system.ticks_nominal = 11500
    collector.system.total_events = 20
    collector.system.events_successfully_handled = 18
    collector.food.eggs_count = 100  # Livestock bonus

    evaluator = MissionEvaluator(collector)
    results = evaluator.evaluate()

    assert "overall_success" in results
    assert "criteria" in results
    assert "scoring" in results

    # Check individual criteria
    assert "earth_independence" in results["criteria"]
    assert "mission_duration" in results["criteria"]
    assert "crew_survival" in results["criteria"]

    # Generate report
    report = evaluator.generate_report()
    assert "MARS TO TABLE" in report
    assert "Earth Independence" in report

    print(f"  ✓ Mission evaluation: Overall {'PASS' if results['overall_success'] else 'FAIL'}")
    print(f"    Score: {results['scoring']['total_score']:.1f}/{results['scoring']['max_possible']}")


# =============================================================================
# XML GENERATOR TESTS
# =============================================================================

def test_store_config():
    """Test StoreConfig XML generation."""
    print("Testing Store Config...")

    from xml.etree import ElementTree as ET

    config = StoreConfig(
        name="TestStore",
        module_type="GenericStore",
        capacity=1000.0,
        initial_level=500.0,
        description="Test store",
    )

    parent = ET.Element("root")
    element = config.to_xml(parent)

    assert element.get("name") == "TestStore"
    assert element.get("moduleType") == "GenericStore"
    assert element.find("capacity").text == "1000.0"
    assert element.find("currentLevel").text == "500.0"

    print("  ✓ Store config XML generation working")


def test_module_config():
    """Test ModuleConfig XML generation."""
    print("Testing Module Config...")

    from xml.etree import ElementTree as ET

    config = ModuleConfig(
        name="TestModule",
        module_type="PowerGenerator",
        power_consumption=50.0,
        inputs={"hydrogen": "HydrogenStore"},
        outputs={"power": "PowerStore"},
        parameters={"efficiency": 0.6},
    )

    parent = ET.Element("root")
    element = config.to_xml(parent)

    assert element.get("name") == "TestModule"
    assert element.find("powerConsumption").text == "50.0"
    assert element.find("efficiency").text == "0.6"

    # Check inputs/outputs
    inputs = element.find("inputs")
    assert inputs is not None
    outputs = element.find("outputs")
    assert outputs is not None

    print("  ✓ Module config XML generation working")


def test_biosim_xml_generator():
    """Test full BioSim XML generation."""
    print("Testing BioSim XML Generator...")

    generator = BioSimXMLGenerator()

    # Check default configuration
    assert len(generator.stores) > 10, "Should have multiple stores"
    assert len(generator.modules) > 10, "Should have multiple modules"

    # Generate XML
    xml_content = generator.generate_xml()

    assert "<?xml" in xml_content
    assert "BioSimConfig" in xml_content
    assert "Mars to Table" in xml_content

    # Check key modules are present
    assert "SolarArray" in xml_content
    assert "FoodPOD_1" in xml_content
    assert "LivestockPOD" in xml_content
    assert "RSV_Extractor_1" in xml_content

    # Check key stores
    assert "PowerStore" in xml_content
    assert "PotableWaterStore" in xml_content
    assert "FreshFoodStore" in xml_content

    print(f"  ✓ Generated XML with {len(generator.modules)} modules, {len(generator.stores)} stores")


def test_xml_save_and_load():
    """Test saving XML to file."""
    print("Testing XML Save...")

    generator = BioSimXMLGenerator()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        xml_path = f.name

    generator.save_xml(xml_path)
    assert os.path.exists(xml_path)

    # Verify file content
    with open(xml_path) as f:
        content = f.read()
    assert "BioSimConfig" in content

    os.unlink(xml_path)

    print("  ✓ XML save working")


def test_xml_customization():
    """Test XML generator customization."""
    print("Testing XML Customization...")

    generator = BioSimXMLGenerator()

    # Set custom duration
    generator.set_simulation_duration(100)  # 100 sols
    assert generator.sim_config.duration_ticks == 100 * 24

    # Set custom crew size
    generator.set_crew_size(20)
    assert generator.crew.crew_size == 20

    # Add custom module
    custom_module = ModuleConfig(
        name="CustomSensor",
        module_type="Sensor",
        power_consumption=5.0,
    )
    generator.add_custom_module(custom_module)
    assert "CustomSensor" in generator.get_module_list()

    # Add custom store
    custom_store = StoreConfig(
        name="CustomBuffer",
        module_type="Buffer",
        capacity=100.0,
    )
    generator.add_custom_store(custom_store)
    assert "CustomBuffer" in generator.get_store_list()

    print("  ✓ XML customization working")


# =============================================================================
# BIOSIM CLIENT TESTS
# =============================================================================

def test_biosim_session():
    """Test BioSimSession tracking."""
    print("Testing BioSim Session...")

    session = BioSimSession(
        simulation_id="test-123",
        name="TestSim",
        status="running",
    )

    session.current_tick = 100
    session.current_sol = 4

    summary = session.get_summary()

    assert summary["simulation_id"] == "test-123"
    assert summary["current_tick"] == 100
    assert summary["current_sol"] == 4
    assert "elapsed_time_s" in summary

    print("  ✓ BioSim session tracking working")


def test_mock_biosim_client():
    """Test MockBioSimClient for testing."""
    print("Testing Mock BioSim Client...")

    client = MockBioSimClient()

    # Test connection
    assert client.test_connection()

    # Start simulation
    session = client.start_simulation(name="MockTest")
    assert session is not None
    assert session.status == "running"

    # Run ticks
    for _ in range(5):
        result = client.tick()
        assert "tick" in result
        assert "status" in result

    assert client.active_session.current_tick == 5

    # Get state
    state = client.get_state()
    assert "tick" in state
    assert "stores" in state

    # Inject malfunction
    result = client.inject_malfunction(
        module_name="TestModule",
        malfunction_type="TestMalfunction",
        intensity=0.5,
    )
    assert "status" in result

    # Stop simulation
    final = client.stop_simulation()
    assert "session" in final

    print("  ✓ Mock BioSim client working")


def test_mock_client_full_simulation():
    """Test running a mini simulation with mock client."""
    print("Testing Mock Client Simulation...")

    client = MockBioSimClient()

    # Start
    client.start_simulation(name="MiniTest")

    # Run one sol
    results = client.run_sol()
    assert len(results) == 24

    assert client.active_session.current_tick == 24
    assert client.active_session.current_sol == 1

    # Stop
    final = client.stop_simulation()
    assert final["session"]["current_tick"] == 24

    print("  ✓ Mock simulation run working")


def test_client_malfunction_injection():
    """Test malfunction injection methods."""
    print("Testing Malfunction Injection...")

    client = MockBioSimClient()
    client.start_simulation()

    # Test power failure
    result = client.inject_power_failure(severity=0.5, duration_ticks=12)
    assert "status" in result

    # Test water failure
    result = client.inject_water_failure(rsv_pod=1, duration_ticks=24)
    assert "status" in result

    # Test food production failure
    result = client.inject_food_production_failure(pod_number=1, severity=0.3)
    assert "status" in result

    # Check events recorded
    assert len(client.active_session.events_injected) == 3

    client.stop_simulation()

    print("  ✓ Malfunction injection working")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_full_output_pipeline():
    """Test full output pipeline: metrics → evaluation → XML."""
    print("Testing Full Output Pipeline...")

    # 1. Create metrics collector and record data
    collector = MetricsCollector()

    # Simulate a successful mission
    collector.mission.current_sol = 500
    collector.mission.earth_independence_achieved = 0.84

    collector.update_food_metrics(
        vegetables_kg=7500,  # 500 sols * 15 kg/day
        flour_kg=2750,       # 500 sols * 5.5 kg/day
        milk_l=4000,
        eggs=8500,
        calories_produced=19000000,  # 500 * 38000 kcal/day
        calories_from_earth=3750000,
    )

    collector.update_resource_metrics(
        power_generated=4000000,  # kWh over 500 sols
        power_consumed=3500000,
        water_extracted=700000,
        water_consumed=650000,
        water_recycled=617000,  # 95% recycling
        h2_remaining=400,
    )

    collector.update_crew_metrics(
        healthy=15,
        calories_received=3000,
        calories_required=3035,
    )

    collector.update_system_metrics(
        total_modules=20,
        operational=19,
        events_today=0,
        events_handled=50,
    )
    collector.system.total_events = 50
    collector.system.total_ticks = 12000
    collector.system.ticks_nominal = 11800

    # 2. Evaluate mission
    evaluator = MissionEvaluator(collector)
    results = evaluator.evaluate()

    assert results["overall_success"] or results["criteria"]["earth_independence"]["passed"]

    # 3. Generate XML config
    generator = BioSimXMLGenerator()
    xml_content = generator.generate_xml()

    assert len(xml_content) > 1000

    # 4. Generate report
    report = evaluator.generate_report()

    # Check report contains key info
    assert "MARS TO TABLE" in report
    assert "Earth Independence" in report

    print(f"  ✓ Full pipeline: EI={collector.mission.earth_independence_achieved * 100:.0f}%")


def test_metrics_with_mock_biosim():
    """Test metrics collection with mock BioSim client."""
    print("Testing Metrics with Mock BioSim...")

    # Set up systems
    collector = MetricsCollector()
    client = MockBioSimClient()

    # Callbacks to collect metrics
    def on_tick(result):
        collector.record_tick(result)

    client.on_tick_complete = on_tick

    # Run mini simulation
    client.start_simulation()

    for sol in range(3):  # 3 sols
        client.run_sol()
        collector.record_sol_end(sol + 1, client.get_state())

        # Update metrics from state
        state = client.get_state()
        collector.update_resource_metrics(
            power_generated=100,
            power_consumed=85,
        )

    client.stop_simulation()

    # Check history recorded
    assert len(collector.sol_history) == 3
    assert collector.mission.current_sol == 3

    print(f"  ✓ Metrics with BioSim: {len(collector.sol_history)} sols recorded")


def test_xml_generator_completeness():
    """Test that XML generator includes all required components."""
    print("Testing XML Generator Completeness...")

    generator = BioSimXMLGenerator()

    module_names = generator.get_module_list()
    store_names = generator.get_store_list()

    # Check required modules
    required_modules = [
        "SolarArray",
        "RSV_FuelCell_1",
        "RSV_FuelCell_2",
        "BiogasSOFC",
        "RSV_Extractor_1",
        "RSV_Extractor_2",
        "WaterRecycler",
        "H2Combuster",
        "FoodPOD_1", "FoodPOD_2", "FoodPOD_3", "FoodPOD_4", "FoodPOD_5",
        "FodderPOD",
        "GrainPOD",
        "LivestockPOD",
        "CrewConsumer",
        "HAB_POD",
        "HaberBoschReactor",
        "WasteProcessor",
    ]

    for module in required_modules:
        assert module in module_names, f"Missing required module: {module}"

    # Check required stores
    required_stores = [
        "PowerStore",
        "PotableWaterStore",
        "OxygenStore",
        "HydrogenStore",
        "FreshFoodStore",
        "ProcessedFoodStore",
        "LivestockFeedStore",
        "BiogasStore",
    ]

    for store in required_stores:
        assert store in store_names, f"Missing required store: {store}"

    print(f"  ✓ XML completeness: {len(module_names)} modules, {len(store_names)} stores")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all Sprint 6 tests."""
    print("=" * 60)
    print("SPRINT 6 TESTS: Output & Integration")
    print("=" * 60)
    print()

    # Metrics tests
    print("METRICS TESTS")
    print("-" * 40)
    test_food_production_metrics()
    test_resource_metrics()
    test_system_metrics()
    test_crew_metrics()
    test_mission_metrics()
    test_metrics_collector()
    test_metrics_export()
    test_mission_evaluator()
    print()

    # XML Generator tests
    print("XML GENERATOR TESTS")
    print("-" * 40)
    test_store_config()
    test_module_config()
    test_biosim_xml_generator()
    test_xml_save_and_load()
    test_xml_customization()
    print()

    # BioSim Client tests
    print("BIOSIM CLIENT TESTS")
    print("-" * 40)
    test_biosim_session()
    test_mock_biosim_client()
    test_mock_client_full_simulation()
    test_client_malfunction_injection()
    print()

    # Integration tests
    print("INTEGRATION TESTS")
    print("-" * 40)
    test_full_output_pipeline()
    test_metrics_with_mock_biosim()
    test_xml_generator_completeness()
    print()

    print("=" * 60)
    print("ALL SPRINT 6 TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
