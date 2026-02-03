"""
Mars to Table — Failure Protocols
Step-by-step procedures for handling specific failure scenarios.

These protocols implement the resilience strategies from Section 4:
- Power outage: RSV fuel cells → Biogas SOFC → Priority load shedding
- Water shortage: Dual RSV → Wall storage → H₂ burn
- Graceful degradation: N+1 redundancy, priority-based operations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum, auto
import logging

from ..core.simulation import Simulation, Event, EventType
from ..core.module import Module, ModuleState, ModuleManager
from ..core.store import Store, StoreManager, ResourceType
from ..config import MISSION, POWER, WATER, Priority

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOL STATUS
# =============================================================================

class ProtocolStatus(Enum):
    """Status of a failure protocol."""
    INACTIVE = auto()       # Protocol not triggered
    MONITORING = auto()     # Watching for threshold breach
    ACTIVE = auto()         # Protocol in effect
    ESCALATING = auto()     # Moving to more severe response
    RECOVERING = auto()     # Returning to normal
    COMPLETED = auto()      # Protocol finished


@dataclass
class ProtocolState:
    """Current state of a protocol execution."""
    status: ProtocolStatus = ProtocolStatus.INACTIVE
    trigger_tick: int = 0
    current_step: int = 0
    escalation_level: int = 0
    resources_consumed: Dict[str, float] = field(default_factory=dict)
    modules_affected: List[str] = field(default_factory=list)
    effectiveness: float = 1.0


# =============================================================================
# FAILURE PROTOCOL BASE CLASS
# =============================================================================

class FailureProtocol(ABC):
    """
    Base class for failure response protocols.

    A protocol is a multi-step procedure that responds to and recovers
    from specific failure conditions.
    """

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.stores = simulation.stores
        self.modules = simulation.modules
        self.state = ProtocolState()
        self.execution_log: List[Dict] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Protocol name."""
        pass

    @property
    @abstractmethod
    def trigger_conditions(self) -> Dict[str, Any]:
        """Conditions that trigger this protocol."""
        pass

    @abstractmethod
    def check_trigger(self) -> bool:
        """Check if protocol should be triggered."""
        pass

    @abstractmethod
    def execute_step(self) -> Tuple[bool, str]:
        """
        Execute current protocol step.

        Returns:
            (success, description) tuple
        """
        pass

    @abstractmethod
    def check_recovery(self) -> bool:
        """Check if conditions have returned to normal."""
        pass

    def activate(self):
        """Activate the protocol."""
        self.state.status = ProtocolStatus.ACTIVE
        self.state.trigger_tick = self.simulation.current_tick
        self.state.current_step = 0
        self.state.escalation_level = 0

        logger.warning(f"PROTOCOL ACTIVATED: {self.name}")
        self._log_event("activated", f"Protocol triggered at tick {self.state.trigger_tick}")

    def deactivate(self):
        """Deactivate the protocol."""
        self.state.status = ProtocolStatus.COMPLETED

        logger.info(f"PROTOCOL COMPLETED: {self.name}")
        self._log_event("completed", "Protocol execution finished")

    def escalate(self):
        """Move to next escalation level."""
        self.state.escalation_level += 1
        self.state.status = ProtocolStatus.ESCALATING

        logger.warning(f"PROTOCOL ESCALATING: {self.name} to level {self.state.escalation_level}")
        self._log_event("escalated", f"Escalated to level {self.state.escalation_level}")

    def tick(self):
        """Execute protocol logic for this tick."""
        if self.state.status == ProtocolStatus.INACTIVE:
            if self.check_trigger():
                self.activate()

        elif self.state.status in (ProtocolStatus.ACTIVE, ProtocolStatus.ESCALATING):
            success, description = self.execute_step()
            self._log_event("step_executed", description, success)

            if self.check_recovery():
                self.state.status = ProtocolStatus.RECOVERING

        elif self.state.status == ProtocolStatus.RECOVERING:
            if self._recovery_complete():
                self.deactivate()

    def _recovery_complete(self) -> bool:
        """Check if recovery is complete (5 ticks of stable conditions)."""
        ticks_stable = self.simulation.current_tick - self.state.trigger_tick
        return ticks_stable > 5 and self.check_recovery()

    def _log_event(self, event_type: str, description: str, success: bool = True):
        """Log protocol event."""
        self.execution_log.append({
            "tick": self.simulation.current_tick,
            "event": event_type,
            "description": description,
            "success": success,
            "escalation_level": self.state.escalation_level,
        })

    def get_status(self) -> Dict:
        """Get current protocol status."""
        return {
            "name": self.name,
            "status": self.state.status.name,
            "escalation_level": self.state.escalation_level,
            "current_step": self.state.current_step,
            "effectiveness": self.state.effectiveness,
            "resources_consumed": dict(self.state.resources_consumed),
            "modules_affected": list(self.state.modules_affected),
        }


# =============================================================================
# POWER OUTAGE PROTOCOL
# =============================================================================

class PowerOutageProtocol(FailureProtocol):
    """
    Protocol for total power outage.

    Steps:
    1. Immediately activate RSV fuel cells
    2. Activate biogas SOFC
    3. Begin priority load shedding (LOW first)
    4. Continue shedding to MEDIUM if needed
    5. Emergency: shed HIGH priority (preserve CRITICAL only)
    """

    ESCALATION_THRESHOLDS = [0.8, 0.5, 0.25, 0.1]  # % of demand met

    @property
    def name(self) -> str:
        return "Power Outage Protocol"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "power_ratio_below": 0.3,  # Less than 30% of demand met
            "duration_threshold": 2,    # Must persist for 2 ticks
        }

    def check_trigger(self) -> bool:
        """Check if power outage protocol should trigger."""
        power_store = self.stores.get("Power")
        if not power_store:
            return False

        demand = self.modules.get_total_power_demand()
        if demand == 0:
            return False

        supply_ratio = power_store.current_level / demand
        return supply_ratio < self.trigger_conditions["power_ratio_below"]

    def execute_step(self) -> Tuple[bool, str]:
        """Execute current protocol step."""
        power_store = self.stores.get("Power")
        demand = self.modules.get_total_power_demand()
        current_supply = power_store.current_level if power_store else 0
        shortfall = demand - current_supply

        if shortfall <= 0:
            return True, "Power supply adequate"

        # Step 1: Fuel cells
        if self.state.current_step == 0:
            result = self._activate_fuel_cells(shortfall)
            if result[0]:
                self.state.current_step = 1
            return result

        # Step 2: Biogas
        if self.state.current_step == 1:
            result = self._activate_biogas(shortfall)
            self.state.current_step = 2
            return result

        # Step 3+: Progressive load shedding
        if self.state.current_step >= 2:
            priorities_to_shed = [Priority.LOW, Priority.MEDIUM, Priority.HIGH]
            shed_index = min(self.state.escalation_level, len(priorities_to_shed) - 1)
            priority = priorities_to_shed[shed_index]

            result = self._shed_load_by_priority(priority, shortfall)

            # Check if we need to escalate
            new_supply = (power_store.current_level if power_store else 0) + result[1] if isinstance(result[1], (int, float)) else 0
            if demand > 0 and new_supply / demand < self.ESCALATION_THRESHOLDS[min(self.state.escalation_level, len(self.ESCALATION_THRESHOLDS) - 1)]:
                self.escalate()

            return (result[0], result[1]) if isinstance(result[1], str) else result

        return False, "Protocol step error"

    def _activate_fuel_cells(self, power_needed: float) -> Tuple[bool, str]:
        """Activate RSV fuel cells."""
        h2_store = self.stores.get("Hydrogen")
        power_store = self.stores.get("Power")

        if not h2_store or h2_store.current_level <= 0:
            return False, "No hydrogen available for fuel cells"

        # Calculate power output (simplified)
        max_power = min(power_needed, POWER.total_fuel_cell_kw)
        h2_needed = max_power / 33.0 / POWER.fuel_cell_efficiency

        if h2_store.current_level >= h2_needed:
            h2_store.remove(h2_needed)
            if power_store:
                power_store.add(max_power)

            self.state.resources_consumed["hydrogen_kg"] = (
                self.state.resources_consumed.get("hydrogen_kg", 0) + h2_needed
            )

            logger.info(f"Fuel cells activated: {max_power:.1f} kW")
            return True, f"Fuel cells providing {max_power:.1f} kW"

        return False, "Insufficient hydrogen"

    def _activate_biogas(self, power_needed: float) -> Tuple[bool, str]:
        """Activate biogas SOFC."""
        biogas_store = self.stores.get("Biogas")
        power_store = self.stores.get("Power")

        if not biogas_store or biogas_store.current_level <= 0:
            return False, "No biogas available"

        max_power = min(power_needed, POWER.biogas_capacity_kw)
        if biogas_store.current_level >= max_power:
            biogas_store.remove(max_power)
            if power_store:
                power_store.add(max_power)

            self.state.resources_consumed["biogas_m3"] = (
                self.state.resources_consumed.get("biogas_m3", 0) + max_power
            )

            logger.info(f"Biogas SOFC activated: {max_power:.1f} kW")
            return True, f"Biogas providing {max_power:.1f} kW"

        return False, "Insufficient biogas"

    def _shed_load_by_priority(self, priority: Priority, power_shortage: float) -> Tuple[bool, str]:
        """Shed load for a specific priority level."""
        modules_to_shed = self.modules.get_by_priority(priority)
        shed_power = 0.0
        shed_names = []

        for module in modules_to_shed:
            if not module.is_operational:
                continue

            module_power = module.spec.power_consumption_kw * module.effective_efficiency
            module.stop()
            shed_power += module_power
            shed_names.append(module.name)
            self.state.modules_affected.append(module.name)

            logger.warning(f"Load shed: {module.name} ({module_power:.1f} kW)")

            if shed_power >= power_shortage:
                break

        if shed_names:
            return True, f"Shed {len(shed_names)} {priority.name} modules ({shed_power:.1f} kW)"

        return False, f"No {priority.name} modules to shed"

    def check_recovery(self) -> bool:
        """Check if power situation has recovered."""
        power_store = self.stores.get("Power")
        if not power_store:
            return False

        demand = self.modules.get_total_power_demand()
        if demand == 0:
            return True

        # Need at least 90% of demand met to consider recovered
        return power_store.current_level >= demand * 0.9


# =============================================================================
# POWER REDUCTION PROTOCOL
# =============================================================================

class PowerReductionProtocol(FailureProtocol):
    """
    Protocol for partial power reduction (less severe than outage).

    Steps:
    1. Supplement with fuel cells
    2. Reduce non-essential loads
    3. Implement power rationing
    """

    @property
    def name(self) -> str:
        return "Power Reduction Protocol"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "power_ratio_below": 0.8,  # Less than 80% of demand
            "power_ratio_above": 0.3,  # But more than 30% (otherwise outage protocol)
        }

    def check_trigger(self) -> bool:
        """Check if power reduction protocol should trigger."""
        power_store = self.stores.get("Power")
        if not power_store:
            return False

        demand = self.modules.get_total_power_demand()
        if demand == 0:
            return False

        supply_ratio = power_store.current_level / demand
        conditions = self.trigger_conditions
        return conditions["power_ratio_above"] <= supply_ratio < conditions["power_ratio_below"]

    def execute_step(self) -> Tuple[bool, str]:
        """Execute power reduction response."""
        power_store = self.stores.get("Power")
        demand = self.modules.get_total_power_demand()
        current_supply = power_store.current_level if power_store else 0
        shortfall = demand - current_supply

        if shortfall <= 0:
            return True, "Power adequate"

        # Try fuel cell supplementation first
        if self.state.current_step == 0:
            h2_store = self.stores.get("Hydrogen")
            if h2_store and h2_store.current_level > 0:
                supplement = min(shortfall, POWER.total_fuel_cell_kw * 0.5)  # Use half capacity
                h2_needed = supplement / 33.0 / POWER.fuel_cell_efficiency

                if h2_store.current_level >= h2_needed:
                    h2_store.remove(h2_needed)
                    if power_store:
                        power_store.add(supplement)
                    self.state.current_step = 1
                    return True, f"Supplementing with {supplement:.1f} kW from fuel cells"

            self.state.current_step = 1

        # Reduce non-essential loads (LOW priority only)
        if self.state.current_step == 1:
            low_modules = self.modules.get_by_priority(Priority.LOW)
            for module in low_modules:
                if module.is_operational:
                    module.set_degraded("power reduction")
                    self.state.modules_affected.append(module.name)

            self.state.current_step = 2
            return True, f"Reduced {len(low_modules)} non-essential modules to degraded mode"

        return True, "Power reduction measures in effect"

    def check_recovery(self) -> bool:
        """Check if power has recovered."""
        power_store = self.stores.get("Power")
        if not power_store:
            return False

        demand = self.modules.get_total_power_demand()
        if demand == 0:
            return True

        return power_store.current_level >= demand * 0.95


# =============================================================================
# WATER INTERRUPTION PROTOCOL
# =============================================================================

class WaterInterruptionProtocol(FailureProtocol):
    """
    Protocol for water supply interruption.

    Steps:
    1. Switch to backup RSV POD
    2. Draw from distributed wall storage
    3. Implement water rationing
    4. Emergency: burn H₂ to produce water
    """

    @property
    def name(self) -> str:
        return "Water Interruption Protocol"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "water_ratio_below": 0.5,   # Less than 50% of daily need
            "both_rsv_failed": True,     # OR both RSV PODs offline
        }

    def check_trigger(self) -> bool:
        """Check if water interruption protocol should trigger."""
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")
        if not water_store:
            return True  # No water store is definitely a problem

        daily_need = (
            WATER.crew_consumption_l_per_person * MISSION.crew_size +
            WATER.crop_consumption_l_per_m2 * 50 +  # Estimate
            WATER.livestock_consumption_l_per_day
        )

        if water_store.current_level < daily_need * 0.5:
            return True

        # Check RSV PODs
        rsv1 = self.modules.get("RSV_POD_1")
        rsv2 = self.modules.get("RSV_POD_2")
        if rsv1 and rsv2:
            if not rsv1.is_operational and not rsv2.is_operational:
                return True

        return False

    def execute_step(self) -> Tuple[bool, str]:
        """Execute water interruption response."""
        # Step 1: Try backup RSV
        if self.state.current_step == 0:
            result = self._switch_rsv()
            if result[0]:
                self.state.current_step = 1
                return result
            self.state.current_step = 1  # Move on even if failed

        # Step 2: Use wall storage
        if self.state.current_step == 1:
            result = self._use_wall_storage()
            self.state.current_step = 2
            return result

        # Step 3: Implement rationing
        if self.state.current_step == 2:
            return self._implement_rationing()

        return False, "Protocol step error"

    def _switch_rsv(self) -> Tuple[bool, str]:
        """Attempt to switch to backup RSV."""
        rsv1 = self.modules.get("RSV_POD_1")
        rsv2 = self.modules.get("RSV_POD_2")

        if rsv1 and not rsv1.is_operational and rsv2 and rsv2.is_operational:
            rsv2.efficiency = min(1.5, rsv2.efficiency * 1.3)  # Boost
            logger.info("Switched to RSV POD 2 at boosted capacity")
            return True, "Switched to RSV POD 2"

        if rsv2 and not rsv2.is_operational and rsv1 and rsv1.is_operational:
            rsv1.efficiency = min(1.5, rsv1.efficiency * 1.3)
            logger.info("Switched to RSV POD 1 at boosted capacity")
            return True, "Switched to RSV POD 1"

        return False, "No backup RSV available"

    def _use_wall_storage(self) -> Tuple[bool, str]:
        """Draw from distributed wall storage."""
        wall_store = self.stores.get("Wall_Water_Reserve")
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")

        if not wall_store:
            return False, "No wall storage configured"

        # Draw enough for 1 sol
        daily_need = (
            WATER.crew_consumption_l_per_person * MISSION.crew_size +
            WATER.crop_consumption_l_per_m2 * 30 +
            WATER.livestock_consumption_l_per_day
        )

        available = wall_store.current_level
        to_draw = min(daily_need, available)

        if to_draw > 0:
            wall_store.remove(to_draw)
            if water_store:
                water_store.add(to_draw)

            self.state.resources_consumed["wall_water_l"] = (
                self.state.resources_consumed.get("wall_water_l", 0) + to_draw
            )

            logger.info(f"Drew {to_draw:.0f} L from wall storage")
            return True, f"Drew {to_draw:.0f} L from wall storage ({available - to_draw:.0f} L remaining)"

        return False, "Wall storage depleted"

    def _implement_rationing(self) -> Tuple[bool, str]:
        """Implement water rationing."""
        # Reduce water consumption by reducing module efficiency
        water_users = ["Food_POD_1", "Food_POD_2", "Food_POD_3", "Food_POD_4", "Food_POD_5",
                       "Fodder_POD", "Grain_POD", "Livestock_POD"]

        for name in water_users:
            module = self.modules.get(name)
            if module and module.is_operational:
                module.efficiency *= 0.8  # 20% reduction
                self.state.modules_affected.append(name)

        logger.warning("Water rationing in effect: 20% reduction")
        return True, "Water rationing: 20% reduction across food production"

    def check_recovery(self) -> bool:
        """Check if water supply has recovered."""
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")
        if not water_store:
            return False

        daily_need = (
            WATER.crew_consumption_l_per_person * MISSION.crew_size +
            WATER.crop_consumption_l_per_m2 * 50 +
            WATER.livestock_consumption_l_per_day
        )

        # Need at least 2 days of water and one RSV operational
        if water_store.current_level < daily_need * 2:
            return False

        rsv1 = self.modules.get("RSV_POD_1")
        rsv2 = self.modules.get("RSV_POD_2")
        return (rsv1 and rsv1.is_operational) or (rsv2 and rsv2.is_operational)


# =============================================================================
# WATER RESTRICTION PROTOCOL
# =============================================================================

class WaterRestrictionProtocol(FailureProtocol):
    """
    Protocol for mandated water restriction.

    Less severe than interruption - focuses on conservation.
    """

    @property
    def name(self) -> str:
        return "Water Restriction Protocol"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "restriction_severity": 0.2,  # 20%+ reduction mandated
        }

    def check_trigger(self) -> bool:
        """Check if water restriction protocol should trigger."""
        # Triggered by events, not automatic monitoring
        return False  # Manual trigger only

    def activate_with_severity(self, severity: float):
        """Activate with specific restriction severity."""
        self.restriction_severity = severity
        self.activate()

    def execute_step(self) -> Tuple[bool, str]:
        """Execute water restriction response."""
        severity = getattr(self, 'restriction_severity', 0.3)
        reduction = 1 - severity

        # Reduce water-intensive operations
        for i in range(1, 6):
            pod = self.modules.get(f"Food_POD_{i}")
            if pod:
                pod.efficiency *= reduction

        logger.info(f"Water restriction: operations at {reduction * 100:.0f}%")
        return True, f"Water operations reduced to {reduction * 100:.0f}%"

    def check_recovery(self) -> bool:
        """Check if restriction has been lifted."""
        # Relies on event duration
        return self.state.status == ProtocolStatus.RECOVERING


# =============================================================================
# EMERGENCY WATER PROTOCOL (H₂ BURN)
# =============================================================================

class EmergencyWaterProtocol(FailureProtocol):
    """
    Emergency protocol: burn H₂ to produce water.

    Only used when all other sources are exhausted.
    1 kg H₂ + 8 kg O₂ → 9 kg H₂O
    """

    @property
    def name(self) -> str:
        return "Emergency Water Protocol (H₂ Burn)"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "water_below_critical": 50,  # Less than 50 L total
            "wall_storage_depleted": True,
        }

    def check_trigger(self) -> bool:
        """Check if emergency water protocol should trigger."""
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")
        wall_store = self.stores.get("Wall_Water_Reserve")

        water_critical = not water_store or water_store.current_level < 50
        wall_depleted = not wall_store or wall_store.current_level < 10

        return water_critical and wall_depleted

    def execute_step(self) -> Tuple[bool, str]:
        """Execute emergency H₂ burn."""
        h2_store = self.stores.get("Hydrogen")
        o2_store = self.stores.get("Oxygen")
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")

        if not h2_store or not o2_store:
            return False, "H₂/O₂ stores not available"

        # Calculate minimum water needed for crew survival (1 sol)
        min_water = WATER.crew_consumption_l_per_person * MISSION.crew_size

        # Calculate H₂ needed
        h2_needed = min_water / WATER.h2_to_water_ratio

        h2_available = h2_store.current_level
        o2_available = o2_store.current_level

        # Check stoichiometry
        h2_can_use = min(h2_needed, h2_available, o2_available / 8)

        if h2_can_use > 0:
            water_produced = h2_can_use * WATER.h2_to_water_ratio

            h2_store.remove(h2_can_use)
            o2_store.remove(h2_can_use * 8)

            if water_store:
                water_store.add(water_produced)

            self.state.resources_consumed["hydrogen_kg"] = (
                self.state.resources_consumed.get("hydrogen_kg", 0) + h2_can_use
            )
            self.state.resources_consumed["oxygen_kg"] = (
                self.state.resources_consumed.get("oxygen_kg", 0) + h2_can_use * 8
            )
            self.state.resources_consumed["water_produced_l"] = (
                self.state.resources_consumed.get("water_produced_l", 0) + water_produced
            )

            logger.error(f"EMERGENCY: Burned {h2_can_use:.2f} kg H₂ → {water_produced:.0f} L water")
            return True, f"Emergency H₂ burn: {water_produced:.0f} L water produced"

        return False, "Insufficient H₂/O₂ for emergency water"

    def check_recovery(self) -> bool:
        """Check if water situation has improved."""
        water_store = self.stores.get("Potable_Water") or self.stores.get("Water")
        return water_store and water_store.current_level > 200


# =============================================================================
# GRACEFUL DEGRADATION PROTOCOL
# =============================================================================

class GracefulDegradationProtocol(FailureProtocol):
    """
    General graceful degradation protocol.

    Ensures N+1 redundancy and priority-based operation during
    any system degradation.
    """

    @property
    def name(self) -> str:
        return "Graceful Degradation Protocol"

    @property
    def trigger_conditions(self) -> Dict[str, Any]:
        return {
            "failed_modules_threshold": 2,  # 2+ modules failed
            "critical_module_degraded": True,
        }

    def check_trigger(self) -> bool:
        """Check if graceful degradation should activate."""
        failed = self.modules.get_failed_modules()
        if len(failed) >= 2:
            return True

        # Check for degraded critical modules
        for priority in [Priority.CRITICAL, Priority.HIGH]:
            for module in self.modules.get_by_priority(priority):
                if module.state == ModuleState.DEGRADED:
                    return True

        return False

    def execute_step(self) -> Tuple[bool, str]:
        """Execute graceful degradation."""
        actions_taken = []

        # 1. Ensure critical modules have priority resources
        critical_modules = self.modules.get_by_priority(Priority.CRITICAL)
        for module in critical_modules:
            if module.state == ModuleState.DEGRADED:
                # Try to restore
                if not module.has_malfunction:
                    module.state = ModuleState.NOMINAL
                    actions_taken.append(f"Restored {module.name}")

        # 2. Redistribute load from failed modules
        failed = self.modules.get_failed_modules()
        for failed_module in failed:
            backup = self._find_backup(failed_module)
            if backup:
                backup.efficiency = min(1.3, backup.efficiency * 1.1)
                actions_taken.append(f"Boosted {backup.name} to cover {failed_module.name}")
                self.state.modules_affected.append(backup.name)

        # 3. Reduce non-essential operations
        low_modules = self.modules.get_by_priority(Priority.LOW)
        for module in low_modules:
            if module.is_operational and module.efficiency > 0.5:
                module.efficiency *= 0.9
                actions_taken.append(f"Reduced {module.name} by 10%")

        if actions_taken:
            return True, "; ".join(actions_taken[:3])  # First 3 actions

        return True, "Monitoring system degradation"

    def _find_backup(self, failed_module: Module) -> Optional[Module]:
        """Find a backup module for the failed one."""
        name = failed_module.name

        # Food PODs have mutual backup
        if name.startswith("Food_POD"):
            for i in range(1, 6):
                backup_name = f"Food_POD_{i}"
                if backup_name != name:
                    backup = self.modules.get(backup_name)
                    if backup and backup.is_operational:
                        return backup

        # RSV PODs have dual redundancy
        if name == "RSV_POD_1":
            return self.modules.get("RSV_POD_2")
        if name == "RSV_POD_2":
            return self.modules.get("RSV_POD_1")

        return None

    def check_recovery(self) -> bool:
        """Check if system has stabilized."""
        failed = self.modules.get_failed_modules()
        if len(failed) > 0:
            return False

        # Check critical modules are nominal
        for module in self.modules.get_by_priority(Priority.CRITICAL):
            if module.state not in (ModuleState.NOMINAL, ModuleState.OFFLINE):
                return False

        return True


# =============================================================================
# PROTOCOL MANAGER
# =============================================================================

class ProtocolManager:
    """
    Manages all failure protocols.

    Coordinates protocol activation, execution, and recovery.
    """

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.protocols: List[FailureProtocol] = []
        self.active_protocols: List[FailureProtocol] = []

        # Register default protocols
        self._register_default_protocols()

    def _register_default_protocols(self):
        """Register all standard protocols."""
        self.protocols = [
            PowerOutageProtocol(self.simulation),
            PowerReductionProtocol(self.simulation),
            WaterInterruptionProtocol(self.simulation),
            WaterRestrictionProtocol(self.simulation),
            EmergencyWaterProtocol(self.simulation),
            GracefulDegradationProtocol(self.simulation),
        ]

    def add_protocol(self, protocol: FailureProtocol):
        """Add a custom protocol."""
        self.protocols.append(protocol)

    def tick(self):
        """Execute all protocols for this tick."""
        for protocol in self.protocols:
            was_active = protocol.state.status == ProtocolStatus.ACTIVE

            protocol.tick()

            # Track newly activated protocols
            if not was_active and protocol.state.status == ProtocolStatus.ACTIVE:
                self.active_protocols.append(protocol)

            # Remove completed protocols from active list
            if protocol.state.status == ProtocolStatus.COMPLETED:
                if protocol in self.active_protocols:
                    self.active_protocols.remove(protocol)

    def get_active_protocols(self) -> List[str]:
        """Get names of currently active protocols."""
        return [p.name for p in self.active_protocols]

    def get_all_status(self) -> Dict:
        """Get status of all protocols."""
        return {
            "active_count": len(self.active_protocols),
            "active_protocols": self.get_active_protocols(),
            "protocols": {
                p.name: p.get_status()
                for p in self.protocols
            },
        }

    def force_protocol(self, protocol_name: str) -> bool:
        """Force activation of a specific protocol."""
        for protocol in self.protocols:
            if protocol.name == protocol_name:
                protocol.activate()
                if protocol not in self.active_protocols:
                    self.active_protocols.append(protocol)
                return True
        return False
