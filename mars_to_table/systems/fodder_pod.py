"""
Mars to Table — Fodder POD
Livestock feed production system (POD 6).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import FOOD, LIVESTOCK, POD, Priority

logger = logging.getLogger(__name__)


class FodderType(Enum):
    """Types of fodder crops."""
    ALFALFA = auto()       # High protein hay
    BARLEY_GRASS = auto()  # Fast-growing grain grass
    CLOVER = auto()        # Nitrogen-fixing legume
    OAT_GRASS = auto()     # Palatable grass
    SPROUTED_GRAIN = auto()  # Hydroponic sprouts


@dataclass
class FodderSpec:
    """Specification for a fodder crop type."""
    fodder_type: FodderType
    name: str
    growth_cycle_days: int
    yield_kg_per_m2: float  # Fresh weight per cycle
    dry_matter_fraction: float  # Fraction that's dry matter
    protein_percent: float  # Crude protein content
    water_l_per_m2_per_day: float

    @property
    def yield_per_day(self) -> float:
        """Average yield per m² per day (fresh weight)."""
        return self.yield_kg_per_m2 / self.growth_cycle_days

    @property
    def dry_yield_per_day(self) -> float:
        """Average dry matter yield per m² per day."""
        return self.yield_per_day * self.dry_matter_fraction


# Standard fodder specifications
FODDER_SPECS: Dict[FodderType, FodderSpec] = {
    FodderType.ALFALFA: FodderSpec(
        FodderType.ALFALFA, "Alfalfa", 35, 3.0, 0.25, 18.0, 5.0
    ),
    FodderType.BARLEY_GRASS: FodderSpec(
        FodderType.BARLEY_GRASS, "Barley Grass", 7, 1.5, 0.15, 12.0, 4.0
    ),
    FodderType.CLOVER: FodderSpec(
        FodderType.CLOVER, "Clover", 30, 2.5, 0.22, 20.0, 4.5
    ),
    FodderType.OAT_GRASS: FodderSpec(
        FodderType.OAT_GRASS, "Oat Grass", 10, 1.8, 0.18, 10.0, 3.5
    ),
    FodderType.SPROUTED_GRAIN: FodderSpec(
        FodderType.SPROUTED_GRAIN, "Sprouted Grain", 6, 2.0, 0.20, 14.0, 6.0
    ),
}


@dataclass
class FodderBed:
    """A fodder growing bed within the POD."""
    bed_id: str
    area_m2: float
    fodder_spec: FodderSpec

    # Growth tracking
    planted_tick: int = 0
    growth_progress: float = 0.0
    health: float = 1.0

    # Production tracking
    total_harvests: int = 0
    total_yield_kg: float = 0.0

    def get_days_growing(self, current_tick: int) -> float:
        """Get days since planting."""
        ticks_growing = current_tick - self.planted_tick
        return ticks_growing / 24

    def update_progress(self, current_tick: int):
        """Update growth progress."""
        days = self.get_days_growing(current_tick)
        self.growth_progress = min(1.0, days / self.fodder_spec.growth_cycle_days)

    def is_ready_to_harvest(self) -> bool:
        """Check if fodder is ready for harvest."""
        return self.growth_progress >= 1.0

    def harvest(self, current_tick: int) -> float:
        """Harvest fodder and reset for next cycle."""
        yield_kg = self.fodder_spec.yield_kg_per_m2 * self.area_m2 * self.health

        self.total_harvests += 1
        self.total_yield_kg += yield_kg

        # Reset for next cycle
        self.planted_tick = current_tick
        self.growth_progress = 0.0

        return yield_kg


class FodderPOD(Module):
    """
    Fodder production POD for livestock feed (POD 6).

    Grows high-yield fodder crops for goats and chickens.
    Uses continuous harvest rotation for steady feed supply.

    Target: ~29 kg fresh fodder/day to feed:
    - 7 goats @ 2 kg/day = 14 kg
    - 22 chickens @ 0.12 kg/day = 2.6 kg
    - Buffer/waste = ~12 kg
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 growing_area_m2: float = None):

        area = growing_area_m2 or FOOD.fodder_area_m2

        spec = ModuleSpec(
            name=name,
            priority=Priority.HIGH,  # Livestock depends on this
            power_consumption_kw=25.0,  # LEDs, irrigation
            consumes=[
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=True),
                ResourceFlow(ResourceType.NUTRIENTS_N, 0.0, "Nutrients_N", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.FODDER, 0.0, "Fodder_Storage"),
                ResourceFlow(ResourceType.OXYGEN, 0.0, "Oxygen"),
            ],
            startup_ticks=1,
            efficiency=1.0
        )
        super().__init__(spec, store_manager)

        self.total_area_m2 = area
        self.beds: List[FodderBed] = []

        # Production tracking
        self.total_yield_kg = 0.0
        self.daily_yield_kg = 0.0

        # Target production
        self.daily_target_kg = FOOD.fodder_yield_kg_per_m2_per_day * area

    def setup_default_allocation(self):
        """Set up default fodder crop allocation."""
        # Stagger planting for continuous harvest
        allocation = {
            FodderType.BARLEY_GRASS: self.total_area_m2 * 0.35,  # Fast, palatable
            FodderType.SPROUTED_GRAIN: self.total_area_m2 * 0.25,  # Very fast
            FodderType.ALFALFA: self.total_area_m2 * 0.20,  # High protein
            FodderType.OAT_GRASS: self.total_area_m2 * 0.15,  # Good variety
            FodderType.CLOVER: self.total_area_m2 * 0.05,  # Nitrogen fixing
        }

        bed_id = 0
        for fodder_type, area in allocation.items():
            if area <= 0:
                continue

            fodder_spec = FODDER_SPECS.get(fodder_type)
            if not fodder_spec:
                continue

            # Create multiple beds for rotation
            beds_per_type = max(1, int(fodder_spec.growth_cycle_days / 2))
            area_per_bed = area / beds_per_type

            for i in range(beds_per_type):
                bed = FodderBed(
                    bed_id=f"{self.name}_bed_{bed_id}",
                    area_m2=area_per_bed,
                    fodder_spec=fodder_spec,
                )
                # Stagger planting times
                bed.planted_tick = -i * 24 * (fodder_spec.growth_cycle_days // beds_per_type)
                self.beds.append(bed)
                bed_id += 1

        logger.info(f"{self.name}: Set up {len(self.beds)} fodder beds, "
                   f"total area {sum(b.area_m2 for b in self.beds):.0f} m²")

    def get_water_requirement(self) -> float:
        """Get current water requirement per tick."""
        total = 0.0
        for bed in self.beds:
            daily = bed.fodder_spec.water_l_per_m2_per_day * bed.area_m2
            total += daily / 24
        return total

    def process_tick(self) -> Dict:
        """Process one tick of fodder growth."""
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
        harvest_total = 0.0
        for bed in self.beds:
            bed.update_progress(current_tick)

            if bed.is_ready_to_harvest():
                yield_kg = bed.harvest(current_tick)
                harvest_total += yield_kg

                # Add to fodder storage
                fodder_store = self.stores.get("Fodder_Storage")
                if fodder_store:
                    fodder_store.add(yield_kg)

                logger.debug(f"{self.name}: Harvested {yield_kg:.1f} kg {bed.fodder_spec.name}")

        self.total_yield_kg += harvest_total
        self.daily_yield_kg += harvest_total

        return {
            "beds_count": len(self.beds),
            "total_area_m2": self.total_area_m2,
            "harvest_this_tick_kg": harvest_total,
            "daily_yield_kg": self.daily_yield_kg,
            "daily_target_kg": self.daily_target_kg,
            "water_used_l": water_available,
            "avg_health": sum(b.health for b in self.beds) / len(self.beds) if self.beds else 0,
        }

    def reset_daily_counters(self):
        """Reset daily tracking counters."""
        self.daily_yield_kg = 0.0

    def get_status(self) -> Dict:
        """Get current POD status."""
        return {
            "name": self.name,
            "state": self.state.name,
            "total_area_m2": self.total_area_m2,
            "beds_count": len(self.beds),
            "total_yield_kg": self.total_yield_kg,
            "daily_yield_kg": self.daily_yield_kg,
            "daily_target_kg": self.daily_target_kg,
            "meeting_target": self.daily_yield_kg >= self.daily_target_kg * 0.9,
        }
