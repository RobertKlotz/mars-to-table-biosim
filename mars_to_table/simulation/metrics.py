"""
Mars to Table — Metrics Collection and Analysis
Performance tracking, resource efficiency, and mission success metrics.

Key metrics tracked:
- Earth independence ratio (target: 84%)
- Calorie production and consumption
- Resource efficiency (water, power, nutrients)
- System reliability and failure rates
- Crew health and nutrition
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime
import json
import logging
import statistics

from ..config import MISSION, POWER, WATER, FOOD, LIVESTOCK

logger = logging.getLogger(__name__)


# =============================================================================
# METRIC CATEGORIES
# =============================================================================

class MetricCategory(Enum):
    """Categories of metrics tracked."""
    FOOD_PRODUCTION = auto()
    RESOURCE_EFFICIENCY = auto()
    SYSTEM_RELIABILITY = auto()
    CREW_HEALTH = auto()
    EARTH_INDEPENDENCE = auto()
    MISSION_SUCCESS = auto()


# =============================================================================
# METRIC DATA CLASSES
# =============================================================================

@dataclass
class FoodProductionMetrics:
    """Metrics for food production systems."""
    # Daily production (kg)
    vegetables_kg: float = 0.0
    potatoes_kg: float = 0.0
    legumes_kg: float = 0.0
    flour_kg: float = 0.0
    fodder_kg: float = 0.0

    # Livestock products
    milk_liters: float = 0.0
    eggs_count: float = 0.0
    cheese_kg: float = 0.0
    meat_kg: float = 0.0

    # Calorie tracking
    calories_produced: float = 0.0
    calories_from_earth: float = 0.0
    calories_consumed: float = 0.0
    calories_wasted: float = 0.0

    # Efficiency
    crop_yield_efficiency: float = 1.0  # Actual vs theoretical
    livestock_efficiency: float = 1.0

    def total_food_kg(self) -> float:
        """Total food produced in kg."""
        return (
            self.vegetables_kg + self.potatoes_kg + self.legumes_kg +
            self.flour_kg + self.cheese_kg + self.meat_kg
        )

    def earth_independence_ratio(self) -> float:
        """Ratio of in-situ calories to total calories."""
        total = self.calories_produced + self.calories_from_earth
        if total == 0:
            return 0.0
        return self.calories_produced / total


@dataclass
class ResourceMetrics:
    """Metrics for resource systems (power, water, nutrients)."""
    # Power
    power_generated_kwh: float = 0.0
    power_consumed_kwh: float = 0.0
    power_from_solar_kwh: float = 0.0
    power_from_fuel_cells_kwh: float = 0.0
    power_from_biogas_kwh: float = 0.0
    power_shortfall_kwh: float = 0.0

    # Water
    water_extracted_liters: float = 0.0
    water_consumed_liters: float = 0.0
    water_recycled_liters: float = 0.0
    water_from_h2_burn_liters: float = 0.0
    water_shortfall_liters: float = 0.0

    # Nutrients
    nitrogen_produced_kg: float = 0.0
    phosphorus_recovered_kg: float = 0.0
    nutrients_consumed_kg: float = 0.0

    # Hydrogen (fuel reserve)
    hydrogen_consumed_kg: float = 0.0
    hydrogen_remaining_kg: float = 0.0

    def power_efficiency(self) -> float:
        """Power utilization efficiency."""
        if self.power_generated_kwh == 0:
            return 0.0
        return self.power_consumed_kwh / self.power_generated_kwh

    def water_recycling_rate(self) -> float:
        """Water recycling efficiency."""
        total_used = self.water_consumed_liters
        if total_used == 0:
            return 0.0
        return self.water_recycled_liters / total_used


@dataclass
class SystemMetrics:
    """Metrics for system reliability."""
    # Module tracking
    total_modules: int = 0
    operational_modules: int = 0
    degraded_modules: int = 0
    failed_modules: int = 0

    # Events
    total_events: int = 0
    power_events: int = 0
    water_events: int = 0
    equipment_events: int = 0

    # Response effectiveness
    events_successfully_handled: int = 0
    events_causing_degradation: int = 0
    events_causing_failure: int = 0

    # Uptime
    total_ticks: int = 0
    ticks_nominal: int = 0
    ticks_degraded: int = 0
    ticks_emergency: int = 0

    def operational_ratio(self) -> float:
        """Ratio of operational modules."""
        if self.total_modules == 0:
            return 0.0
        return self.operational_modules / self.total_modules

    def uptime_ratio(self) -> float:
        """System uptime ratio."""
        if self.total_ticks == 0:
            return 0.0
        return self.ticks_nominal / self.total_ticks


@dataclass
class CrewMetrics:
    """Metrics for crew health and nutrition."""
    # Crew status
    crew_size: int = 15
    crew_healthy: int = 15
    crew_fatigued: int = 0
    crew_ill: int = 0

    # Nutrition
    avg_calories_received: float = 0.0
    avg_calories_required: float = 0.0
    nutrition_deficit_days: int = 0
    nutrition_surplus_days: int = 0

    # Macros
    protein_g_avg: float = 0.0
    carbs_g_avg: float = 0.0
    fat_g_avg: float = 0.0
    fiber_g_avg: float = 0.0

    # EVA
    eva_hours_total: float = 0.0
    eva_calories_extra: float = 0.0

    def nutrition_adequacy(self) -> float:
        """Ratio of calories received to required."""
        if self.avg_calories_required == 0:
            return 0.0
        return self.avg_calories_received / self.avg_calories_required

    def health_ratio(self) -> float:
        """Ratio of healthy crew."""
        if self.crew_size == 0:
            return 0.0
        return self.crew_healthy / self.crew_size


@dataclass
class MissionMetrics:
    """Overall mission success metrics."""
    # Mission progress
    current_sol: int = 0
    total_sols: int = 500
    mission_complete: bool = False
    mission_success: bool = False
    end_reason: str = ""

    # Key success metrics
    earth_independence_achieved: float = 0.0
    earth_independence_target: float = 0.84
    crew_survival_rate: float = 1.0

    # Resource sustainability
    days_food_remaining: float = 0.0
    days_water_remaining: float = 0.0
    days_power_remaining: float = 0.0

    def progress_ratio(self) -> float:
        """Mission progress ratio."""
        return self.current_sol / self.total_sols if self.total_sols > 0 else 0.0

    def earth_independence_margin(self) -> float:
        """Margin above/below target."""
        return self.earth_independence_achieved - self.earth_independence_target


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """
    Collects and aggregates metrics from simulation components.

    Provides:
    - Per-tick metric collection
    - Per-sol aggregation
    - Historical tracking
    - Export to various formats
    """

    def __init__(self):
        # Current metrics
        self.food = FoodProductionMetrics()
        self.resources = ResourceMetrics()
        self.system = SystemMetrics()
        self.crew = CrewMetrics()
        self.mission = MissionMetrics()

        # Historical data
        self.sol_history: List[Dict] = []
        self.tick_samples: List[Dict] = []  # Sampled tick data
        self.sample_rate: int = 24  # Sample every sol

        # Tracking
        self.current_tick: int = 0
        self.current_sol: int = 0

        # Aggregation buffers
        self._tick_buffer: List[Dict] = []

    def record_tick(self, tick_data: Dict):
        """
        Record metrics for a single tick.

        Args:
            tick_data: Dictionary of metrics from simulation tick
        """
        self.current_tick = tick_data.get("tick", self.current_tick)
        self._tick_buffer.append(tick_data)

        # Sample at configured rate
        if self.current_tick % self.sample_rate == 0:
            self.tick_samples.append({
                "tick": self.current_tick,
                "sol": self.current_tick // 24,
                "food_calories": self.food.calories_produced,
                "power_kwh": self.resources.power_generated_kwh,
                "water_liters": self.resources.water_extracted_liters,
                "operational_modules": self.system.operational_modules,
            })

    def record_sol_end(self, sol: int, sol_data: Dict):
        """
        Record end-of-sol summary and aggregate tick data.

        Args:
            sol: Sol number
            sol_data: Summary data from simulation
        """
        self.current_sol = sol
        self.mission.current_sol = sol

        # Aggregate tick buffer
        self._aggregate_tick_buffer()

        # Create sol summary
        sol_summary = {
            "sol": sol,
            "food": {
                "calories_produced": self.food.calories_produced,
                "earth_independence": self.food.earth_independence_ratio(),
                "total_food_kg": self.food.total_food_kg(),
            },
            "resources": {
                "power_efficiency": self.resources.power_efficiency(),
                "water_recycling": self.resources.water_recycling_rate(),
                "h2_remaining_kg": self.resources.hydrogen_remaining_kg,
            },
            "system": {
                "operational_ratio": self.system.operational_ratio(),
                "uptime_ratio": self.system.uptime_ratio(),
                "events_today": len([e for e in self._tick_buffer if e.get("events")]),
            },
            "crew": {
                "health_ratio": self.crew.health_ratio(),
                "nutrition_adequacy": self.crew.nutrition_adequacy(),
            },
            "mission": {
                "progress": self.mission.progress_ratio(),
                "earth_independence": self.mission.earth_independence_achieved,
            },
        }

        self.sol_history.append(sol_summary)
        self._tick_buffer = []

    def _aggregate_tick_buffer(self):
        """Aggregate tick buffer into current metrics."""
        if not self._tick_buffer:
            return

        # Aggregate system metrics
        operational_counts = []
        for tick in self._tick_buffer:
            modules = tick.get("modules", {})
            operational = sum(1 for m in modules.values() if isinstance(m, dict) and m.get("state") == "NOMINAL")
            operational_counts.append(operational)

        if operational_counts:
            self.system.operational_modules = int(statistics.mean(operational_counts))
            self.system.total_ticks += len(self._tick_buffer)
            self.system.ticks_nominal += sum(1 for c in operational_counts if c == self.system.total_modules)

    def update_food_metrics(
        self,
        vegetables_kg: float = 0,
        potatoes_kg: float = 0,
        legumes_kg: float = 0,
        flour_kg: float = 0,
        milk_l: float = 0,
        eggs: float = 0,
        cheese_kg: float = 0,
        meat_kg: float = 0,
        calories_produced: float = 0,
        calories_from_earth: float = 0,
    ):
        """Update food production metrics."""
        self.food.vegetables_kg += vegetables_kg
        self.food.potatoes_kg += potatoes_kg
        self.food.legumes_kg += legumes_kg
        self.food.flour_kg += flour_kg
        self.food.milk_liters += milk_l
        self.food.eggs_count += eggs
        self.food.cheese_kg += cheese_kg
        self.food.meat_kg += meat_kg
        self.food.calories_produced += calories_produced
        self.food.calories_from_earth += calories_from_earth

        # Update mission earth independence
        self.mission.earth_independence_achieved = self.food.earth_independence_ratio()

    def update_resource_metrics(
        self,
        power_generated: float = 0,
        power_consumed: float = 0,
        power_solar: float = 0,
        power_fuel_cell: float = 0,
        power_biogas: float = 0,
        water_extracted: float = 0,
        water_consumed: float = 0,
        water_recycled: float = 0,
        water_h2_burn: float = 0,
        h2_consumed: float = 0,
        h2_remaining: float = 0,
    ):
        """Update resource metrics."""
        self.resources.power_generated_kwh += power_generated
        self.resources.power_consumed_kwh += power_consumed
        self.resources.power_from_solar_kwh += power_solar
        self.resources.power_from_fuel_cells_kwh += power_fuel_cell
        self.resources.power_from_biogas_kwh += power_biogas
        self.resources.water_extracted_liters += water_extracted
        self.resources.water_consumed_liters += water_consumed
        self.resources.water_recycled_liters += water_recycled
        self.resources.water_from_h2_burn_liters += water_h2_burn
        self.resources.hydrogen_consumed_kg += h2_consumed
        self.resources.hydrogen_remaining_kg = h2_remaining

    def update_crew_metrics(
        self,
        healthy: int = 0,
        fatigued: int = 0,
        ill: int = 0,
        calories_received: float = 0,
        calories_required: float = 0,
        protein_g: float = 0,
        carbs_g: float = 0,
        fat_g: float = 0,
    ):
        """Update crew metrics."""
        self.crew.crew_healthy = healthy
        self.crew.crew_fatigued = fatigued
        self.crew.crew_ill = ill
        self.crew.avg_calories_received = calories_received
        self.crew.avg_calories_required = calories_required
        self.crew.protein_g_avg = protein_g
        self.crew.carbs_g_avg = carbs_g
        self.crew.fat_g_avg = fat_g

        # Track deficit/surplus days
        if calories_received < calories_required * 0.9:
            self.crew.nutrition_deficit_days += 1
        elif calories_received > calories_required * 1.1:
            self.crew.nutrition_surplus_days += 1

    def update_system_metrics(
        self,
        total_modules: int = 0,
        operational: int = 0,
        degraded: int = 0,
        failed: int = 0,
        events_today: int = 0,
        events_handled: int = 0,
    ):
        """Update system metrics."""
        self.system.total_modules = total_modules
        self.system.operational_modules = operational
        self.system.degraded_modules = degraded
        self.system.failed_modules = failed
        self.system.total_events += events_today
        self.system.events_successfully_handled += events_handled

    def get_summary(self) -> Dict:
        """Get current metrics summary."""
        return {
            "mission": {
                "sol": self.mission.current_sol,
                "progress": f"{self.mission.progress_ratio() * 100:.1f}%",
                "earth_independence": f"{self.mission.earth_independence_achieved * 100:.1f}%",
                "target": f"{self.mission.earth_independence_target * 100:.1f}%",
                "margin": f"{self.mission.earth_independence_margin() * 100:+.1f}%",
            },
            "food_production": {
                "total_calories": self.food.calories_produced,
                "earth_ratio": f"{self.food.earth_independence_ratio() * 100:.1f}%",
                "total_food_kg": f"{self.food.total_food_kg():.1f}",
            },
            "resources": {
                "power_efficiency": f"{self.resources.power_efficiency() * 100:.1f}%",
                "water_recycling": f"{self.resources.water_recycling_rate() * 100:.1f}%",
                "h2_remaining_kg": f"{self.resources.hydrogen_remaining_kg:.1f}",
            },
            "crew": {
                "health_ratio": f"{self.crew.health_ratio() * 100:.1f}%",
                "nutrition_adequacy": f"{self.crew.nutrition_adequacy() * 100:.1f}%",
                "deficit_days": self.crew.nutrition_deficit_days,
            },
            "system": {
                "uptime": f"{self.system.uptime_ratio() * 100:.1f}%",
                "total_events": self.system.total_events,
                "events_handled": self.system.events_successfully_handled,
            },
        }

    def get_detailed_report(self) -> Dict:
        """Get detailed metrics report."""
        return {
            "generated_at": datetime.now().isoformat(),
            "mission_summary": {
                "sol": self.mission.current_sol,
                "total_sols": self.mission.total_sols,
                "complete": self.mission.mission_complete,
                "success": self.mission.mission_success,
                "end_reason": self.mission.end_reason,
            },
            "earth_independence": {
                "achieved": self.mission.earth_independence_achieved,
                "target": self.mission.earth_independence_target,
                "margin": self.mission.earth_independence_margin(),
                "meets_requirement": self.mission.earth_independence_achieved >= 0.50,
                "meets_target": self.mission.earth_independence_achieved >= self.mission.earth_independence_target,
            },
            "food_production": {
                "vegetables_kg": self.food.vegetables_kg,
                "potatoes_kg": self.food.potatoes_kg,
                "legumes_kg": self.food.legumes_kg,
                "flour_kg": self.food.flour_kg,
                "milk_liters": self.food.milk_liters,
                "eggs_count": self.food.eggs_count,
                "cheese_kg": self.food.cheese_kg,
                "meat_kg": self.food.meat_kg,
                "calories_produced": self.food.calories_produced,
                "calories_from_earth": self.food.calories_from_earth,
                "calories_consumed": self.food.calories_consumed,
                "calories_wasted": self.food.calories_wasted,
            },
            "resources": {
                "power": {
                    "generated_kwh": self.resources.power_generated_kwh,
                    "consumed_kwh": self.resources.power_consumed_kwh,
                    "solar_kwh": self.resources.power_from_solar_kwh,
                    "fuel_cell_kwh": self.resources.power_from_fuel_cells_kwh,
                    "biogas_kwh": self.resources.power_from_biogas_kwh,
                    "efficiency": self.resources.power_efficiency(),
                },
                "water": {
                    "extracted_liters": self.resources.water_extracted_liters,
                    "consumed_liters": self.resources.water_consumed_liters,
                    "recycled_liters": self.resources.water_recycled_liters,
                    "h2_burn_liters": self.resources.water_from_h2_burn_liters,
                    "recycling_rate": self.resources.water_recycling_rate(),
                },
                "hydrogen": {
                    "consumed_kg": self.resources.hydrogen_consumed_kg,
                    "remaining_kg": self.resources.hydrogen_remaining_kg,
                },
            },
            "crew": {
                "size": self.crew.crew_size,
                "healthy": self.crew.crew_healthy,
                "fatigued": self.crew.crew_fatigued,
                "ill": self.crew.crew_ill,
                "avg_calories_received": self.crew.avg_calories_received,
                "avg_calories_required": self.crew.avg_calories_required,
                "nutrition_adequacy": self.crew.nutrition_adequacy(),
                "deficit_days": self.crew.nutrition_deficit_days,
                "surplus_days": self.crew.nutrition_surplus_days,
            },
            "system": {
                "total_modules": self.system.total_modules,
                "operational": self.system.operational_modules,
                "degraded": self.system.degraded_modules,
                "failed": self.system.failed_modules,
                "uptime_ratio": self.system.uptime_ratio(),
                "total_events": self.system.total_events,
                "events_handled": self.system.events_successfully_handled,
            },
            "history": {
                "sols_recorded": len(self.sol_history),
                "tick_samples": len(self.tick_samples),
            },
        }

    def export_json(self, filepath: str):
        """Export metrics to JSON file."""
        report = self.get_detailed_report()
        report["sol_history"] = self.sol_history
        report["tick_samples"] = self.tick_samples[-100:]  # Last 100 samples

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Metrics exported to {filepath}")

    def export_csv_summary(self, filepath: str):
        """Export sol history to CSV for analysis."""
        if not self.sol_history:
            logger.warning("No sol history to export")
            return

        import csv

        with open(filepath, 'w', newline='') as f:
            # Flatten nested dict for CSV
            fieldnames = [
                "sol",
                "earth_independence",
                "calories_produced",
                "total_food_kg",
                "power_efficiency",
                "water_recycling",
                "h2_remaining_kg",
                "operational_ratio",
                "uptime_ratio",
                "health_ratio",
                "nutrition_adequacy",
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sol_data in self.sol_history:
                row = {
                    "sol": sol_data["sol"],
                    "earth_independence": sol_data["food"]["earth_independence"],
                    "calories_produced": sol_data["food"]["calories_produced"],
                    "total_food_kg": sol_data["food"]["total_food_kg"],
                    "power_efficiency": sol_data["resources"]["power_efficiency"],
                    "water_recycling": sol_data["resources"]["water_recycling"],
                    "h2_remaining_kg": sol_data["resources"]["h2_remaining_kg"],
                    "operational_ratio": sol_data["system"]["operational_ratio"],
                    "uptime_ratio": sol_data["system"]["uptime_ratio"],
                    "health_ratio": sol_data["crew"]["health_ratio"],
                    "nutrition_adequacy": sol_data["crew"]["nutrition_adequacy"],
                }
                writer.writerow(row)

        logger.info(f"CSV summary exported to {filepath}")


# =============================================================================
# MISSION SUCCESS EVALUATOR
# =============================================================================

class MissionEvaluator:
    """
    Evaluates mission success against challenge requirements.

    NASA Deep Space Food Challenge criteria:
    - 50% minimum Earth independence (we target 84%)
    - 500 sols mission duration
    - 15 crew supported
    - System resilience under failures
    """

    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics

    def evaluate(self) -> Dict:
        """
        Evaluate mission against all success criteria.

        Returns:
            Dictionary with pass/fail status for each criterion
        """
        results = {
            "overall_success": True,
            "criteria": {},
        }

        # Criterion 1: Earth Independence >= 50%
        ei = self.metrics.mission.earth_independence_achieved
        results["criteria"]["earth_independence"] = {
            "requirement": "≥50%",
            "achieved": f"{ei * 100:.1f}%",
            "passed": ei >= 0.50,
            "target_met": ei >= 0.84,
        }

        # Criterion 2: Mission Duration (500 sols)
        sols = self.metrics.mission.current_sol
        results["criteria"]["mission_duration"] = {
            "requirement": "500 sols",
            "achieved": f"{sols} sols",
            "passed": sols >= 500,
            "progress": f"{sols / 500 * 100:.1f}%",
        }

        # Criterion 3: Crew Survival
        survival = self.metrics.crew.health_ratio()
        results["criteria"]["crew_survival"] = {
            "requirement": "All crew survive",
            "achieved": f"{self.metrics.crew.crew_healthy}/{self.metrics.crew.crew_size}",
            "passed": survival >= 1.0,
            "health_ratio": f"{survival * 100:.1f}%",
        }

        # Criterion 4: System Resilience
        uptime = self.metrics.system.uptime_ratio()
        events_handled = self.metrics.system.events_successfully_handled
        total_events = self.metrics.system.total_events
        handle_rate = events_handled / total_events if total_events > 0 else 1.0

        results["criteria"]["system_resilience"] = {
            "requirement": "Graceful degradation under failures",
            "uptime": f"{uptime * 100:.1f}%",
            "events_handled": f"{events_handled}/{total_events}",
            "passed": uptime >= 0.8 and handle_rate >= 0.8,
        }

        # Criterion 5: Nutrition Adequacy
        nutrition = self.metrics.crew.nutrition_adequacy()
        deficit_days = self.metrics.crew.nutrition_deficit_days
        results["criteria"]["nutrition_adequacy"] = {
            "requirement": "Adequate crew nutrition",
            "achieved": f"{nutrition * 100:.1f}%",
            "deficit_days": deficit_days,
            "passed": nutrition >= 0.9 and deficit_days <= 10,
        }

        # Calculate overall success
        results["overall_success"] = all(
            c["passed"] for c in results["criteria"].values()
        )

        # Challenge scoring
        results["scoring"] = self._calculate_score()

        return results

    def _calculate_score(self) -> Dict:
        """Calculate competition scoring."""
        score = 0
        breakdown = {}

        # Earth Independence bonus (up to 34 points above 50% baseline)
        ei = self.metrics.mission.earth_independence_achieved
        ei_bonus = max(0, (ei - 0.50) * 100)
        breakdown["earth_independence_bonus"] = ei_bonus
        score += ei_bonus

        # System reliability bonus
        uptime = self.metrics.system.uptime_ratio()
        reliability_bonus = uptime * 20
        breakdown["reliability_bonus"] = reliability_bonus
        score += reliability_bonus

        # Nutrition adequacy bonus
        nutrition = self.metrics.crew.nutrition_adequacy()
        nutrition_bonus = min(nutrition, 1.0) * 20
        breakdown["nutrition_bonus"] = nutrition_bonus
        score += nutrition_bonus

        # Livestock bonus (unique differentiator)
        if self.metrics.food.eggs_count > 0 or self.metrics.food.milk_liters > 0:
            livestock_bonus = 10
            breakdown["livestock_bonus"] = livestock_bonus
            score += livestock_bonus

        return {
            "total_score": score,
            "breakdown": breakdown,
            "max_possible": 100,
        }

    def generate_report(self) -> str:
        """Generate human-readable evaluation report."""
        results = self.evaluate()

        lines = [
            "=" * 60,
            "MARS TO TABLE — MISSION EVALUATION REPORT",
            "=" * 60,
            "",
            f"Mission Progress: Sol {self.metrics.mission.current_sol}/{self.metrics.mission.total_sols}",
            f"Overall Status: {'PASS ✓' if results['overall_success'] else 'FAIL ✗'}",
            "",
            "-" * 40,
            "CHALLENGE CRITERIA",
            "-" * 40,
        ]

        for name, criteria in results["criteria"].items():
            status = "✓ PASS" if criteria["passed"] else "✗ FAIL"
            lines.append(f"  {name.replace('_', ' ').title()}:")
            lines.append(f"    Requirement: {criteria['requirement']}")
            # Handle different criterion formats
            if "achieved" in criteria:
                lines.append(f"    Achieved: {criteria['achieved']}")
            elif "uptime" in criteria:
                lines.append(f"    Uptime: {criteria['uptime']}")
                lines.append(f"    Events Handled: {criteria['events_handled']}")
            lines.append(f"    Status: {status}")
            lines.append("")

        lines.extend([
            "-" * 40,
            "COMPETITION SCORING",
            "-" * 40,
            f"  Total Score: {results['scoring']['total_score']:.1f} / {results['scoring']['max_possible']}",
        ])

        for item, value in results["scoring"]["breakdown"].items():
            lines.append(f"    {item.replace('_', ' ').title()}: {value:.1f}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)
