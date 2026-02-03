"""
Mars to Table — Simulation Engine
Main simulation loop, event handling, and metrics collection.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum, auto
import logging
import json
from datetime import datetime

from .store import Store, StoreManager, ResourceType
from .module import Module, ModuleManager, ModuleState
from ..config import MissionConfig, MISSION

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can occur during simulation."""
    # Power events
    POWER_OUTAGE_TOTAL = auto()
    POWER_OUTAGE_PARTIAL = auto()
    POWER_REDUCTION = auto()
    
    # Water events
    WATER_SUPPLY_INTERRUPTION = auto()
    WATER_RESTRICTION = auto()
    WATER_CONTAMINATION = auto()
    
    # Crew events
    CREW_SIZE_INCREASE = auto()
    CREW_SIZE_DECREASE = auto()
    CREW_METABOLIC_INCREASE = auto()
    CREW_EVA_DAY = auto()
    
    # Equipment events
    POD_FAILURE = auto()
    EQUIPMENT_MALFUNCTION = auto()
    SENSOR_FAILURE = auto()
    
    # Environmental events
    DUST_STORM = auto()  # Reduces solar
    RADIATION_EVENT = auto()


@dataclass
class Event:
    """A scheduled or triggered event."""
    event_type: EventType
    trigger_tick: int
    duration_ticks: int = 1
    severity: float = 1.0  # 0.0 to 1.0
    target_module: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state
    active: bool = False
    ticks_remaining: int = 0


@dataclass
class SimulationState:
    """Current state of the simulation."""
    current_tick: int = 0
    current_sol: int = 0
    current_hour: int = 0
    
    is_running: bool = False
    is_paused: bool = False
    is_ended: bool = False
    end_reason: str = ""
    
    # Crew tracking
    crew_size: int = 15
    crew_alive: int = 15
    
    # Mission success tracking
    total_calories_produced: float = 0.0
    total_calories_consumed: float = 0.0
    earth_independence_achieved: float = 0.0


class Simulation:
    """
    Main simulation engine.
    
    Manages:
    - Tick-based simulation loop
    - Event scheduling and handling
    - Metrics collection
    - State management
    """
    
    def __init__(self, config: MissionConfig = MISSION):
        self.config = config
        
        # Core managers
        self.stores = StoreManager()
        self.modules = ModuleManager(self.stores)
        
        # State
        self.state = SimulationState()
        self.state.crew_size = config.crew_size
        self.state.crew_alive = config.crew_size
        
        # Events
        self.scheduled_events: List[Event] = []
        self.active_events: List[Event] = []
        self.event_history: List[Dict] = []
        
        # Metrics collection
        self.tick_metrics: List[Dict] = []
        self.sol_summaries: List[Dict] = []
        
        # Callbacks
        self.on_tick_complete: Optional[Callable] = None
        self.on_sol_complete: Optional[Callable] = None
        self.on_event_triggered: Optional[Callable] = None
        self.on_simulation_end: Optional[Callable] = None
        
        logger.info("Simulation initialized")
    
    @property
    def current_tick(self) -> int:
        return self.state.current_tick
    
    @property
    def current_sol(self) -> int:
        return self.state.current_sol
    
    @property
    def current_hour(self) -> int:
        return self.state.current_hour
    
    def schedule_event(self, event: Event):
        """Schedule an event for future execution."""
        self.scheduled_events.append(event)
        self.scheduled_events.sort(key=lambda e: e.trigger_tick)
        logger.info(f"Scheduled {event.event_type.name} at tick {event.trigger_tick}")
    
    def _trigger_event(self, event: Event):
        """Activate an event."""
        event.active = True
        event.ticks_remaining = event.duration_ticks
        self.active_events.append(event)
        
        self.event_history.append({
            "tick": self.current_tick,
            "sol": self.current_sol,
            "event_type": event.event_type.name,
            "severity": event.severity,
            "duration": event.duration_ticks,
            "target": event.target_module,
        })
        
        logger.warning(f"EVENT TRIGGERED: {event.event_type.name} (severity {event.severity})")
        
        # Handle event effects
        self._apply_event_effects(event)
        
        if self.on_event_triggered:
            self.on_event_triggered(event)
    
    def _apply_event_effects(self, event: Event):
        """Apply the effects of an event to the simulation."""
        
        if event.event_type == EventType.POWER_OUTAGE_TOTAL:
            # Zero out power generation
            power_store = self.stores.get("Power")
            if power_store:
                power_store.current_level = 0
            logger.error("TOTAL POWER OUTAGE")
        
        elif event.event_type == EventType.POWER_REDUCTION:
            # Reduce available power by severity percentage
            power_store = self.stores.get("Power")
            if power_store:
                power_store.current_level *= (1 - event.severity)
            logger.warning(f"Power reduced by {event.severity * 100:.0f}%")
        
        elif event.event_type == EventType.WATER_SUPPLY_INTERRUPTION:
            # Stop water extraction
            for module in self.modules.modules.values():
                if "RSV" in module.name:
                    module.set_degraded("water supply interrupted")
        
        elif event.event_type == EventType.WATER_RESTRICTION:
            # Reduce water consumption allowed
            restriction_factor = 1 - event.severity
            event.parameters["restriction_factor"] = restriction_factor
            logger.warning(f"Water restricted to {restriction_factor * 100:.0f}% of normal")
        
        elif event.event_type == EventType.POD_FAILURE:
            if event.target_module:
                module = self.modules.get(event.target_module)
                if module:
                    module.inject_malfunction(event.severity, event.duration_ticks)
        
        elif event.event_type == EventType.EQUIPMENT_MALFUNCTION:
            if event.target_module:
                module = self.modules.get(event.target_module)
                if module:
                    module.inject_malfunction(event.severity, event.duration_ticks)
        
        elif event.event_type == EventType.CREW_SIZE_DECREASE:
            decrease = int(event.parameters.get("count", 1))
            self.state.crew_size = max(1, self.state.crew_size - decrease)
            self.state.crew_alive = min(self.state.crew_alive, self.state.crew_size)
            logger.warning(f"Crew size decreased to {self.state.crew_size}")
        
        elif event.event_type == EventType.CREW_SIZE_INCREASE:
            increase = int(event.parameters.get("count", 1))
            self.state.crew_size += increase
            self.state.crew_alive = self.state.crew_size
            logger.info(f"Crew size increased to {self.state.crew_size}")
        
        elif event.event_type == EventType.DUST_STORM:
            # Reduce solar generation
            logger.warning(f"Dust storm: solar reduced by {event.severity * 100:.0f}%")
    
    def _deactivate_event(self, event: Event):
        """Deactivate an event when its duration expires."""
        event.active = False
        
        logger.info(f"Event ended: {event.event_type.name}")
        
        # Reverse effects where applicable
        if event.event_type in (EventType.WATER_RESTRICTION,):
            event.parameters.pop("restriction_factor", None)
    
    def _process_events(self):
        """Process scheduled and active events for current tick."""
        
        # Trigger scheduled events
        while (self.scheduled_events and 
               self.scheduled_events[0].trigger_tick <= self.current_tick):
            event = self.scheduled_events.pop(0)
            self._trigger_event(event)
        
        # Update active events
        completed_events = []
        for event in self.active_events:
            event.ticks_remaining -= 1
            if event.ticks_remaining <= 0:
                completed_events.append(event)
        
        # Deactivate completed events
        for event in completed_events:
            self._deactivate_event(event)
            self.active_events.remove(event)
    
    def tick(self) -> Dict:
        """
        Execute one simulation tick.
        
        Returns:
            Dictionary of metrics from this tick.
        """
        if self.state.is_ended:
            return {"error": "Simulation has ended"}
        
        # Reset per-tick counters
        self.stores.reset_all_tick_counters()
        
        # Process events
        self._process_events()
        
        # Execute all modules
        module_metrics = self.modules.tick_all()
        
        # Collect tick metrics
        tick_data = {
            "tick": self.current_tick,
            "sol": self.current_sol,
            "hour": self.current_hour,
            "stores": self.stores.get_all_status(),
            "modules": module_metrics,
            "active_events": [e.event_type.name for e in self.active_events],
            "crew_size": self.state.crew_size,
        }
        
        self.tick_metrics.append(tick_data)
        
        # Check for critical failures
        self._check_failure_conditions()
        
        # Advance time
        self.state.current_tick += 1
        self.state.current_hour = self.current_tick % self.config.ticks_per_sol
        
        # Check for sol boundary
        if self.state.current_hour == 0 and self.current_tick > 0:
            self.state.current_sol = self.current_tick // self.config.ticks_per_sol
            self._on_sol_complete()
        
        # Check for mission end
        if self.current_tick >= self.config.total_ticks:
            self._end_simulation("Mission duration complete")
        
        if self.on_tick_complete:
            self.on_tick_complete(tick_data)
        
        return tick_data
    
    def _on_sol_complete(self):
        """Called at the end of each sol."""
        sol_summary = {
            "sol": self.current_sol,
            "stores": {name: s.current_level for name, s in self.stores.stores.items()},
            "operational_modules": len(self.modules.get_operational_modules()),
            "failed_modules": len(self.modules.get_failed_modules()),
            "active_events": len(self.active_events),
            "crew_size": self.state.crew_size,
        }
        
        self.sol_summaries.append(sol_summary)
        
        if self.on_sol_complete:
            self.on_sol_complete(sol_summary)
        
        # Log progress every 10 sols
        if self.current_sol % 10 == 0:
            logger.info(f"Sol {self.current_sol} complete")
    
    def _check_failure_conditions(self):
        """Check for conditions that end the simulation."""
        
        # Check for crew death (no food for extended period)
        food_stores = self.stores.get_by_type(ResourceType.BIOMASS_EDIBLE)
        total_food = sum(s.current_level for s in food_stores)
        
        # Check oxygen
        o2_store = self.stores.get("Oxygen")
        if o2_store and o2_store.is_empty:
            self.state.crew_alive = 0
            self._end_simulation("Crew death: oxygen depleted")
            return
        
        # Check water (critical after 3 days without)
        water_store = self.stores.get("Potable_Water")
        if water_store and water_store.total_shortfall > self.state.crew_size * 3 * 3:  # 3L/person/day * 3 days
            self.state.crew_alive = 0
            self._end_simulation("Crew death: water depleted")
            return
    
    def _end_simulation(self, reason: str):
        """End the simulation."""
        self.state.is_running = False
        self.state.is_ended = True
        self.state.end_reason = reason
        
        logger.info(f"Simulation ended: {reason}")
        
        if self.on_simulation_end:
            self.on_simulation_end(self.get_final_report())
    
    def run(self, ticks: Optional[int] = None):
        """
        Run the simulation for specified ticks (or until end).
        
        Args:
            ticks: Number of ticks to run, or None for full mission.
        """
        self.state.is_running = True
        target_ticks = ticks or self.config.total_ticks
        
        for _ in range(target_ticks):
            if self.state.is_ended or self.state.is_paused:
                break
            self.tick()
        
        self.state.is_running = False
    
    def run_sol(self):
        """Run the simulation for one complete sol (24 ticks)."""
        self.run(self.config.ticks_per_sol)
    
    def pause(self):
        """Pause the simulation."""
        self.state.is_paused = True
    
    def resume(self):
        """Resume a paused simulation."""
        self.state.is_paused = False
    
    def get_status(self) -> Dict:
        """Get current simulation status."""
        return {
            "tick": self.current_tick,
            "sol": self.current_sol,
            "hour": self.current_hour,
            "is_running": self.state.is_running,
            "is_ended": self.state.is_ended,
            "end_reason": self.state.end_reason,
            "crew_size": self.state.crew_size,
            "crew_alive": self.state.crew_alive,
            "active_events": len(self.active_events),
            "operational_modules": len(self.modules.get_operational_modules()),
            "failed_modules": len(self.modules.get_failed_modules()),
        }
    
    def get_final_report(self) -> Dict:
        """Generate final mission report."""
        return {
            "mission_summary": {
                "total_sols": self.current_sol,
                "total_ticks": self.current_tick,
                "end_reason": self.state.end_reason,
                "crew_survived": self.state.crew_alive,
                "mission_success": self.state.crew_alive > 0 and self.current_sol >= self.config.total_sols,
            },
            "resource_totals": {
                name: {
                    "final_level": store.current_level,
                    "total_inflow": store.total_inflow,
                    "total_outflow": store.total_outflow,
                    "total_overflow": store.total_overflow,
                    "total_shortfall": store.total_shortfall,
                }
                for name, store in self.stores.stores.items()
            },
            "module_stats": self.modules.get_all_status(),
            "event_history": self.event_history,
            "sol_summaries": self.sol_summaries[-10:],  # Last 10 sols
        }
    
    def export_log(self, filepath: str):
        """Export simulation log to JSON file."""
        report = self.get_final_report()
        report["tick_metrics"] = self.tick_metrics  # Full tick data
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Simulation log exported to {filepath}")
