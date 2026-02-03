"""
Mars to Table — Systems Package
Resource management, food production, and processing systems.
"""

# Sprint 2: Resource Systems
from .power_system import PowerSystem, SolarArray, FuelCell, BiogasGenerator
from .water_system import WaterSystem, RSVExtractor, WaterRecycler
from .nutrient_system import NutrientSystem, HaberBoschReactor, WasteProcessor

# Sprint 3: Food Production
from .food_pod import FoodPOD, FoodPODManager, CropType, CropSpec, CROP_SPECS
from .fodder_pod import FodderPOD, FodderType, FODDER_SPECS
from .grain_pod import GrainPOD, GrainMill, GrainType, GRAIN_SPECS
from .livestock_pod import LivestockPOD, GoatHerd, ChickenFlock

# Sprint 7: Advanced Processing
from .processing import (
    ProcessingType,
    OilCrop,
    OIL_CROPS,
    FermentedProduct,
    FERMENTED_PRODUCTS,
    OilProcessor,
    FermentationVessel,
    GrainMill as FlourMill,  # Renamed to avoid conflict
    FoodDryer,
    FoodProcessingPOD,
)
from .aquaponics import (
    FishSpecies,
    FishLifeStage,
    FishSpec,
    FISH_SPECIES,
    Fish,
    FishTank,
    AquaponicsManager,
    AquaponicsPOD,
)

__all__ = [
    # Power
    'PowerSystem', 'SolarArray', 'FuelCell', 'BiogasGenerator',
    # Water
    'WaterSystem', 'RSVExtractor', 'WaterRecycler',
    # Nutrients
    'NutrientSystem', 'HaberBoschReactor', 'WasteProcessor',
    # Food Production
    'FoodPOD', 'FoodPODManager', 'CropType', 'CropSpec', 'CROP_SPECS',
    'FodderPOD', 'FodderType', 'FODDER_SPECS',
    'GrainPOD', 'GrainMill', 'GrainType', 'GRAIN_SPECS',
    'LivestockPOD', 'GoatHerd', 'ChickenFlock',
    # Food Processing
    'ProcessingType', 'OilCrop', 'OIL_CROPS',
    'FermentedProduct', 'FERMENTED_PRODUCTS',
    'OilProcessor', 'FermentationVessel', 'FlourMill', 'FoodDryer',
    'FoodProcessingPOD',
    # Aquaponics
    'FishSpecies', 'FishLifeStage', 'FishSpec', 'FISH_SPECIES',
    'Fish', 'FishTank', 'AquaponicsManager', 'AquaponicsPOD',
]
