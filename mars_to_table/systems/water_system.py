"""
Mars to Table — Water System
Ice extraction, storage, recycling, and emergency water generation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import WATER, POD, MISSION, Priority

logger = logging.getLogger(__name__)


class WaterSource(Enum):
    """Water source types."""
    RSV_EXTRACTION = auto()    # Ice mining from regolith
    RECYCLING = auto()         # Grey/waste water recovery
    FUEL_CELL_BYPRODUCT = auto()  # H2O from fuel cells
    H2_COMBUSTION = auto()     # Emergency: burn H2 for water
    WALL_RESERVE = auto()      # Emergency: POD wall storage


@dataclass
class WaterState:
    """Current state of the water system."""
    extraction_rate_l_per_tick: float = 0.0
    recycling_rate_l_per_tick: float = 0.0
    consumption_rate_l_per_tick: float = 0.0
    total_potable_l: float = 0.0
    total_grey_l: float = 0.0
    total_reserve_l: float = 0.0
    deficit_l: float = 0.0
    rsv_pods_operational: int = 0
    emergency_mode: bool = False
    using_wall_reserve: bool = False
    using_h2_burn: bool = False


class RSVExtractor(Module):
    """
    Resource Supply Vehicle ice extraction system.

    Extracts water ice from Martian regolith using:
    - Drill and excavation
    - Heating to sublimate ice
    - Vapor capture and condensation

    Each RSV POD provides ~700 L/day capacity.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 extraction_rate_l_per_day: float = None, tank_capacity_l: float = None):

        rate = extraction_rate_l_per_day or WATER.ice_extraction_rate_l_per_day
        tank = tank_capacity_l or WATER.rsv_tank_capacity_l

        spec = ModuleSpec(
            name=name,
            priority=Priority.CRITICAL,
            power_consumption_kw=25.0,  # Heating, pumps, drill
            produces=[
                # Extraction rate per tick (rate/24 for hourly)
                ResourceFlow(ResourceType.POTABLE_WATER, rate / 24, "Potable_Water"),
            ],
            startup_ticks=2,  # Takes 2 hours to warm up
            efficiency=1.0
        )
        super().__init__(spec, store_manager)

        self.extraction_rate_l_per_day = rate
        self.tank_capacity_l = tank
        self.local_tank_level = 0.0

        # Ice deposit tracking
        self.ice_deposit_remaining = 1_000_000.0  # Liters equivalent, essentially unlimited

    @property
    def extraction_rate_per_tick(self) -> float:
        """Current extraction rate in L/tick."""
        return (self.extraction_rate_l_per_day / 24) * self.effective_efficiency

    def process_tick(self) -> Dict:
        """Extract water from ice deposit."""
        if self.ice_deposit_remaining <= 0:
            logger.warning(f"{self.name}: Ice deposit exhausted!")
            return {"extracted_l": 0.0, "ice_remaining": 0.0}

        # Extract water
        extracted = min(self.extraction_rate_per_tick, self.ice_deposit_remaining)
        self.ice_deposit_remaining -= extracted

        # Water is added to store by parent class via produces flow
        return {
            "extracted_l": extracted,
            "rate_l_per_day": self.extraction_rate_l_per_day * self.effective_efficiency,
            "ice_remaining": self.ice_deposit_remaining,
        }


class WaterRecycler(Module):
    """
    Water recycling system.

    Processes grey water and waste water back to potable water.
    Achieves 95% recovery efficiency.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 efficiency: float = None):

        eff = efficiency or WATER.recycling_efficiency

        spec = ModuleSpec(
            name=name,
            priority=Priority.HIGH,
            power_consumption_kw=5.0,
            consumes=[
                ResourceFlow(ResourceType.GREY_WATER, 10.0, "Grey_Water", required=False),
                ResourceFlow(ResourceType.WASTE_WATER, 5.0, "Waste_Water", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water"),  # Calculated
            ],
            efficiency=eff
        )
        super().__init__(spec, store_manager)

        self.recovery_efficiency = eff
        self.processed_this_tick = 0.0

    def process_tick(self) -> Dict:
        """Process grey/waste water to potable."""
        total_input = 0.0

        # Sum up actual input flows
        for flow in self.spec.consumes:
            total_input += flow.actual_flow

        # Convert to potable water
        recovered = total_input * self.recovery_efficiency * self.effective_efficiency
        self.processed_this_tick = recovered

        # Add to potable water store
        potable_store = self.stores.get("Potable_Water")
        if potable_store and recovered > 0:
            potable_store.add(recovered)

        return {
            "input_l": total_input,
            "recovered_l": recovered,
            "efficiency": self.recovery_efficiency,
        }


class H2Combuster(Module):
    """
    Emergency water generation via hydrogen combustion.

    2H2 + O2 -> 2H2O

    1 kg H2 + 8 kg O2 -> 9 kg H2O (~9 L)

    Only used in extreme water shortage emergencies.
    """

    def __init__(self, name: str, store_manager: StoreManager):
        spec = ModuleSpec(
            name=name,
            priority=Priority.CRITICAL,
            power_consumption_kw=1.0,  # Ignition/control only
            consumes=[
                ResourceFlow(ResourceType.HYDROGEN, 1.0, "Hydrogen", required=True),
                ResourceFlow(ResourceType.OXYGEN, 8.0, "Oxygen", required=True),
            ],
            produces=[
                ResourceFlow(ResourceType.POTABLE_WATER, 9.0, "Potable_Water"),
            ],
            efficiency=0.95  # Some losses
        )
        super().__init__(spec, store_manager)

        self.is_active = False
        self.water_produced_total = 0.0

    def activate(self):
        """Activate emergency H2 combustion."""
        if not self.is_active:
            self.is_active = True
            self.start()
            logger.warning(f"{self.name}: EMERGENCY H2 combustion activated!")

    def deactivate(self):
        """Deactivate H2 combustion."""
        if self.is_active:
            self.is_active = False
            self.stop()
            logger.info(f"{self.name}: H2 combustion deactivated")

    def process_tick(self) -> Dict:
        """Burn H2 to produce water if active."""
        if not self.is_active:
            return {"water_produced_l": 0.0, "active": False}

        # Water production handled by parent class produces flow
        # Track total
        h2_flow = next((f for f in self.spec.consumes
                       if f.resource_type == ResourceType.HYDROGEN), None)

        water_produced = 0.0
        if h2_flow and h2_flow.actual_flow > 0:
            water_produced = h2_flow.actual_flow * WATER.h2_to_water_ratio * self.effective_efficiency
            self.water_produced_total += water_produced

        return {
            "water_produced_l": water_produced,
            "total_produced_l": self.water_produced_total,
            "active": self.is_active,
        }


class WallWaterReserve:
    """
    Distributed water storage in POD walls.

    Each POD has ~800L in the 25cm water shielding wall.
    This is emergency reserve only - using it degrades radiation protection.
    """

    def __init__(self, store_manager: StoreManager, num_pods: int = 13):
        self.stores = store_manager
        self.num_pods = num_pods
        self.capacity_per_pod = POD.wall_water_storage_liters
        self.total_capacity = self.capacity_per_pod * num_pods
        self.current_level = self.total_capacity  # Starts full
        self.is_tapped = False

    def tap_reserve(self, amount_l: float) -> float:
        """
        Draw from wall reserve.

        Returns actual amount drawn.
        """
        if not self.is_tapped:
            self.is_tapped = True
            logger.warning("WALL WATER RESERVE TAPPED - radiation shielding degraded!")

        actual = min(amount_l, self.current_level)
        self.current_level -= actual

        # Add to potable water store
        potable_store = self.stores.get("Potable_Water")
        if potable_store and actual > 0:
            potable_store.add(actual)

        return actual

    def get_status(self) -> Dict:
        """Get reserve status."""
        return {
            "total_capacity_l": self.total_capacity,
            "current_level_l": self.current_level,
            "fill_fraction": self.current_level / self.total_capacity if self.total_capacity > 0 else 0,
            "is_tapped": self.is_tapped,
            "pods_affected": self.num_pods if self.is_tapped else 0,
        }


class WaterSystem:
    """
    Integrated water management system.

    Manages:
    - RSV ice extraction (primary)
    - Water recycling (95% recovery)
    - Fuel cell water byproduct
    - Emergency H2 combustion
    - Wall reserve (last resort)

    Implements dual RSV redundancy and automatic failover.
    """

    def __init__(self, store_manager: StoreManager, module_manager: ModuleManager):
        self.stores = store_manager
        self.modules = module_manager

        # Water sources
        self.rsv_extractors: List[RSVExtractor] = []
        self.recyclers: List[WaterRecycler] = []
        self.h2_combuster: Optional[H2Combuster] = None
        self.wall_reserve: Optional[WallWaterReserve] = None

        # State
        self.state = WaterState()

        # Thresholds (in liters)
        self.low_water_threshold = 500.0  # Start conservation
        self.critical_water_threshold = 200.0  # Activate H2 burn
        self.emergency_water_threshold = 50.0  # Tap wall reserve

        # Daily requirements
        self.crew_requirement_l_per_day = MISSION.crew_size * WATER.crew_consumption_l_per_person
        self.crop_requirement_l_per_day = 400.0  # From config
        self.livestock_requirement_l_per_day = WATER.livestock_consumption_l_per_day

        # History
        self.daily_extraction: List[float] = []
        self.daily_consumption: List[float] = []

    def add_rsv_extractor(self, extractor: RSVExtractor):
        """Register an RSV extractor."""
        self.rsv_extractors.append(extractor)
        self.modules.add_module(extractor)

    def add_recycler(self, recycler: WaterRecycler):
        """Register a water recycler."""
        self.recyclers.append(recycler)
        self.modules.add_module(recycler)

    def set_h2_combuster(self, combuster: H2Combuster):
        """Set the H2 combuster for emergencies."""
        self.h2_combuster = combuster
        self.modules.add_module(combuster)

    def set_wall_reserve(self, reserve: WallWaterReserve):
        """Set the wall water reserve."""
        self.wall_reserve = reserve

    def initialize_default_system(self):
        """Set up the default water system from config."""
        # Two RSV extractors (dual redundancy)
        for i in range(WATER.num_rsv_pods):
            extractor = RSVExtractor(
                f"RSV_Extractor_{i+1}",
                self.stores,
                WATER.ice_extraction_rate_l_per_day,
                WATER.rsv_tank_capacity_l
            )
            extractor.start()
            self.add_rsv_extractor(extractor)

        # Main water recycler
        recycler = WaterRecycler("Water_Recycler_Main", self.stores, WATER.recycling_efficiency)
        recycler.start()
        self.add_recycler(recycler)

        # Emergency H2 combuster (starts offline)
        combuster = H2Combuster("H2_Combuster_Emergency", self.stores)
        self.set_h2_combuster(combuster)

        # Wall reserve
        reserve = WallWaterReserve(self.stores, num_pods=13)
        self.set_wall_reserve(reserve)

        logger.info(f"Water system initialized: {len(self.rsv_extractors)} RSV extractors, "
                   f"{len(self.recyclers)} recyclers, wall reserve: {reserve.total_capacity:.0f}L")

    def get_total_extraction_capacity(self) -> float:
        """Get total water extraction capacity (L/day)."""
        return sum(
            e.extraction_rate_l_per_day * e.effective_efficiency
            for e in self.rsv_extractors if e.is_operational
        )

    def get_potable_water_level(self) -> float:
        """Get current potable water level."""
        store = self.stores.get("Potable_Water")
        return store.current_level if store else 0.0

    def get_daily_requirement(self) -> float:
        """Get total daily water requirement."""
        return (self.crew_requirement_l_per_day +
                self.crop_requirement_l_per_day +
                self.livestock_requirement_l_per_day)

    def tick(self) -> WaterState:
        """
        Execute one water system tick.

        1. Check current water levels
        2. Monitor extraction/recycling
        3. Activate emergency measures if needed
        4. Update state
        """
        # Reset state
        self.state = WaterState()

        # Get current water level
        potable_level = self.get_potable_water_level()
        self.state.total_potable_l = potable_level

        # Count operational RSV pods
        self.state.rsv_pods_operational = sum(
            1 for e in self.rsv_extractors if e.is_operational
        )

        # Calculate extraction rate
        self.state.extraction_rate_l_per_tick = sum(
            e.extraction_rate_per_tick
            for e in self.rsv_extractors if e.is_operational
        )

        # Calculate recycling rate
        self.state.recycling_rate_l_per_tick = sum(
            r.processed_this_tick
            for r in self.recyclers if r.is_operational
        )

        # Check for water emergencies
        self._check_water_emergency(potable_level)

        # Get grey water level
        grey_store = self.stores.get("Grey_Water")
        self.state.total_grey_l = grey_store.current_level if grey_store else 0.0

        # Get wall reserve level
        if self.wall_reserve:
            self.state.total_reserve_l = self.wall_reserve.current_level

        return self.state

    def _check_water_emergency(self, current_level: float):
        """Check and respond to water shortage situations."""

        # Level 1: Low water - conservation mode
        if current_level < self.low_water_threshold:
            logger.warning(f"LOW WATER: {current_level:.0f}L - conservation mode")
            self.state.emergency_mode = True

        # Level 2: Critical - activate H2 combustion
        if current_level < self.critical_water_threshold:
            logger.error(f"CRITICAL WATER: {current_level:.0f}L - activating H2 burn")
            if self.h2_combuster and not self.h2_combuster.is_active:
                self.h2_combuster.activate()
            self.state.using_h2_burn = True

        # Level 3: Emergency - tap wall reserve
        if current_level < self.emergency_water_threshold:
            logger.error(f"EMERGENCY WATER: {current_level:.0f}L - tapping wall reserve!")
            if self.wall_reserve and self.wall_reserve.current_level > 0:
                # Draw enough to get above emergency threshold
                needed = self.emergency_water_threshold - current_level + 50
                drawn = self.wall_reserve.tap_reserve(needed)
                self.state.using_wall_reserve = True
                logger.warning(f"Drew {drawn:.0f}L from wall reserve")

        # Deactivate H2 burn if water restored
        if current_level > self.critical_water_threshold * 2:
            if self.h2_combuster and self.h2_combuster.is_active:
                self.h2_combuster.deactivate()

        # Exit emergency mode if water restored
        if current_level > self.low_water_threshold * 1.5:
            self.state.emergency_mode = False

    def handle_rsv_failure(self, rsv_index: int):
        """Handle failure of an RSV extractor."""
        if rsv_index < len(self.rsv_extractors):
            failed = self.rsv_extractors[rsv_index]
            failed.inject_malfunction(1.0, 0)  # Total failure, no auto-repair

            # Check if we still have redundancy
            operational = sum(1 for e in self.rsv_extractors if e.is_operational)
            if operational == 0:
                logger.error("ALL RSV EXTRACTORS FAILED - water supply interrupted!")
            else:
                logger.warning(f"RSV {rsv_index+1} failed, {operational} remaining")

    def handle_water_restriction(self, reduction_factor: float):
        """
        Handle water restriction event.

        Args:
            reduction_factor: 0.0 to 1.0, fraction to reduce consumption
        """
        # Reduce extraction rate
        for extractor in self.rsv_extractors:
            extractor.efficiency *= (1 - reduction_factor)

        logger.warning(f"Water restricted by {reduction_factor*100:.0f}%")

    def restore_water_supply(self):
        """Restore normal water operations."""
        # Restore extraction efficiency
        for extractor in self.rsv_extractors:
            extractor.efficiency = 1.0
            if not extractor.is_operational and not extractor.has_malfunction:
                extractor.start()

        # Deactivate emergency systems
        if self.h2_combuster and self.h2_combuster.is_active:
            self.h2_combuster.deactivate()

        logger.info("Water supply restored to normal")

    def get_status(self) -> Dict:
        """Get current water system status."""
        return {
            "total_potable_l": self.state.total_potable_l,
            "total_grey_l": self.state.total_grey_l,
            "total_reserve_l": self.state.total_reserve_l,
            "extraction_rate_l_per_tick": self.state.extraction_rate_l_per_tick,
            "recycling_rate_l_per_tick": self.state.recycling_rate_l_per_tick,
            "rsv_pods_operational": self.state.rsv_pods_operational,
            "emergency_mode": self.state.emergency_mode,
            "using_h2_burn": self.state.using_h2_burn,
            "using_wall_reserve": self.state.using_wall_reserve,
            "daily_requirement_l": self.get_daily_requirement(),
            "extraction_capacity_l_per_day": self.get_total_extraction_capacity(),
        }
