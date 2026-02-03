"""
Mars to Table — Grain POD
Grain and flour production system (POD 7).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import FOOD, POD, Priority

logger = logging.getLogger(__name__)


class GrainType(Enum):
    """Types of grain crops."""
    WHEAT = auto()        # Primary bread grain
    AMARANTH = auto()     # High protein pseudo-grain
    BUCKWHEAT = auto()    # Gluten-free, fast growing
    QUINOA = auto()       # Complete protein
    RICE = auto()         # Staple grain


@dataclass
class GrainSpec:
    """Specification for a grain crop type."""
    grain_type: GrainType
    name: str
    growth_cycle_days: int
    yield_kg_per_m2: float  # Grain yield per cycle
    flour_conversion: float  # kg flour per kg grain
    calorie_density_kcal_per_kg: float
    protein_percent: float
    water_l_per_m2_per_day: float

    @property
    def yield_per_day(self) -> float:
        """Average grain yield per m² per day."""
        return self.yield_kg_per_m2 / self.growth_cycle_days

    @property
    def flour_per_day(self) -> float:
        """Average flour production per m² per day."""
        return self.yield_per_day * self.flour_conversion


# Standard grain specifications
GRAIN_SPECS: Dict[GrainType, GrainSpec] = {
    GrainType.WHEAT: GrainSpec(
        GrainType.WHEAT, "Wheat", 120, 0.8, 0.72, 3640, 12.0, 4.0
    ),
    GrainType.AMARANTH: GrainSpec(
        GrainType.AMARANTH, "Amaranth", 90, 0.5, 0.85, 3710, 14.0, 3.0
    ),
    GrainType.BUCKWHEAT: GrainSpec(
        GrainType.BUCKWHEAT, "Buckwheat", 75, 0.4, 0.80, 3430, 13.0, 3.5
    ),
    GrainType.QUINOA: GrainSpec(
        GrainType.QUINOA, "Quinoa", 100, 0.35, 0.90, 3680, 14.0, 4.0
    ),
    GrainType.RICE: GrainSpec(
        GrainType.RICE, "Rice", 130, 0.6, 0.65, 3650, 7.0, 5.0
    ),
}


@dataclass
class GrainBed:
    """A grain growing bed within the POD."""
    bed_id: str
    area_m2: float
    grain_spec: GrainSpec

    # Growth tracking
    planted_tick: int = 0
    growth_progress: float = 0.0
    health: float = 1.0

    # Production tracking
    total_harvests: int = 0
    total_grain_kg: float = 0.0
    total_flour_kg: float = 0.0

    def get_days_growing(self, current_tick: int) -> float:
        """Get days since planting."""
        ticks_growing = current_tick - self.planted_tick
        return ticks_growing / 24

    def update_progress(self, current_tick: int):
        """Update growth progress."""
        days = self.get_days_growing(current_tick)
        self.growth_progress = min(1.0, days / self.grain_spec.growth_cycle_days)

    def is_ready_to_harvest(self) -> bool:
        """Check if grain is ready for harvest."""
        return self.growth_progress >= 1.0

    def harvest(self, current_tick: int) -> tuple:
        """
        Harvest grain and reset for next cycle.

        Returns:
            Tuple of (grain_kg, flour_kg)
        """
        grain_kg = self.grain_spec.yield_kg_per_m2 * self.area_m2 * self.health
        flour_kg = grain_kg * self.grain_spec.flour_conversion

        self.total_harvests += 1
        self.total_grain_kg += grain_kg
        self.total_flour_kg += flour_kg

        # Reset for next cycle
        self.planted_tick = current_tick
        self.growth_progress = 0.0

        return grain_kg, flour_kg


class GrainMill(Module):
    """
    Grain milling system.

    Converts harvested grain into flour.
    Located within the Grain POD.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 capacity_kg_per_day: float = 10.0):

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=2.0,  # Small electric mill
            consumes=[
                ResourceFlow(ResourceType.BIOMASS_EDIBLE, capacity_kg_per_day / 24, "Grain_Storage", required=True),
            ],
            produces=[
                ResourceFlow(ResourceType.GRAIN_FLOUR, 0.0, "Flour_Storage"),
            ],
            efficiency=0.95  # 5% loss in milling
        )
        super().__init__(spec, store_manager)

        self.capacity_kg_per_day = capacity_kg_per_day
        self.grain_processed = 0.0
        self.flour_produced = 0.0

    def process_tick(self) -> Dict:
        """Mill grain into flour."""
        # Get grain input
        grain_flow = next((f for f in self.spec.consumes
                          if f.resource_type == ResourceType.BIOMASS_EDIBLE), None)

        flour_produced = 0.0
        if grain_flow and grain_flow.actual_flow > 0:
            # Average 75% flour conversion
            flour_produced = grain_flow.actual_flow * 0.75 * self.effective_efficiency

            # Add to flour storage
            flour_store = self.stores.get("Flour_Storage")
            if flour_store:
                flour_store.add(flour_produced)

            self.grain_processed += grain_flow.actual_flow
            self.flour_produced += flour_produced

        return {
            "grain_processed_kg": grain_flow.actual_flow if grain_flow else 0,
            "flour_produced_kg": flour_produced,
            "total_flour_kg": self.flour_produced,
        }


class GrainPOD(Module):
    """
    Grain production POD (POD 7).

    Grows grain crops and mills them into flour.

    Target: 5.5 kg flour/day for 15 crew
    - ~365g flour per person per day
    - Used for bread, pasta, tortillas, etc.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 growing_area_m2: float = None):

        area = growing_area_m2 or FOOD.grain_area_m2

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=28.0,  # LEDs, irrigation, mill
            consumes=[
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=True),
                ResourceFlow(ResourceType.NUTRIENTS_N, 0.0, "Nutrients_N", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.GRAIN_FLOUR, 0.0, "Flour_Storage"),
                ResourceFlow(ResourceType.OXYGEN, 0.0, "Oxygen"),
                ResourceFlow(ResourceType.BIOMASS_INEDIBLE, 0.0, "Crop_Waste"),  # Straw
            ],
            startup_ticks=1,
            efficiency=1.0
        )
        super().__init__(spec, store_manager)

        self.total_area_m2 = area
        self.beds: List[GrainBed] = []

        # Integrated grain mill
        self.mill: Optional[GrainMill] = None

        # Production tracking
        self.total_grain_kg = 0.0
        self.total_flour_kg = 0.0
        self.daily_flour_kg = 0.0

        # Target production
        self.daily_target_flour_kg = FOOD.flour_yield_kg_per_day

    def setup_default_allocation(self):
        """Set up default grain crop allocation."""
        # Mix of grains for nutritional variety
        allocation = {
            GrainType.WHEAT: self.total_area_m2 * 0.40,      # Primary bread grain
            GrainType.AMARANTH: self.total_area_m2 * 0.25,   # High protein
            GrainType.BUCKWHEAT: self.total_area_m2 * 0.20,  # Fast, gluten-free
            GrainType.QUINOA: self.total_area_m2 * 0.15,     # Complete protein
        }

        bed_id = 0
        for grain_type, area in allocation.items():
            if area <= 0:
                continue

            grain_spec = GRAIN_SPECS.get(grain_type)
            if not grain_spec:
                continue

            # Create multiple beds for rotation
            beds_per_type = max(1, grain_spec.growth_cycle_days // 15)
            area_per_bed = area / beds_per_type

            for i in range(beds_per_type):
                bed = GrainBed(
                    bed_id=f"{self.name}_bed_{bed_id}",
                    area_m2=area_per_bed,
                    grain_spec=grain_spec,
                )
                # Stagger planting times for continuous harvest
                bed.planted_tick = -i * 24 * (grain_spec.growth_cycle_days // beds_per_type)
                self.beds.append(bed)
                bed_id += 1

        # Set up grain mill
        self.mill = GrainMill(f"{self.name}_Mill", self.stores, capacity_kg_per_day=10.0)
        self.mill.start()

        logger.info(f"{self.name}: Set up {len(self.beds)} grain beds, "
                   f"total area {sum(b.area_m2 for b in self.beds):.0f} m²")

    def get_water_requirement(self) -> float:
        """Get current water requirement per tick."""
        total = 0.0
        for bed in self.beds:
            daily = bed.grain_spec.water_l_per_m2_per_day * bed.area_m2
            total += daily / 24
        return total

    def process_tick(self) -> Dict:
        """Process one tick of grain growth and milling."""
        current_tick = self.ticks_operational

        # Consume water
        water_needed = self.get_water_requirement()
        water_store = self.stores.get("Potable_Water")
        water_available = 0.0
        if water_store:
            water_available = water_store.remove(water_needed)

        # Update health based on water
        water_factor = water_available / water_needed if water_needed > 0 else 0
        for bed in self.beds:
            bed.health = min(1.0, bed.health * 0.95 + water_factor * 0.05)

        # Produce oxygen
        o2_rate = 0.008 * self.total_area_m2 / 24
        o2_store = self.stores.get("Oxygen")
        if o2_store:
            o2_store.add(o2_rate * self.effective_efficiency)

        # Check for harvests
        grain_total = 0.0
        flour_total = 0.0

        for bed in self.beds:
            bed.update_progress(current_tick)

            if bed.is_ready_to_harvest():
                grain_kg, flour_kg = bed.harvest(current_tick)
                grain_total += grain_kg
                flour_total += flour_kg

                # Add flour directly to storage
                flour_store = self.stores.get("Flour_Storage")
                if flour_store:
                    flour_store.add(flour_kg)

                # Generate straw waste (~1.5x grain weight)
                waste_store = self.stores.get("Crop_Waste")
                if waste_store:
                    waste_store.add(grain_kg * 1.5)

                logger.debug(f"{self.name}: Harvested {grain_kg:.1f} kg {bed.grain_spec.name}, "
                           f"produced {flour_kg:.1f} kg flour")

        self.total_grain_kg += grain_total
        self.total_flour_kg += flour_total
        self.daily_flour_kg += flour_total

        # Process any grain through mill (if we have intermediate storage)
        mill_metrics = {}
        if self.mill and self.mill.is_operational:
            self.mill.tick()
            mill_metrics = self.mill.process_tick()

        return {
            "beds_count": len(self.beds),
            "total_area_m2": self.total_area_m2,
            "grain_harvested_kg": grain_total,
            "flour_produced_kg": flour_total,
            "daily_flour_kg": self.daily_flour_kg,
            "daily_target_flour_kg": self.daily_target_flour_kg,
            "water_used_l": water_available,
            "avg_health": sum(b.health for b in self.beds) / len(self.beds) if self.beds else 0,
            "mill": mill_metrics,
        }

    def reset_daily_counters(self):
        """Reset daily tracking counters."""
        self.daily_flour_kg = 0.0

    def get_expected_daily_flour(self) -> float:
        """Get expected daily flour production at full health."""
        total = 0.0
        for bed in self.beds:
            total += bed.grain_spec.flour_per_day * bed.area_m2
        return total

    def get_status(self) -> Dict:
        """Get current POD status."""
        beds_by_grain = {}
        for grain_type in GrainType:
            beds_by_grain[grain_type.name] = sum(
                b.area_m2 for b in self.beds if b.grain_spec.grain_type == grain_type
            )

        return {
            "name": self.name,
            "state": self.state.name,
            "total_area_m2": self.total_area_m2,
            "beds_count": len(self.beds),
            "beds_by_grain": beds_by_grain,
            "total_grain_kg": self.total_grain_kg,
            "total_flour_kg": self.total_flour_kg,
            "daily_flour_kg": self.daily_flour_kg,
            "daily_target_flour_kg": self.daily_target_flour_kg,
            "expected_daily_flour_kg": self.get_expected_daily_flour(),
            "meeting_target": self.daily_flour_kg >= self.daily_target_flour_kg * 0.9,
        }
