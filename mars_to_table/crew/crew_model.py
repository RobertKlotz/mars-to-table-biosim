"""
Mars to Table — Crew Model
Individual crew member modeling with metabolic needs and activity tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging
import random

from ..config import MISSION

logger = logging.getLogger(__name__)


class CrewRole(Enum):
    """Crew member roles/specializations."""
    COMMANDER = auto()
    PILOT = auto()
    FLIGHT_ENGINEER = auto()
    MISSION_SPECIALIST = auto()
    SCIENCE_OFFICER = auto()
    MEDICAL_OFFICER = auto()
    FOOD_SYSTEM_ENGINEER = auto()
    NUTRITION_SPECIALIST = auto()
    EVA_SPECIALIST = auto()
    SYSTEMS_ENGINEER = auto()
    GEOLOGIST = auto()
    BIOLOGIST = auto()


class ActivityLevel(Enum):
    """Activity levels affecting caloric needs."""
    SLEEP = auto()        # 0.9x basal
    SEDENTARY = auto()    # 1.0x basal (desk work)
    LIGHT = auto()        # 1.2x basal (lab work)
    MODERATE = auto()     # 1.5x basal (maintenance)
    ACTIVE = auto()       # 1.75x basal (heavy work)
    EVA = auto()          # 2.0x basal + EVA bonus


# Activity level multipliers for caloric calculation
ACTIVITY_MULTIPLIERS = {
    ActivityLevel.SLEEP: 0.9,
    ActivityLevel.SEDENTARY: 1.0,
    ActivityLevel.LIGHT: 1.2,
    ActivityLevel.MODERATE: 1.5,
    ActivityLevel.ACTIVE: 1.75,
    ActivityLevel.EVA: 2.0,
}


class HealthStatus(Enum):
    """Crew member health status."""
    HEALTHY = auto()
    FATIGUED = auto()
    MILDLY_ILL = auto()
    ILL = auto()
    INJURED = auto()
    INCAPACITATED = auto()


@dataclass
class CrewMember:
    """
    Individual crew member with metabolic and activity tracking.

    Based on NASA STD-3001 crew health standards.
    """
    crew_id: str
    name: str
    role: CrewRole
    age: int
    sex: str  # 'M' or 'F'
    weight_kg: float
    height_cm: float

    # Current state
    health_status: HealthStatus = HealthStatus.HEALTHY
    current_activity: ActivityLevel = ActivityLevel.SEDENTARY
    morale: float = 1.0  # 0.0 to 1.0

    # Daily tracking
    calories_consumed_today: float = 0.0
    water_consumed_today_l: float = 0.0
    hours_eva_today: float = 0.0
    hours_sleep_today: float = 0.0

    # Cumulative tracking
    total_calories_consumed: float = 0.0
    total_eva_hours: float = 0.0
    days_without_adequate_food: int = 0
    days_without_adequate_water: int = 0

    @property
    def bmi(self) -> float:
        """Calculate Body Mass Index."""
        height_m = self.height_cm / 100
        return self.weight_kg / (height_m ** 2)

    @property
    def basal_metabolic_rate(self) -> float:
        """
        Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.

        Returns kcal/day at rest.
        """
        if self.sex == 'M':
            bmr = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age + 5
        else:
            bmr = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age - 161
        return bmr

    @property
    def daily_calorie_requirement(self) -> float:
        """
        Calculate daily calorie requirement based on activity.

        Uses NASA STD-3001 baseline of 3035 kcal for active astronaut.
        """
        # Start with NASA baseline
        base = MISSION.base_calories_per_crew_per_day

        # Small adjustment for individual BMR variation (+/- 10%)
        standard_bmr = 1700  # Approximate average BMR
        bmr_factor = 0.9 + 0.2 * (self.basal_metabolic_rate / standard_bmr - 1)
        bmr_factor = max(0.85, min(1.15, bmr_factor))  # Clamp to +/- 15%

        # Adjust for activity level (baseline assumes moderate activity)
        activity_multipliers = {
            ActivityLevel.SLEEP: 0.85,
            ActivityLevel.SEDENTARY: 0.90,
            ActivityLevel.LIGHT: 0.95,
            ActivityLevel.MODERATE: 1.0,
            ActivityLevel.ACTIVE: 1.10,
            ActivityLevel.EVA: 1.20,
        }
        activity_factor = activity_multipliers.get(self.current_activity, 1.0)

        # Adjust for health status
        health_factors = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.FATIGUED: 0.95,
            HealthStatus.MILDLY_ILL: 0.9,
            HealthStatus.ILL: 0.8,
            HealthStatus.INJURED: 0.85,
            HealthStatus.INCAPACITATED: 0.7,
        }
        health_factor = health_factors.get(self.health_status, 1.0)

        # Calculate requirement
        requirement = base * bmr_factor * activity_factor * health_factor

        # Add EVA bonus if applicable
        if self.current_activity == ActivityLevel.EVA:
            requirement += self.hours_eva_today * MISSION.eva_bonus_calories_per_hour

        return requirement

    @property
    def daily_water_requirement_l(self) -> float:
        """Calculate daily water requirement in liters."""
        # Base: 3L per day per NASA standards
        base = 3.0

        # Increase for activity
        activity_factors = {
            ActivityLevel.SLEEP: 0.8,
            ActivityLevel.SEDENTARY: 1.0,
            ActivityLevel.LIGHT: 1.1,
            ActivityLevel.MODERATE: 1.3,
            ActivityLevel.ACTIVE: 1.5,
            ActivityLevel.EVA: 2.0,
        }
        factor = activity_factors.get(self.current_activity, 1.0)

        return base * factor

    def set_activity(self, activity: ActivityLevel, eva_hours: float = 0.0):
        """Set current activity level."""
        self.current_activity = activity
        if activity == ActivityLevel.EVA:
            self.hours_eva_today += eva_hours
            self.total_eva_hours += eva_hours

    def consume_meal(self, calories: float, water_l: float = 0.5):
        """Record consumption of a meal."""
        self.calories_consumed_today += calories
        self.water_consumed_today_l += water_l
        self.total_calories_consumed += calories

    def sleep(self, hours: float):
        """Record sleep hours."""
        self.hours_sleep_today += hours
        self.current_activity = ActivityLevel.SLEEP

    def end_day(self) -> Dict:
        """
        End of day processing.

        Returns summary of the day's nutrition status.
        """
        calorie_deficit = self.daily_calorie_requirement - self.calories_consumed_today
        water_deficit = self.daily_water_requirement_l - self.water_consumed_today_l

        # Track inadequate nutrition days
        if calorie_deficit > self.daily_calorie_requirement * 0.2:  # >20% deficit
            self.days_without_adequate_food += 1
        else:
            self.days_without_adequate_food = max(0, self.days_without_adequate_food - 1)

        if water_deficit > 0.5:  # >0.5L deficit
            self.days_without_adequate_water += 1
        else:
            self.days_without_adequate_water = max(0, self.days_without_adequate_water - 1)

        # Update health based on nutrition
        self._update_health()

        # Update morale
        self._update_morale()

        summary = {
            "crew_id": self.crew_id,
            "name": self.name,
            "calories_required": self.daily_calorie_requirement,
            "calories_consumed": self.calories_consumed_today,
            "calorie_deficit": calorie_deficit,
            "water_required_l": self.daily_water_requirement_l,
            "water_consumed_l": self.water_consumed_today_l,
            "water_deficit_l": water_deficit,
            "hours_eva": self.hours_eva_today,
            "hours_sleep": self.hours_sleep_today,
            "health_status": self.health_status.name,
            "morale": self.morale,
        }

        # Reset daily counters
        self.calories_consumed_today = 0.0
        self.water_consumed_today_l = 0.0
        self.hours_eva_today = 0.0
        self.hours_sleep_today = 0.0
        self.current_activity = ActivityLevel.SEDENTARY

        return summary

    def _update_health(self):
        """Update health status based on nutrition history."""
        if self.days_without_adequate_food >= 7 or self.days_without_adequate_water >= 3:
            self.health_status = HealthStatus.ILL
        elif self.days_without_adequate_food >= 3 or self.days_without_adequate_water >= 2:
            self.health_status = HealthStatus.MILDLY_ILL
        elif self.days_without_adequate_food >= 1 or self.days_without_adequate_water >= 1:
            self.health_status = HealthStatus.FATIGUED
        elif self.health_status in (HealthStatus.FATIGUED, HealthStatus.MILDLY_ILL):
            self.health_status = HealthStatus.HEALTHY

    def _update_morale(self):
        """Update morale based on various factors."""
        # Base morale recovery/decay
        target_morale = 0.8

        # Factors affecting morale
        if self.health_status == HealthStatus.HEALTHY:
            target_morale += 0.1
        elif self.health_status in (HealthStatus.ILL, HealthStatus.INJURED):
            target_morale -= 0.2

        if self.days_without_adequate_food > 0:
            target_morale -= 0.1 * self.days_without_adequate_food

        if self.hours_sleep_today < 6:
            target_morale -= 0.1

        # Slowly adjust morale toward target
        self.morale = self.morale * 0.9 + target_morale * 0.1
        self.morale = max(0.0, min(1.0, self.morale))

    def get_status(self) -> Dict:
        """Get current crew member status."""
        return {
            "crew_id": self.crew_id,
            "name": self.name,
            "role": self.role.name,
            "health_status": self.health_status.name,
            "current_activity": self.current_activity.name,
            "morale": self.morale,
            "daily_calorie_requirement": self.daily_calorie_requirement,
            "daily_water_requirement_l": self.daily_water_requirement_l,
            "calories_consumed_today": self.calories_consumed_today,
            "water_consumed_today_l": self.water_consumed_today_l,
            "bmi": self.bmi,
            "total_eva_hours": self.total_eva_hours,
        }


class CrewManager:
    """
    Manages the full crew complement.

    Handles crew-wide operations, scheduling, and aggregate tracking.
    """

    def __init__(self):
        self.crew: Dict[str, CrewMember] = {}
        self.crew_size = 0

        # Daily schedule template (hour -> typical activity)
        self.default_schedule = {
            0: ActivityLevel.SLEEP,
            1: ActivityLevel.SLEEP,
            2: ActivityLevel.SLEEP,
            3: ActivityLevel.SLEEP,
            4: ActivityLevel.SLEEP,
            5: ActivityLevel.SLEEP,
            6: ActivityLevel.LIGHT,      # Wake up, breakfast
            7: ActivityLevel.LIGHT,      # Morning prep
            8: ActivityLevel.MODERATE,   # Work period 1
            9: ActivityLevel.MODERATE,
            10: ActivityLevel.MODERATE,
            11: ActivityLevel.MODERATE,
            12: ActivityLevel.LIGHT,     # Lunch
            13: ActivityLevel.MODERATE,  # Work period 2
            14: ActivityLevel.MODERATE,
            15: ActivityLevel.MODERATE,
            16: ActivityLevel.MODERATE,
            17: ActivityLevel.LIGHT,     # Wrap up
            18: ActivityLevel.LIGHT,     # Dinner
            19: ActivityLevel.SEDENTARY, # Personal time
            20: ActivityLevel.SEDENTARY,
            21: ActivityLevel.SEDENTARY,
            22: ActivityLevel.SLEEP,     # Sleep prep
            23: ActivityLevel.SLEEP,
        }

    def add_crew_member(self, member: CrewMember):
        """Add a crew member."""
        self.crew[member.crew_id] = member
        self.crew_size = len(self.crew)

    def get_crew_member(self, crew_id: str) -> Optional[CrewMember]:
        """Get a crew member by ID."""
        return self.crew.get(crew_id)

    def initialize_default_crew(self):
        """
        Initialize default 15-person crew.

        Based on challenge requirement for diverse, realistic crew.
        """
        crew_templates = [
            ("CDR", "Commander Chen", CrewRole.COMMANDER, 45, 'F', 65, 168),
            ("PLT", "Pilot Rodriguez", CrewRole.PILOT, 38, 'M', 80, 180),
            ("FE1", "Engineer Okonkwo", CrewRole.FLIGHT_ENGINEER, 35, 'M', 75, 175),
            ("MS1", "Specialist Nakamura", CrewRole.MISSION_SPECIALIST, 40, 'F', 58, 162),
            ("MS2", "Specialist Petrov", CrewRole.MISSION_SPECIALIST, 42, 'M', 82, 183),
            ("SCI", "Scientist Dubois", CrewRole.SCIENCE_OFFICER, 36, 'F', 62, 170),
            ("MED", "Dr. Abubakar", CrewRole.MEDICAL_OFFICER, 44, 'M', 78, 178),
            ("FSE", "Food Eng. Martinez", CrewRole.FOOD_SYSTEM_ENGINEER, 33, 'F', 60, 165),
            ("NUT", "Nutritionist Kim", CrewRole.NUTRITION_SPECIALIST, 31, 'F', 55, 160),
            ("EVA1", "EVA Spec. Johnson", CrewRole.EVA_SPECIALIST, 37, 'M', 85, 185),
            ("EVA2", "EVA Spec. Singh", CrewRole.EVA_SPECIALIST, 34, 'M', 77, 176),
            ("SYS", "Systems Eng. Mueller", CrewRole.SYSTEMS_ENGINEER, 39, 'M', 73, 172),
            ("GEO", "Geologist Thompson", CrewRole.GEOLOGIST, 41, 'F', 64, 167),
            ("BIO", "Biologist Sato", CrewRole.BIOLOGIST, 32, 'F', 52, 158),
            ("MS3", "Specialist Kowalski", CrewRole.MISSION_SPECIALIST, 36, 'M', 79, 179),
        ]

        for crew_id, name, role, age, sex, weight, height in crew_templates:
            member = CrewMember(
                crew_id=crew_id,
                name=name,
                role=role,
                age=age,
                sex=sex,
                weight_kg=weight,
                height_cm=height,
            )
            self.add_crew_member(member)

        logger.info(f"Crew initialized: {self.crew_size} members")

    def get_total_calorie_requirement(self) -> float:
        """Get total daily calorie requirement for all crew."""
        return sum(m.daily_calorie_requirement for m in self.crew.values())

    def get_total_water_requirement(self) -> float:
        """Get total daily water requirement for all crew."""
        return sum(m.daily_water_requirement_l for m in self.crew.values())

    def update_activity_for_hour(self, hour: int):
        """Update all crew activities based on schedule."""
        activity = self.default_schedule.get(hour, ActivityLevel.SEDENTARY)

        for member in self.crew.values():
            # Don't change activity if on EVA or incapacitated
            if member.current_activity != ActivityLevel.EVA and \
               member.health_status != HealthStatus.INCAPACITATED:
                member.current_activity = activity

    def schedule_eva(self, crew_ids: List[str], hours: float):
        """Schedule EVA for specified crew members."""
        for crew_id in crew_ids:
            member = self.crew.get(crew_id)
            if member and member.health_status == HealthStatus.HEALTHY:
                member.set_activity(ActivityLevel.EVA, hours)
                logger.info(f"{member.name} scheduled for {hours}h EVA")

    def serve_meal(self, calories_per_person: float, water_per_person_l: float = 0.5):
        """Serve a meal to all crew members."""
        for member in self.crew.values():
            if member.health_status != HealthStatus.INCAPACITATED:
                member.consume_meal(calories_per_person, water_per_person_l)

    def end_day(self) -> Dict:
        """
        Process end of day for all crew.

        Returns aggregate summary.
        """
        summaries = []
        total_calories_consumed = 0.0
        total_calories_required = 0.0
        healthy_count = 0
        fatigued_count = 0
        ill_count = 0

        for member in self.crew.values():
            summary = member.end_day()
            summaries.append(summary)

            total_calories_consumed += summary["calories_consumed"]
            total_calories_required += summary["calories_required"]

            if member.health_status == HealthStatus.HEALTHY:
                healthy_count += 1
            elif member.health_status == HealthStatus.FATIGUED:
                fatigued_count += 1
            else:
                ill_count += 1

        avg_morale = sum(m.morale for m in self.crew.values()) / self.crew_size

        return {
            "crew_size": self.crew_size,
            "total_calories_required": total_calories_required,
            "total_calories_consumed": total_calories_consumed,
            "calorie_satisfaction": total_calories_consumed / total_calories_required if total_calories_required > 0 else 0,
            "healthy_count": healthy_count,
            "fatigued_count": fatigued_count,
            "ill_count": ill_count,
            "average_morale": avg_morale,
            "individual_summaries": summaries,
        }

    def get_status(self) -> Dict:
        """Get current crew status."""
        return {
            "crew_size": self.crew_size,
            "total_calorie_requirement": self.get_total_calorie_requirement(),
            "total_water_requirement_l": self.get_total_water_requirement(),
            "health_summary": {
                "healthy": sum(1 for m in self.crew.values() if m.health_status == HealthStatus.HEALTHY),
                "fatigued": sum(1 for m in self.crew.values() if m.health_status == HealthStatus.FATIGUED),
                "ill": sum(1 for m in self.crew.values() if m.health_status in (HealthStatus.MILDLY_ILL, HealthStatus.ILL)),
                "injured": sum(1 for m in self.crew.values() if m.health_status == HealthStatus.INJURED),
            },
            "average_morale": sum(m.morale for m in self.crew.values()) / max(1, self.crew_size),
            "crew_members": [m.get_status() for m in self.crew.values()],
        }
