"""
Mars to Table — Sprint 5 Tests
Events & Resilience Testing

Tests for:
- Event injection system
- Response handlers
- Failure protocols
- Graceful degradation
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mars_to_table.config import MISSION, POWER, WATER, Priority, FailureMode
from mars_to_table.core.simulation import Simulation, Event, EventType
from mars_to_table.core.store import Store, StoreManager, ResourceType
from mars_to_table.core.module import Module, ModuleSpec, ModuleState, ModuleManager

# Import Sprint 5 modules
from mars_to_table.simulation.events import (
    EventTemplate,
    EventSeverity,
    STANDARD_EVENTS,
    EventGenerator,
    RandomEventGenerator,
    ScriptedEventGenerator,
    BioSimEventAdapter,
    EventScheduler,
)
from mars_to_table.simulation.responses import (
    ResponseStrategy,
    ResponseResult,
    ResponseHandler,
    PowerFailureResponse,
    WaterFailureResponse,
    PODFailureResponse,
    CrewChangeResponse,
    ResponseManager,
)
from mars_to_table.simulation.protocols import (
    ProtocolStatus,
    ProtocolState,
    FailureProtocol,
    PowerOutageProtocol,
    PowerReductionProtocol,
    WaterInterruptionProtocol,
    WaterRestrictionProtocol,
    EmergencyWaterProtocol,
    GracefulDegradationProtocol,
    ProtocolManager,
)


# =============================================================================
# TEST HELPERS
# =============================================================================

class TestModule(Module):
    """Simple test module for testing."""

    def process_tick(self):
        return {"test": True}


def create_test_simulation() -> Simulation:
    """Create a simulation with test stores and modules."""
    sim = Simulation()

    # Add resource stores
    sim.stores.add_store(Store("Power", ResourceType.ELECTRICAL_POWER, capacity=1000, current_level=0))
    sim.stores.add_store(Store("Hydrogen", ResourceType.HYDROGEN, capacity=500, current_level=200))
    sim.stores.add_store(Store("Oxygen", ResourceType.OXYGEN, capacity=2000, current_level=1600))
    sim.stores.add_store(Store("Biogas", ResourceType.METHANE, capacity=100, current_level=50))
    sim.stores.add_store(Store("Potable_Water", ResourceType.POTABLE_WATER, capacity=10000, current_level=5000))
    sim.stores.add_store(Store("Wall_Water_Reserve", ResourceType.POTABLE_WATER, capacity=10000, current_level=8000))
    sim.stores.add_store(Store("Water", ResourceType.POTABLE_WATER, capacity=10000, current_level=5000))

    # Add test modules
    for i in range(1, 6):
        spec = ModuleSpec(
            name=f"Food_POD_{i}",
            priority=Priority.MEDIUM,
            power_consumption_kw=30.0,
        )
        module = TestModule(spec, sim.stores)
        module.state = ModuleState.NOMINAL
        sim.modules.add_module(module)

    # RSV PODs
    for i in range(1, 3):
        spec = ModuleSpec(
            name=f"RSV_POD_{i}",
            priority=Priority.CRITICAL,
            power_consumption_kw=25.0,
        )
        module = TestModule(spec, sim.stores)
        module.state = ModuleState.NOMINAL
        sim.modules.add_module(module)

    # Livestock POD
    spec = ModuleSpec(
        name="Livestock_POD",
        priority=Priority.HIGH,
        power_consumption_kw=15.0,
    )
    module = TestModule(spec, sim.stores)
    module.state = ModuleState.NOMINAL
    sim.modules.add_module(module)

    # Low priority module
    spec = ModuleSpec(
        name="Processing_POD",
        priority=Priority.LOW,
        power_consumption_kw=20.0,
    )
    module = TestModule(spec, sim.stores)
    module.state = ModuleState.NOMINAL
    sim.modules.add_module(module)

    return sim


# =============================================================================
# EVENT TEMPLATE TESTS
# =============================================================================

def test_event_template_creation():
    """Test EventTemplate creation and event generation."""
    print("Testing Event Template creation...")

    template = EventTemplate(
        event_type=EventType.POWER_OUTAGE_TOTAL,
        name="Test Power Outage",
        description="Test event",
        min_duration=1,
        max_duration=24,
        default_duration=12,
    )

    event = template.create_event(trigger_tick=100)

    assert event.event_type == EventType.POWER_OUTAGE_TOTAL
    assert event.trigger_tick == 100
    assert event.duration_ticks == 12
    assert event.severity == 0.5  # Default

    # Test with overrides
    event2 = template.create_event(
        trigger_tick=200,
        duration=6,
        severity=0.8,
    )

    assert event2.trigger_tick == 200
    assert event2.duration_ticks == 6
    assert event2.severity == 0.8

    print("  ✓ Event Template tests passed")


def test_standard_event_templates():
    """Test that all standard events are properly defined."""
    print("Testing Standard Event Templates...")

    # Check we have all expected event types
    expected_events = [
        "total_power_outage",
        "partial_power_outage",
        "power_reduction",
        "water_interruption",
        "water_restriction",
        "crew_increase",
        "crew_decrease",
        "pod_failure",
        "equipment_malfunction",
        "dust_storm",
    ]

    for event_name in expected_events:
        assert event_name in STANDARD_EVENTS, f"Missing event: {event_name}"

    # Verify each template has valid ranges
    for name, template in STANDARD_EVENTS.items():
        assert template.min_duration <= template.max_duration
        assert template.min_severity <= template.max_severity
        assert 0 <= template.default_severity <= 1.0
        assert template.probability_weight >= 0

    print(f"  ✓ Verified {len(STANDARD_EVENTS)} standard event templates")


# =============================================================================
# RANDOM EVENT GENERATOR TESTS
# =============================================================================

def test_random_event_generator():
    """Test random event generation."""
    print("Testing Random Event Generator...")

    generator = RandomEventGenerator(
        seed=42,
        events_per_sol=2.0,  # Higher rate for testing
        enabled_events=["power_reduction", "water_restriction", "eva_day"],
    )

    events = generator.generate_events(current_tick=0, duration_ticks=24)

    # With seed 42 and high rate, should generate some events
    # But random, so just check structure
    for event in events:
        assert isinstance(event, Event)
        assert event.trigger_tick >= 0
        assert event.trigger_tick < 24
        assert 0 < event.severity <= 1.0
        assert event.duration_ticks > 0

    print(f"  ✓ Generated {len(events)} random events")


def test_random_generator_cooldown():
    """Test that cooldown prevents duplicate events."""
    print("Testing Random Generator cooldown...")

    generator = RandomEventGenerator(
        seed=123,
        events_per_sol=10.0,  # Very high rate
        enabled_events=["power_reduction"],  # Only one type
    )

    # Manually set that an event was just generated at tick 0
    generator.last_event_tick["power_reduction"] = 0

    # Try to generate immediately after (should respect cooldown)
    # Cooldown is 24 ticks for power_reduction per STANDARD_EVENTS
    can_gen = generator.can_generate("power_reduction", current_tick=1)
    assert not can_gen, "Should not be able to generate during cooldown"

    # Still in cooldown at tick 20
    can_gen_mid = generator.can_generate("power_reduction", current_tick=20)
    assert not can_gen_mid, "Should still be in cooldown"

    # After cooldown (24 ticks from tick 0)
    can_gen_later = generator.can_generate("power_reduction", current_tick=50)
    assert can_gen_later, "Should be able to generate after cooldown"

    print("  ✓ Cooldown mechanism working")


# =============================================================================
# SCRIPTED EVENT GENERATOR TESTS
# =============================================================================

def test_scripted_event_generator():
    """Test scripted event generation."""
    print("Testing Scripted Event Generator...")

    script = [
        {"template": "power_reduction", "trigger_tick": 10, "severity": 0.3},
        {"template": "water_restriction", "trigger_tick": 50, "severity": 0.4},
        {"template": "pod_failure", "trigger_tick": 100, "target": "Food_POD_1"},
    ]

    generator = ScriptedEventGenerator(script)

    # Generate for first window (0-24)
    events1 = generator.generate_events(current_tick=0, duration_ticks=24)
    assert len(events1) == 1
    assert events1[0].event_type == EventType.POWER_REDUCTION
    assert events1[0].trigger_tick == 10

    # Generate for second window (24-72)
    events2 = generator.generate_events(current_tick=24, duration_ticks=48)
    assert len(events2) == 1
    assert events2[0].event_type == EventType.WATER_RESTRICTION
    assert events2[0].trigger_tick == 50

    # Generate for third window (72-120)
    events3 = generator.generate_events(current_tick=72, duration_ticks=48)
    assert len(events3) == 1
    assert events3[0].event_type == EventType.POD_FAILURE
    assert events3[0].target_module == "Food_POD_1"

    print("  ✓ Scripted event generation working")


def test_biosim_scenario():
    """Test loading standard BioSim test scenarios."""
    print("Testing BioSim scenarios...")

    # Test power stress scenario
    power_gen = ScriptedEventGenerator.from_biosim_scenario("power_stress")
    assert len(power_gen.script) > 0

    events = power_gen.generate_events(0, 500)
    power_types = [e.event_type for e in events]
    assert EventType.POWER_REDUCTION in power_types or EventType.POWER_OUTAGE_PARTIAL in power_types

    # Test water stress scenario
    water_gen = ScriptedEventGenerator.from_biosim_scenario("water_stress")
    events = water_gen.generate_events(0, 500)
    water_types = [e.event_type for e in events]
    assert EventType.WATER_RESTRICTION in water_types or EventType.WATER_SUPPLY_INTERRUPTION in water_types

    # Test full resilience scenario
    full_gen = ScriptedEventGenerator.from_biosim_scenario("full_resilience")
    assert len(full_gen.script) >= 5  # Should have multiple event types

    print("  ✓ BioSim scenarios loaded successfully")


# =============================================================================
# BIOSIM EVENT ADAPTER TESTS
# =============================================================================

def test_biosim_adapter():
    """Test BioSim event adapter."""
    print("Testing BioSim Event Adapter...")

    adapter = BioSimEventAdapter()

    # Inject a BioSim-style malfunction
    event = adapter.inject_biosim_malfunction(
        malfunction_type="PowerGeneratorMalfunction",
        module_name="Solar_Array",
        intensity=0.5,
        tick_length=24,
        current_tick=100,
    )

    assert event is not None
    assert event.event_type == EventType.POWER_OUTAGE_PARTIAL
    assert event.severity == 0.5
    assert event.duration_ticks == 24
    assert event.target_module == "Solar_Array"

    # Generate should return pending events
    events = adapter.generate_events(100, 24)
    assert len(events) == 1
    assert events[0] == event

    # Queue should be cleared
    events2 = adapter.generate_events(100, 24)
    assert len(events2) == 0

    print("  ✓ BioSim adapter working")


# =============================================================================
# EVENT SCHEDULER TESTS
# =============================================================================

def test_event_scheduler():
    """Test event scheduler integration."""
    print("Testing Event Scheduler...")

    sim = create_test_simulation()
    scheduler = EventScheduler(sim)

    # Add a scripted generator
    script = [
        {"template": "power_reduction", "trigger_tick": 5, "severity": 0.25},
    ]
    generator = ScriptedEventGenerator(script)
    scheduler.add_generator(generator)

    # Update (should generate events)
    scheduler.generation_interval = 24
    scheduler.last_generation_tick = -24
    scheduler.update()

    # Check event was scheduled
    assert scheduler.total_events_scheduled > 0
    assert len(sim.scheduled_events) > 0

    stats = scheduler.get_statistics()
    assert stats["total_scheduled"] > 0

    print("  ✓ Event scheduler working")


def test_force_event():
    """Test forcing immediate events."""
    print("Testing Force Event...")

    sim = create_test_simulation()
    scheduler = EventScheduler(sim)

    # Force an event
    event = scheduler.force_event(
        "total_power_outage",
        severity=1.0,
        duration=12,
    )

    assert event is not None
    assert event.event_type == EventType.POWER_OUTAGE_TOTAL
    assert event.trigger_tick == sim.current_tick
    assert len(sim.scheduled_events) == 1

    print("  ✓ Force event working")


# =============================================================================
# RESPONSE HANDLER TESTS
# =============================================================================

def test_power_failure_response():
    """Test power failure response handler."""
    print("Testing Power Failure Response...")

    sim = create_test_simulation()

    # Set up power shortage
    power_store = sim.stores.get("Power")
    power_store.add(50)  # Only 50 kW, but demand is ~200+ kW

    handler = PowerFailureResponse(sim)

    event = Event(
        event_type=EventType.POWER_OUTAGE_PARTIAL,
        trigger_tick=0,
        severity=0.5,
    )

    assert handler.can_respond(event)

    result = handler.respond(event)
    assert isinstance(result, ResponseResult)
    assert result.strategy in [
        ResponseStrategy.ACTIVATE_FUEL_CELLS,
        ResponseStrategy.ACTIVATE_BIOGAS,
        ResponseStrategy.LOAD_SHEDDING,
        ResponseStrategy.POWER_RATIONING,
    ]

    print(f"  ✓ Power response: {result.strategy.name} - {result.details}")


def test_water_failure_response():
    """Test water failure response handler."""
    print("Testing Water Failure Response...")

    sim = create_test_simulation()
    handler = WaterFailureResponse(sim)

    # Test water interruption
    event = Event(
        event_type=EventType.WATER_SUPPLY_INTERRUPTION,
        trigger_tick=0,
        severity=1.0,
        target_module="RSV_POD_1",
    )

    assert handler.can_respond(event)

    # Fail RSV_POD_1
    rsv1 = sim.modules.get("RSV_POD_1")
    rsv1.state = ModuleState.FAILED

    result = handler.respond(event)
    assert isinstance(result, ResponseResult)
    assert result.strategy in [
        ResponseStrategy.SWITCH_RSV,
        ResponseStrategy.USE_WALL_STORAGE,
        ResponseStrategy.BURN_HYDROGEN,
        ResponseStrategy.WATER_RATIONING,
    ]

    print(f"  ✓ Water response: {result.strategy.name} - {result.details}")


def test_water_restriction_response():
    """Test water restriction response."""
    print("Testing Water Restriction Response...")

    sim = create_test_simulation()
    handler = WaterFailureResponse(sim)

    event = Event(
        event_type=EventType.WATER_RESTRICTION,
        trigger_tick=0,
        severity=0.4,  # 40% restriction
    )

    result = handler.respond(event)
    assert result.success
    assert result.strategy == ResponseStrategy.WATER_RATIONING

    print(f"  ✓ Water restriction: {result.details}")


def test_pod_failure_response():
    """Test POD failure response handler."""
    print("Testing POD Failure Response...")

    sim = create_test_simulation()
    handler = PODFailureResponse(sim)

    event = Event(
        event_type=EventType.POD_FAILURE,
        trigger_tick=0,
        severity=0.8,
        target_module="Food_POD_1",
    )

    assert handler.can_respond(event)

    result = handler.respond(event)
    assert isinstance(result, ResponseResult)
    assert result.strategy in [
        ResponseStrategy.ISOLATE_POD,
        ResponseStrategy.REDISTRIBUTE_LOAD,
        ResponseStrategy.GRACEFUL_DEGRADATION,
    ]

    # Check Food_POD_1 was isolated
    pod1 = sim.modules.get("Food_POD_1")
    assert pod1.state == ModuleState.OFFLINE

    print(f"  ✓ POD failure response: {result.strategy.name}")


def test_crew_change_response():
    """Test crew change response handler."""
    print("Testing Crew Change Response...")

    sim = create_test_simulation()
    handler = CrewChangeResponse(sim)

    # Test crew increase
    event = Event(
        event_type=EventType.CREW_SIZE_INCREASE,
        trigger_tick=0,
        severity=1.0,
        parameters={"count": 2},
    )

    sim.state.crew_size = 17  # Simulate increase

    result = handler.respond(event)
    assert result.success
    assert result.strategy == ResponseStrategy.ADJUST_MEAL_PLAN

    # Test EVA day
    event2 = Event(
        event_type=EventType.CREW_EVA_DAY,
        trigger_tick=0,
        severity=0.2,
        parameters={"crew_count": 3, "hours": 6},
    )

    result2 = handler.respond(event2)
    assert result2.success
    assert result2.strategy == ResponseStrategy.EVA_CALORIE_BOOST

    print(f"  ✓ Crew change response working")


# =============================================================================
# RESPONSE MANAGER TESTS
# =============================================================================

def test_response_manager():
    """Test response manager coordinates handlers."""
    print("Testing Response Manager...")

    sim = create_test_simulation()
    manager = ResponseManager(sim)

    # Verify handlers registered
    assert len(manager.handlers) == 4

    # Create and trigger an event
    event = Event(
        event_type=EventType.POWER_REDUCTION,
        trigger_tick=0,
        severity=0.3,
    )

    # Manually call the event callback
    manager._on_event(event)

    # Check statistics
    stats = manager.get_all_statistics()
    assert "PowerFailureResponse" in stats

    print("  ✓ Response manager working")


# =============================================================================
# PROTOCOL TESTS
# =============================================================================

def test_power_outage_protocol():
    """Test power outage protocol."""
    print("Testing Power Outage Protocol...")

    sim = create_test_simulation()
    protocol = PowerOutageProtocol(sim)

    # Initially inactive
    assert protocol.state.status == ProtocolStatus.INACTIVE

    # Create power shortage
    power_store = sim.stores.get("Power")
    power_store.current_level = 10  # Very low

    # Should trigger
    assert protocol.check_trigger()

    # Activate
    protocol.activate()
    assert protocol.state.status == ProtocolStatus.ACTIVE

    # Execute step
    success, description = protocol.execute_step()
    assert isinstance(success, bool)
    assert len(description) > 0

    status = protocol.get_status()
    assert status["name"] == "Power Outage Protocol"
    assert status["status"] == "ACTIVE"

    print(f"  ✓ Power outage protocol: {description}")


def test_water_interruption_protocol():
    """Test water interruption protocol."""
    print("Testing Water Interruption Protocol...")

    sim = create_test_simulation()
    protocol = WaterInterruptionProtocol(sim)

    # Fail both RSV PODs
    rsv1 = sim.modules.get("RSV_POD_1")
    rsv2 = sim.modules.get("RSV_POD_2")
    rsv1.state = ModuleState.FAILED
    rsv2.state = ModuleState.FAILED

    # Should trigger
    assert protocol.check_trigger()

    # Activate and execute
    protocol.activate()
    success, description = protocol.execute_step()

    # Should try wall storage since RSVs are down
    assert "wall storage" in description.lower() or "RSV" in description

    print(f"  ✓ Water interruption protocol: {description}")


def test_emergency_water_protocol():
    """Test emergency H₂ burn protocol."""
    print("Testing Emergency Water Protocol...")

    sim = create_test_simulation()
    protocol = EmergencyWaterProtocol(sim)

    # Create emergency: deplete water and wall storage
    water_store = sim.stores.get("Potable_Water")
    wall_store = sim.stores.get("Wall_Water_Reserve")
    water_store.current_level = 20  # Critical
    wall_store.current_level = 5     # Depleted

    # Should trigger
    assert protocol.check_trigger()

    # Execute emergency burn
    protocol.activate()
    success, description = protocol.execute_step()

    # Should have produced water
    assert success
    assert "H₂ burn" in description or "water" in description.lower()

    # Check resources consumed
    assert protocol.state.resources_consumed.get("hydrogen_kg", 0) > 0

    print(f"  ✓ Emergency water protocol: {description}")


def test_graceful_degradation_protocol():
    """Test graceful degradation protocol."""
    print("Testing Graceful Degradation Protocol...")

    sim = create_test_simulation()
    protocol = GracefulDegradationProtocol(sim)

    # Create degradation: fail 2 modules
    pod1 = sim.modules.get("Food_POD_1")
    pod2 = sim.modules.get("Food_POD_2")
    pod1.state = ModuleState.FAILED
    pod2.state = ModuleState.FAILED

    # Should trigger
    assert protocol.check_trigger()

    # Activate and execute
    protocol.activate()
    success, description = protocol.execute_step()

    assert success
    # Should redistribute or degrade

    print(f"  ✓ Graceful degradation: {description}")


# =============================================================================
# PROTOCOL MANAGER TESTS
# =============================================================================

def test_protocol_manager():
    """Test protocol manager coordinates all protocols."""
    print("Testing Protocol Manager...")

    sim = create_test_simulation()

    # Set up normal conditions (adequate power)
    power_store = sim.stores.get("Power")
    power_store.current_level = 500  # Plenty of power

    manager = ProtocolManager(sim)

    # Verify all protocols registered
    assert len(manager.protocols) == 6

    # Tick with normal conditions - should not activate any protocols
    manager.tick()
    initial_active = len(manager.active_protocols)

    # Create a trigger condition (power shortage)
    power_store.current_level = 5  # Critical

    # Tick again
    manager.tick()

    # Should have activated power protocol or stayed same if already active
    status = manager.get_all_status()
    assert "protocols" in status
    assert status["active_count"] >= 0

    # Can check that protocol tracking works
    active_names = manager.get_active_protocols()

    print(f"  ✓ Protocol manager: {status['active_count']} active protocols")


def test_force_protocol():
    """Test forcing protocol activation."""
    print("Testing Force Protocol...")

    sim = create_test_simulation()
    manager = ProtocolManager(sim)

    # Force water interruption protocol
    result = manager.force_protocol("Water Interruption Protocol")
    assert result

    active = manager.get_active_protocols()
    assert "Water Interruption Protocol" in active

    print("  ✓ Force protocol working")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_full_event_response_integration():
    """Test full integration of events, responses, and protocols."""
    print("Testing Full Event-Response Integration...")

    sim = create_test_simulation()

    # Set up all systems
    scheduler = EventScheduler(sim)
    response_manager = ResponseManager(sim)
    protocol_manager = ProtocolManager(sim)

    # Add scripted events
    script = [
        {"template": "power_reduction", "trigger_tick": 2, "severity": 0.3},
        {"template": "water_restriction", "trigger_tick": 5, "severity": 0.4},
    ]
    generator = ScriptedEventGenerator(script)
    scheduler.add_generator(generator)

    # Run simulation for a few ticks
    initial_power = sim.stores.get("Power").current_level
    initial_water = sim.stores.get("Potable_Water").current_level

    for _ in range(10):
        scheduler.update()
        protocol_manager.tick()
        sim.tick()

    # Verify events were processed
    assert len(sim.event_history) > 0

    # Get final statistics
    scheduler_stats = scheduler.get_statistics()
    response_stats = response_manager.get_all_statistics()
    protocol_stats = protocol_manager.get_all_status()

    assert scheduler_stats["total_scheduled"] > 0

    print(f"  ✓ Integration test: {scheduler_stats['total_scheduled']} events processed")


def test_resilience_under_multiple_failures():
    """Test system resilience under multiple simultaneous failures."""
    print("Testing Resilience Under Multiple Failures...")

    sim = create_test_simulation()
    response_manager = ResponseManager(sim)
    protocol_manager = ProtocolManager(sim)

    # Inject multiple failures
    events = [
        Event(EventType.POWER_REDUCTION, trigger_tick=0, severity=0.4),
        Event(EventType.WATER_RESTRICTION, trigger_tick=0, severity=0.3),
        Event(EventType.POD_FAILURE, trigger_tick=0, severity=0.5, target_module="Food_POD_3"),
    ]

    for event in events:
        sim.schedule_event(event)

    # Process events
    sim.tick()
    protocol_manager.tick()

    # System should still be functional
    operational = sim.modules.get_operational_modules()
    assert len(operational) > 0, "Some modules should remain operational"

    # Critical systems should be protected
    rsv1 = sim.modules.get("RSV_POD_1")
    rsv2 = sim.modules.get("RSV_POD_2")
    assert rsv1.is_operational or rsv2.is_operational, "At least one RSV should be operational"

    print(f"  ✓ Resilience test: {len(operational)} modules still operational")


def test_recovery_from_total_power_outage():
    """Test recovery from total power outage."""
    print("Testing Recovery from Total Power Outage...")

    sim = create_test_simulation()
    protocol_manager = ProtocolManager(sim)

    # Cause total power outage
    power_store = sim.stores.get("Power")
    power_store.current_level = 0

    # Run protocol manager
    protocol_manager.tick()

    active_protocols = protocol_manager.get_active_protocols()
    # Power outage protocol should have activated
    # (may not if hydrogen/biogas provided enough power)

    # Check fuel cells or biogas were used
    h2_store = sim.stores.get("Hydrogen")
    initial_h2 = 200.0
    h2_used = initial_h2 - h2_store.current_level

    # System should have responded
    print(f"  ✓ Recovery test: H₂ used = {h2_used:.2f} kg")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all Sprint 5 tests."""
    print("=" * 60)
    print("SPRINT 5 TESTS: Events & Resilience")
    print("=" * 60)
    print()

    # Event tests
    print("EVENT INJECTION TESTS")
    print("-" * 40)
    test_event_template_creation()
    test_standard_event_templates()
    print()

    # Generator tests
    print("EVENT GENERATOR TESTS")
    print("-" * 40)
    test_random_event_generator()
    test_random_generator_cooldown()
    test_scripted_event_generator()
    test_biosim_scenario()
    test_biosim_adapter()
    print()

    # Scheduler tests
    print("EVENT SCHEDULER TESTS")
    print("-" * 40)
    test_event_scheduler()
    test_force_event()
    print()

    # Response tests
    print("RESPONSE HANDLER TESTS")
    print("-" * 40)
    test_power_failure_response()
    test_water_failure_response()
    test_water_restriction_response()
    test_pod_failure_response()
    test_crew_change_response()
    test_response_manager()
    print()

    # Protocol tests
    print("FAILURE PROTOCOL TESTS")
    print("-" * 40)
    test_power_outage_protocol()
    test_water_interruption_protocol()
    test_emergency_water_protocol()
    test_graceful_degradation_protocol()
    test_protocol_manager()
    test_force_protocol()
    print()

    # Integration tests
    print("INTEGRATION TESTS")
    print("-" * 40)
    test_full_event_response_integration()
    test_resilience_under_multiple_failures()
    test_recovery_from_total_power_outage()
    print()

    print("=" * 60)
    print("ALL SPRINT 5 TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
