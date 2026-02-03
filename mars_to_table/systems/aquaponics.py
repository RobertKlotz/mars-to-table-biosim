"""
Mars to Table — Aquaponics System (POD 13)

Integrated fish farming with hydroponics:
- Tilapia for protein (fast-growing, tolerant)
- Fish waste provides nutrients for plants
- Plants filter water for fish
- Closed-loop water cycling
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import logging
import random
import math

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ResourceFlow
from ..config import Priority

logger = logging.getLogger(__name__)


class FishSpecies(Enum):
    """Fish species suitable for Mars aquaponics."""
    TILAPIA = auto()      # Primary protein source
    CATFISH = auto()      # Alternative protein
    TROUT = auto()        # Cold water option


class FishLifeStage(Enum):
    """Life stages for fish."""
    FRY = auto()          # Newly hatched (0-2 weeks)
    FINGERLING = auto()   # Juvenile (2-8 weeks)
    GROWOUT = auto()      # Growing to market size (2-6 months)
    ADULT = auto()        # Breeding size
    BROODSTOCK = auto()   # Selected for breeding


@dataclass
class FishSpec:
    """Species-specific parameters."""
    name: str
    optimal_temp_c: float
    temp_tolerance: float  # +/- degrees
    growth_rate_g_day: float  # At optimal conditions
    feed_conversion_ratio: float  # kg feed per kg fish gain
    market_weight_g: float
    days_to_market: int
    protein_content_pct: float
    spawning_frequency_days: int
    fry_per_spawn: int


FISH_SPECIES = {
    FishSpecies.TILAPIA: FishSpec(
        name="Nile Tilapia",
        optimal_temp_c=28,
        temp_tolerance=5,
        growth_rate_g_day=3.0,  # Up to 3g/day at optimal
        feed_conversion_ratio=1.5,  # 1.5 kg feed per kg fish
        market_weight_g=500,
        days_to_market=180,
        protein_content_pct=0.20,  # 20% protein
        spawning_frequency_days=21,  # Every 3 weeks
        fry_per_spawn=200,
    ),
    FishSpecies.CATFISH: FishSpec(
        name="Channel Catfish",
        optimal_temp_c=26,
        temp_tolerance=6,
        growth_rate_g_day=2.5,
        feed_conversion_ratio=1.8,
        market_weight_g=600,
        days_to_market=200,
        protein_content_pct=0.18,
        spawning_frequency_days=365,  # Once per year
        fry_per_spawn=3000,
    ),
}


@dataclass
class Fish:
    """Individual fish tracking."""
    fish_id: str
    species: FishSpecies
    life_stage: FishLifeStage
    age_days: int = 0
    weight_g: float = 1.0  # Starting weight for fry
    health: float = 1.0

    # Breeding tracking
    is_broodstock: bool = False
    days_since_spawn: int = 0

    def is_harvestable(self, spec: FishSpec) -> bool:
        """Check if fish is ready for harvest."""
        return (self.weight_g >= spec.market_weight_g * 0.9 and
                self.life_stage in [FishLifeStage.GROWOUT, FishLifeStage.ADULT])


@dataclass
class FishTank:
    """
    Individual tank in the aquaponics system.

    Each tank has:
    - Specific water volume
    - Temperature control
    - Aeration system
    - Fish population
    """
    tank_id: str
    volume_l: float
    max_fish_density_kg_m3: float = 50.0  # Conservative stocking

    # Current state
    fish: List[Fish] = field(default_factory=list)
    water_temp_c: float = 28.0
    ph: float = 7.0
    ammonia_ppm: float = 0.0
    nitrate_ppm: float = 20.0
    dissolved_oxygen_ppm: float = 6.0

    # Production tracking
    total_harvested_kg: float = 0.0
    total_feed_kg: float = 0.0

    @property
    def volume_m3(self) -> float:
        return self.volume_l / 1000

    @property
    def fish_count(self) -> int:
        return len(self.fish)

    @property
    def total_fish_weight_kg(self) -> float:
        return sum(f.weight_g for f in self.fish) / 1000

    @property
    def stocking_density_kg_m3(self) -> float:
        return self.total_fish_weight_kg / self.volume_m3 if self.volume_m3 > 0 else 0

    def can_add_fish(self, weight_kg: float) -> bool:
        """Check if tank can accept more fish."""
        projected = (self.total_fish_weight_kg + weight_kg) / self.volume_m3
        return projected < self.max_fish_density_kg_m3


class AquaponicsManager:
    """
    Manages the integrated aquaponics system.

    Components:
    - Fish tanks (grow-out, breeding, nursery)
    - Biofilter (bacteria convert ammonia → nitrate)
    - Grow beds (plants use nitrate, clean water)
    - Sump tank (water collection)

    Water Flow:
    Fish tanks → Biofilter → Grow beds → Sump → Fish tanks
    """

    def __init__(self, num_tanks: int = 4, tank_volume_l: float = 2000):
        self.species = FishSpecies.TILAPIA
        self.species_spec = FISH_SPECIES[self.species]

        # Tanks
        self.tanks = [
            FishTank(tank_id=f"tank_{i+1:02d}", volume_l=tank_volume_l)
            for i in range(num_tanks)
        ]

        # Designate tanks
        self.nursery_tank = self.tanks[0]  # Fry and fingerlings
        self.growout_tanks = self.tanks[1:-1]  # Main production
        self.broodstock_tank = self.tanks[-1]  # Breeding fish

        # System parameters
        self.total_volume_l = tank_volume_l * num_tanks
        self.water_exchange_rate = 0.05  # 5% daily
        self.biofilter_efficiency = 0.95

        # Grow bed integration
        self.grow_bed_area_m2 = 50.0  # Plant growing area
        self.nutrient_uptake_rate = 0.8  # Plants absorb 80% of nitrates

        # Production tracking
        self.total_fish_harvested_kg = 0.0
        self.total_feed_used_kg = 0.0
        self.total_fry_produced = 0

        # Fish ID counter
        self.next_fish_id = 1

    def initialize_population(self, num_fish: int = 200, include_broodstock: int = 10):
        """Initialize starting fish population."""
        spec = self.species_spec

        # Add broodstock to breeding tank
        for i in range(include_broodstock):
            fish = self._create_fish(
                age_days=spec.days_to_market + 30,
                weight_g=spec.market_weight_g * 1.2,
            )
            fish.is_broodstock = True
            fish.life_stage = FishLifeStage.BROODSTOCK
            self.broodstock_tank.fish.append(fish)

        # Distribute remaining fish across grow-out tanks
        fish_per_tank = (num_fish - include_broodstock) // len(self.growout_tanks)

        for tank in self.growout_tanks:
            for _ in range(fish_per_tank):
                # Random ages for initial population
                age = random.randint(30, 120)
                weight = self._calculate_weight_for_age(age)

                fish = self._create_fish(age_days=age, weight_g=weight)
                tank.fish.append(fish)

        logger.info(f"Aquaponics initialized: {num_fish} tilapia, "
                   f"{include_broodstock} broodstock, {len(self.tanks)} tanks")

    def _create_fish(self, age_days: int = 0, weight_g: float = 1.0) -> Fish:
        """Create a new fish."""
        fish_id = f"fish_{self.next_fish_id:05d}"
        self.next_fish_id += 1

        # Determine life stage
        if age_days < 14:
            stage = FishLifeStage.FRY
        elif age_days < 56:
            stage = FishLifeStage.FINGERLING
        elif age_days < self.species_spec.days_to_market:
            stage = FishLifeStage.GROWOUT
        else:
            stage = FishLifeStage.ADULT

        return Fish(
            fish_id=fish_id,
            species=self.species,
            life_stage=stage,
            age_days=age_days,
            weight_g=weight_g,
        )

    def _calculate_weight_for_age(self, age_days: int) -> float:
        """Calculate expected weight for age."""
        spec = self.species_spec

        # Simplified growth curve (sigmoid-like)
        if age_days < 14:
            # Fry stage - slow growth
            return 1.0 + age_days * 0.2
        elif age_days < 56:
            # Fingerling - accelerating
            return 5.0 + (age_days - 14) * 1.0
        else:
            # Grow-out - fast growth tapering off
            base = 50.0
            growth = (age_days - 56) * spec.growth_rate_g_day
            max_weight = spec.market_weight_g * 1.5
            return min(max_weight, base + growth)

    def update_tick(
        self,
        tick: int,
        feed_available_kg: float,
        water_temp_c: float = 28.0,
    ) -> Dict:
        """
        Update aquaponics system for one tick.

        Returns production and status data.
        """
        hour_of_day = tick % 24
        spec = self.species_spec

        results = {
            "feed_consumed_kg": 0.0,
            "fish_grown_kg": 0.0,
            "harvested": [],
            "spawned": [],
            "deaths": [],
            "water_quality": {},
        }

        # Distribute feed across tanks
        total_fish_kg = sum(t.total_fish_weight_kg for t in self.tanks)
        if total_fish_kg > 0:
            # Feed rate: ~3% body weight per day, distributed across ticks
            daily_feed_rate = 0.03
            feed_per_tick = total_fish_kg * daily_feed_rate / 24
            feed_used = min(feed_available_kg, feed_per_tick)
            feed_ratio = feed_used / feed_per_tick if feed_per_tick > 0 else 0

            results["feed_consumed_kg"] = feed_used
            self.total_feed_used_kg += feed_used
        else:
            feed_ratio = 0

        # Update each tank
        for tank in self.tanks:
            tank.water_temp_c = water_temp_c

            # Update water quality
            self._update_water_quality(tank)

            # Process each fish
            fish_to_remove = []

            for fish in tank.fish:
                fish.age_days += 1 / 24  # Increment by 1 hour

                # Growth (affected by temp, feed, water quality)
                growth = self._calculate_growth(fish, tank, feed_ratio)
                fish.weight_g += growth
                results["fish_grown_kg"] += growth / 1000

                # Update life stage
                self._update_life_stage(fish)

                # Health and mortality
                if self._check_mortality(fish, tank):
                    fish_to_remove.append(fish)
                    results["deaths"].append({
                        "fish_id": fish.fish_id,
                        "weight_g": fish.weight_g,
                        "cause": "natural",
                    })

            # Remove dead fish
            for fish in fish_to_remove:
                tank.fish.remove(fish)

        # Breeding (check once per day at hour 6)
        if hour_of_day == 6:
            spawn_result = self._check_breeding()
            if spawn_result:
                results["spawned"].append(spawn_result)

        # Harvesting (check once per day at hour 12)
        if hour_of_day == 12:
            harvest_result = self._check_harvest()
            if harvest_result:
                results["harvested"].extend(harvest_result)

        # Water quality summary
        results["water_quality"] = self._get_water_quality_summary()

        return results

    def _calculate_growth(self, fish: Fish, tank: FishTank, feed_ratio: float) -> float:
        """Calculate growth for a fish this tick."""
        spec = self.species_spec

        # Base growth rate (per hour)
        base_growth = spec.growth_rate_g_day / 24

        # Temperature factor
        temp_diff = abs(tank.water_temp_c - spec.optimal_temp_c)
        temp_factor = max(0.2, 1.0 - (temp_diff / spec.temp_tolerance) * 0.5)

        # Feed factor
        feed_factor = min(1.0, feed_ratio)

        # Water quality factor
        if tank.ammonia_ppm > 1.0:
            wq_factor = 0.5
        elif tank.dissolved_oxygen_ppm < 4.0:
            wq_factor = 0.6
        else:
            wq_factor = 1.0

        # Life stage factor (fry grow slower)
        stage_factor = {
            FishLifeStage.FRY: 0.3,
            FishLifeStage.FINGERLING: 0.7,
            FishLifeStage.GROWOUT: 1.0,
            FishLifeStage.ADULT: 0.3,  # Adults grow slowly
            FishLifeStage.BROODSTOCK: 0.1,
        }.get(fish.life_stage, 1.0)

        growth = base_growth * temp_factor * feed_factor * wq_factor * stage_factor * fish.health

        return max(0, growth)

    def _update_life_stage(self, fish: Fish):
        """Update fish life stage based on age/weight."""
        spec = self.species_spec

        if fish.is_broodstock:
            fish.life_stage = FishLifeStage.BROODSTOCK
        elif fish.age_days < 14:
            fish.life_stage = FishLifeStage.FRY
        elif fish.age_days < 56:
            fish.life_stage = FishLifeStage.FINGERLING
        elif fish.weight_g < spec.market_weight_g * 0.9:
            fish.life_stage = FishLifeStage.GROWOUT
        else:
            fish.life_stage = FishLifeStage.ADULT

    def _update_water_quality(self, tank: FishTank):
        """Update water quality parameters."""
        # Ammonia production from fish
        fish_kg = tank.total_fish_weight_kg
        ammonia_produced = fish_kg * 0.03 / 24  # ~30g per kg fish per day

        # Biofilter conversion
        ammonia_converted = tank.ammonia_ppm * self.biofilter_efficiency / 24
        tank.nitrate_ppm += ammonia_converted * 3.5  # Stoichiometric ratio

        tank.ammonia_ppm = max(0, tank.ammonia_ppm + ammonia_produced - ammonia_converted)

        # Plant uptake of nitrates
        nitrate_absorbed = tank.nitrate_ppm * self.nutrient_uptake_rate / 24
        tank.nitrate_ppm = max(0, tank.nitrate_ppm - nitrate_absorbed)

        # Dissolved oxygen (aeration maintains it)
        tank.dissolved_oxygen_ppm = 6.0 + random.gauss(0, 0.5)
        tank.dissolved_oxygen_ppm = max(4.0, min(8.0, tank.dissolved_oxygen_ppm))

    def _check_mortality(self, fish: Fish, tank: FishTank) -> bool:
        """Check if fish dies this tick."""
        base_mortality = 0.0001  # 0.01% per tick

        # Poor water quality
        if tank.ammonia_ppm > 2.0:
            base_mortality *= 10
        if tank.dissolved_oxygen_ppm < 3.0:
            base_mortality *= 20

        # Age factor
        spec = self.species_spec
        if fish.age_days > spec.days_to_market * 2:
            base_mortality *= 5

        # Health factor
        base_mortality *= (2 - fish.health)

        return random.random() < base_mortality

    def _check_breeding(self) -> Optional[Dict]:
        """Check for spawning in broodstock tank."""
        spec = self.species_spec

        for fish in self.broodstock_tank.fish:
            if not fish.is_broodstock:
                continue

            fish.days_since_spawn += 1 / 24

            if fish.days_since_spawn >= spec.spawning_frequency_days:
                # Spawn!
                num_fry = int(spec.fry_per_spawn * fish.health * random.uniform(0.7, 1.0))

                # Add fry to nursery tank
                for _ in range(num_fry):
                    fry = self._create_fish(age_days=0, weight_g=0.1)
                    fry.life_stage = FishLifeStage.FRY

                    if self.nursery_tank.can_add_fish(0.0001):
                        self.nursery_tank.fish.append(fry)
                    else:
                        break  # Nursery full

                fish.days_since_spawn = 0
                self.total_fry_produced += num_fry

                return {
                    "broodstock_id": fish.fish_id,
                    "fry_produced": num_fry,
                }

        return None

    def _check_harvest(self) -> List[Dict]:
        """Check for fish ready to harvest."""
        spec = self.species_spec
        harvested = []

        for tank in self.growout_tanks:
            fish_to_harvest = []

            for fish in tank.fish:
                if fish.is_harvestable(spec):
                    fish_to_harvest.append(fish)

            # Harvest up to 10% of harvestable fish per day
            num_to_harvest = max(1, len(fish_to_harvest) // 10)

            for fish in fish_to_harvest[:num_to_harvest]:
                tank.fish.remove(fish)
                harvest_kg = fish.weight_g / 1000

                tank.total_harvested_kg += harvest_kg
                self.total_fish_harvested_kg += harvest_kg

                harvested.append({
                    "fish_id": fish.fish_id,
                    "weight_kg": harvest_kg,
                    "protein_kg": harvest_kg * spec.protein_content_pct,
                    "calories": harvest_kg * 1050,  # ~1050 kcal/kg tilapia
                })

        return harvested

    def _get_water_quality_summary(self) -> Dict:
        """Get water quality across all tanks."""
        return {
            "avg_temp_c": sum(t.water_temp_c for t in self.tanks) / len(self.tanks),
            "avg_ammonia_ppm": sum(t.ammonia_ppm for t in self.tanks) / len(self.tanks),
            "avg_nitrate_ppm": sum(t.nitrate_ppm for t in self.tanks) / len(self.tanks),
            "avg_do_ppm": sum(t.dissolved_oxygen_ppm for t in self.tanks) / len(self.tanks),
        }

    def get_status(self) -> Dict:
        """Get system status."""
        spec = self.species_spec

        total_fish = sum(len(t.fish) for t in self.tanks)
        total_weight = sum(t.total_fish_weight_kg for t in self.tanks)

        harvestable = sum(
            1 for t in self.tanks
            for f in t.fish
            if f.is_harvestable(spec)
        )

        return {
            "species": spec.name,
            "total_tanks": len(self.tanks),
            "total_volume_l": self.total_volume_l,
            "total_fish": total_fish,
            "total_fish_weight_kg": total_weight,
            "harvestable_count": harvestable,
            "fish_by_stage": self._count_by_stage(),
            "total_harvested_kg": self.total_fish_harvested_kg,
            "total_feed_used_kg": self.total_feed_used_kg,
            "total_fry_produced": self.total_fry_produced,
            "water_quality": self._get_water_quality_summary(),
            "tanks": [
                {
                    "tank_id": t.tank_id,
                    "fish_count": t.fish_count,
                    "fish_weight_kg": t.total_fish_weight_kg,
                    "stocking_density": t.stocking_density_kg_m3,
                }
                for t in self.tanks
            ],
        }

    def _count_by_stage(self) -> Dict:
        """Count fish by life stage."""
        counts = {stage.name: 0 for stage in FishLifeStage}
        for tank in self.tanks:
            for fish in tank.fish:
                counts[fish.life_stage.name] += 1
        return counts


class AquaponicsPOD(Module):
    """
    Aquaponics Production POD (POD 13).

    Integrated fish farming with hydroponics for:
    - Fresh fish protein (tilapia)
    - Nutrient-rich water for plant growth
    - Closed-loop water cycling
    - High-efficiency protein production

    Layout:
    - Deck 1: Fish tanks (4 x 2000L)
    - Deck 2: Biofilter and grow beds
    - Deck 3: Processing, feed storage, hatchery

    Production targets:
    - 200+ fish at various growth stages
    - ~2 kg fish/week harvest
    - Fish waste nutrients 100% plant-available
    """

    def __init__(self, name: str, store_manager: StoreManager):
        spec = ModuleSpec(
            name=name,
            priority=Priority.HIGH,
            power_consumption_kw=12.0,  # Pumps, aeration, heating
            consumes=[
                ResourceFlow(ResourceType.FISH_FEED, 0.0, "Fish_Feed_Storage", required=True),
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.FISH, 0.0, "Fish_Storage"),
                ResourceFlow(ResourceType.GREY_WATER, 0.0, "Grey_Water"),  # Nutrient water
            ],
            startup_ticks=2,
            efficiency=1.0,
        )
        super().__init__(spec, store_manager)

        # Aquaponics system
        self.aquaponics = AquaponicsManager(num_tanks=4, tank_volume_l=2000)

        # Production tracking
        self.total_fish_kg = 0.0
        self.total_protein_kg = 0.0
        self.daily_fish_kg = 0.0

    def initialize_system(self, num_fish: int = 200):
        """Initialize the aquaponics system."""
        self.aquaponics.initialize_population(num_fish=num_fish, include_broodstock=10)

    def process_tick(self) -> Dict:
        """Process one tick of aquaponics operation."""
        # Get feed
        feed_store = self.stores.get("Fish_Feed_Storage")
        feed_available = 0.0
        if feed_store:
            # Request enough feed for one tick
            feed_needed = sum(t.total_fish_weight_kg for t in self.aquaponics.tanks) * 0.03 / 24
            feed_available = feed_store.remove(feed_needed)

        # Update aquaponics
        result = self.aquaponics.update_tick(
            tick=self.ticks_operational,
            feed_available_kg=feed_available,
            water_temp_c=28.0,
        )

        # Store harvested fish
        for harvest in result.get("harvested", []):
            fish_store = self.stores.get("Fish_Storage")
            if fish_store:
                fish_store.add(harvest["weight_kg"])

            self.total_fish_kg += harvest["weight_kg"]
            self.total_protein_kg += harvest["protein_kg"]
            self.daily_fish_kg += harvest["weight_kg"]

        return result

    def reset_daily_counters(self):
        """Reset daily tracking."""
        self.daily_fish_kg = 0.0

    def get_status(self) -> Dict:
        """Get POD status."""
        return {
            "name": self.name,
            "state": self.state.name,
            "total_fish_kg": self.total_fish_kg,
            "total_protein_kg": self.total_protein_kg,
            "daily_fish_kg": self.daily_fish_kg,
            "aquaponics": self.aquaponics.get_status(),
        }
