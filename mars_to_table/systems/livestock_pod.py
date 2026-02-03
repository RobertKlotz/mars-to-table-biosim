"""
Mars to Table — Livestock POD
Goat and chicken production system (POD 8).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging
import random

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import LIVESTOCK, FOOD, POD, Priority

logger = logging.getLogger(__name__)


class AnimalType(Enum):
    """Types of livestock."""
    GOAT_DOE = auto()      # Female dairy goat
    GOAT_BUCK = auto()     # Male goat
    GOAT_KID = auto()      # Young goat
    HEN = auto()           # Laying hen
    ROOSTER = auto()       # Male chicken
    CHICK = auto()         # Young chicken


class AnimalState(Enum):
    """Health/production state of an animal."""
    HEALTHY = auto()
    STRESSED = auto()
    SICK = auto()
    RECOVERING = auto()
    PREGNANT = auto()      # Goats only
    LACTATING = auto()     # Goats only
    MOLTING = auto()       # Chickens only


@dataclass
class Animal:
    """Individual animal in the herd/flock."""
    animal_id: str
    animal_type: AnimalType
    age_days: int = 0
    health: float = 1.0
    state: AnimalState = AnimalState.HEALTHY

    # Production tracking
    total_milk_l: float = 0.0      # Goats
    total_eggs: int = 0            # Chickens

    # Breeding
    days_pregnant: int = 0
    days_since_kidding: int = 0    # Goats
    days_since_laying: int = 0     # Chickens

    def is_productive(self) -> bool:
        """Check if animal is in productive state."""
        if self.animal_type == AnimalType.GOAT_DOE:
            return self.state == AnimalState.LACTATING and self.health > 0.5
        elif self.animal_type == AnimalType.HEN:
            return self.state != AnimalState.MOLTING and self.health > 0.5
        return False


@dataclass
class GoatHerd:
    """
    Dairy goat herd management.

    Nigerian Dwarf goats selected for:
    - Small size (25-35 kg)
    - High butterfat milk
    - Good feed conversion
    - Adaptable temperament
    """
    does: List[Animal] = field(default_factory=list)
    bucks: List[Animal] = field(default_factory=list)
    kids: List[Animal] = field(default_factory=list)

    # Production parameters
    milk_per_doe_l_per_day: float = LIVESTOCK.milk_per_doe_l_per_day
    feed_per_goat_kg_per_day: float = LIVESTOCK.goat_feed_kg_per_day
    water_per_goat_l_per_day: float = 4.0

    # Breeding parameters
    gestation_days: int = 150
    lactation_days: int = 305
    breeding_age_days: int = 240

    # Daily tracking
    daily_milk_l: float = 0.0
    daily_feed_consumed_kg: float = 0.0

    @property
    def total_goats(self) -> int:
        return len(self.does) + len(self.bucks) + len(self.kids)

    @property
    def lactating_does(self) -> int:
        return sum(1 for doe in self.does if doe.state == AnimalState.LACTATING)

    def initialize_herd(self, num_does: int, num_bucks: int):
        """Set up initial herd."""
        for i in range(num_does):
            doe = Animal(
                animal_id=f"doe_{i+1}",
                animal_type=AnimalType.GOAT_DOE,
                age_days=365 + random.randint(0, 365),  # 1-2 years old
                state=AnimalState.LACTATING,  # Start in production
            )
            self.does.append(doe)

        for i in range(num_bucks):
            buck = Animal(
                animal_id=f"buck_{i+1}",
                animal_type=AnimalType.GOAT_BUCK,
                age_days=365 + random.randint(0, 180),
            )
            self.bucks.append(buck)

        logger.info(f"Goat herd initialized: {num_does} does, {num_bucks} bucks")

    def get_daily_feed_requirement(self) -> float:
        """Get total daily feed requirement."""
        return self.total_goats * self.feed_per_goat_kg_per_day

    def get_daily_water_requirement(self) -> float:
        """Get total daily water requirement."""
        return self.total_goats * self.water_per_goat_l_per_day

    def produce_milk(self, feed_available_kg: float, water_available_l: float) -> float:
        """
        Produce milk based on available resources.

        Returns milk produced in liters.
        """
        feed_needed = self.get_daily_feed_requirement()
        water_needed = self.get_daily_water_requirement()

        feed_factor = min(1.0, feed_available_kg / feed_needed) if feed_needed > 0 else 0
        water_factor = min(1.0, water_available_l / water_needed) if water_needed > 0 else 0

        resource_factor = min(feed_factor, water_factor)

        total_milk = 0.0
        for doe in self.does:
            if doe.is_productive():
                milk = self.milk_per_doe_l_per_day * doe.health * resource_factor
                total_milk += milk
                doe.total_milk_l += milk

                # Update health based on resources
                doe.health = min(1.0, doe.health * 0.99 + resource_factor * 0.01)

        self.daily_milk_l = total_milk
        self.daily_feed_consumed_kg = min(feed_available_kg, feed_needed)

        return total_milk

    def get_status(self) -> Dict:
        """Get herd status."""
        return {
            "total_goats": self.total_goats,
            "does": len(self.does),
            "bucks": len(self.bucks),
            "kids": len(self.kids),
            "lactating_does": self.lactating_does,
            "daily_milk_l": self.daily_milk_l,
            "daily_feed_kg": self.daily_feed_consumed_kg,
            "avg_health": sum(g.health for g in self.does + self.bucks) / max(1, len(self.does) + len(self.bucks)),
        }


@dataclass
class ChickenFlock:
    """
    Laying hen flock management.

    ISA Brown hens selected for:
    - High egg production (300+ eggs/year)
    - Good feed conversion
    - Calm temperament
    - Heat tolerance
    """
    hens: List[Animal] = field(default_factory=list)
    roosters: List[Animal] = field(default_factory=list)
    chicks: List[Animal] = field(default_factory=list)

    # Production parameters
    eggs_per_hen_per_day: float = LIVESTOCK.eggs_per_hen_per_day
    feed_per_bird_kg_per_day: float = LIVESTOCK.chicken_feed_kg_per_day
    water_per_bird_l_per_day: float = 0.25
    egg_weight_g: float = LIVESTOCK.egg_weight_g

    # Daily tracking
    daily_eggs: int = 0
    daily_feed_consumed_kg: float = 0.0

    @property
    def total_birds(self) -> int:
        return len(self.hens) + len(self.roosters) + len(self.chicks)

    @property
    def productive_hens(self) -> int:
        return sum(1 for hen in self.hens if hen.is_productive())

    def initialize_flock(self, num_hens: int, num_roosters: int):
        """Set up initial flock."""
        for i in range(num_hens):
            hen = Animal(
                animal_id=f"hen_{i+1}",
                animal_type=AnimalType.HEN,
                age_days=180 + random.randint(0, 180),  # 6-12 months old
                state=AnimalState.HEALTHY,
            )
            self.hens.append(hen)

        for i in range(num_roosters):
            rooster = Animal(
                animal_id=f"rooster_{i+1}",
                animal_type=AnimalType.ROOSTER,
                age_days=180 + random.randint(0, 90),
            )
            self.roosters.append(rooster)

        logger.info(f"Chicken flock initialized: {num_hens} hens, {num_roosters} roosters")

    def get_daily_feed_requirement(self) -> float:
        """Get total daily feed requirement."""
        return self.total_birds * self.feed_per_bird_kg_per_day

    def get_daily_water_requirement(self) -> float:
        """Get total daily water requirement."""
        return self.total_birds * self.water_per_bird_l_per_day

    def produce_eggs(self, feed_available_kg: float, water_available_l: float) -> int:
        """
        Produce eggs based on available resources.

        Returns number of eggs produced.
        """
        feed_needed = self.get_daily_feed_requirement()
        water_needed = self.get_daily_water_requirement()

        feed_factor = min(1.0, feed_available_kg / feed_needed) if feed_needed > 0 else 0
        water_factor = min(1.0, water_available_l / water_needed) if water_needed > 0 else 0

        resource_factor = min(feed_factor, water_factor)

        total_eggs = 0
        for hen in self.hens:
            if hen.is_productive():
                # Egg production is probabilistic
                egg_chance = self.eggs_per_hen_per_day * hen.health * resource_factor
                if random.random() < egg_chance:
                    total_eggs += 1
                    hen.total_eggs += 1

                # Update health based on resources
                hen.health = min(1.0, hen.health * 0.99 + resource_factor * 0.01)

        self.daily_eggs = total_eggs
        self.daily_feed_consumed_kg = min(feed_available_kg, feed_needed)

        return total_eggs

    def get_status(self) -> Dict:
        """Get flock status."""
        return {
            "total_birds": self.total_birds,
            "hens": len(self.hens),
            "roosters": len(self.roosters),
            "chicks": len(self.chicks),
            "productive_hens": self.productive_hens,
            "daily_eggs": self.daily_eggs,
            "daily_feed_kg": self.daily_feed_consumed_kg,
            "avg_health": sum(h.health for h in self.hens) / max(1, len(self.hens)),
        }


class CheeseProcessor:
    """
    Simple cheese processing from goat milk.

    Produces fresh chevre-style cheese.
    ~10L milk = 1kg cheese
    """

    def __init__(self):
        self.milk_to_cheese_ratio = 10.0  # L milk per kg cheese
        self.total_cheese_kg = 0.0
        self.daily_cheese_kg = 0.0

    def process_milk(self, milk_l: float, fraction_for_cheese: float = 0.3) -> tuple:
        """
        Process milk, converting some to cheese.

        Args:
            milk_l: Total milk available
            fraction_for_cheese: Fraction to convert to cheese

        Returns:
            Tuple of (milk_remaining_l, cheese_produced_kg)
        """
        milk_for_cheese = milk_l * fraction_for_cheese
        cheese_kg = milk_for_cheese / self.milk_to_cheese_ratio

        self.total_cheese_kg += cheese_kg
        self.daily_cheese_kg = cheese_kg

        milk_remaining = milk_l - milk_for_cheese

        return milk_remaining, cheese_kg

    def reset_daily(self):
        """Reset daily counter."""
        self.daily_cheese_kg = 0.0


class LivestockPOD(Module):
    """
    Livestock production POD (POD 8).

    Houses goats and chickens for eggs, dairy, and occasional meat.

    Layout:
    - Deck 1: Goat housing and milking
    - Deck 2: Chicken housing and egg collection
    - Deck 3: Feed storage, processing, veterinary

    Production targets:
    - 8 L milk/day (from 6 lactating does)
    - 17 eggs/day (from 20 hens)
    - 300g cheese/day (from ~3L milk)
    """

    def __init__(self, name: str, store_manager: StoreManager):
        spec = ModuleSpec(
            name=name,
            priority=Priority.HIGH,
            power_consumption_kw=15.0,  # Climate control, milking, egg collection
            consumes=[
                ResourceFlow(ResourceType.FODDER, 0.0, "Fodder_Storage", required=True),
                ResourceFlow(ResourceType.POTABLE_WATER, 0.0, "Potable_Water", required=True),
            ],
            produces=[
                ResourceFlow(ResourceType.MILK, 0.0, "Milk_Storage"),
                ResourceFlow(ResourceType.EGGS, 0.0, "Egg_Storage"),
                ResourceFlow(ResourceType.CHEESE, 0.0, "Cheese_Storage"),
                ResourceFlow(ResourceType.ANIMAL_WASTE, 0.0, "Animal_Waste"),
            ],
            startup_ticks=1,
            efficiency=1.0
        )
        super().__init__(spec, store_manager)

        # Animal populations
        self.goat_herd = GoatHerd()
        self.chicken_flock = ChickenFlock()

        # Processing
        self.cheese_processor = CheeseProcessor()

        # Production tracking
        self.total_milk_l = 0.0
        self.total_eggs = 0
        self.total_cheese_kg = 0.0

        # Daily tracking
        self.daily_milk_l = 0.0
        self.daily_eggs = 0
        self.daily_cheese_kg = 0.0

        # Meat tracking (from culls)
        self.meat_available_kg = 0.0

    def initialize_livestock(self):
        """Set up initial livestock populations."""
        self.goat_herd.initialize_herd(
            num_does=LIVESTOCK.num_does,
            num_bucks=LIVESTOCK.num_bucks
        )
        self.chicken_flock.initialize_flock(
            num_hens=LIVESTOCK.num_hens,
            num_roosters=LIVESTOCK.num_roosters
        )

        logger.info(f"{self.name}: Livestock initialized - "
                   f"{self.goat_herd.total_goats} goats, {self.chicken_flock.total_birds} chickens")

    def get_feed_requirement(self) -> float:
        """Get total daily feed requirement per tick."""
        goat_feed = self.goat_herd.get_daily_feed_requirement()
        chicken_feed = self.chicken_flock.get_daily_feed_requirement()
        return (goat_feed + chicken_feed) / 24  # Per tick

    def get_water_requirement(self) -> float:
        """Get total daily water requirement per tick."""
        goat_water = self.goat_herd.get_daily_water_requirement()
        chicken_water = self.chicken_flock.get_daily_water_requirement()
        return (goat_water + chicken_water) / 24  # Per tick

    def process_tick(self) -> Dict:
        """Process one tick of livestock production."""
        # Get feed
        feed_needed = self.get_feed_requirement() * 24  # Daily amount for calculations
        fodder_store = self.stores.get("Fodder_Storage")
        feed_available = fodder_store.remove(self.get_feed_requirement()) * 24 if fodder_store else 0

        # Get water
        water_needed = self.get_water_requirement() * 24
        water_store = self.stores.get("Potable_Water")
        water_available = water_store.remove(self.get_water_requirement()) * 24 if water_store else 0

        # Split resources between goats and chickens (proportionally)
        goat_feed_fraction = (self.goat_herd.get_daily_feed_requirement() /
                            (feed_needed if feed_needed > 0 else 1))
        chicken_feed_fraction = 1 - goat_feed_fraction

        goat_feed = feed_available * goat_feed_fraction
        chicken_feed = feed_available * chicken_feed_fraction

        goat_water = water_available * 0.9  # Goats need more water
        chicken_water = water_available * 0.1

        # Produce milk (only process once per day, at hour 0)
        current_hour = self.ticks_operational % 24
        milk_l = 0.0
        eggs = 0
        cheese_kg = 0.0

        if current_hour == 0:  # Once per day
            # Milk production
            milk_l = self.goat_herd.produce_milk(goat_feed, goat_water)

            # Process some milk to cheese
            milk_remaining, cheese_kg = self.cheese_processor.process_milk(milk_l, fraction_for_cheese=0.3)

            # Store milk
            milk_store = self.stores.get("Milk_Storage")
            if milk_store:
                milk_store.add(milk_remaining)

            # Store cheese
            cheese_store = self.stores.get("Cheese_Storage")
            if cheese_store:
                cheese_store.add(cheese_kg)

            # Egg production
            eggs = self.chicken_flock.produce_eggs(chicken_feed, chicken_water)

            # Store eggs (as kg, ~50g each)
            egg_store = self.stores.get("Egg_Storage")
            if egg_store:
                egg_store.add(eggs * self.chicken_flock.egg_weight_g / 1000)

            # Generate waste
            waste_kg = (self.goat_herd.total_goats * 1.5 + self.chicken_flock.total_birds * 0.1)
            waste_store = self.stores.get("Animal_Waste")
            if waste_store:
                waste_store.add(waste_kg)

            # Update totals
            self.total_milk_l += milk_l
            self.total_eggs += eggs
            self.total_cheese_kg += cheese_kg

            self.daily_milk_l = milk_l
            self.daily_eggs = eggs
            self.daily_cheese_kg = cheese_kg

            logger.debug(f"{self.name}: Daily production - {milk_l:.1f}L milk, "
                       f"{eggs} eggs, {cheese_kg:.2f}kg cheese")

        return {
            "goats": self.goat_herd.total_goats,
            "chickens": self.chicken_flock.total_birds,
            "daily_milk_l": self.daily_milk_l,
            "daily_eggs": self.daily_eggs,
            "daily_cheese_kg": self.daily_cheese_kg,
            "feed_available_kg": feed_available,
            "water_available_l": water_available,
            "goat_status": self.goat_herd.get_status(),
            "chicken_status": self.chicken_flock.get_status(),
        }

    def reset_daily_counters(self):
        """Reset daily tracking counters."""
        self.daily_milk_l = 0.0
        self.daily_eggs = 0
        self.daily_cheese_kg = 0.0
        self.cheese_processor.reset_daily()

    def get_daily_calories(self) -> float:
        """Calculate daily calorie production."""
        milk_cal = self.daily_milk_l * FOOD.calorie_density.get("milk", 610)
        egg_cal = self.daily_eggs * (self.chicken_flock.egg_weight_g / 1000) * FOOD.calorie_density.get("egg", 1550)
        cheese_cal = self.daily_cheese_kg * FOOD.calorie_density.get("cheese", 3640)
        return milk_cal + egg_cal + cheese_cal

    def get_status(self) -> Dict:
        """Get current POD status."""
        return {
            "name": self.name,
            "state": self.state.name,
            "goat_herd": self.goat_herd.get_status(),
            "chicken_flock": self.chicken_flock.get_status(),
            "total_milk_l": self.total_milk_l,
            "total_eggs": self.total_eggs,
            "total_cheese_kg": self.total_cheese_kg,
            "daily_milk_l": self.daily_milk_l,
            "daily_eggs": self.daily_eggs,
            "daily_cheese_kg": self.daily_cheese_kg,
            "daily_calories": self.get_daily_calories(),
            "meat_available_kg": self.meat_available_kg,
        }
