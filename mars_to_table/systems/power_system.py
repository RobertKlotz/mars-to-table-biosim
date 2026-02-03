"""
Mars to Table — Power System
Solar arrays, fuel cells, and biogas generation with automatic failover.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging
import math

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import POWER, MISSION, Priority

logger = logging.getLogger(__name__)


class PowerSource(Enum):
    """Power generation source types."""
    SOLAR = auto()
    FUEL_CELL = auto()
    BIOGAS = auto()


@dataclass
class PowerState:
    """Current state of the power system."""
    solar_output_kw: float = 0.0
    fuel_cell_output_kw: float = 0.0
    biogas_output_kw: float = 0.0
    total_generation_kw: float = 0.0
    total_demand_kw: float = 0.0
    deficit_kw: float = 0.0
    is_day: bool = True
    dust_storm_factor: float = 1.0  # 1.0 = clear, 0.0 = total blackout
    modules_shed: List[str] = field(default_factory=list)


class SolarArray(Module):
    """
    iROSA-style solar array for primary power generation.

    Output varies with:
    - Day/night cycle (Mars sol ~24h 37m)
    - Dust storm conditions
    - Panel degradation over time
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 array_area_m2: float = None, efficiency: float = None):

        area = array_area_m2 or POWER.solar_array_area_m2
        eff = efficiency or POWER.solar_efficiency

        spec = ModuleSpec(
            name=name,
            priority=Priority.CRITICAL,
            power_consumption_kw=0.0,  # Generates, doesn't consume
            efficiency=eff
        )
        super().__init__(spec, store_manager)

        self.array_area_m2 = area
        self.solar_constant = POWER.mars_solar_constant_w_m2
        self.degradation_rate = 0.0001  # Per sol, ~3.6% per year
        self.current_degradation = 1.0

        # Dust storm factor (can be set externally)
        self.dust_factor = 1.0

        # Time tracking for day/night
        self.current_hour = 0

    @property
    def peak_output_kw(self) -> float:
        """Maximum output at noon, clear conditions."""
        base = self.array_area_m2 * self.solar_constant * self.efficiency / 1000
        return base * self.current_degradation

    def get_solar_factor(self, hour: int) -> float:
        """
        Calculate solar intensity factor based on hour of sol.

        Uses cosine curve: peak at noon (hour 12), zero at night.
        Mars sol is ~24.6 hours, we use 24 ticks.
        """
        # Assume sunrise at hour 6, sunset at hour 18
        if hour < 6 or hour >= 18:
            return 0.0

        # Cosine curve peaks at noon (hour 12)
        # Map hour 6-18 to 0-pi for half cosine
        angle = (hour - 6) * math.pi / 12
        return math.sin(angle)

    def set_hour(self, hour: int):
        """Update current hour for day/night calculation."""
        self.current_hour = hour

    def set_dust_storm(self, factor: float):
        """Set dust storm reduction factor (0.0 to 1.0)."""
        self.dust_factor = max(0.0, min(1.0, factor))

    def process_tick(self) -> Dict:
        """Generate power based on current conditions."""
        solar_factor = self.get_solar_factor(self.current_hour)
        output_kw = self.peak_output_kw * solar_factor * self.dust_factor

        # Add to power store
        power_store = self.stores.get("Power")
        if power_store:
            power_store.add(output_kw)

        return {
            "output_kw": output_kw,
            "solar_factor": solar_factor,
            "dust_factor": self.dust_factor,
            "is_day": solar_factor > 0,
            "degradation": self.current_degradation,
        }

    def apply_daily_degradation(self):
        """Apply panel degradation (call once per sol)."""
        self.current_degradation *= (1 - self.degradation_rate)


class FuelCell(Module):
    """
    H2/O2 fuel cell for backup power.

    Consumes hydrogen and oxygen to produce electricity and water.
    Used during night, dust storms, or power shortages.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 capacity_kw: float = None):

        cap = capacity_kw or POWER.fuel_cell_capacity_kw

        spec = ModuleSpec(
            name=name,
            priority=Priority.CRITICAL,
            power_consumption_kw=0.0,
            consumes=[
                # H2 consumption: ~0.05 kg/kWh at 60% efficiency
                ResourceFlow(ResourceType.HYDROGEN, 0.05, "Hydrogen", required=True),
                # O2 consumption: ~0.4 kg/kWh
                ResourceFlow(ResourceType.OXYGEN, 0.4, "Oxygen", required=True),
            ],
            produces=[
                # Water byproduct: ~0.45 kg/kWh
                ResourceFlow(ResourceType.POTABLE_WATER, 0.45, "Potable_Water"),
            ],
            efficiency=POWER.fuel_cell_efficiency
        )
        super().__init__(spec, store_manager)

        self.capacity_kw = cap
        self.requested_output_kw = 0.0
        self.actual_output_kw = 0.0

    def request_power(self, kw: float):
        """Request power output from fuel cell."""
        self.requested_output_kw = min(kw, self.capacity_kw)

    def process_tick(self) -> Dict:
        """Generate requested power if resources available."""
        if self.requested_output_kw <= 0:
            self.actual_output_kw = 0.0
            return {"output_kw": 0.0, "requested_kw": 0.0}

        # Check if we got our required inputs
        h2_flow = next((f for f in self.spec.consumes
                       if f.resource_type == ResourceType.HYDROGEN), None)

        if h2_flow and h2_flow.actual_flow > 0:
            # Scale output by how much H2 we actually got
            h2_needed = self.requested_output_kw * 0.05
            efficiency_factor = h2_flow.actual_flow / h2_needed if h2_needed > 0 else 0
            self.actual_output_kw = self.requested_output_kw * efficiency_factor
        else:
            self.actual_output_kw = 0.0

        # Add to power store
        power_store = self.stores.get("Power")
        if power_store and self.actual_output_kw > 0:
            power_store.add(self.actual_output_kw)

        # Reset request for next tick
        requested = self.requested_output_kw
        self.requested_output_kw = 0.0

        return {
            "output_kw": self.actual_output_kw,
            "requested_kw": requested,
            "capacity_kw": self.capacity_kw,
        }


class BiogasGenerator(Module):
    """
    Solid Oxide Fuel Cell running on biogas (methane from waste digestion).

    Provides continuous low-level backup power.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 capacity_kw: float = None):

        cap = capacity_kw or POWER.biogas_capacity_kw

        spec = ModuleSpec(
            name=name,
            priority=Priority.HIGH,
            power_consumption_kw=0.0,
            consumes=[
                # Methane consumption: ~0.2 kg/kWh
                ResourceFlow(ResourceType.METHANE, 0.2, "Biogas", required=True),
            ],
            efficiency=0.50  # SOFC efficiency
        )
        super().__init__(spec, store_manager)

        self.capacity_kw = cap
        self.actual_output_kw = 0.0

    def process_tick(self) -> Dict:
        """Generate power from biogas."""
        # Check methane supply
        methane_flow = next((f for f in self.spec.consumes
                           if f.resource_type == ResourceType.METHANE), None)

        if methane_flow and methane_flow.actual_flow > 0:
            # Scale output by available methane
            methane_needed = self.capacity_kw * 0.2
            efficiency_factor = methane_flow.actual_flow / methane_needed if methane_needed > 0 else 0
            self.actual_output_kw = self.capacity_kw * efficiency_factor * self.effective_efficiency
        else:
            self.actual_output_kw = 0.0

        # Add to power store
        power_store = self.stores.get("Power")
        if power_store and self.actual_output_kw > 0:
            power_store.add(self.actual_output_kw)

        return {
            "output_kw": self.actual_output_kw,
            "capacity_kw": self.capacity_kw,
        }


class PowerSystem:
    """
    Integrated power management system.

    Coordinates:
    - Solar arrays (primary)
    - Fuel cells (backup)
    - Biogas SOFC (supplemental)
    - Load shedding (emergency)

    Implements automatic failover when primary power insufficient.
    """

    def __init__(self, store_manager: StoreManager, module_manager: ModuleManager):
        self.stores = store_manager
        self.modules = module_manager

        # Power sources
        self.solar_arrays: List[SolarArray] = []
        self.fuel_cells: List[FuelCell] = []
        self.biogas_generators: List[BiogasGenerator] = []

        # State
        self.state = PowerState()
        self.current_hour = 0

        # Thresholds
        self.fuel_cell_activation_threshold = 0.8  # Activate if demand > 80% of solar
        self.load_shedding_threshold = 0.95  # Shed if demand > 95% of total capacity

        # History
        self.hourly_generation: List[float] = []
        self.hourly_demand: List[float] = []

    def add_solar_array(self, array: SolarArray):
        """Register a solar array."""
        self.solar_arrays.append(array)
        self.modules.add_module(array)

    def add_fuel_cell(self, fuel_cell: FuelCell):
        """Register a fuel cell."""
        self.fuel_cells.append(fuel_cell)
        self.modules.add_module(fuel_cell)

    def add_biogas_generator(self, generator: BiogasGenerator):
        """Register a biogas generator."""
        self.biogas_generators.append(generator)
        self.modules.add_module(generator)

    def initialize_default_system(self):
        """Set up the default power system from config."""
        # Main solar array
        solar = SolarArray("Solar_Array_Main", self.stores)
        solar.start()
        self.add_solar_array(solar)

        # Two RSV fuel cells
        for i in range(POWER.num_rsv_pods):
            fc = FuelCell(f"Fuel_Cell_RSV_{i+1}", self.stores, POWER.fuel_cell_capacity_kw)
            fc.start()
            self.add_fuel_cell(fc)

        # Biogas SOFC
        biogas = BiogasGenerator("Biogas_SOFC", self.stores, POWER.biogas_capacity_kw)
        biogas.start()
        self.add_biogas_generator(biogas)

        logger.info(f"Power system initialized: {len(self.solar_arrays)} solar, "
                   f"{len(self.fuel_cells)} fuel cells, {len(self.biogas_generators)} biogas")

    def set_hour(self, hour: int):
        """Update hour for all solar arrays."""
        self.current_hour = hour
        for array in self.solar_arrays:
            array.set_hour(hour)

    def set_dust_storm(self, factor: float):
        """Set dust storm factor for all solar arrays."""
        self.state.dust_storm_factor = factor
        for array in self.solar_arrays:
            array.set_dust_storm(factor)

    def get_total_solar_capacity(self) -> float:
        """Get total potential solar output."""
        return sum(a.peak_output_kw for a in self.solar_arrays if a.is_operational)

    def get_total_fuel_cell_capacity(self) -> float:
        """Get total fuel cell capacity."""
        return sum(fc.capacity_kw for fc in self.fuel_cells if fc.is_operational)

    def get_total_biogas_capacity(self) -> float:
        """Get total biogas capacity."""
        return sum(bg.capacity_kw for bg in self.biogas_generators if bg.is_operational)

    def get_total_capacity(self) -> float:
        """Get total power generation capacity."""
        return (self.get_total_solar_capacity() +
                self.get_total_fuel_cell_capacity() +
                self.get_total_biogas_capacity())

    def tick(self, hour: int) -> PowerState:
        """
        Execute one power system tick.

        1. Update hour for day/night
        2. Calculate demand
        3. Generate solar power
        4. Activate backup if needed
        5. Shed load if still insufficient
        """
        self.set_hour(hour)

        # Reset state
        self.state = PowerState()
        self.state.is_day = hour >= 6 and hour < 18
        self.state.dust_storm_factor = self.solar_arrays[0].dust_factor if self.solar_arrays else 1.0

        # Get power demand from all modules
        self.state.total_demand_kw = self.modules.get_total_power_demand()

        # Calculate expected solar output
        expected_solar = sum(
            a.peak_output_kw * a.get_solar_factor(hour) * a.dust_factor
            for a in self.solar_arrays if a.is_operational
        )
        self.state.solar_output_kw = expected_solar

        # Determine if backup power needed
        deficit = self.state.total_demand_kw - expected_solar

        if deficit > 0:
            # First, try biogas (always running if available)
            biogas_available = sum(
                bg.capacity_kw * bg.effective_efficiency
                for bg in self.biogas_generators if bg.is_operational
            )
            self.state.biogas_output_kw = min(biogas_available, deficit)
            deficit -= self.state.biogas_output_kw

            # Then, activate fuel cells for remaining deficit
            if deficit > 0:
                for fc in self.fuel_cells:
                    if fc.is_operational and deficit > 0:
                        request = min(deficit, fc.capacity_kw)
                        fc.request_power(request)
                        self.state.fuel_cell_output_kw += request
                        deficit -= request

        # Calculate total generation
        self.state.total_generation_kw = (
            self.state.solar_output_kw +
            self.state.fuel_cell_output_kw +
            self.state.biogas_output_kw
        )

        # Check if load shedding needed
        if deficit > 0:
            self.state.deficit_kw = deficit
            available_power = self.state.total_generation_kw
            shed = self.modules.shed_load(available_power)
            self.state.modules_shed = shed

            if shed:
                logger.warning(f"Load shedding: {len(shed)} modules shut down")

        # Record history
        self.hourly_generation.append(self.state.total_generation_kw)
        self.hourly_demand.append(self.state.total_demand_kw)

        return self.state

    def apply_daily_maintenance(self):
        """Apply daily maintenance tasks (call once per sol)."""
        for array in self.solar_arrays:
            array.apply_daily_degradation()

    def get_status(self) -> Dict:
        """Get current power system status."""
        return {
            "solar_output_kw": self.state.solar_output_kw,
            "fuel_cell_output_kw": self.state.fuel_cell_output_kw,
            "biogas_output_kw": self.state.biogas_output_kw,
            "total_generation_kw": self.state.total_generation_kw,
            "total_demand_kw": self.state.total_demand_kw,
            "deficit_kw": self.state.deficit_kw,
            "is_day": self.state.is_day,
            "dust_storm_factor": self.state.dust_storm_factor,
            "modules_shed": self.state.modules_shed,
            "solar_arrays_operational": sum(1 for a in self.solar_arrays if a.is_operational),
            "fuel_cells_operational": sum(1 for fc in self.fuel_cells if fc.is_operational),
            "biogas_operational": sum(1 for bg in self.biogas_generators if bg.is_operational),
        }

    def handle_power_outage(self, severity: float = 1.0):
        """
        Handle power outage event.

        Args:
            severity: 0.0 (minor) to 1.0 (total blackout)
        """
        if severity >= 1.0:
            # Total outage - only fuel cells can save us
            self.set_dust_storm(0.0)
            logger.error("TOTAL POWER OUTAGE - activating all fuel cells")

            for fc in self.fuel_cells:
                if fc.is_operational:
                    fc.request_power(fc.capacity_kw)
        else:
            # Partial outage - reduce solar
            self.set_dust_storm(1.0 - severity)
            logger.warning(f"Partial power outage - solar reduced by {severity*100:.0f}%")

    def restore_power(self):
        """Restore normal power operations."""
        self.set_dust_storm(1.0)
        logger.info("Power restored to normal")
