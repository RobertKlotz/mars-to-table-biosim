"""
Mars to Table — Failure Response Handlers
Automated response strategies for different failure modes.

Based on Section 4 of the handoff document:
| Failure Mode | Our Response Strategy |
|--------------|----------------------|
| Power outage (total) | RSV fuel cells → Biogas SOFC → Priority load shedding |
| Power reduction | Reduce non-critical loads, fuel cell supplementation |
| Water interruption | Dual RSV redundancy, switch to backup POD |
| Water restriction | Draw from 25cm POD wall storage (distributed reserve) |
| Water emergency | Burn stored H₂ to create H₂O (1 kg H₂ → 9 kg H₂O) |
| Crew size increase | Surplus production capacity (84% > 50% requirement) |
| Crew size decrease | Scalable meal plan, reduce production |
| Metabolic increase (EVA) | +200 kcal/hour EVA bonus from reserves |
| Equipment malfunction | Graceful degradation, N+1 redundancy |
| POD failure | Isolate POD, redistribute load to others |
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from enum import Enum, auto
import logging

from ..core.simulation import Event, EventType, Simulation, SimulationState
from ..core.module import Module, ModuleState, ModuleManager
from ..core.store import Store, StoreManager, ResourceType
from ..config import MISSION, POWER, WATER, Priority

if TYPE_CHECKING:
    from ..systems.power_system import PowerSystem
    from ..systems.water_system import WaterSystem

logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE STRATEGY ENUM
# =============================================================================

class ResponseStrategy(Enum):
    """Available response strategies for different failures."""
    # Power strategies
    ACTIVATE_FUEL_CELLS = auto()
    ACTIVATE_BIOGAS = auto()
    LOAD_SHEDDING = auto()
    POWER_RATIONING = auto()

    # Water strategies
    SWITCH_RSV = auto()
    USE_WALL_STORAGE = auto()
    BURN_HYDROGEN = auto()
    WATER_RATIONING = auto()

    # General strategies
    ISOLATE_POD = auto()
    REDISTRIBUTE_LOAD = auto()
    GRACEFUL_DEGRADATION = auto()
    EMERGENCY_MODE = auto()

    # Crew strategies
    ADJUST_MEAL_PLAN = auto()
    REDUCE_ACTIVITY = auto()
    EVA_CALORIE_BOOST = auto()


# =============================================================================
# RESPONSE HANDLER BASE CLASS
# =============================================================================

@dataclass
class ResponseResult:
    """Result of executing a response strategy."""
    success: bool
    strategy: ResponseStrategy
    details: str
    resources_used: Dict[str, float] = field(default_factory=dict)
    modules_affected: List[str] = field(default_factory=list)
    effectiveness: float = 1.0  # 0.0 to 1.0 - how well did response mitigate issue


class ResponseHandler(ABC):
    """
    Base class for failure response handlers.

    Each handler specializes in responding to specific failure types.
    """

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.stores = simulation.stores
        self.modules = simulation.modules
        self.response_history: List[Dict] = []

    @property
    @abstractmethod
    def handled_event_types(self) -> List[EventType]:
        """Event types this handler responds to."""
        pass

    @abstractmethod
    def respond(self, event: Event) -> ResponseResult:
        """
        Execute response to an event.

        Args:
            event: The event to respond to

        Returns:
            ResponseResult indicating success and details
        """
        pass

    def can_respond(self, event: Event) -> bool:
        """Check if this handler can respond to the event."""
        return event.event_type in self.handled_event_types

    def record_response(self, event: Event, result: ResponseResult):
        """Record response for history and metrics."""
        self.response_history.append({
            "tick": self.simulation.current_tick,
            "event_type": event.event_type.name,
            "strategy": result.strategy.name,
            "success": result.success,
            "effectiveness": result.effectiveness,
            "details": result.details,
        })

    def get_statistics(self) -> Dict:
        """Get response statistics."""
        if not self.response_history:
            return {"total_responses": 0, "success_rate": 0.0, "avg_effectiveness": 0.0}

        successes = sum(1 for r in self.response_history if r["success"])
        avg_eff = sum(r["effectiveness"] for r in self.response_history) / len(self.response_history)

        return {
            "total_responses": len(self.response_history),
            "success_rate": successes / len(self.response_history),
            "avg_effectiveness": avg_eff,
            "by_strategy": self._count_by_strategy(),
        }

    def _count_by_strategy(self) -> Dict[str, int]:
        counts = {}
        for r in self.response_history:
            strategy = r["strategy"]
            counts[strategy] = counts.get(strategy, 0) + 1
        return counts


# =============================================================================
# POWER FAILURE RESPONSE
# =============================================================================

class PowerFailureResponse(ResponseHandler):
    """
    Handles power-related failures.

    Response hierarchy:
    1. Activate RSV fuel cells (H₂/O₂)
    2. Activate biogas SOFC
    3. Priority-based load shedding
    """

    @property
    def handled_event_types(self) -> List[EventType]:
        return [
            EventType.POWER_OUTAGE_TOTAL,
            EventType.POWER_OUTAGE_PARTIAL,
            EventType.POWER_REDUCTION,
            EventType.DUST_STORM,  # Affects solar
        ]

    def respond(self, event: Event) -> ResponseResult:
        """Execute power failure response."""
        logger.warning(f"PowerFailureResponse: Responding to {event.event_type.name}")

        # Determine power shortfall
        power_store = self.stores.get("Power")
        power_demand = self.modules.get_total_power_demand()
        power_available = power_store.current_level if power_store else 0

        shortfall = power_demand - power_available
        severity = event.severity

        if shortfall <= 0:
            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.POWER_RATIONING,
                details="No power shortfall detected",
                effectiveness=1.0,
            )

        strategies_tried = []
        total_recovered = 0.0

        # Strategy 1: Activate fuel cells
        if shortfall > 0:
            result = self._activate_fuel_cells(shortfall)
            strategies_tried.append(result)
            total_recovered += result.resources_used.get("power_kw", 0)
            shortfall -= result.resources_used.get("power_kw", 0)

        # Strategy 2: Activate biogas
        if shortfall > 0:
            result = self._activate_biogas(shortfall)
            strategies_tried.append(result)
            total_recovered += result.resources_used.get("power_kw", 0)
            shortfall -= result.resources_used.get("power_kw", 0)

        # Strategy 3: Load shedding
        if shortfall > 0:
            result = self._shed_load(shortfall)
            strategies_tried.append(result)
            shortfall -= result.resources_used.get("load_shed_kw", 0)

        # Calculate effectiveness
        effectiveness = 1.0 - (max(0, shortfall) / power_demand) if power_demand > 0 else 1.0

        # Determine primary strategy
        primary_strategy = ResponseStrategy.POWER_RATIONING
        if strategies_tried:
            # Pick most effective strategy used
            for result in strategies_tried:
                if result.success:
                    primary_strategy = result.strategy
                    break

        final_result = ResponseResult(
            success=shortfall <= 0,
            strategy=primary_strategy,
            details=f"Recovered {total_recovered:.1f} kW, shortfall now {max(0, shortfall):.1f} kW",
            resources_used={"power_recovered_kw": total_recovered},
            effectiveness=effectiveness,
        )

        self.record_response(event, final_result)
        return final_result

    def _activate_fuel_cells(self, power_needed: float) -> ResponseResult:
        """Activate RSV fuel cells."""
        h2_store = self.stores.get("Hydrogen")
        o2_store = self.stores.get("Oxygen")

        if not h2_store or not o2_store:
            return ResponseResult(
                success=False,
                strategy=ResponseStrategy.ACTIVATE_FUEL_CELLS,
                details="Hydrogen or oxygen store not found",
                effectiveness=0.0,
            )

        # Calculate H₂ needed (fuel cell efficiency ~60%)
        # 1 kg H₂ + 8 kg O₂ produces ~33 kWh at 60% efficiency
        h2_per_kw = 1.0 / (33.0 * POWER.fuel_cell_efficiency)
        h2_needed = power_needed * h2_per_kw

        h2_available = h2_store.current_level
        h2_used = min(h2_needed, h2_available)

        # Calculate power output
        power_output = h2_used / h2_per_kw
        power_output = min(power_output, POWER.total_fuel_cell_kw)  # Cap at capacity

        if h2_used > 0:
            h2_store.remove(h2_used)
            o2_store.remove(h2_used * 8)  # Stoichiometric ratio

            # Add to power store
            power_store = self.stores.get("Power")
            if power_store:
                power_store.add(power_output)

            logger.info(f"Fuel cells activated: {power_output:.1f} kW using {h2_used:.2f} kg H₂")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.ACTIVATE_FUEL_CELLS,
                details=f"Fuel cells providing {power_output:.1f} kW",
                resources_used={"power_kw": power_output, "h2_kg": h2_used},
                effectiveness=min(1.0, power_output / power_needed),
            )

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.ACTIVATE_FUEL_CELLS,
            details="Insufficient hydrogen for fuel cells",
            effectiveness=0.0,
        )

    def _activate_biogas(self, power_needed: float) -> ResponseResult:
        """Activate biogas SOFC."""
        biogas_store = self.stores.get("Biogas")

        if not biogas_store or biogas_store.current_level <= 0:
            return ResponseResult(
                success=False,
                strategy=ResponseStrategy.ACTIVATE_BIOGAS,
                details="No biogas available",
                effectiveness=0.0,
            )

        # Biogas provides up to 5 kW continuous
        power_output = min(power_needed, POWER.biogas_capacity_kw)

        # Consume biogas (roughly 1 m³/kWh)
        biogas_needed = power_output  # Simplified model
        biogas_used = min(biogas_needed, biogas_store.current_level)
        power_output = biogas_used  # 1:1 ratio simplified

        if biogas_used > 0:
            biogas_store.remove(biogas_used)

            power_store = self.stores.get("Power")
            if power_store:
                power_store.add(power_output)

            logger.info(f"Biogas SOFC activated: {power_output:.1f} kW")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.ACTIVATE_BIOGAS,
                details=f"Biogas SOFC providing {power_output:.1f} kW",
                resources_used={"power_kw": power_output, "biogas_m3": biogas_used},
                effectiveness=min(1.0, power_output / power_needed),
            )

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.ACTIVATE_BIOGAS,
            details="Biogas depleted",
            effectiveness=0.0,
        )

    def _shed_load(self, power_shortage: float) -> ResponseResult:
        """Shed non-critical loads."""
        shed_modules = self.modules.shed_load(
            self.modules.get_total_power_demand() - power_shortage
        )

        if shed_modules:
            load_shed = sum(
                self.modules.get(name).spec.power_consumption_kw
                for name in shed_modules
                if self.modules.get(name)
            )

            logger.warning(f"Load shedding: {len(shed_modules)} modules shut down")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.LOAD_SHEDDING,
                details=f"Shed {len(shed_modules)} modules ({load_shed:.1f} kW)",
                resources_used={"load_shed_kw": load_shed},
                modules_affected=shed_modules,
                effectiveness=min(1.0, load_shed / power_shortage),
            )

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.LOAD_SHEDDING,
            details="No modules available to shed",
            effectiveness=0.0,
        )


# =============================================================================
# WATER FAILURE RESPONSE
# =============================================================================

class WaterFailureResponse(ResponseHandler):
    """
    Handles water-related failures.

    Response hierarchy:
    1. Switch to backup RSV POD
    2. Draw from distributed wall storage
    3. Burn H₂ to produce water (emergency)
    4. Implement water rationing
    """

    @property
    def handled_event_types(self) -> List[EventType]:
        return [
            EventType.WATER_SUPPLY_INTERRUPTION,
            EventType.WATER_RESTRICTION,
            EventType.WATER_CONTAMINATION,
        ]

    def respond(self, event: Event) -> ResponseResult:
        """Execute water failure response."""
        logger.warning(f"WaterFailureResponse: Responding to {event.event_type.name}")

        water_store = self.stores.get("Potable_Water")
        if not water_store:
            water_store = self.stores.get("Water")

        # Calculate water shortfall
        daily_demand = (
            WATER.crew_consumption_l_per_person * MISSION.crew_size +
            WATER.crop_consumption_l_per_m2 * 100 +  # Estimated active crop area
            WATER.livestock_consumption_l_per_day
        ) / MISSION.ticks_per_sol  # Per tick

        water_available = water_store.current_level if water_store else 0
        shortfall = daily_demand - water_available

        if event.event_type == EventType.WATER_SUPPLY_INTERRUPTION:
            return self._handle_interruption(event, shortfall)
        elif event.event_type == EventType.WATER_RESTRICTION:
            return self._handle_restriction(event)
        elif event.event_type == EventType.WATER_CONTAMINATION:
            return self._handle_contamination(event, shortfall)

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.WATER_RATIONING,
            details="Unknown water event type",
            effectiveness=0.0,
        )

    def _handle_interruption(self, event: Event, shortfall: float) -> ResponseResult:
        """Handle water supply interruption."""
        # Try to switch RSV PODs
        target = event.target_module

        if target == "RSV_POD_1":
            backup = self.modules.get("RSV_POD_2")
            if backup and backup.state != ModuleState.FAILED:
                logger.info("Switching to backup RSV POD 2")
                return ResponseResult(
                    success=True,
                    strategy=ResponseStrategy.SWITCH_RSV,
                    details="Switched to RSV POD 2",
                    modules_affected=["RSV_POD_1", "RSV_POD_2"],
                    effectiveness=1.0,
                )
        elif target == "RSV_POD_2":
            backup = self.modules.get("RSV_POD_1")
            if backup and backup.state != ModuleState.FAILED:
                logger.info("Switching to backup RSV POD 1")
                return ResponseResult(
                    success=True,
                    strategy=ResponseStrategy.SWITCH_RSV,
                    details="Switched to RSV POD 1",
                    modules_affected=["RSV_POD_1", "RSV_POD_2"],
                    effectiveness=1.0,
                )

        # If both RSV PODs down, use wall storage
        return self._use_wall_storage(shortfall)

    def _handle_restriction(self, event: Event) -> ResponseResult:
        """Handle water restriction mandate."""
        restriction_factor = 1 - event.severity

        # Implement rationing across systems
        logger.info(f"Water rationing: {restriction_factor * 100:.0f}% of normal allocation")

        # Reduce non-critical water usage
        return ResponseResult(
            success=True,
            strategy=ResponseStrategy.WATER_RATIONING,
            details=f"Water reduced to {restriction_factor * 100:.0f}% of normal",
            effectiveness=restriction_factor,
        )

    def _handle_contamination(self, event: Event, shortfall: float) -> ResponseResult:
        """Handle water contamination."""
        # Use wall storage until contamination cleared
        result = self._use_wall_storage(shortfall * event.duration_ticks)

        if result.success:
            result.details = f"Using wall storage during contamination treatment. {result.details}"

        return result

    def _use_wall_storage(self, water_needed: float) -> ResponseResult:
        """Draw from distributed wall storage."""
        wall_store = self.stores.get("Wall_Water_Reserve")

        if not wall_store:
            # Fall back to emergency H₂ burn
            return self._burn_hydrogen(water_needed)

        available = wall_store.current_level
        used = min(water_needed, available)

        if used > 0:
            wall_store.remove(used)

            # Add to potable water
            water_store = self.stores.get("Potable_Water")
            if water_store:
                water_store.add(used)
            else:
                water_store = self.stores.get("Water")
                if water_store:
                    water_store.add(used)

            logger.info(f"Wall storage: Drew {used:.1f} L")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.USE_WALL_STORAGE,
                details=f"Drew {used:.1f} L from wall storage ({available - used:.1f} L remaining)",
                resources_used={"water_l": used},
                effectiveness=min(1.0, used / water_needed) if water_needed > 0 else 1.0,
            )

        # Wall storage empty, try hydrogen burn
        return self._burn_hydrogen(water_needed)

    def _burn_hydrogen(self, water_needed: float) -> ResponseResult:
        """
        Emergency: Burn H₂ + O₂ to produce water.

        1 kg H₂ + 8 kg O₂ → 9 kg H₂O
        """
        h2_store = self.stores.get("Hydrogen")
        o2_store = self.stores.get("Oxygen")

        if not h2_store or not o2_store:
            return ResponseResult(
                success=False,
                strategy=ResponseStrategy.BURN_HYDROGEN,
                details="Hydrogen or oxygen store not available",
                effectiveness=0.0,
            )

        # Calculate H₂ needed
        h2_needed = water_needed / WATER.h2_to_water_ratio
        h2_available = h2_store.current_level
        o2_available = o2_store.current_level

        # Check stoichiometric limits
        h2_can_use = min(h2_needed, h2_available, o2_available / 8)

        if h2_can_use > 0:
            water_produced = h2_can_use * WATER.h2_to_water_ratio

            h2_store.remove(h2_can_use)
            o2_store.remove(h2_can_use * 8)

            # Add produced water
            water_store = self.stores.get("Potable_Water") or self.stores.get("Water")
            if water_store:
                water_store.add(water_produced)

            logger.warning(f"EMERGENCY: Burned {h2_can_use:.2f} kg H₂ → {water_produced:.1f} L H₂O")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.BURN_HYDROGEN,
                details=f"Emergency H₂ burn: {h2_can_use:.2f} kg → {water_produced:.1f} L water",
                resources_used={"h2_kg": h2_can_use, "o2_kg": h2_can_use * 8, "water_l": water_produced},
                effectiveness=min(1.0, water_produced / water_needed) if water_needed > 0 else 1.0,
            )

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.BURN_HYDROGEN,
            details="Insufficient H₂/O₂ for emergency water production",
            effectiveness=0.0,
        )


# =============================================================================
# POD FAILURE RESPONSE
# =============================================================================

class PODFailureResponse(ResponseHandler):
    """
    Handles POD and equipment failures.

    Response: Isolate failed POD, redistribute load to others.
    """

    @property
    def handled_event_types(self) -> List[EventType]:
        return [
            EventType.POD_FAILURE,
            EventType.EQUIPMENT_MALFUNCTION,
            EventType.SENSOR_FAILURE,
        ]

    def respond(self, event: Event) -> ResponseResult:
        """Execute POD failure response."""
        logger.warning(f"PODFailureResponse: Responding to {event.event_type.name}")

        target = event.target_module
        if not target:
            return ResponseResult(
                success=False,
                strategy=ResponseStrategy.ISOLATE_POD,
                details="No target module specified",
                effectiveness=0.0,
            )

        module = self.modules.get(target)
        if not module:
            return ResponseResult(
                success=False,
                strategy=ResponseStrategy.ISOLATE_POD,
                details=f"Module {target} not found",
                effectiveness=0.0,
            )

        # Isolate the failed module
        module.stop()
        logger.info(f"Isolated failed module: {target}")

        # Find backup modules of same type
        backup_found = False
        pod_type = self._get_pod_type(target)

        if pod_type == "Food_POD":
            # Redistribute to other Food PODs (we have 5)
            backup_found = self._redistribute_food_load(target)
        elif pod_type == "RSV_POD":
            # Switch to other RSV POD
            backup_found = self._switch_rsv(target)
        elif pod_type == "Livestock_POD":
            # No backup, enter graceful degradation
            backup_found = False

        if backup_found:
            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.REDISTRIBUTE_LOAD,
                details=f"Isolated {target}, redistributed load",
                modules_affected=[target],
                effectiveness=0.9,  # Some efficiency loss
            )
        else:
            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.GRACEFUL_DEGRADATION,
                details=f"Isolated {target}, operating in degraded mode",
                modules_affected=[target],
                effectiveness=1.0 - event.severity,
            )

    def _get_pod_type(self, module_name: str) -> str:
        """Extract POD type from module name."""
        if module_name.startswith("Food_POD"):
            return "Food_POD"
        elif module_name.startswith("RSV_POD"):
            return "RSV_POD"
        elif module_name.startswith("Livestock"):
            return "Livestock_POD"
        elif module_name.startswith("Fodder"):
            return "Fodder_POD"
        elif module_name.startswith("Grain"):
            return "Grain_POD"
        return "Unknown"

    def _redistribute_food_load(self, failed_pod: str) -> bool:
        """Redistribute food production to other PODs."""
        active_food_pods = []
        for i in range(1, 6):
            pod_name = f"Food_POD_{i}"
            if pod_name != failed_pod:
                pod = self.modules.get(pod_name)
                if pod and pod.is_operational:
                    active_food_pods.append(pod)

        if active_food_pods:
            # Increase efficiency of remaining PODs (they can grow more)
            boost_factor = 1.0 + (1.0 / len(active_food_pods))
            for pod in active_food_pods:
                pod.efficiency = min(1.2, pod.efficiency * boost_factor)
            logger.info(f"Redistributed load to {len(active_food_pods)} Food PODs")
            return True

        return False

    def _switch_rsv(self, failed_rsv: str) -> bool:
        """Switch to backup RSV POD."""
        backup_name = "RSV_POD_2" if failed_rsv == "RSV_POD_1" else "RSV_POD_1"
        backup = self.modules.get(backup_name)

        if backup and backup.state != ModuleState.FAILED:
            # Increase backup capacity
            backup.efficiency = min(1.5, backup.efficiency * 1.5)  # 50% boost
            logger.info(f"Switched to {backup_name} at boosted capacity")
            return True

        return False


# =============================================================================
# CREW CHANGE RESPONSE
# =============================================================================

class CrewChangeResponse(ResponseHandler):
    """
    Handles crew size and metabolic changes.

    Responses:
    - Crew increase: Utilize surplus production capacity
    - Crew decrease: Scale down meal plan
    - Metabolic increase: Use calorie reserves
    """

    @property
    def handled_event_types(self) -> List[EventType]:
        return [
            EventType.CREW_SIZE_INCREASE,
            EventType.CREW_SIZE_DECREASE,
            EventType.CREW_METABOLIC_INCREASE,
            EventType.CREW_EVA_DAY,
        ]

    def respond(self, event: Event) -> ResponseResult:
        """Execute crew change response."""
        logger.info(f"CrewChangeResponse: Responding to {event.event_type.name}")

        if event.event_type == EventType.CREW_SIZE_INCREASE:
            return self._handle_increase(event)
        elif event.event_type == EventType.CREW_SIZE_DECREASE:
            return self._handle_decrease(event)
        elif event.event_type in (EventType.CREW_METABOLIC_INCREASE, EventType.CREW_EVA_DAY):
            return self._handle_metabolic_increase(event)

        return ResponseResult(
            success=False,
            strategy=ResponseStrategy.ADJUST_MEAL_PLAN,
            details="Unknown crew event type",
            effectiveness=0.0,
        )

    def _handle_increase(self, event: Event) -> ResponseResult:
        """Handle crew size increase."""
        increase = event.parameters.get("count", 1)
        new_crew = self.simulation.state.crew_size

        # Check if we have capacity (84% target > 50% requirement)
        # We can support ~26 crew at 50% target vs our 15-crew design
        max_sustainable = int(MISSION.crew_size * (MISSION.target_earth_independence / MISSION.min_earth_independence))

        if new_crew <= max_sustainable:
            logger.info(f"Crew increased to {new_crew}, within sustainable capacity")
            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.ADJUST_MEAL_PLAN,
                details=f"Crew now {new_crew}, using surplus capacity",
                effectiveness=1.0,
            )
        else:
            # Need to ration
            logger.warning(f"Crew at {new_crew}, exceeds sustainable {max_sustainable}")
            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.ADJUST_MEAL_PLAN,
                details=f"Crew at {new_crew}, implementing rationing",
                effectiveness=max_sustainable / new_crew,
            )

    def _handle_decrease(self, event: Event) -> ResponseResult:
        """Handle crew size decrease."""
        decrease = event.parameters.get("count", 1)
        new_crew = self.simulation.state.crew_size

        logger.info(f"Crew decreased to {new_crew}")

        # Scale down production
        return ResponseResult(
            success=True,
            strategy=ResponseStrategy.ADJUST_MEAL_PLAN,
            details=f"Crew now {new_crew}, scaling production",
            effectiveness=1.0,
        )

    def _handle_metabolic_increase(self, event: Event) -> ResponseResult:
        """Handle increased calorie needs."""
        increase_pct = event.severity * 100

        if event.event_type == EventType.CREW_EVA_DAY:
            eva_crew = event.parameters.get("crew_count", 2)
            eva_hours = event.parameters.get("hours", 6)
            extra_calories = eva_crew * eva_hours * MISSION.eva_bonus_calories_per_hour

            logger.info(f"EVA day: {eva_crew} crew × {eva_hours} hours = {extra_calories} extra kcal")

            return ResponseResult(
                success=True,
                strategy=ResponseStrategy.EVA_CALORIE_BOOST,
                details=f"EVA bonus: {extra_calories} kcal from reserves",
                resources_used={"extra_calories": extra_calories},
                effectiveness=1.0,
            )

        # General metabolic increase
        logger.info(f"Metabolic increase: {increase_pct:.0f}%")

        return ResponseResult(
            success=True,
            strategy=ResponseStrategy.ADJUST_MEAL_PLAN,
            details=f"Metabolic increase {increase_pct:.0f}%, adjusting meal plan",
            effectiveness=1.0 - (event.severity * 0.2),  # Slight degradation
        )


# =============================================================================
# RESPONSE MANAGER
# =============================================================================

class ResponseManager:
    """
    Coordinates all response handlers.

    Automatically dispatches events to appropriate handlers.
    """

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.handlers: List[ResponseHandler] = []

        # Register default handlers
        self._register_default_handlers()

        # Hook into simulation event system
        self.original_event_callback = simulation.on_event_triggered
        simulation.on_event_triggered = self._on_event

    def _register_default_handlers(self):
        """Register all standard response handlers."""
        self.handlers = [
            PowerFailureResponse(self.simulation),
            WaterFailureResponse(self.simulation),
            PODFailureResponse(self.simulation),
            CrewChangeResponse(self.simulation),
        ]

    def add_handler(self, handler: ResponseHandler):
        """Add a custom response handler."""
        self.handlers.append(handler)

    def _on_event(self, event: Event):
        """Called when an event is triggered."""
        # Find and execute appropriate handler
        for handler in self.handlers:
            if handler.can_respond(event):
                result = handler.respond(event)
                logger.info(
                    f"Response to {event.event_type.name}: "
                    f"{result.strategy.name} - {result.details}"
                )
                break

        # Call original callback if any
        if self.original_event_callback:
            self.original_event_callback(event)

    def get_all_statistics(self) -> Dict:
        """Get statistics from all handlers."""
        return {
            type(handler).__name__: handler.get_statistics()
            for handler in self.handlers
        }
