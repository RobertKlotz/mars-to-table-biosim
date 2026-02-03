"""
Test: Core Framework
Verifies Store, Module, and Simulation basics work correctly.
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mars_to_table.core.store import Store, StoreManager, ResourceType
from mars_to_table.core.module import Module, ModuleManager, ModuleSpec, ResourceFlow
from mars_to_table.core.simulation import Simulation, Event, EventType
from mars_to_table.config import MISSION, Priority


def test_store_basic():
    """Test basic store operations."""
    print("Testing Store...")
    
    store = Store(
        name="Test_Water",
        resource_type=ResourceType.POTABLE_WATER,
        capacity=1000.0,
        current_level=500.0,
        reserve_level=100.0
    )
    
    # Test properties
    assert store.available == 400.0, f"Expected 400, got {store.available}"
    assert store.free_capacity == 500.0, f"Expected 500, got {store.free_capacity}"
    assert store.fill_fraction == 0.5, f"Expected 0.5, got {store.fill_fraction}"
    
    # Test add
    added = store.add(200.0)
    assert added == 200.0, f"Expected 200, got {added}"
    assert store.current_level == 700.0, f"Expected 700, got {store.current_level}"
    
    # Test remove
    removed = store.remove(100.0)
    assert removed == 100.0, f"Expected 100, got {removed}"
    assert store.current_level == 600.0, f"Expected 600, got {store.current_level}"
    
    # Test overflow
    store.current_level = 950.0
    added = store.add(100.0)
    assert added == 50.0, f"Expected 50, got {added}"
    assert store.overflow_this_tick == 50.0, f"Expected overflow 50, got {store.overflow_this_tick}"
    
    # Test shortfall
    store.current_level = 150.0  # 50 available above reserve
    removed = store.remove(100.0, allow_reserve=False)
    assert removed == 50.0, f"Expected 50, got {removed}"
    assert store.shortfall_this_tick == 50.0, f"Expected shortfall 50, got {store.shortfall_this_tick}"
    
    print("  ✓ Store tests passed")


def test_store_manager():
    """Test store manager operations."""
    print("Testing StoreManager...")
    
    manager = StoreManager()
    
    water1 = Store("Water_Tank_1", ResourceType.POTABLE_WATER, 1000.0, 500.0)
    water2 = Store("Water_Tank_2", ResourceType.POTABLE_WATER, 1000.0, 300.0)
    power = Store("Power", ResourceType.ELECTRICAL_POWER, 500.0, 400.0)
    
    manager.add_store(water1)
    manager.add_store(water2)
    manager.add_store(power)
    
    # Test retrieval
    assert manager.get("Water_Tank_1") == water1
    assert manager.get("Power") == power
    
    # Test by type
    water_stores = manager.get_by_type(ResourceType.POTABLE_WATER)
    assert len(water_stores) == 2
    
    # Test totals
    total_water = manager.total_level(ResourceType.POTABLE_WATER)
    assert total_water == 800.0, f"Expected 800, got {total_water}"
    
    print("  ✓ StoreManager tests passed")


class TestModule(Module):
    """Simple test module implementation."""
    
    def process_tick(self):
        return {"test_output": 42}


def test_module_basic():
    """Test basic module operations."""
    print("Testing Module...")
    
    manager = StoreManager()
    power = Store("Power", ResourceType.ELECTRICAL_POWER, 1000.0, 500.0)
    water_in = Store("Water_In", ResourceType.POTABLE_WATER, 1000.0, 500.0)
    water_out = Store("Water_Out", ResourceType.POTABLE_WATER, 1000.0, 0.0)
    
    manager.add_store(power)
    manager.add_store(water_in)
    manager.add_store(water_out)
    
    spec = ModuleSpec(
        name="Test_Module",
        priority=Priority.MEDIUM,
        power_consumption_kw=10.0,
        consumes=[
            ResourceFlow(ResourceType.POTABLE_WATER, 5.0, "Water_In", required=True)
        ],
        produces=[
            ResourceFlow(ResourceType.POTABLE_WATER, 4.0, "Water_Out")  # Some loss
        ],
        efficiency=1.0
    )
    
    module = TestModule(spec, manager)
    
    # Test startup
    assert module.state.name == "OFFLINE"
    module.start()
    assert module.state.name == "STARTING"
    
    # Tick through startup
    module.tick()
    assert module.state.name == "NOMINAL"
    
    # Test operation
    initial_water_in = water_in.current_level
    initial_water_out = water_out.current_level
    initial_power = power.current_level
    
    metrics = module.tick()
    
    assert water_in.current_level < initial_water_in, "Should have consumed water"
    assert water_out.current_level > initial_water_out, "Should have produced water"
    assert power.current_level < initial_power, "Should have consumed power"
    assert metrics["test_output"] == 42
    
    print("  ✓ Module tests passed")


def test_simulation_basic():
    """Test basic simulation operations."""
    print("Testing Simulation...")
    
    sim = Simulation()
    
    # Add some stores
    sim.stores.add_store(Store("Power", ResourceType.ELECTRICAL_POWER, 10000.0, 5000.0))
    sim.stores.add_store(Store("Oxygen", ResourceType.OXYGEN, 10000.0, 8000.0))
    sim.stores.add_store(Store("Potable_Water", ResourceType.POTABLE_WATER, 10000.0, 8000.0))
    
    # Check initial state
    assert sim.current_tick == 0
    assert sim.current_sol == 0
    assert not sim.state.is_ended
    
    # Run a few ticks
    for _ in range(5):
        sim.tick()
    
    assert sim.current_tick == 5
    
    # Test event scheduling
    event = Event(
        event_type=EventType.POWER_REDUCTION,
        trigger_tick=10,
        duration_ticks=5,
        severity=0.5
    )
    sim.schedule_event(event)
    
    # Run to event
    while sim.current_tick < 12:
        sim.tick()
    
    assert len(sim.active_events) > 0, "Event should be active"
    
    # Run past event
    while sim.current_tick < 20:
        sim.tick()
    
    assert len(sim.active_events) == 0, "Event should have ended"
    
    print("  ✓ Simulation tests passed")


def test_simulation_sol_tracking():
    """Test sol (day) tracking."""
    print("Testing Sol Tracking...")
    
    sim = Simulation()
    sim.stores.add_store(Store("Power", ResourceType.ELECTRICAL_POWER, 10000.0, 5000.0))
    sim.stores.add_store(Store("Oxygen", ResourceType.OXYGEN, 10000.0, 8000.0))
    sim.stores.add_store(Store("Potable_Water", ResourceType.POTABLE_WATER, 10000.0, 8000.0))
    
    # Run one full sol (24 ticks)
    sim.run(24)
    
    assert sim.current_tick == 24
    assert sim.current_sol == 1, f"Expected sol 1, got {sim.current_sol}"
    assert len(sim.sol_summaries) == 1, "Should have 1 sol summary"
    
    # Run another sol
    sim.run(24)
    
    assert sim.current_tick == 48
    assert sim.current_sol == 2
    
    print("  ✓ Sol Tracking tests passed")


def run_all_tests():
    """Run all framework tests."""
    print("\n" + "="*50)
    print("MARS TO TABLE — Core Framework Tests")
    print("="*50 + "\n")
    
    try:
        test_store_basic()
        test_store_manager()
        test_module_basic()
        test_simulation_basic()
        test_simulation_sol_tracking()
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✓")
        print("="*50 + "\n")
        return True
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
