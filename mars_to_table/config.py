"""
Mars to Table — Configuration
Mission parameters, physical constants, and system specifications.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum, auto


class FailureMode(Enum):
    """Types of failures BioSim may inject."""
    POWER_OUTAGE = auto()
    POWER_REDUCTION = auto()
    WATER_RESTRICTION = auto()
    WATER_INTERRUPTION = auto()
    CREW_SIZE_CHANGE = auto()
    METABOLIC_INCREASE = auto()
    POD_FAILURE = auto()
    EQUIPMENT_MALFUNCTION = auto()


class Priority(Enum):
    """Load shedding priority (lower = shed first during power shortage)."""
    CRITICAL = 1      # Life support, crew habitat
    HIGH = 2          # Livestock, food storage
    MEDIUM = 3        # Active crop production
    LOW = 4           # Processing, non-essential


@dataclass
class MissionConfig:
    """Core mission parameters from challenge requirements."""
    
    # Mission duration
    total_sols: int = 500
    ticks_per_sol: int = 24  # Hourly resolution
    
    # Crew
    crew_size: int = 15
    food_system_engineer: int = 1
    nutrition_specialist: int = 1
    
    # Calorie requirements (STD-3001)
    base_calories_per_crew_per_day: int = 3035  # kcal
    eva_bonus_calories_per_hour: int = 200      # kcal
    
    # Earth independence target
    min_earth_independence: float = 0.50  # 50% required
    target_earth_independence: float = 0.84  # Our design: 84%
    
    # Environment (Mars habitat)
    gravity_mars: float = 3.71  # m/s²
    atmosphere_pressure_psi: float = 8.2
    atmosphere_o2_percent: float = 34.0
    temperature_min_c: float = 18.0
    temperature_max_c: float = 27.0
    
    @property
    def total_ticks(self) -> int:
        return self.total_sols * self.ticks_per_sol
    
    @property
    def daily_calories_required(self) -> int:
        return self.crew_size * self.base_calories_per_crew_per_day


@dataclass
class PODSpec:
    """Standard POD physical specifications."""
    length_m: float = 10.0
    diameter_m: float = 7.6
    inner_diameter_m: float = 7.1  # After wall + shielding
    wall_thickness_m: float = 0.25  # 25cm water shielding
    num_decks: int = 3
    deck_height_m: float = 2.3
    
    @property
    def volume_m3(self) -> float:
        """Total internal volume."""
        import math
        return math.pi * (self.inner_diameter_m / 2) ** 2 * self.length_m
    
    @property
    def floor_area_per_deck_m2(self) -> float:
        """Usable floor area per deck (accounting for trunk)."""
        import math
        trunk_diameter = 2.4  # Central elevator/utility trunk
        total_area = math.pi * (self.inner_diameter_m / 2) ** 2
        trunk_area = math.pi * (trunk_diameter / 2) ** 2
        return total_area - trunk_area
    
    @property
    def total_floor_area_m2(self) -> float:
        """Total usable floor area across all decks."""
        return self.floor_area_per_deck_m2 * self.num_decks
    
    @property
    def wall_water_storage_liters(self) -> float:
        """Water storage capacity in 25cm wall shielding."""
        import math
        outer_vol = math.pi * (self.diameter_m / 2) ** 2 * self.length_m
        inner_vol = math.pi * (self.inner_diameter_m / 2) ** 2 * self.length_m
        wall_vol_m3 = outer_vol - inner_vol
        # Assume 80% of wall volume is usable for water
        return wall_vol_m3 * 0.80 * 1000  # Convert m³ to liters


@dataclass
class PowerConfig:
    """Power system specifications."""
    
    # Primary: Solar
    solar_array_area_m2: float = 3000.0
    solar_efficiency: float = 0.22  # 22% efficiency
    mars_solar_constant_w_m2: float = 590.0  # Average at Mars orbit
    solar_day_fraction: float = 0.5  # ~12 hours daylight
    
    # Secondary: RSV Fuel Cells
    fuel_cell_capacity_kw: float = 50.0  # Per RSV POD
    num_rsv_pods: int = 2
    h2_storage_kg: float = 500.0  # Per RSV POD
    fuel_cell_efficiency: float = 0.60
    
    # Tertiary: Biogas SOFC
    biogas_capacity_kw: float = 5.0
    
    # System loads (kW)
    food_pod_load_kw: float = 30.0  # Per Food POD (LEDs, pumps, HVAC)
    livestock_pod_load_kw: float = 15.0
    rsv_pod_load_kw: float = 25.0  # Electrolysis, pumps
    processing_pod_load_kw: float = 20.0
    hab_pod_load_kw: float = 20.0
    
    @property
    def peak_solar_kw(self) -> float:
        """Peak solar generation."""
        return self.solar_array_area_m2 * self.mars_solar_constant_w_m2 * self.solar_efficiency / 1000
    
    @property
    def average_solar_kw(self) -> float:
        """Average solar generation (accounting for night)."""
        return self.peak_solar_kw * self.solar_day_fraction
    
    @property
    def total_fuel_cell_kw(self) -> float:
        """Total backup fuel cell capacity."""
        return self.fuel_cell_capacity_kw * self.num_rsv_pods
    
    @property
    def total_backup_kw(self) -> float:
        """Total backup power (fuel cells + biogas)."""
        return self.total_fuel_cell_kw + self.biogas_capacity_kw


@dataclass
class WaterConfig:
    """Water system specifications."""
    
    # Extraction
    ice_extraction_rate_l_per_day: float = 700.0  # Per RSV POD
    num_rsv_pods: int = 2
    
    # Storage
    rsv_tank_capacity_l: float = 5000.0  # Per RSV POD
    distributed_wall_storage_l: float = 0.0  # Calculated from POD specs
    
    # Recycling
    recycling_efficiency: float = 0.95  # 95% water recovery
    
    # Consumption estimates (L/day)
    crew_consumption_l_per_person: float = 3.0  # Drinking + cooking
    crop_consumption_l_per_m2: float = 5.0  # Hydroponic crops
    livestock_consumption_l_per_day: float = 50.0  # Goats + chickens total
    
    # Emergency: H₂ combustion for water
    h2_to_water_ratio: float = 9.0  # 1 kg H₂ + 8 kg O₂ → 9 kg H₂O
    
    @property
    def total_extraction_capacity_l_per_day(self) -> float:
        return self.ice_extraction_rate_l_per_day * self.num_rsv_pods
    
    @property
    def total_tank_storage_l(self) -> float:
        return self.rsv_tank_capacity_l * self.num_rsv_pods


@dataclass 
class FoodProductionConfig:
    """Food production parameters."""
    
    # Food PODs 1-5: Human crops
    num_food_pods: int = 5
    growing_area_per_pod_m2: float = 361.0  # Effective with vertical racks
    
    # POD 6: Fodder
    fodder_area_m2: float = 361.0
    fodder_yield_kg_per_m2_per_day: float = 0.08  # ~29 kg/day total
    
    # POD 7: Grain
    grain_area_m2: float = 361.0
    flour_yield_kg_per_day: float = 5.5
    
    # Crop yields (kg edible per m² per day, averaged over growth cycle)
    crop_yields: Dict[str, float] = field(default_factory=lambda: {
        "potato": 0.015,      # ~120 day cycle, high calorie
        "sweet_potato": 0.012,
        "tomato": 0.025,
        "pepper": 0.015,
        "lettuce": 0.030,     # Fast cycle
        "spinach": 0.025,
        "beans": 0.010,
        "peas": 0.010,
        "soybean": 0.008,
        "herbs": 0.020,
    })
    
    # Calorie density (kcal per kg)
    calorie_density: Dict[str, float] = field(default_factory=lambda: {
        "potato": 770,
        "sweet_potato": 860,
        "tomato": 180,
        "pepper": 200,
        "lettuce": 150,
        "spinach": 230,
        "beans": 310,
        "peas": 810,
        "soybean": 1470,
        "herbs": 300,
        "flour": 3640,  # Wheat/amaranth/buckwheat blend
        "egg": 1550,    # Per kg
        "milk": 610,    # Goat milk
        "cheese": 3640, # Goat cheese
        "meat": 1430,   # Goat/chicken average
    })
    
    @property
    def total_crop_area_m2(self) -> float:
        return self.growing_area_per_pod_m2 * self.num_food_pods


@dataclass
class LivestockConfig:
    """Livestock parameters."""
    
    # Goats
    num_does: int = 6
    num_bucks: int = 1
    milk_per_doe_l_per_day: float = 1.33  # ~8L total from 6 does
    
    # Chickens
    num_hens: int = 20
    num_roosters: int = 2
    eggs_per_hen_per_day: float = 0.85  # ~17 eggs/day from 20 hens
    egg_weight_g: float = 50
    
    # Feed requirements
    goat_feed_kg_per_day: float = 2.0  # Per goat
    chicken_feed_kg_per_day: float = 0.12  # Per bird
    
    # Breeding/meat (averaged over time)
    meat_yield_kg_per_week: float = 0.55  # From culls
    
    @property
    def total_goats(self) -> int:
        return self.num_does + self.num_bucks
    
    @property
    def total_chickens(self) -> int:
        return self.num_hens + self.num_roosters
    
    @property
    def daily_milk_l(self) -> float:
        return self.num_does * self.milk_per_doe_l_per_day
    
    @property
    def daily_eggs(self) -> float:
        return self.num_hens * self.eggs_per_hen_per_day
    
    @property
    def daily_feed_required_kg(self) -> float:
        goat_feed = self.total_goats * self.goat_feed_kg_per_day
        chicken_feed = self.total_chickens * self.chicken_feed_kg_per_day
        return goat_feed + chicken_feed


@dataclass
class NutrientConfig:
    """Nutrient cycling parameters."""
    
    # Nitrogen (Haber-Bosch from Mars atmosphere)
    n2_capture_rate_kg_per_day: float = 5.0
    haber_bosch_efficiency: float = 0.15  # N₂ → NH₃ conversion
    nitrogen_self_sufficiency: float = 0.90  # 90% from in-situ
    
    # Phosphorus (from waste)
    phosphorus_recovery_rate: float = 0.80  # 80% from urine/manure
    
    # Potassium (Earth-supplied + ash)
    potassium_from_earth_kg: float = 200.0  # 500-sol supply
    
    # Waste processing
    human_waste_kg_per_person_per_day: float = 0.15  # Solid
    animal_waste_kg_per_day: float = 15.0  # Goats + chickens
    biogas_yield_m3_per_kg_waste: float = 0.3


# Default configurations
MISSION = MissionConfig()
POD = PODSpec()
POWER = PowerConfig()
WATER = WaterConfig()
FOOD = FoodProductionConfig()
LIVESTOCK = LivestockConfig()
NUTRIENTS = NutrientConfig()


def calculate_water_wall_storage() -> float:
    """Calculate total distributed water storage in POD walls."""
    # 13 PODs total
    return POD.wall_water_storage_liters * 13


# Update water config with calculated value
WATER.distributed_wall_storage_l = calculate_water_wall_storage()
