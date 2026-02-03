"""
Mars to Table — Food Processing Systems

Advanced food processing capabilities including:
- Oil extraction from oilseed crops (soybeans, sunflower)
- Fermentation (sauerkraut, kimchi, tempeh, bread)
- Food preservation (drying, pickling)
- Flour milling from grains
- Sugar extraction from beets
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import logging
import math

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ResourceFlow
from ..config import Priority

logger = logging.getLogger(__name__)


class ProcessingType(Enum):
    """Types of food processing."""
    OIL_EXTRACTION = auto()
    FERMENTATION = auto()
    DRYING = auto()
    PICKLING = auto()
    MILLING = auto()
    SUGAR_EXTRACTION = auto()
    CHEESE_MAKING = auto()
    BREAD_BAKING = auto()


@dataclass
class OilCrop:
    """Oilseed crop specifications."""
    name: str
    oil_content_pct: float      # Percentage of seed that is oil
    protein_content_pct: float  # Protein in remaining meal
    yield_kg_per_m2: float      # Annual yield
    pressing_efficiency: float  # How much oil we can extract

    @property
    def oil_yield_per_kg_seed(self) -> float:
        """Oil yield per kg of seed processed."""
        return self.oil_content_pct * self.pressing_efficiency


# Oil crop specifications
OIL_CROPS = {
    "soybean": OilCrop(
        name="soybean",
        oil_content_pct=0.20,       # 20% oil
        protein_content_pct=0.40,   # 40% protein in meal
        yield_kg_per_m2=0.3,
        pressing_efficiency=0.85,
    ),
    "sunflower": OilCrop(
        name="sunflower",
        oil_content_pct=0.40,       # 40% oil (high oil variety)
        protein_content_pct=0.25,
        yield_kg_per_m2=0.25,
        pressing_efficiency=0.90,
    ),
    "peanut": OilCrop(
        name="peanut",
        oil_content_pct=0.45,       # 45% oil
        protein_content_pct=0.25,
        yield_kg_per_m2=0.35,
        pressing_efficiency=0.85,
    ),
    "flax": OilCrop(
        name="flax",
        oil_content_pct=0.35,       # 35% oil (omega-3 rich)
        protein_content_pct=0.20,
        yield_kg_per_m2=0.15,
        pressing_efficiency=0.80,
    ),
}


@dataclass
class FermentedProduct:
    """Fermented food product specification."""
    name: str
    base_ingredient: str
    fermentation_days: int
    yield_ratio: float          # Output kg per input kg
    probiotic_benefit: float    # Health benefit score 0-1
    shelf_life_days: int
    calories_per_kg: float


FERMENTED_PRODUCTS = {
    "sauerkraut": FermentedProduct(
        name="sauerkraut",
        base_ingredient="cabbage",
        fermentation_days=14,
        yield_ratio=0.9,
        probiotic_benefit=0.8,
        shelf_life_days=180,
        calories_per_kg=190,
    ),
    "kimchi": FermentedProduct(
        name="kimchi",
        base_ingredient="cabbage",
        fermentation_days=7,
        yield_ratio=0.85,
        probiotic_benefit=0.85,
        shelf_life_days=90,
        calories_per_kg=230,
    ),
    "tempeh": FermentedProduct(
        name="tempeh",
        base_ingredient="soybean",
        fermentation_days=2,
        yield_ratio=1.1,  # Gains weight from mycelium
        probiotic_benefit=0.7,
        shelf_life_days=14,
        calories_per_kg=1920,
    ),
    "miso": FermentedProduct(
        name="miso",
        base_ingredient="soybean",
        fermentation_days=60,  # Minimum, better with longer
        yield_ratio=2.0,  # Includes added rice/barley
        probiotic_benefit=0.9,
        shelf_life_days=365,
        calories_per_kg=1990,
    ),
    "sourdough_starter": FermentedProduct(
        name="sourdough_starter",
        base_ingredient="flour",
        fermentation_days=7,
        yield_ratio=1.0,
        probiotic_benefit=0.6,
        shelf_life_days=365,  # Can be maintained indefinitely
        calories_per_kg=1200,
    ),
    "vinegar": FermentedProduct(
        name="vinegar",
        base_ingredient="fruit",
        fermentation_days=30,
        yield_ratio=0.8,
        probiotic_benefit=0.3,
        shelf_life_days=730,
        calories_per_kg=180,
    ),
}


class OilProcessor:
    """
    Oil extraction from oilseed crops.

    Uses mechanical cold-pressing to extract oil while
    preserving protein-rich meal for animal feed or direct consumption.

    Process:
    1. Clean and dehull seeds
    2. Condition (heat slightly to improve flow)
    3. Cold press extraction
    4. Filter and store oil
    5. Collect meal for feed/food
    """

    def __init__(self, power_kw: float = 5.0):
        self.power_consumption_kw = power_kw
        self.processing_capacity_kg_hr = 10.0  # kg seeds/hour

        # Production tracking
        self.total_oil_produced_l = 0.0
        self.total_meal_produced_kg = 0.0
        self.total_seeds_processed_kg = 0.0

        # Current batch
        self.current_batch: Optional[Dict] = None
        self.processing_ticks_remaining = 0

    def start_batch(self, seed_type: str, seed_kg: float) -> bool:
        """Start processing a batch of oilseeds."""
        if self.current_batch is not None:
            logger.warning("Cannot start new batch while processing")
            return False

        if seed_type not in OIL_CROPS:
            logger.error(f"Unknown oil crop: {seed_type}")
            return False

        crop = OIL_CROPS[seed_type]
        processing_hours = seed_kg / self.processing_capacity_kg_hr
        processing_ticks = max(1, int(processing_hours))

        self.current_batch = {
            "seed_type": seed_type,
            "seed_kg": seed_kg,
            "crop_spec": crop,
            "start_tick": 0,
        }
        self.processing_ticks_remaining = processing_ticks

        logger.info(f"Started oil processing: {seed_kg}kg {seed_type}, "
                   f"ETA {processing_ticks} ticks")
        return True

    def process_tick(self, power_available_kw: float) -> Optional[Dict]:
        """
        Process one tick of oil extraction.

        Returns production data when batch completes.
        """
        if self.current_batch is None:
            return None

        if power_available_kw < self.power_consumption_kw:
            logger.warning("Insufficient power for oil processing")
            return None

        self.processing_ticks_remaining -= 1

        if self.processing_ticks_remaining <= 0:
            # Batch complete
            return self._complete_batch()

        return None

    def _complete_batch(self) -> Dict:
        """Complete current batch and return production."""
        batch = self.current_batch
        crop = batch["crop_spec"]
        seed_kg = batch["seed_kg"]

        # Calculate outputs
        oil_kg = seed_kg * crop.oil_yield_per_kg_seed
        oil_l = oil_kg / 0.92  # Oil density ~0.92 kg/L

        meal_kg = seed_kg * (1 - crop.oil_content_pct) * 0.95  # 5% loss

        # Update totals
        self.total_oil_produced_l += oil_l
        self.total_meal_produced_kg += meal_kg
        self.total_seeds_processed_kg += seed_kg

        result = {
            "seed_type": batch["seed_type"],
            "seed_processed_kg": seed_kg,
            "oil_produced_l": oil_l,
            "meal_produced_kg": meal_kg,
            "meal_protein_pct": crop.protein_content_pct,
            "calories_from_oil": oil_l * 8840,  # ~8840 kcal/L
        }

        logger.info(f"Oil batch complete: {oil_l:.2f}L oil, {meal_kg:.2f}kg meal")

        self.current_batch = None
        return result

    def get_status(self) -> Dict:
        """Get processor status."""
        return {
            "is_processing": self.current_batch is not None,
            "current_batch": self.current_batch,
            "ticks_remaining": self.processing_ticks_remaining,
            "total_oil_l": self.total_oil_produced_l,
            "total_meal_kg": self.total_meal_produced_kg,
            "power_consumption_kw": self.power_consumption_kw,
        }


class FermentationVessel:
    """
    Fermentation vessel for producing fermented foods.

    Supports various fermentation processes:
    - Lacto-fermentation (sauerkraut, kimchi)
    - Fungal fermentation (tempeh, miso)
    - Yeast fermentation (bread starter)
    - Acetic fermentation (vinegar)
    """

    def __init__(self, capacity_kg: float = 20.0, vessel_id: str = "ferm_01"):
        self.vessel_id = vessel_id
        self.capacity_kg = capacity_kg

        # Current fermentation
        self.product_type: Optional[str] = None
        self.batch_kg: float = 0.0
        self.fermentation_start_tick: int = 0
        self.fermentation_ticks_required: int = 0
        self.current_tick: int = 0

        # Environment
        self.temperature_c: float = 22.0
        self.is_anaerobic: bool = True

        # Production tracking
        self.total_batches = 0
        self.total_output_kg = 0.0

    def start_fermentation(
        self,
        product_type: str,
        input_kg: float,
        current_tick: int,
    ) -> bool:
        """Start a fermentation batch."""
        if self.product_type is not None:
            logger.warning(f"Vessel {self.vessel_id} already fermenting")
            return False

        if product_type not in FERMENTED_PRODUCTS:
            logger.error(f"Unknown fermented product: {product_type}")
            return False

        if input_kg > self.capacity_kg:
            logger.warning(f"Batch {input_kg}kg exceeds capacity {self.capacity_kg}kg")
            input_kg = self.capacity_kg

        product = FERMENTED_PRODUCTS[product_type]
        self.product_type = product_type
        self.batch_kg = input_kg
        self.fermentation_start_tick = current_tick
        self.fermentation_ticks_required = product.fermentation_days * 24

        logger.info(f"Started fermentation: {input_kg}kg {product_type}, "
                   f"ready in {product.fermentation_days} days")
        return True

    def update_tick(self, tick: int, temperature_c: float = 22.0) -> Optional[Dict]:
        """
        Update fermentation progress.

        Returns product data when fermentation completes.
        """
        self.current_tick = tick
        self.temperature_c = temperature_c

        if self.product_type is None:
            return None

        elapsed = tick - self.fermentation_start_tick

        # Temperature affects fermentation speed
        temp_factor = 1.0
        if temperature_c < 18:
            temp_factor = 0.7  # Slower in cold
        elif temperature_c > 28:
            temp_factor = 1.3  # Faster in warm (but might affect quality)

        effective_elapsed = elapsed * temp_factor

        if effective_elapsed >= self.fermentation_ticks_required:
            return self._complete_fermentation()

        return None

    def _complete_fermentation(self) -> Dict:
        """Complete fermentation and return product."""
        product = FERMENTED_PRODUCTS[self.product_type]

        output_kg = self.batch_kg * product.yield_ratio
        calories = output_kg * product.calories_per_kg

        result = {
            "product": self.product_type,
            "input_kg": self.batch_kg,
            "output_kg": output_kg,
            "calories": calories,
            "probiotic_benefit": product.probiotic_benefit,
            "shelf_life_days": product.shelf_life_days,
            "fermentation_days": product.fermentation_days,
        }

        self.total_batches += 1
        self.total_output_kg += output_kg

        logger.info(f"Fermentation complete: {output_kg:.2f}kg {self.product_type}")

        # Reset vessel
        self.product_type = None
        self.batch_kg = 0.0

        return result

    def get_progress(self) -> float:
        """Get fermentation progress (0-1)."""
        if self.product_type is None:
            return 0.0

        elapsed = self.current_tick - self.fermentation_start_tick
        return min(1.0, elapsed / self.fermentation_ticks_required)

    def get_status(self) -> Dict:
        """Get vessel status."""
        return {
            "vessel_id": self.vessel_id,
            "capacity_kg": self.capacity_kg,
            "is_fermenting": self.product_type is not None,
            "product_type": self.product_type,
            "batch_kg": self.batch_kg,
            "progress": self.get_progress(),
            "temperature_c": self.temperature_c,
            "total_batches": self.total_batches,
            "total_output_kg": self.total_output_kg,
        }


class GrainMill:
    """
    Grain milling for flour production.

    Processes wheat, rice, corn into flour/meal.
    """

    def __init__(self, power_kw: float = 3.0):
        self.power_consumption_kw = power_kw
        self.milling_rate_kg_hr = 20.0  # kg grain per hour

        self.total_flour_kg = 0.0
        self.total_bran_kg = 0.0

    def mill_grain(
        self,
        grain_type: str,
        grain_kg: float,
        whole_grain: bool = False,
    ) -> Dict:
        """
        Mill grain into flour.

        Args:
            grain_type: Type of grain (wheat, rice, corn)
            grain_kg: Amount to mill
            whole_grain: If True, include bran; if False, separate bran

        Returns:
            Production results
        """
        # Milling yields
        yields = {
            "wheat": {"flour": 0.72, "bran": 0.25, "loss": 0.03},
            "rice": {"flour": 0.65, "bran": 0.10, "loss": 0.25},  # More hulls
            "corn": {"flour": 0.68, "bran": 0.12, "loss": 0.20},
        }

        grain_yield = yields.get(grain_type, {"flour": 0.70, "bran": 0.15, "loss": 0.15})

        if whole_grain:
            # Keep bran in flour
            flour_kg = grain_kg * (grain_yield["flour"] + grain_yield["bran"])
            bran_kg = 0.0
        else:
            flour_kg = grain_kg * grain_yield["flour"]
            bran_kg = grain_kg * grain_yield["bran"]

        self.total_flour_kg += flour_kg
        self.total_bran_kg += bran_kg

        # Calories (roughly 3400 kcal/kg flour)
        calories = flour_kg * 3400

        processing_time_hr = grain_kg / self.milling_rate_kg_hr

        return {
            "grain_type": grain_type,
            "grain_input_kg": grain_kg,
            "flour_output_kg": flour_kg,
            "bran_output_kg": bran_kg,
            "whole_grain": whole_grain,
            "calories": calories,
            "processing_time_hr": processing_time_hr,
            "power_used_kwh": processing_time_hr * self.power_consumption_kw,
        }

    def get_status(self) -> Dict:
        """Get mill status."""
        return {
            "total_flour_kg": self.total_flour_kg,
            "total_bran_kg": self.total_bran_kg,
            "milling_rate_kg_hr": self.milling_rate_kg_hr,
            "power_consumption_kw": self.power_consumption_kw,
        }


class FoodDryer:
    """
    Food dehydration system for preservation.

    Dries fruits, vegetables, and herbs for long-term storage.
    """

    def __init__(self, capacity_kg: float = 10.0, power_kw: float = 2.0):
        self.capacity_kg = capacity_kg
        self.power_consumption_kw = power_kw

        # Drying parameters
        self.temperature_c = 60.0  # Typical drying temp
        self.drying_time_hr = 12.0  # Base drying time

        self.total_dried_kg = 0.0
        self.batches_processed = 0

    def dry_food(self, food_type: str, fresh_kg: float) -> Dict:
        """
        Dry food for preservation.

        Returns dried food weight and stats.
        """
        if fresh_kg > self.capacity_kg:
            fresh_kg = self.capacity_kg
            logger.warning(f"Batch reduced to capacity: {self.capacity_kg}kg")

        # Water content by food type
        water_content = {
            "fruit": 0.85,      # Most fruits 80-90% water
            "vegetable": 0.90,
            "herbs": 0.80,
            "meat": 0.65,
            "tomato": 0.94,
            "potato": 0.80,
        }

        water_pct = water_content.get(food_type, 0.85)
        target_moisture = 0.10  # Dried to 10% moisture

        # Calculate dried weight
        dry_matter = fresh_kg * (1 - water_pct)
        dried_kg = dry_matter / (1 - target_moisture)

        # Drying time varies with water content
        time_factor = water_pct / 0.85
        drying_hours = self.drying_time_hr * time_factor

        self.total_dried_kg += dried_kg
        self.batches_processed += 1

        return {
            "food_type": food_type,
            "fresh_input_kg": fresh_kg,
            "dried_output_kg": dried_kg,
            "water_removed_kg": fresh_kg - dried_kg,
            "weight_reduction_pct": (1 - dried_kg / fresh_kg) * 100,
            "drying_time_hr": drying_hours,
            "power_used_kwh": drying_hours * self.power_consumption_kw,
            "shelf_life_months": 12,  # Dried food lasts ~1 year
        }

    def get_status(self) -> Dict:
        """Get dryer status."""
        return {
            "capacity_kg": self.capacity_kg,
            "total_dried_kg": self.total_dried_kg,
            "batches_processed": self.batches_processed,
            "temperature_c": self.temperature_c,
            "power_consumption_kw": self.power_consumption_kw,
        }


class FoodProcessingPOD(Module):
    """
    Food Processing POD (POD 12).

    Comprehensive food processing facility including:
    - Oil extraction from oilseeds
    - Grain milling for flour
    - Fermentation vessels for probiotics
    - Food drying for preservation

    This POD transforms raw agricultural outputs into
    shelf-stable, varied food products that improve
    crew nutrition and morale.
    """

    def __init__(self, name: str, store_manager: StoreManager):
        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=15.0,  # Base consumption
            consumes=[
                ResourceFlow(ResourceType.GRAIN, 0.0, "Grain_Storage", required=False),
                ResourceFlow(ResourceType.VEGETABLES, 0.0, "Vegetable_Storage", required=False),
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.OIL, 0.0, "Oil_Storage"),
                ResourceFlow(ResourceType.FLOUR, 0.0, "Flour_Storage"),
                ResourceFlow(ResourceType.PRESERVED_FOOD, 0.0, "Preserved_Food_Storage"),
            ],
            startup_ticks=1,
            efficiency=1.0,
        )
        super().__init__(spec, store_manager)

        # Processing equipment
        self.oil_processor = OilProcessor(power_kw=5.0)
        self.grain_mill = GrainMill(power_kw=3.0)
        self.food_dryer = FoodDryer(capacity_kg=10.0, power_kw=2.0)

        # Fermentation vessels (multiple for continuous production)
        self.fermentation_vessels = [
            FermentationVessel(capacity_kg=20.0, vessel_id=f"ferm_{i+1:02d}")
            for i in range(4)  # 4 vessels
        ]

        # Production tracking
        self.daily_oil_l = 0.0
        self.daily_flour_kg = 0.0
        self.daily_fermented_kg = 0.0
        self.daily_dried_kg = 0.0

    def process_tick(self) -> Dict:
        """Process one tick of food processing."""
        results = {
            "oil": None,
            "fermentation": [],
            "milling": None,
            "drying": None,
        }

        # Oil processing
        oil_result = self.oil_processor.process_tick(
            power_available_kw=self.spec.power_consumption_kw
        )
        if oil_result:
            results["oil"] = oil_result
            self.daily_oil_l += oil_result["oil_produced_l"]

        # Fermentation vessels
        for vessel in self.fermentation_vessels:
            ferm_result = vessel.update_tick(self.ticks_operational)
            if ferm_result:
                results["fermentation"].append(ferm_result)
                self.daily_fermented_kg += ferm_result["output_kg"]

        return results

    def start_oil_batch(self, seed_type: str, seed_kg: float) -> bool:
        """Start an oil extraction batch."""
        return self.oil_processor.start_batch(seed_type, seed_kg)

    def start_fermentation(self, product_type: str, input_kg: float) -> bool:
        """Start fermentation in an available vessel."""
        for vessel in self.fermentation_vessels:
            if vessel.product_type is None:
                return vessel.start_fermentation(
                    product_type, input_kg, self.ticks_operational
                )

        logger.warning("No available fermentation vessels")
        return False

    def mill_grain(self, grain_type: str, grain_kg: float, whole_grain: bool = False) -> Dict:
        """Mill grain into flour."""
        result = self.grain_mill.mill_grain(grain_type, grain_kg, whole_grain)
        self.daily_flour_kg += result["flour_output_kg"]
        return result

    def dry_food(self, food_type: str, fresh_kg: float) -> Dict:
        """Dry food for preservation."""
        result = self.food_dryer.dry_food(food_type, fresh_kg)
        self.daily_dried_kg += result["dried_output_kg"]
        return result

    def reset_daily_counters(self):
        """Reset daily production counters."""
        self.daily_oil_l = 0.0
        self.daily_flour_kg = 0.0
        self.daily_fermented_kg = 0.0
        self.daily_dried_kg = 0.0

    def get_status(self) -> Dict:
        """Get POD status."""
        return {
            "name": self.name,
            "state": self.state.name,
            "oil_processor": self.oil_processor.get_status(),
            "grain_mill": self.grain_mill.get_status(),
            "food_dryer": self.food_dryer.get_status(),
            "fermentation_vessels": [v.get_status() for v in self.fermentation_vessels],
            "daily_production": {
                "oil_l": self.daily_oil_l,
                "flour_kg": self.daily_flour_kg,
                "fermented_kg": self.daily_fermented_kg,
                "dried_kg": self.daily_dried_kg,
            },
        }
