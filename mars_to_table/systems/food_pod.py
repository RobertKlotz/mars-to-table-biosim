"""
Mars to Table — Food POD
Hydroponic crop production system for human food (PODs 1-5).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging
import math

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import FOOD, POD, MISSION, Priority

logger = logging.getLogger(__name__)


class CropType(Enum):
    """Types of crops grown in food PODs."""
    POTATO = auto()
    SWEET_POTATO = auto()
    TOMATO = auto()
    PEPPER = auto()
    LETTUCE = auto()
    SPINACH = auto()
    BEANS = auto()
    PEAS = auto()
    SOYBEAN = auto()
    HERBS = auto()


class GrowthStage(Enum):
    """Crop growth stages."""
    GERMINATION = auto()
    SEEDLING = auto()
    VEGETATIVE = auto()
    FLOWERING = auto()
    FRUITING = auto()
    HARVEST = auto()


@dataclass
class CropSpec:
    """Specification for a crop type."""
    crop_type: CropType
    name: str
    growth_cycle_days: int  # Days from planting to harvest
    yield_kg_per_m2: float  # Total yield per growth cycle
    calorie_density_kcal_per_kg: float
    water_l_per_m2_per_day: float
    light_hours_per_day: int
    optimal_temp_c: float = 22.0

    # Nutrient requirements (kg per m² per cycle)
    nitrogen_kg_per_m2: float = 0.01
    phosphorus_kg_per_m2: float = 0.005
    potassium_kg_per_m2: float = 0.008

    @property
    def yield_per_day(self) -> float:
        """Average yield per m² per day."""
        return self.yield_kg_per_m2 / self.growth_cycle_days

    @property
    def calories_per_m2_per_day(self) -> float:
        """Average calorie production per m² per day."""
        return self.yield_per_day * self.calorie_density_kcal_per_kg


# Standard crop specifications
CROP_SPECS: Dict[CropType, CropSpec] = {
    CropType.POTATO: CropSpec(
        CropType.POTATO, "Potato", 120, 4.0, 770, 4.0, 14
    ),
    CropType.SWEET_POTATO: CropSpec(
        CropType.SWEET_POTATO, "Sweet Potato", 120, 3.5, 860, 4.0, 14
    ),
    CropType.TOMATO: CropSpec(
        CropType.TOMATO, "Tomato", 80, 5.0, 180, 5.0, 16
    ),
    CropType.PEPPER: CropSpec(
        CropType.PEPPER, "Pepper", 90, 3.0, 200, 4.5, 14
    ),
    CropType.LETTUCE: CropSpec(
        CropType.LETTUCE, "Lettuce", 45, 2.5, 150, 3.0, 12
    ),
    CropType.SPINACH: CropSpec(
        CropType.SPINACH, "Spinach", 40, 2.0, 230, 3.0, 12
    ),
    CropType.BEANS: CropSpec(
        CropType.BEANS, "Beans", 60, 1.5, 310, 4.0, 14
    ),
    CropType.PEAS: CropSpec(
        CropType.PEAS, "Peas", 60, 1.2, 810, 3.5, 14
    ),
    CropType.SOYBEAN: CropSpec(
        CropType.SOYBEAN, "Soybean", 100, 2.0, 1470, 4.5, 14
    ),
    CropType.HERBS: CropSpec(
        CropType.HERBS, "Herbs", 30, 1.0, 300, 2.0, 12
    ),
}


@dataclass
class CropBed:
    """A single crop growing bed within a POD."""
    bed_id: str
    area_m2: float
    crop_spec: CropSpec

    # Growth tracking
    planted_tick: int = 0
    current_stage: GrowthStage = GrowthStage.GERMINATION
    growth_progress: float = 0.0  # 0.0 to 1.0
    health: float = 1.0  # 0.0 to 1.0

    # Accumulated resources this cycle
    water_received: float = 0.0
    light_received: float = 0.0
    nutrients_received: Dict[str, float] = field(default_factory=dict)

    # Production tracking
    total_harvests: int = 0
    total_yield_kg: float = 0.0

    def reset_for_new_cycle(self, current_tick: int):
        """Reset bed for a new growing cycle."""
        self.planted_tick = current_tick
        self.current_stage = GrowthStage.GERMINATION
        self.growth_progress = 0.0
        self.water_received = 0.0
        self.light_received = 0.0
        self.nutrients_received = {"N": 0.0, "P": 0.0, "K": 0.0}

    def get_days_growing(self, current_tick: int) -> float:
        """Get days since planting."""
        ticks_growing = current_tick - self.planted_tick
        return ticks_growing / 24  # 24 ticks per sol

    def update_stage(self, current_tick: int):
        """Update growth stage based on progress."""
        days = self.get_days_growing(current_tick)
        cycle = self.crop_spec.growth_cycle_days

        self.growth_progress = min(1.0, days / cycle)

        if self.growth_progress < 0.1:
            self.current_stage = GrowthStage.GERMINATION
        elif self.growth_progress < 0.25:
            self.current_stage = GrowthStage.SEEDLING
        elif self.growth_progress < 0.5:
            self.current_stage = GrowthStage.VEGETATIVE
        elif self.growth_progress < 0.75:
            self.current_stage = GrowthStage.FLOWERING
        elif self.growth_progress < 1.0:
            self.current_stage = GrowthStage.FRUITING
        else:
            self.current_stage = GrowthStage.HARVEST

    def is_ready_to_harvest(self) -> bool:
        """Check if crop is ready for harvest."""
        return self.current_stage == GrowthStage.HARVEST

    def calculate_yield(self) -> float:
        """Calculate harvest yield based on health and resources."""
        base_yield = self.crop_spec.yield_kg_per_m2 * self.area_m2

        # Reduce yield based on health
        health_factor = self.health

        # Reduce yield if resources were insufficient
        cycle_days = self.crop_spec.growth_cycle_days
        expected_water = self.crop_spec.water_l_per_m2_per_day * self.area_m2 * cycle_days
        water_factor = min(1.0, self.water_received / expected_water) if expected_water > 0 else 0

        # Overall yield factor
        yield_factor = health_factor * water_factor

        return base_yield * yield_factor

    def harvest(self, current_tick: int) -> float:
        """Harvest the crop and reset for next cycle."""
        yield_kg = self.calculate_yield()

        self.total_harvests += 1
        self.total_yield_kg += yield_kg

        # Reset for next cycle
        self.reset_for_new_cycle(current_tick)

        return yield_kg


class FoodPOD(Module):
    """
    Food production POD for human crops.

    Each POD contains multiple growing beds with different crops.
    Uses vertical hydroponic racks for 3x effective growing area.

    POD specs:
    - 3 decks × 38 m² per deck = 114 m² base
    - Vertical racks multiply by ~3.2x = 361 m² effective
    """

    def __init__(self, name: str, pod_number: int, store_manager: StoreManager,
                 growing_area_m2: float = None):

        area = growing_area_m2 or FOOD.growing_area_per_pod_m2

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=30.0,  # LEDs, pumps, climate control
            consumes=[
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=True),
                ResourceFlow(ResourceType.NUTRIENTS_N, 0.0, "Nutrients_N", required=True),
                ResourceFlow(ResourceType.NUTRIENTS_P, 0.0, "Nutrients_P", required=False),
                ResourceFlow(ResourceType.NUTRIENTS_K, 0.0, "Nutrients_K", required=False),
                ResourceFlow(ResourceType.CO2, 0.0, "CO2_Store", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.BIOMASS_EDIBLE, 0.0, "Food_Storage"),
                ResourceFlow(ResourceType.OXYGEN, 0.0, "Oxygen"),
                ResourceFlow(ResourceType.BIOMASS_INEDIBLE, 0.0, "Crop_Waste"),
            ],
            startup_ticks=1,
            efficiency=1.0
        )
        super().__init__(spec, store_manager)

        self.pod_number = pod_number
        self.total_area_m2 = area

        # Growing beds
        self.beds: List[CropBed] = []

        # Environment
        self.temperature_c = 22.0
        self.humidity_percent = 70.0
        self.co2_ppm = 1000  # Elevated for plant growth
        self.light_on = True

        # Production tracking
        self.total_yield_kg = 0.0
        self.total_calories = 0.0
        self.harvests_today = 0

        # Daily tracking (reset each sol)
        self.daily_water_used = 0.0
        self.daily_yield_kg = 0.0
        self.daily_calories = 0.0

    def setup_crop_allocation(self, allocation: Dict[CropType, float]):
        """
        Set up growing beds with specified crop allocation.

        Args:
            allocation: Dict mapping CropType to area in m²
        """
        self.beds.clear()
        bed_id = 0

        for crop_type, area in allocation.items():
            if area <= 0:
                continue

            crop_spec = CROP_SPECS.get(crop_type)
            if not crop_spec:
                logger.warning(f"Unknown crop type: {crop_type}")
                continue

            bed = CropBed(
                bed_id=f"{self.name}_bed_{bed_id}",
                area_m2=area,
                crop_spec=crop_spec,
            )
            self.beds.append(bed)
            bed_id += 1

        logger.info(f"{self.name}: Set up {len(self.beds)} crop beds, "
                   f"total area {sum(b.area_m2 for b in self.beds):.0f} m²")

    def setup_default_allocation(self):
        """Set up default balanced crop allocation."""
        # Balanced allocation across crop types
        area_per_crop = self.total_area_m2 / 8  # 8 main crop types

        allocation = {
            CropType.POTATO: area_per_crop * 1.5,      # More starches
            CropType.SWEET_POTATO: area_per_crop,
            CropType.TOMATO: area_per_crop,
            CropType.LETTUCE: area_per_crop * 0.8,
            CropType.SPINACH: area_per_crop * 0.8,
            CropType.BEANS: area_per_crop,
            CropType.PEAS: area_per_crop * 0.5,
            CropType.SOYBEAN: area_per_crop * 0.9,
            CropType.HERBS: area_per_crop * 0.5,
        }

        self.setup_crop_allocation(allocation)

    def get_water_requirement(self) -> float:
        """Get current water requirement per tick."""
        total = 0.0
        for bed in self.beds:
            # Daily requirement / 24 ticks
            daily = bed.crop_spec.water_l_per_m2_per_day * bed.area_m2
            total += daily / 24
        return total

    def get_nutrient_requirement(self) -> Dict[str, float]:
        """Get current nutrient requirements per tick."""
        n_total = 0.0
        p_total = 0.0
        k_total = 0.0

        for bed in self.beds:
            # Convert per-cycle requirement to per-tick
            cycle_days = bed.crop_spec.growth_cycle_days
            ticks_per_cycle = cycle_days * 24

            n_total += (bed.crop_spec.nitrogen_kg_per_m2 * bed.area_m2) / ticks_per_cycle
            p_total += (bed.crop_spec.phosphorus_kg_per_m2 * bed.area_m2) / ticks_per_cycle
            k_total += (bed.crop_spec.potassium_kg_per_m2 * bed.area_m2) / ticks_per_cycle

        return {"N": n_total, "P": p_total, "K": k_total}

    def _consume_resources(self, current_tick: int):
        """Consume water and nutrients for all beds."""
        water_needed = self.get_water_requirement()
        nutrients_needed = self.get_nutrient_requirement()

        # Get water
        water_store = self.stores.get("Potable_Water")
        water_available = 0.0
        if water_store:
            water_available = water_store.remove(water_needed)
            self.daily_water_used += water_available

        # Get nutrients
        n_store = self.stores.get("Nutrients_N")
        p_store = self.stores.get("Nutrients_P")
        k_store = self.stores.get("Nutrients_K")

        n_available = n_store.remove(nutrients_needed["N"]) if n_store else 0
        p_available = p_store.remove(nutrients_needed["P"]) if p_store else 0
        k_available = k_store.remove(nutrients_needed["K"]) if k_store else 0

        # Distribute to beds proportionally
        for bed in self.beds:
            bed_fraction = bed.area_m2 / self.total_area_m2 if self.total_area_m2 > 0 else 0

            bed.water_received += water_available * bed_fraction
            bed.nutrients_received["N"] = bed.nutrients_received.get("N", 0) + n_available * bed_fraction
            bed.nutrients_received["P"] = bed.nutrients_received.get("P", 0) + p_available * bed_fraction
            bed.nutrients_received["K"] = bed.nutrients_received.get("K", 0) + k_available * bed_fraction

            # Update health based on resource availability
            water_factor = water_available / water_needed if water_needed > 0 else 0
            bed.health = min(1.0, bed.health * 0.99 + water_factor * 0.01)  # Slow health adjustment

    def _produce_oxygen(self):
        """Produce oxygen from photosynthesis."""
        # Plants produce ~0.01 kg O2 per m² per day during light hours
        if self.light_on:
            o2_rate = 0.01 * self.total_area_m2 / 24  # Per tick
            o2_store = self.stores.get("Oxygen")
            if o2_store:
                o2_store.add(o2_rate * self.effective_efficiency)

    def _check_harvests(self, current_tick: int) -> float:
        """Check and process any ready harvests."""
        total_harvest = 0.0

        for bed in self.beds:
            bed.update_stage(current_tick)

            if bed.is_ready_to_harvest():
                yield_kg = bed.harvest(current_tick)
                total_harvest += yield_kg

                calories = yield_kg * bed.crop_spec.calorie_density_kcal_per_kg
                self.total_calories += calories
                self.daily_calories += calories

                # Add to food storage
                food_store = self.stores.get("Food_Storage")
                if food_store:
                    food_store.add(yield_kg)

                # Generate crop waste (inedible biomass ~30% of yield)
                waste_store = self.stores.get("Crop_Waste")
                if waste_store:
                    waste_store.add(yield_kg * 0.3)

                logger.info(f"{self.name}: Harvested {yield_kg:.1f} kg {bed.crop_spec.name} "
                           f"({calories:.0f} kcal)")
                self.harvests_today += 1

        self.total_yield_kg += total_harvest
        self.daily_yield_kg += total_harvest

        return total_harvest

    def process_tick(self) -> Dict:
        """Process one tick of crop growth."""
        current_tick = self.ticks_operational

        # Consume resources
        self._consume_resources(current_tick)

        # Produce oxygen
        self._produce_oxygen()

        # Check for harvests
        harvest_kg = self._check_harvests(current_tick)

        # Calculate current production rate
        avg_yield_per_day = sum(
            bed.crop_spec.yield_per_day * bed.area_m2 * bed.health
            for bed in self.beds
        )
        avg_calories_per_day = sum(
            bed.crop_spec.calories_per_m2_per_day * bed.area_m2 * bed.health
            for bed in self.beds
        )

        return {
            "pod_number": self.pod_number,
            "beds_count": len(self.beds),
            "total_area_m2": self.total_area_m2,
            "harvest_this_tick_kg": harvest_kg,
            "daily_yield_kg": self.daily_yield_kg,
            "daily_calories": self.daily_calories,
            "expected_yield_per_day_kg": avg_yield_per_day,
            "expected_calories_per_day": avg_calories_per_day,
            "water_used_today_l": self.daily_water_used,
            "harvests_today": self.harvests_today,
            "avg_health": sum(b.health for b in self.beds) / len(self.beds) if self.beds else 0,
        }

    def reset_daily_counters(self):
        """Reset daily tracking counters (call at start of each sol)."""
        self.daily_water_used = 0.0
        self.daily_yield_kg = 0.0
        self.daily_calories = 0.0
        self.harvests_today = 0

    def get_status(self) -> Dict:
        """Get current POD status."""
        beds_by_stage = {}
        for stage in GrowthStage:
            beds_by_stage[stage.name] = sum(1 for b in self.beds if b.current_stage == stage)

        return {
            "name": self.name,
            "pod_number": self.pod_number,
            "state": self.state.name,
            "total_area_m2": self.total_area_m2,
            "beds_count": len(self.beds),
            "beds_by_stage": beds_by_stage,
            "total_yield_kg": self.total_yield_kg,
            "total_calories": self.total_calories,
            "temperature_c": self.temperature_c,
            "humidity_percent": self.humidity_percent,
            "light_on": self.light_on,
        }


class FoodPODManager:
    """
    Manages multiple food PODs.

    Coordinates production across PODs 1-5 for human food.
    """

    def __init__(self, store_manager: StoreManager, module_manager: ModuleManager):
        self.stores = store_manager
        self.modules = module_manager
        self.pods: List[FoodPOD] = []

        # Aggregate tracking
        self.total_daily_yield_kg = 0.0
        self.total_daily_calories = 0.0

    def add_pod(self, pod: FoodPOD):
        """Register a food POD."""
        self.pods.append(pod)
        self.modules.add_module(pod)

    def initialize_default_pods(self, num_pods: int = 5):
        """Set up default food PODs."""
        for i in range(num_pods):
            pod = FoodPOD(
                f"Food_POD_{i+1}",
                pod_number=i+1,
                store_manager=self.stores,
                growing_area_m2=FOOD.growing_area_per_pod_m2
            )
            pod.setup_default_allocation()
            pod.start()
            self.add_pod(pod)

        total_area = sum(p.total_area_m2 for p in self.pods)
        logger.info(f"Food POD Manager: {len(self.pods)} PODs, {total_area:.0f} m² total growing area")

    def get_total_growing_area(self) -> float:
        """Get total growing area across all PODs."""
        return sum(p.total_area_m2 for p in self.pods)

    def get_total_daily_production(self) -> Dict[str, float]:
        """Get total daily food production."""
        return {
            "yield_kg": self.total_daily_yield_kg,
            "calories": self.total_daily_calories,
        }

    def get_expected_daily_production(self) -> Dict[str, float]:
        """Get expected daily production at full health."""
        total_yield = 0.0
        total_calories = 0.0

        for pod in self.pods:
            for bed in pod.beds:
                total_yield += bed.crop_spec.yield_per_day * bed.area_m2
                total_calories += bed.crop_spec.calories_per_m2_per_day * bed.area_m2

        return {
            "yield_kg": total_yield,
            "calories": total_calories,
        }

    def on_sol_complete(self):
        """Called at end of each sol to update tracking."""
        self.total_daily_yield_kg = sum(p.daily_yield_kg for p in self.pods)
        self.total_daily_calories = sum(p.daily_calories for p in self.pods)

        # Reset pod daily counters
        for pod in self.pods:
            pod.reset_daily_counters()

    def get_status(self) -> Dict:
        """Get status of all food PODs."""
        return {
            "pod_count": len(self.pods),
            "total_area_m2": self.get_total_growing_area(),
            "total_daily_yield_kg": self.total_daily_yield_kg,
            "total_daily_calories": self.total_daily_calories,
            "expected_daily": self.get_expected_daily_production(),
            "pods": [p.get_status() for p in self.pods],
        }
