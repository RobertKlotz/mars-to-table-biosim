"""
Mars to Table — Module Base Class
Base class for all system modules (producers/consumers).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import logging

from .store import Store, StoreManager, ResourceType
from ..config import Priority

logger = logging.getLogger(__name__)


class ModuleState(Enum):
    """Operating state of a module."""
    OFFLINE = auto()      # Not running
    STARTING = auto()     # Warming up
    NOMINAL = auto()      # Normal operation
    DEGRADED = auto()     # Reduced capacity
    EMERGENCY = auto()    # Emergency mode
    FAILED = auto()       # Malfunction
    MAINTENANCE = auto()  # Scheduled downtime


@dataclass
class ResourceFlow:
    """Defines a resource consumption or production rate."""
    resource_type: ResourceType
    rate_per_tick: float  # Units per tick at nominal operation
    store_name: str       # Which store to draw from / add to
    required: bool = True # If True, module fails if resource unavailable
    
    # Actual flow this tick (may differ from rate due to constraints)
    actual_flow: float = 0.0


@dataclass
class ModuleSpec:
    """Specification for a module."""
    name: str
    priority: Priority
    power_consumption_kw: float = 0.0
    
    # Resource flows
    consumes: List[ResourceFlow] = field(default_factory=list)
    produces: List[ResourceFlow] = field(default_factory=list)
    
    # Operational parameters
    startup_ticks: int = 1
    efficiency: float = 1.0  # 0.0 to 1.0


class Module(ABC):
    """
    Base class for all system modules.
    
    A module:
    - Consumes resources from stores
    - Produces resources to stores
    - Has operating states (nominal, degraded, failed, etc.)
    - Can respond to events and malfunctions
    """
    
    def __init__(self, spec: ModuleSpec, store_manager: StoreManager):
        self.spec = spec
        self.stores = store_manager
        
        self.state = ModuleState.OFFLINE
        self.efficiency = spec.efficiency
        self.startup_ticks_remaining = 0
        
        # Malfunction tracking
        self.has_malfunction = False
        self.malfunction_severity = 0.0  # 0.0 = none, 1.0 = total failure
        self.ticks_until_repair = 0
        
        # Statistics
        self.ticks_operational = 0
        self.ticks_failed = 0
        self.total_power_consumed = 0.0
    
    @property
    def name(self) -> str:
        return self.spec.name
    
    @property
    def priority(self) -> Priority:
        return self.spec.priority
    
    @property
    def is_operational(self) -> bool:
        return self.state in (ModuleState.NOMINAL, ModuleState.DEGRADED, ModuleState.EMERGENCY)
    
    @property
    def effective_efficiency(self) -> float:
        """Current efficiency accounting for state and malfunctions."""
        if not self.is_operational:
            return 0.0
        
        base = self.efficiency
        
        # Reduce for degraded state
        if self.state == ModuleState.DEGRADED:
            base *= 0.5
        elif self.state == ModuleState.EMERGENCY:
            base *= 0.25
        
        # Reduce for malfunction
        if self.has_malfunction:
            base *= (1.0 - self.malfunction_severity)
        
        return base
    
    def start(self):
        """Begin startup sequence."""
        if self.state == ModuleState.OFFLINE:
            self.state = ModuleState.STARTING
            self.startup_ticks_remaining = self.spec.startup_ticks
            logger.info(f"{self.name}: Starting up ({self.startup_ticks_remaining} ticks)")
    
    def stop(self):
        """Shut down the module."""
        self.state = ModuleState.OFFLINE
        logger.info(f"{self.name}: Shut down")
    
    def set_degraded(self, reason: str = ""):
        """Enter degraded mode."""
        if self.is_operational:
            self.state = ModuleState.DEGRADED
            logger.warning(f"{self.name}: Entering degraded mode - {reason}")
    
    def set_emergency(self, reason: str = ""):
        """Enter emergency mode."""
        if self.state != ModuleState.FAILED:
            self.state = ModuleState.EMERGENCY
            logger.warning(f"{self.name}: EMERGENCY mode - {reason}")
    
    def inject_malfunction(self, severity: float, duration_ticks: int):
        """
        Inject a malfunction.
        
        Args:
            severity: 0.0 (minor) to 1.0 (total failure)
            duration_ticks: How long until auto-repair (0 = permanent)
        """
        self.has_malfunction = True
        self.malfunction_severity = min(1.0, severity)
        self.ticks_until_repair = duration_ticks
        
        if severity >= 1.0:
            self.state = ModuleState.FAILED
            logger.error(f"{self.name}: FAILED (severity {severity})")
        else:
            self.set_degraded(f"malfunction severity {severity}")
    
    def clear_malfunction(self):
        """Clear malfunction and attempt to restore normal operation."""
        self.has_malfunction = False
        self.malfunction_severity = 0.0
        self.ticks_until_repair = 0
        
        if self.state == ModuleState.FAILED:
            self.state = ModuleState.OFFLINE
            logger.info(f"{self.name}: Malfunction cleared, restarting")
            self.start()
        elif self.state == ModuleState.DEGRADED:
            self.state = ModuleState.NOMINAL
            logger.info(f"{self.name}: Malfunction cleared, returning to nominal")
    
    def tick(self) -> Dict:
        """
        Execute one simulation tick.
        
        Returns:
            Dictionary of metrics from this tick.
        """
        metrics = {
            "name": self.name,
            "state": self.state.name,
            "efficiency": self.effective_efficiency,
        }
        
        # Handle startup
        if self.state == ModuleState.STARTING:
            self.startup_ticks_remaining -= 1
            if self.startup_ticks_remaining <= 0:
                self.state = ModuleState.NOMINAL
                logger.info(f"{self.name}: Startup complete, now NOMINAL")
            return metrics
        
        # Handle malfunction repair countdown
        if self.has_malfunction and self.ticks_until_repair > 0:
            self.ticks_until_repair -= 1
            if self.ticks_until_repair <= 0:
                self.clear_malfunction()
        
        # Skip if not operational
        if not self.is_operational:
            self.ticks_failed += 1
            return metrics
        
        self.ticks_operational += 1
        
        # Try to get power
        power_ok = self._consume_power()
        if not power_ok:
            self.set_degraded("insufficient power")
            metrics["power_shortfall"] = True
            return metrics
        
        # Consume inputs
        inputs_ok = self._consume_inputs()
        if not inputs_ok:
            self.set_degraded("insufficient inputs")
            metrics["input_shortfall"] = True
        
        # Produce outputs (scaled by efficiency)
        self._produce_outputs()
        
        # Module-specific processing
        module_metrics = self.process_tick()
        metrics.update(module_metrics)
        
        return metrics
    
    def _consume_power(self) -> bool:
        """
        Attempt to consume required power.
        
        Returns:
            True if sufficient power available.
        """
        power_needed = self.spec.power_consumption_kw * self.effective_efficiency
        if power_needed <= 0:
            return True
        
        power_store = self.stores.get("Power")
        if power_store is None:
            logger.warning(f"{self.name}: No power store found")
            return False
        
        actual = power_store.remove(power_needed, allow_reserve=False)
        self.total_power_consumed += actual
        
        if actual < power_needed * 0.9:  # Allow 10% tolerance
            return False
        return True
    
    def _consume_inputs(self) -> bool:
        """
        Consume all input resources.
        
        Returns:
            True if all required inputs satisfied.
        """
        all_satisfied = True
        
        for flow in self.spec.consumes:
            store = self.stores.get(flow.store_name)
            if store is None:
                logger.warning(f"{self.name}: Store '{flow.store_name}' not found")
                if flow.required:
                    all_satisfied = False
                continue
            
            needed = flow.rate_per_tick * self.effective_efficiency
            actual = store.remove(needed, allow_reserve=False)
            flow.actual_flow = actual
            
            if flow.required and actual < needed * 0.9:
                all_satisfied = False
        
        return all_satisfied
    
    def _produce_outputs(self):
        """Produce all output resources (scaled by efficiency)."""
        for flow in self.spec.produces:
            store = self.stores.get(flow.store_name)
            if store is None:
                logger.warning(f"{self.name}: Store '{flow.store_name}' not found")
                continue
            
            amount = flow.rate_per_tick * self.effective_efficiency
            actual = store.add(amount)
            flow.actual_flow = actual
    
    @abstractmethod
    def process_tick(self) -> Dict:
        """
        Module-specific processing for this tick.
        
        Override in subclasses to implement module logic.
        
        Returns:
            Dictionary of module-specific metrics.
        """
        pass
    
    def get_status(self) -> Dict:
        """Get current module status."""
        return {
            "name": self.name,
            "state": self.state.name,
            "priority": self.priority.name,
            "efficiency": self.effective_efficiency,
            "has_malfunction": self.has_malfunction,
            "malfunction_severity": self.malfunction_severity,
            "ticks_operational": self.ticks_operational,
            "ticks_failed": self.ticks_failed,
            "total_power_consumed": self.total_power_consumed,
        }


class ModuleManager:
    """
    Manages all modules in the simulation.
    """
    
    def __init__(self, store_manager: StoreManager):
        self.stores = store_manager
        self.modules: Dict[str, Module] = {}
        self._by_priority: Dict[Priority, List[Module]] = {p: [] for p in Priority}
    
    def add_module(self, module: Module):
        """Register a module."""
        self.modules[module.name] = module
        self._by_priority[module.priority].append(module)
    
    def get(self, name: str) -> Optional[Module]:
        """Get module by name."""
        return self.modules.get(name)
    
    def get_by_priority(self, priority: Priority) -> List[Module]:
        """Get all modules of a given priority."""
        return self._by_priority.get(priority, [])
    
    def start_all(self):
        """Start all modules."""
        for module in self.modules.values():
            module.start()
    
    def tick_all(self) -> List[Dict]:
        """
        Execute tick on all modules.
        
        Processes in priority order (CRITICAL first).
        
        Returns:
            List of metrics from each module.
        """
        metrics = []
        
        for priority in Priority:
            for module in self._by_priority[priority]:
                module_metrics = module.tick()
                metrics.append(module_metrics)
        
        return metrics
    
    def get_operational_modules(self) -> List[Module]:
        """Get all currently operational modules."""
        return [m for m in self.modules.values() if m.is_operational]
    
    def get_failed_modules(self) -> List[Module]:
        """Get all failed modules."""
        return [m for m in self.modules.values() if m.state == ModuleState.FAILED]
    
    def get_total_power_demand(self) -> float:
        """Get total power demand from all operational modules."""
        return sum(
            m.spec.power_consumption_kw * m.effective_efficiency 
            for m in self.modules.values() 
            if m.is_operational
        )
    
    def shed_load(self, power_available: float) -> List[str]:
        """
        Shed load to fit within available power.
        
        Sheds lowest priority modules first.
        
        Returns:
            List of module names that were shut down.
        """
        shed_modules = []
        current_demand = self.get_total_power_demand()
        
        # Work backwards through priorities (LOW first)
        for priority in reversed(list(Priority)):
            if current_demand <= power_available:
                break
            
            for module in self._by_priority[priority]:
                if not module.is_operational:
                    continue
                
                module_power = module.spec.power_consumption_kw * module.effective_efficiency
                module.stop()
                shed_modules.append(module.name)
                current_demand -= module_power
                logger.warning(f"Load shedding: {module.name} shut down (priority {priority.name})")
                
                if current_demand <= power_available:
                    break
        
        return shed_modules
    
    def get_all_status(self) -> Dict:
        """Get status of all modules."""
        return {name: module.get_status() for name, module in self.modules.items()}
