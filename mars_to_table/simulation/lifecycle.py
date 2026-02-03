"""
Mars to Table — Livestock Lifecycle & Breeding Simulation

Full lifecycle modeling for goats and chickens including:
- Breeding cycles and reproduction
- Growth stages and maturation
- Health tracking and veterinary events
- Mortality and culling decisions
- Population dynamics over mission duration
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import random
import logging

logger = logging.getLogger(__name__)


class LifeStage(Enum):
    """Life stages for animals."""
    NEWBORN = auto()      # First weeks of life
    JUVENILE = auto()     # Growing phase
    MATURE = auto()       # Adult, productive
    SENIOR = auto()       # Declining production
    DECEASED = auto()     # No longer alive


class BreedingStatus(Enum):
    """Breeding status for female animals."""
    OPEN = auto()         # Not pregnant, can breed
    BRED = auto()         # Recently bred, awaiting confirmation
    PREGNANT = auto()     # Confirmed pregnant
    LACTATING = auto()    # Post-birth, producing milk
    DRY = auto()          # Resting period
    INFERTILE = auto()    # Cannot reproduce


class HealthEvent(Enum):
    """Health events that can affect animals."""
    HEALTHY = auto()
    MINOR_ILLNESS = auto()
    MAJOR_ILLNESS = auto()
    INJURY = auto()
    STRESS = auto()
    NUTRITIONAL_DEFICIENCY = auto()
    PARASITES = auto()
    MASTITIS = auto()       # Udder infection (goats)
    RESPIRATORY = auto()    # Respiratory infection
    BIRTHING_COMPLICATIONS = auto()


@dataclass
class BreedingRecord:
    """Record of a breeding event."""
    breeding_tick: int
    sire_id: str
    dam_id: str
    expected_birth_tick: int
    actual_birth_tick: Optional[int] = None
    offspring_count: int = 0
    offspring_ids: List[str] = field(default_factory=list)
    success: bool = False


@dataclass
class HealthRecord:
    """Record of a health event."""
    tick: int
    event_type: HealthEvent
    severity: float  # 0-1
    treatment_given: bool = False
    recovery_ticks: int = 0
    outcome: str = ""


@dataclass
class AnimalLifecycle:
    """
    Full lifecycle tracking for an individual animal.

    Tracks birth, growth, reproduction, health, and death.
    """
    animal_id: str
    species: str  # "goat" or "chicken"
    sex: str  # "male" or "female"
    birth_tick: int

    # Current state
    current_tick: int = 0
    life_stage: LifeStage = LifeStage.NEWBORN
    breeding_status: BreedingStatus = BreedingStatus.OPEN
    health: float = 1.0
    weight_kg: float = 0.0

    # Genetics (affects production)
    genetic_potential: float = 1.0  # 0.8-1.2 multiplier

    # Breeding tracking
    times_bred: int = 0
    total_offspring: int = 0
    breeding_history: List[BreedingRecord] = field(default_factory=list)

    # Health tracking
    health_history: List[HealthRecord] = field(default_factory=list)
    current_health_event: Optional[HealthEvent] = None
    recovery_ticks_remaining: int = 0

    # Production tracking (species-specific)
    lifetime_milk_l: float = 0.0      # Goats
    lifetime_eggs: int = 0            # Chickens
    current_lactation_milk_l: float = 0.0
    days_in_lactation: int = 0

    # Death tracking
    death_tick: Optional[int] = None
    cause_of_death: str = ""

    def get_age_days(self) -> int:
        """Get age in days (24 ticks per day)."""
        return (self.current_tick - self.birth_tick) // 24

    def is_alive(self) -> bool:
        """Check if animal is alive."""
        return self.life_stage != LifeStage.DECEASED

    def is_productive(self) -> bool:
        """Check if animal can produce (milk/eggs)."""
        if not self.is_alive():
            return False
        if self.life_stage not in [LifeStage.MATURE, LifeStage.SENIOR]:
            return False
        if self.health < 0.3:
            return False
        if self.sex == "male":
            return False
        return True

    def can_breed(self) -> bool:
        """Check if animal can breed."""
        if not self.is_alive():
            return False
        if self.life_stage not in [LifeStage.MATURE]:
            return False
        if self.health < 0.5:
            return False
        if self.sex == "female" and self.breeding_status not in [BreedingStatus.OPEN, BreedingStatus.LACTATING]:
            return False
        return True


class GoatLifecycleManager:
    """
    Manages goat lifecycle and breeding.

    Nigerian Dwarf Goat Parameters:
    - Gestation: 145-153 days (avg 150)
    - Sexual maturity: 3-4 months (females), 4-5 months (males)
    - Breeding age: 7-8 months (after reaching 40% adult weight)
    - Kids per birth: 1-4 (avg 2-3)
    - Lactation length: 305 days
    - Productive lifespan: 8-12 years
    - Adult weight: Does 30-35kg, Bucks 35-40kg
    """

    # Species parameters
    GESTATION_DAYS = 150
    BREEDING_AGE_DAYS = 240  # 8 months
    SEXUAL_MATURITY_DAYS = 120  # 4 months
    LACTATION_DAYS = 305
    DRY_PERIOD_DAYS = 60
    PRODUCTIVE_YEARS = 8
    MAX_AGE_YEARS = 12

    BIRTH_WEIGHT_KG = 1.5
    ADULT_DOE_WEIGHT_KG = 32.0
    ADULT_BUCK_WEIGHT_KG = 38.0
    GROWTH_RATE_KG_PER_DAY = 0.08

    AVG_KIDS_PER_BIRTH = 2.3
    BREEDING_SUCCESS_RATE = 0.85
    KID_SURVIVAL_RATE = 0.92

    PEAK_MILK_L_PER_DAY = 1.5

    def __init__(self):
        self.animals: Dict[str, AnimalLifecycle] = {}
        self.next_id = 1
        self.breeding_records: List[BreedingRecord] = []

        # Population stats
        self.total_births = 0
        self.total_deaths = 0
        self.total_culled = 0

    def create_animal(self, sex: str, birth_tick: int, genetic_potential: float = None) -> AnimalLifecycle:
        """Create a new goat."""
        if genetic_potential is None:
            genetic_potential = random.gauss(1.0, 0.1)
            genetic_potential = max(0.7, min(1.3, genetic_potential))

        animal_id = f"goat_{self.next_id:04d}"
        self.next_id += 1

        animal = AnimalLifecycle(
            animal_id=animal_id,
            species="goat",
            sex=sex,
            birth_tick=birth_tick,
            current_tick=birth_tick,
            weight_kg=self.BIRTH_WEIGHT_KG,
            genetic_potential=genetic_potential,
        )

        self.animals[animal_id] = animal
        return animal

    def initialize_herd(self, num_does: int, num_bucks: int, start_tick: int = 0) -> List[AnimalLifecycle]:
        """Initialize a starting herd with mature animals."""
        created = []

        # Create does (start at breeding age, in various stages)
        for i in range(num_does):
            age_days = random.randint(365, 730)  # 1-2 years old
            birth_tick = start_tick - (age_days * 24)

            doe = self.create_animal("female", birth_tick)
            doe.current_tick = start_tick
            doe.life_stage = LifeStage.MATURE
            doe.weight_kg = self.ADULT_DOE_WEIGHT_KG * random.uniform(0.9, 1.1)

            # Start some in lactation
            if random.random() < 0.7:
                doe.breeding_status = BreedingStatus.LACTATING
                doe.days_in_lactation = random.randint(30, 200)
            else:
                doe.breeding_status = BreedingStatus.OPEN

            created.append(doe)

        # Create bucks
        for i in range(num_bucks):
            age_days = random.randint(365, 540)  # 1-1.5 years old
            birth_tick = start_tick - (age_days * 24)

            buck = self.create_animal("male", birth_tick)
            buck.current_tick = start_tick
            buck.life_stage = LifeStage.MATURE
            buck.weight_kg = self.ADULT_BUCK_WEIGHT_KG * random.uniform(0.9, 1.1)

            created.append(buck)

        logger.info(f"GoatLifecycleManager: Initialized herd with {num_does} does, {num_bucks} bucks")
        return created

    def update_tick(self, tick: int, feed_available: float, water_available: float) -> Dict:
        """
        Update all animals for one tick.

        Returns production and event data.
        """
        milk_produced = 0.0
        births = []
        deaths = []
        health_events = []

        for animal in list(self.animals.values()):
            if not animal.is_alive():
                continue

            animal.current_tick = tick
            age_days = animal.get_age_days()

            # Update life stage
            self._update_life_stage(animal, age_days)

            # Growth (if not adult)
            self._update_growth(animal, age_days, feed_available)

            # Health check (random events)
            event = self._check_health(animal, tick)
            if event:
                health_events.append(event)

            # Breeding/pregnancy
            birth_result = self._update_breeding(animal, tick)
            if birth_result:
                births.extend(birth_result)
                self.total_births += len(birth_result)

            # Milk production (only at start of day)
            if tick % 24 == 0 and animal.is_productive() and animal.breeding_status == BreedingStatus.LACTATING:
                milk = self._calculate_milk_production(animal, feed_available, water_available)
                milk_produced += milk

            # Mortality check
            if self._check_mortality(animal, tick):
                deaths.append(animal.animal_id)
                self.total_deaths += 1

        return {
            "milk_produced_l": milk_produced,
            "births": births,
            "deaths": deaths,
            "health_events": health_events,
            "total_goats": len([a for a in self.animals.values() if a.is_alive()]),
            "lactating_does": len([a for a in self.animals.values()
                                  if a.is_alive() and a.sex == "female"
                                  and a.breeding_status == BreedingStatus.LACTATING]),
        }

    def _update_life_stage(self, animal: AnimalLifecycle, age_days: int):
        """Update animal's life stage based on age."""
        if animal.life_stage == LifeStage.DECEASED:
            return

        if age_days < 60:
            animal.life_stage = LifeStage.NEWBORN
        elif age_days < self.BREEDING_AGE_DAYS:
            animal.life_stage = LifeStage.JUVENILE
        elif age_days < self.PRODUCTIVE_YEARS * 365:
            animal.life_stage = LifeStage.MATURE
        else:
            animal.life_stage = LifeStage.SENIOR

    def _update_growth(self, animal: AnimalLifecycle, age_days: int, feed_available: float):
        """Update animal weight based on growth."""
        if animal.life_stage in [LifeStage.MATURE, LifeStage.SENIOR]:
            return

        target_weight = self.ADULT_DOE_WEIGHT_KG if animal.sex == "female" else self.ADULT_BUCK_WEIGHT_KG

        if animal.weight_kg < target_weight:
            # Growth rate affected by feed availability
            feed_factor = min(1.0, feed_available / 2.0)  # 2kg/day full ration
            growth = self.GROWTH_RATE_KG_PER_DAY * feed_factor * animal.genetic_potential
            animal.weight_kg = min(target_weight, animal.weight_kg + growth / 24)  # Per tick

    def _check_health(self, animal: AnimalLifecycle, tick: int) -> Optional[Dict]:
        """Check for random health events."""
        if animal.current_health_event:
            # Already dealing with health issue
            animal.recovery_ticks_remaining -= 1
            if animal.recovery_ticks_remaining <= 0:
                animal.current_health_event = None
                animal.health = min(1.0, animal.health + 0.2)
            return None

        # Random health event chance (0.1% per tick = ~2.4% per day)
        if random.random() < 0.001:
            event_type = random.choice([
                HealthEvent.MINOR_ILLNESS,
                HealthEvent.STRESS,
                HealthEvent.NUTRITIONAL_DEFICIENCY,
            ])

            severity = random.uniform(0.1, 0.4)
            animal.health = max(0.2, animal.health - severity)
            animal.current_health_event = event_type
            animal.recovery_ticks_remaining = random.randint(24, 72)

            record = HealthRecord(
                tick=tick,
                event_type=event_type,
                severity=severity,
                recovery_ticks=animal.recovery_ticks_remaining,
            )
            animal.health_history.append(record)

            return {
                "animal_id": animal.animal_id,
                "event": event_type.name,
                "severity": severity,
            }

        return None

    def _update_breeding(self, animal: AnimalLifecycle, tick: int) -> Optional[List[AnimalLifecycle]]:
        """Update breeding status and handle births."""
        if animal.sex != "female":
            return None

        # Check for birth
        if animal.breeding_status == BreedingStatus.PREGNANT:
            for record in animal.breeding_history:
                if not record.success and record.expected_birth_tick <= tick:
                    # Time to give birth!
                    return self._give_birth(animal, record, tick)

        # Update lactation
        if animal.breeding_status == BreedingStatus.LACTATING:
            animal.days_in_lactation += 1 / 24  # Per tick

            # End lactation after 305 days
            if animal.days_in_lactation >= self.LACTATION_DAYS:
                animal.breeding_status = BreedingStatus.DRY
                animal.days_in_lactation = 0

        # Dry period ends
        if animal.breeding_status == BreedingStatus.DRY:
            dry_days = (tick - animal.breeding_history[-1].actual_birth_tick if animal.breeding_history else 0) / 24
            if dry_days >= self.LACTATION_DAYS + self.DRY_PERIOD_DAYS:
                animal.breeding_status = BreedingStatus.OPEN

        return None

    def breed_animals(self, doe_id: str, buck_id: str, tick: int) -> bool:
        """Attempt to breed two animals."""
        doe = self.animals.get(doe_id)
        buck = self.animals.get(buck_id)

        if not doe or not buck:
            return False
        if not doe.can_breed() or not buck.can_breed():
            return False
        if doe.sex != "female" or buck.sex != "male":
            return False

        # Breeding success check
        success = random.random() < self.BREEDING_SUCCESS_RATE * doe.health * buck.health

        if success:
            expected_birth = tick + (self.GESTATION_DAYS * 24)

            record = BreedingRecord(
                breeding_tick=tick,
                sire_id=buck_id,
                dam_id=doe_id,
                expected_birth_tick=expected_birth,
            )

            doe.breeding_status = BreedingStatus.PREGNANT
            doe.times_bred += 1
            doe.breeding_history.append(record)
            self.breeding_records.append(record)

            logger.info(f"Breeding successful: {doe_id} x {buck_id}, expected birth at tick {expected_birth}")
            return True

        return False

    def _give_birth(self, doe: AnimalLifecycle, record: BreedingRecord, tick: int) -> List[AnimalLifecycle]:
        """Handle birth event."""
        # Determine number of kids
        num_kids = max(1, int(random.gauss(self.AVG_KIDS_PER_BIRTH, 0.7)))
        num_kids = min(4, num_kids)

        # Birth complications check
        if random.random() < 0.05:  # 5% complication rate
            doe.health = max(0.3, doe.health - 0.3)
            health_record = HealthRecord(
                tick=tick,
                event_type=HealthEvent.BIRTHING_COMPLICATIONS,
                severity=0.3,
            )
            doe.health_history.append(health_record)

        kids = []
        for i in range(num_kids):
            # Kid survival check
            if random.random() < self.KID_SURVIVAL_RATE:
                sex = "female" if random.random() < 0.5 else "male"

                # Inherit genetics
                sire = self.animals.get(record.sire_id)
                sire_genetics = sire.genetic_potential if sire else 1.0
                kid_genetics = (doe.genetic_potential + sire_genetics) / 2
                kid_genetics += random.gauss(0, 0.05)  # Variation

                kid = self.create_animal(sex, tick, kid_genetics)
                kids.append(kid)
                record.offspring_ids.append(kid.animal_id)

        record.success = True
        record.actual_birth_tick = tick
        record.offspring_count = len(kids)

        doe.total_offspring += len(kids)
        doe.breeding_status = BreedingStatus.LACTATING
        doe.days_in_lactation = 0
        doe.current_lactation_milk_l = 0.0

        logger.info(f"{doe.animal_id} gave birth to {len(kids)} kids at tick {tick}")

        return kids

    def _calculate_milk_production(self, doe: AnimalLifecycle, feed_available: float, water_available: float) -> float:
        """Calculate daily milk production for a doe."""
        if doe.breeding_status != BreedingStatus.LACTATING:
            return 0.0

        # Lactation curve (peaks around day 60, declines after)
        days = doe.days_in_lactation
        if days < 60:
            curve_factor = 0.5 + (days / 60) * 0.5  # Ramp up
        elif days < 150:
            curve_factor = 1.0  # Peak
        else:
            curve_factor = max(0.3, 1.0 - (days - 150) / 300)  # Decline

        # Resource factors
        feed_factor = min(1.0, feed_available / 2.0)
        water_factor = min(1.0, water_available / 4.0)

        milk = (self.PEAK_MILK_L_PER_DAY *
                doe.genetic_potential *
                doe.health *
                curve_factor *
                min(feed_factor, water_factor))

        doe.lifetime_milk_l += milk
        doe.current_lactation_milk_l += milk

        return milk

    def _check_mortality(self, animal: AnimalLifecycle, tick: int) -> bool:
        """Check if animal dies."""
        if not animal.is_alive():
            return False

        age_days = animal.get_age_days()

        # Natural mortality increases with age and poor health
        base_mortality = 0.0001  # 0.01% per tick baseline

        if animal.life_stage == LifeStage.NEWBORN:
            base_mortality = 0.0005  # Higher for young
        elif animal.life_stage == LifeStage.SENIOR:
            base_mortality = 0.001  # Higher for old

        # Health factor
        health_factor = max(1.0, 2.0 - animal.health)  # Lower health = higher mortality

        # Age factor (exponential increase after max age)
        if age_days > self.MAX_AGE_YEARS * 365:
            age_factor = 1 + (age_days - self.MAX_AGE_YEARS * 365) / 365
        else:
            age_factor = 1.0

        mortality_chance = base_mortality * health_factor * age_factor

        if random.random() < mortality_chance:
            animal.life_stage = LifeStage.DECEASED
            animal.death_tick = tick
            animal.cause_of_death = "natural"
            return True

        return False

    def cull_animal(self, animal_id: str, tick: int, reason: str = "management") -> Optional[float]:
        """
        Cull an animal and return meat yield.

        Returns meat in kg, or None if animal not found.
        """
        animal = self.animals.get(animal_id)
        if not animal or not animal.is_alive():
            return None

        # Calculate meat yield (about 50% of live weight)
        meat_yield = animal.weight_kg * 0.5

        animal.life_stage = LifeStage.DECEASED
        animal.death_tick = tick
        animal.cause_of_death = f"culled: {reason}"

        self.total_culled += 1

        logger.info(f"Culled {animal_id}: {meat_yield:.1f}kg meat")

        return meat_yield

    def get_population_stats(self) -> Dict:
        """Get current population statistics."""
        alive = [a for a in self.animals.values() if a.is_alive()]

        does = [a for a in alive if a.sex == "female"]
        bucks = [a for a in alive if a.sex == "male"]

        return {
            "total_alive": len(alive),
            "does": len(does),
            "bucks": len(bucks),
            "lactating": len([d for d in does if d.breeding_status == BreedingStatus.LACTATING]),
            "pregnant": len([d for d in does if d.breeding_status == BreedingStatus.PREGNANT]),
            "kids": len([a for a in alive if a.life_stage == LifeStage.JUVENILE]),
            "avg_health": sum(a.health for a in alive) / max(1, len(alive)),
            "total_births": self.total_births,
            "total_deaths": self.total_deaths,
            "total_culled": self.total_culled,
        }


class ChickenLifecycleManager:
    """
    Manages chicken lifecycle and breeding.

    ISA Brown Layer Parameters:
    - Sexual maturity: 18-20 weeks
    - Peak production: 24-36 weeks
    - Laying period: 72-78 weeks
    - Eggs per year: 300-320
    - Adult weight: Hens 2.0-2.5kg, Roosters 2.5-3.0kg
    - Incubation: 21 days
    - Chicks per hatch: 8-12 (from setting of 12 eggs)
    """

    MATURITY_DAYS = 140  # 20 weeks
    PEAK_START_DAYS = 168  # 24 weeks
    PEAK_END_DAYS = 252  # 36 weeks
    LAYING_END_DAYS = 546  # 78 weeks
    MAX_AGE_DAYS = 1095  # 3 years

    INCUBATION_DAYS = 21
    EGGS_PER_CLUTCH = 12
    HATCH_RATE = 0.75
    CHICK_SURVIVAL = 0.90

    ADULT_HEN_WEIGHT_KG = 2.2
    ADULT_ROOSTER_WEIGHT_KG = 2.8
    CHICK_WEIGHT_KG = 0.04

    PEAK_EGGS_PER_DAY = 0.95  # 95% laying rate at peak

    def __init__(self):
        self.animals: Dict[str, AnimalLifecycle] = {}
        self.next_id = 1
        self.incubating_eggs: List[Dict] = []

        self.total_births = 0
        self.total_deaths = 0
        self.total_culled = 0

    def create_animal(self, sex: str, birth_tick: int, genetic_potential: float = None) -> AnimalLifecycle:
        """Create a new chicken."""
        if genetic_potential is None:
            genetic_potential = random.gauss(1.0, 0.08)
            genetic_potential = max(0.8, min(1.2, genetic_potential))

        animal_id = f"chicken_{self.next_id:04d}"
        self.next_id += 1

        animal = AnimalLifecycle(
            animal_id=animal_id,
            species="chicken",
            sex=sex,
            birth_tick=birth_tick,
            current_tick=birth_tick,
            weight_kg=self.CHICK_WEIGHT_KG,
            genetic_potential=genetic_potential,
        )

        self.animals[animal_id] = animal
        return animal

    def initialize_flock(self, num_hens: int, num_roosters: int, start_tick: int = 0) -> List[AnimalLifecycle]:
        """Initialize a starting flock with mature birds."""
        created = []

        # Create hens at various ages within laying period
        for i in range(num_hens):
            age_days = random.randint(self.MATURITY_DAYS, self.PEAK_END_DAYS)
            birth_tick = start_tick - (age_days * 24)

            hen = self.create_animal("female", birth_tick)
            hen.current_tick = start_tick
            hen.life_stage = LifeStage.MATURE
            hen.weight_kg = self.ADULT_HEN_WEIGHT_KG * random.uniform(0.95, 1.05)

            created.append(hen)

        # Create roosters
        for i in range(num_roosters):
            age_days = random.randint(self.MATURITY_DAYS, 365)
            birth_tick = start_tick - (age_days * 24)

            rooster = self.create_animal("male", birth_tick)
            rooster.current_tick = start_tick
            rooster.life_stage = LifeStage.MATURE
            rooster.weight_kg = self.ADULT_ROOSTER_WEIGHT_KG * random.uniform(0.95, 1.05)

            created.append(rooster)

        logger.info(f"ChickenLifecycleManager: Initialized flock with {num_hens} hens, {num_roosters} roosters")
        return created

    def update_tick(self, tick: int, feed_available: float, water_available: float) -> Dict:
        """Update all chickens for one tick."""
        eggs_produced = 0
        hatches = []
        deaths = []

        # Check incubating eggs
        for egg_batch in list(self.incubating_eggs):
            if tick >= egg_batch["hatch_tick"]:
                chicks = self._hatch_eggs(egg_batch, tick)
                hatches.extend(chicks)
                self.incubating_eggs.remove(egg_batch)

        # Update each bird
        for animal in list(self.animals.values()):
            if not animal.is_alive():
                continue

            animal.current_tick = tick
            age_days = animal.get_age_days()

            self._update_life_stage(animal, age_days)
            self._update_growth(animal, feed_available)

            # Egg production (only at start of day)
            if tick % 24 == 0 and animal.is_productive():
                if self._check_egg_production(animal, age_days, feed_available, water_available):
                    eggs_produced += 1

            # Mortality check
            if self._check_mortality(animal, tick, age_days):
                deaths.append(animal.animal_id)
                self.total_deaths += 1

        return {
            "eggs_produced": eggs_produced,
            "hatches": hatches,
            "deaths": deaths,
            "total_chickens": len([a for a in self.animals.values() if a.is_alive()]),
            "laying_hens": len([a for a in self.animals.values()
                               if a.is_alive() and a.sex == "female"
                               and a.life_stage == LifeStage.MATURE]),
        }

    def _update_life_stage(self, animal: AnimalLifecycle, age_days: int):
        """Update chicken's life stage."""
        if animal.life_stage == LifeStage.DECEASED:
            return

        if age_days < 42:  # 6 weeks
            animal.life_stage = LifeStage.NEWBORN
        elif age_days < self.MATURITY_DAYS:
            animal.life_stage = LifeStage.JUVENILE
        elif age_days < self.LAYING_END_DAYS:
            animal.life_stage = LifeStage.MATURE
        else:
            animal.life_stage = LifeStage.SENIOR

    def _update_growth(self, animal: AnimalLifecycle, feed_available: float):
        """Update chicken weight."""
        if animal.life_stage in [LifeStage.MATURE, LifeStage.SENIOR]:
            return

        target = self.ADULT_HEN_WEIGHT_KG if animal.sex == "female" else self.ADULT_ROOSTER_WEIGHT_KG

        if animal.weight_kg < target:
            feed_factor = min(1.0, feed_available / 0.1)
            growth_rate = (target - self.CHICK_WEIGHT_KG) / (self.MATURITY_DAYS * 24)
            animal.weight_kg = min(target, animal.weight_kg + growth_rate * feed_factor)

    def _check_egg_production(self, hen: AnimalLifecycle, age_days: int,
                              feed_available: float, water_available: float) -> bool:
        """Check if hen lays an egg today."""
        if hen.sex != "female":
            return False

        # Laying rate curve
        if age_days < self.MATURITY_DAYS:
            return False
        elif age_days < self.PEAK_START_DAYS:
            base_rate = 0.5 + (age_days - self.MATURITY_DAYS) / (self.PEAK_START_DAYS - self.MATURITY_DAYS) * 0.45
        elif age_days < self.PEAK_END_DAYS:
            base_rate = self.PEAK_EGGS_PER_DAY
        elif age_days < self.LAYING_END_DAYS:
            decline_days = age_days - self.PEAK_END_DAYS
            base_rate = self.PEAK_EGGS_PER_DAY * (1 - decline_days / (self.LAYING_END_DAYS - self.PEAK_END_DAYS) * 0.5)
        else:
            base_rate = 0.3  # Older hens still lay occasionally

        # Factors
        feed_factor = min(1.0, feed_available / 0.12)
        water_factor = min(1.0, water_available / 0.25)

        final_rate = base_rate * hen.genetic_potential * hen.health * min(feed_factor, water_factor)

        if random.random() < final_rate:
            hen.lifetime_eggs += 1
            return True

        return False

    def set_eggs_for_incubation(self, num_eggs: int, tick: int):
        """Set eggs aside for incubation."""
        hatch_tick = tick + (self.INCUBATION_DAYS * 24)

        self.incubating_eggs.append({
            "set_tick": tick,
            "hatch_tick": hatch_tick,
            "num_eggs": num_eggs,
        })

        logger.info(f"Set {num_eggs} eggs for incubation, expected hatch at tick {hatch_tick}")

    def _hatch_eggs(self, egg_batch: Dict, tick: int) -> List[AnimalLifecycle]:
        """Hatch a batch of incubating eggs."""
        chicks = []

        for _ in range(egg_batch["num_eggs"]):
            # Hatch rate check
            if random.random() < self.HATCH_RATE:
                # Chick survival check
                if random.random() < self.CHICK_SURVIVAL:
                    sex = "female" if random.random() < 0.5 else "male"
                    chick = self.create_animal(sex, tick)
                    chicks.append(chick)
                    self.total_births += 1

        logger.info(f"Hatched {len(chicks)} chicks from {egg_batch['num_eggs']} eggs")
        return chicks

    def _check_mortality(self, animal: AnimalLifecycle, tick: int, age_days: int) -> bool:
        """Check for chicken mortality."""
        if not animal.is_alive():
            return False

        base_mortality = 0.00005  # Lower than goats

        if animal.life_stage == LifeStage.NEWBORN:
            base_mortality = 0.0002
        elif age_days > self.MAX_AGE_DAYS:
            base_mortality = 0.002

        health_factor = max(1.0, 2.0 - animal.health)

        if random.random() < base_mortality * health_factor:
            animal.life_stage = LifeStage.DECEASED
            animal.death_tick = tick
            animal.cause_of_death = "natural"
            return True

        return False

    def cull_animal(self, animal_id: str, tick: int, reason: str = "management") -> Optional[float]:
        """Cull a chicken and return meat yield."""
        animal = self.animals.get(animal_id)
        if not animal or not animal.is_alive():
            return None

        meat_yield = animal.weight_kg * 0.65  # Higher dress percentage than goats

        animal.life_stage = LifeStage.DECEASED
        animal.death_tick = tick
        animal.cause_of_death = f"culled: {reason}"

        self.total_culled += 1

        return meat_yield

    def get_population_stats(self) -> Dict:
        """Get current population statistics."""
        alive = [a for a in self.animals.values() if a.is_alive()]

        hens = [a for a in alive if a.sex == "female"]
        roosters = [a for a in alive if a.sex == "male"]

        return {
            "total_alive": len(alive),
            "hens": len(hens),
            "roosters": len(roosters),
            "laying_hens": len([h for h in hens if h.life_stage == LifeStage.MATURE]),
            "chicks": len([a for a in alive if a.life_stage in [LifeStage.NEWBORN, LifeStage.JUVENILE]]),
            "incubating_eggs": sum(e["num_eggs"] for e in self.incubating_eggs),
            "avg_health": sum(a.health for a in alive) / max(1, len(alive)),
            "total_births": self.total_births,
            "total_deaths": self.total_deaths,
            "total_culled": self.total_culled,
        }
