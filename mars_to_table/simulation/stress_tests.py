"""
Mars to Table — Stress Testing Scenarios

Comprehensive stress tests for validating system resilience:
- Worst-case failure scenarios
- Edge cases and boundary conditions
- Multi-system cascading failures
- Long-duration degradation
- Recovery validation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple
from enum import Enum, auto
import logging
import random
import math

logger = logging.getLogger(__name__)


class StressTestCategory(Enum):
    """Categories of stress tests."""
    POWER = auto()           # Power system failures
    WATER = auto()           # Water system failures
    ATMOSPHERE = auto()      # Life support failures
    FOOD = auto()            # Food production failures
    CREW = auto()            # Crew-related emergencies
    COMBINED = auto()        # Multiple simultaneous failures
    ENDURANCE = auto()       # Long-duration degradation


class StressTestSeverity(Enum):
    """Severity levels for stress tests."""
    NOMINAL = auto()         # Normal operations (baseline)
    DEGRADED = auto()        # Reduced capacity
    STRESSED = auto()        # Significant impairment
    CRITICAL = auto()        # Near-failure
    EMERGENCY = auto()       # Life-threatening


@dataclass
class StressTestScenario:
    """A stress test scenario definition."""
    scenario_id: str
    name: str
    category: StressTestCategory
    severity: StressTestSeverity
    description: str

    # Scenario parameters
    duration_ticks: int
    trigger_conditions: Dict[str, float]

    # Expected impacts
    expected_impacts: Dict[str, str]

    # Success criteria
    success_criteria: Dict[str, float]

    # Sequence of events
    event_sequence: List[Dict] = field(default_factory=list)


@dataclass
class StressTestResult:
    """Results from running a stress test."""
    scenario_id: str
    passed: bool
    score: float  # 0-100
    metrics: Dict[str, float]
    events_triggered: List[Dict]
    failures: List[str]
    recovery_time_ticks: int
    notes: str = ""


# =============================================================================
# STANDARD STRESS TEST SCENARIOS
# =============================================================================

STRESS_TEST_SCENARIOS = {
    # -------------------------------------------------------------------------
    # POWER SCENARIOS
    # -------------------------------------------------------------------------
    "power_total_outage": StressTestScenario(
        scenario_id="power_total_outage",
        name="Total Power Outage",
        category=StressTestCategory.POWER,
        severity=StressTestSeverity.EMERGENCY,
        description="Complete loss of all power generation for extended period",
        duration_ticks=48,  # 2 sols
        trigger_conditions={
            "solar_output": 0.0,
            "fuel_cell_output": 0.0,
            "biogas_output": 0.0,
        },
        expected_impacts={
            "life_support": "Emergency reserves only",
            "food_production": "Complete halt",
            "water": "No extraction or recycling",
        },
        success_criteria={
            "crew_survival": 1.0,      # All crew survive
            "min_o2_level": 0.19,      # O2 never below 19%
            "recovery_time": 72,       # Full recovery within 72 ticks
        },
        event_sequence=[
            {"tick": 0, "event": "solar_failure", "intensity": 1.0},
            {"tick": 0, "event": "fuel_cell_failure", "intensity": 1.0},
            {"tick": 24, "event": "partial_solar_restore", "intensity": 0.5},
            {"tick": 36, "event": "fuel_cell_restore", "intensity": 1.0},
            {"tick": 48, "event": "full_solar_restore", "intensity": 1.0},
        ],
    ),

    "power_dust_storm_30_day": StressTestScenario(
        scenario_id="power_dust_storm_30_day",
        name="30-Day Dust Storm",
        category=StressTestCategory.POWER,
        severity=StressTestSeverity.CRITICAL,
        description="Extended dust storm reducing solar output to 10% for 30 sols",
        duration_ticks=30 * 24,
        trigger_conditions={
            "solar_efficiency": 0.10,
        },
        expected_impacts={
            "power": "90% reduction in solar generation",
            "food_production": "Severely limited",
            "crew_morale": "Significantly reduced",
        },
        success_criteria={
            "crew_survival": 1.0,
            "min_food_reserve_days": 7,
            "power_balance": -0.1,  # Max 10% daily deficit
        },
    ),

    # -------------------------------------------------------------------------
    # WATER SCENARIOS
    # -------------------------------------------------------------------------
    "water_total_loss": StressTestScenario(
        scenario_id="water_total_loss",
        name="Total Water System Failure",
        category=StressTestCategory.WATER,
        severity=StressTestSeverity.EMERGENCY,
        description="Both RSV extractors fail, no water recycling",
        duration_ticks=72,
        trigger_conditions={
            "rsv1_output": 0.0,
            "rsv2_output": 0.0,
            "recycler_output": 0.0,
        },
        expected_impacts={
            "water_reserve": "Depletion within 5-7 days",
            "crop_irrigation": "Suspended",
            "livestock": "Emergency rationing",
        },
        success_criteria={
            "crew_survival": 1.0,
            "min_water_reserve_l": 500,  # Emergency minimum
            "recovery_time": 24,
        },
        event_sequence=[
            {"tick": 0, "event": "rsv1_failure", "intensity": 1.0},
            {"tick": 0, "event": "rsv2_failure", "intensity": 1.0},
            {"tick": 0, "event": "recycler_failure", "intensity": 1.0},
            {"tick": 12, "event": "emergency_h2_burn", "intensity": 0.5},
            {"tick": 24, "event": "rsv1_restore", "intensity": 0.7},
            {"tick": 48, "event": "recycler_restore", "intensity": 1.0},
            {"tick": 72, "event": "rsv2_restore", "intensity": 1.0},
        ],
    ),

    "water_contamination": StressTestScenario(
        scenario_id="water_contamination",
        name="Water Contamination Event",
        category=StressTestCategory.WATER,
        severity=StressTestSeverity.CRITICAL,
        description="Bacterial contamination in main water storage",
        duration_ticks=168,  # 7 days for decontamination
        trigger_conditions={
            "water_quality": 0.3,  # 30% contaminated
        },
        expected_impacts={
            "potable_water": "70% unavailable",
            "crew_health": "Risk of illness",
            "food_prep": "Limited",
        },
        success_criteria={
            "crew_illness_rate": 0.1,  # Max 10% get sick
            "decontamination_success": 1.0,
        },
    ),

    # -------------------------------------------------------------------------
    # ATMOSPHERE SCENARIOS
    # -------------------------------------------------------------------------
    "atmosphere_o2_generation_failure": StressTestScenario(
        scenario_id="atmosphere_o2_generation_failure",
        name="O2 Generation System Failure",
        category=StressTestCategory.ATMOSPHERE,
        severity=StressTestSeverity.EMERGENCY,
        description="Primary and backup O2 generation offline",
        duration_ticks=24,
        trigger_conditions={
            "o2_generation": 0.0,
        },
        expected_impacts={
            "o2_level": "Declining at ~0.5%/hour with 15 crew",
            "crew_activity": "Reduced to conserve O2",
        },
        success_criteria={
            "crew_survival": 1.0,
            "min_o2_pct": 18.0,  # Never below 18%
            "recovery_time": 12,
        },
    ),

    "atmosphere_co2_scrubber_failure": StressTestScenario(
        scenario_id="atmosphere_co2_scrubber_failure",
        name="CO2 Scrubber Failure",
        category=StressTestCategory.ATMOSPHERE,
        severity=StressTestSeverity.CRITICAL,
        description="CO2 removal system offline",
        duration_ticks=48,
        trigger_conditions={
            "co2_scrubbing": 0.0,
        },
        expected_impacts={
            "co2_level": "Rising toward dangerous levels",
            "crew_cognition": "Impaired above 2%",
        },
        success_criteria={
            "max_co2_pct": 2.0,  # Stay below 2%
            "crew_symptoms": 0.0,  # No hypercapnia
        },
    ),

    # -------------------------------------------------------------------------
    # FOOD SCENARIOS
    # -------------------------------------------------------------------------
    "food_total_crop_failure": StressTestScenario(
        scenario_id="food_total_crop_failure",
        name="Total Crop Failure",
        category=StressTestCategory.FOOD,
        severity=StressTestSeverity.CRITICAL,
        description="Disease wipes out all active crops",
        duration_ticks=90 * 24,  # 90 days to regrow
        trigger_conditions={
            "crop_health": 0.0,
        },
        expected_impacts={
            "fresh_food": "Zero production for 60+ days",
            "calorie_supply": "Reserves and stored food only",
            "crew_nutrition": "Deficiencies possible",
        },
        success_criteria={
            "crew_survival": 1.0,
            "min_calorie_ratio": 0.7,  # At least 70% of needs
            "regrowth_success": 0.8,  # 80% crop recovery
        },
    ),

    "food_livestock_disease": StressTestScenario(
        scenario_id="food_livestock_disease",
        name="Livestock Disease Outbreak",
        category=StressTestCategory.FOOD,
        severity=StressTestSeverity.STRESSED,
        description="Disease affects goat herd and chicken flock",
        duration_ticks=30 * 24,
        trigger_conditions={
            "livestock_health": 0.3,  # 70% sick
        },
        expected_impacts={
            "milk_production": "90% reduction",
            "egg_production": "80% reduction",
            "protein_supply": "Significantly impacted",
        },
        success_criteria={
            "livestock_survival": 0.5,  # At least 50% survive
            "breeding_stock_survival": 0.8,  # Preserve genetics
        },
    ),

    # -------------------------------------------------------------------------
    # CREW SCENARIOS
    # -------------------------------------------------------------------------
    "crew_medical_emergency": StressTestScenario(
        scenario_id="crew_medical_emergency",
        name="Mass Medical Emergency",
        category=StressTestCategory.CREW,
        severity=StressTestSeverity.EMERGENCY,
        description="5 crew members incapacitated simultaneously",
        duration_ticks=14 * 24,
        trigger_conditions={
            "crew_available": 10,  # Only 10 of 15 working
        },
        expected_impacts={
            "labor_capacity": "33% reduction",
            "food_system_ops": "Skeleton crew only",
            "workload": "Remaining crew stressed",
        },
        success_criteria={
            "operations_maintained": 0.6,  # 60% operations
            "crew_recovery": 1.0,  # All recover
        },
    ),

    "crew_psychological_crisis": StressTestScenario(
        scenario_id="crew_psychological_crisis",
        name="Crew Psychological Crisis",
        category=StressTestCategory.CREW,
        severity=StressTestSeverity.CRITICAL,
        description="Multiple crew members in psychological distress",
        duration_ticks=30 * 24,
        trigger_conditions={
            "crew_morale": 0.3,  # Very low morale
            "interpersonal_conflict": 0.8,  # High conflict
        },
        expected_impacts={
            "productivity": "50% reduction",
            "error_rate": "Doubled",
            "food_satisfaction": "Critical for recovery",
        },
        success_criteria={
            "morale_recovery": 0.6,  # Recover to 60%
            "no_critical_incidents": 1.0,
        },
    ),

    # -------------------------------------------------------------------------
    # COMBINED SCENARIOS
    # -------------------------------------------------------------------------
    "combined_dust_storm_water_failure": StressTestScenario(
        scenario_id="combined_dust_storm_water_failure",
        name="Dust Storm + Water System Failure",
        category=StressTestCategory.COMBINED,
        severity=StressTestSeverity.EMERGENCY,
        description="Dust storm coincides with RSV extractor failure",
        duration_ticks=14 * 24,
        trigger_conditions={
            "solar_efficiency": 0.15,
            "rsv1_output": 0.0,
        },
        expected_impacts={
            "power": "Severely limited",
            "water": "No extraction, limited recycling",
            "all_systems": "Emergency protocols",
        },
        success_criteria={
            "crew_survival": 1.0,
            "system_recovery": 0.9,  # 90% systems recover
        },
    ),

    "combined_triple_failure": StressTestScenario(
        scenario_id="combined_triple_failure",
        name="Triple System Failure",
        category=StressTestCategory.COMBINED,
        severity=StressTestSeverity.EMERGENCY,
        description="Simultaneous power, water, and atmosphere failures",
        duration_ticks=24,  # Must resolve quickly
        trigger_conditions={
            "solar_output": 0.1,
            "rsv_output": 0.0,
            "o2_generation": 0.5,
        },
        expected_impacts={
            "all_systems": "Critical emergency",
            "crew": "Life-threatening conditions",
        },
        success_criteria={
            "crew_survival": 1.0,
            "stabilization_time": 6,  # Stabilize within 6 ticks
        },
    ),

    # -------------------------------------------------------------------------
    # ENDURANCE SCENARIOS
    # -------------------------------------------------------------------------
    "endurance_500_sol_nominal": StressTestScenario(
        scenario_id="endurance_500_sol_nominal",
        name="500-Sol Nominal Operations",
        category=StressTestCategory.ENDURANCE,
        severity=StressTestSeverity.NOMINAL,
        description="Full 500-sol mission with normal operations",
        duration_ticks=500 * 24,
        trigger_conditions={},  # No artificial failures
        expected_impacts={
            "all_systems": "Normal wear and degradation",
        },
        success_criteria={
            "earth_independence": 0.84,
            "crew_survival": 1.0,
            "system_uptime": 0.95,
            "final_food_reserve_days": 30,
        },
    ),

    "endurance_500_sol_realistic": StressTestScenario(
        scenario_id="endurance_500_sol_realistic",
        name="500-Sol Realistic Operations",
        category=StressTestCategory.ENDURANCE,
        severity=StressTestSeverity.DEGRADED,
        description="Full mission with realistic failure rates",
        duration_ticks=500 * 24,
        trigger_conditions={
            "failure_probability": 0.001,  # 0.1% per tick base failure rate
        },
        expected_impacts={
            "all_systems": "Multiple failures expected",
        },
        success_criteria={
            "earth_independence": 0.80,  # Allow slight reduction
            "crew_survival": 1.0,
            "mission_success": 0.95,
        },
    ),
}


class StressTestRunner:
    """
    Runs stress tests against the food production system.

    Validates system resilience under various failure scenarios.
    """

    def __init__(self):
        self.scenarios = STRESS_TEST_SCENARIOS
        self.results: Dict[str, StressTestResult] = {}
        self.current_scenario: Optional[StressTestScenario] = None

    def list_scenarios(self, category: Optional[StressTestCategory] = None) -> List[str]:
        """List available scenarios, optionally filtered by category."""
        if category:
            return [
                s_id for s_id, s in self.scenarios.items()
                if s.category == category
            ]
        return list(self.scenarios.keys())

    def get_scenario(self, scenario_id: str) -> Optional[StressTestScenario]:
        """Get scenario by ID."""
        return self.scenarios.get(scenario_id)

    def run_scenario(
        self,
        scenario_id: str,
        system_state: Dict,
        tick_callback: Callable[[int, Dict], Dict],
    ) -> StressTestResult:
        """
        Run a stress test scenario.

        Args:
            scenario_id: ID of scenario to run
            system_state: Initial system state
            tick_callback: Function called each tick with (tick, conditions)
                          Returns updated system state

        Returns:
            StressTestResult with pass/fail and metrics
        """
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        self.current_scenario = scenario
        events_triggered = []
        metrics = {}
        failures = []

        logger.info(f"Starting stress test: {scenario.name}")
        logger.info(f"  Duration: {scenario.duration_ticks} ticks")
        logger.info(f"  Severity: {scenario.severity.name}")

        # Apply trigger conditions
        conditions = dict(scenario.trigger_conditions)
        event_index = 0
        events = scenario.event_sequence

        # Run simulation
        for tick in range(scenario.duration_ticks):
            # Check for scheduled events
            while event_index < len(events) and events[event_index]["tick"] <= tick:
                event = events[event_index]
                conditions[event["event"]] = event.get("intensity", 1.0)
                events_triggered.append({
                    "tick": tick,
                    "event": event["event"],
                    "intensity": event.get("intensity", 1.0),
                })
                event_index += 1

            # Execute tick
            try:
                system_state = tick_callback(tick, conditions)
            except Exception as e:
                failures.append(f"Tick {tick}: {str(e)}")
                logger.error(f"Error at tick {tick}: {e}")

            # Collect metrics at key points
            if tick == 0 or tick == scenario.duration_ticks - 1 or tick % 24 == 0:
                metrics[f"tick_{tick}"] = self._extract_metrics(system_state)

        # Evaluate results
        passed, score = self._evaluate_results(scenario, system_state, metrics, failures)

        result = StressTestResult(
            scenario_id=scenario_id,
            passed=passed,
            score=score,
            metrics=metrics,
            events_triggered=events_triggered,
            failures=failures,
            recovery_time_ticks=self._calculate_recovery_time(metrics),
            notes=f"Completed {scenario.duration_ticks} ticks with {len(failures)} failures",
        )

        self.results[scenario_id] = result
        self.current_scenario = None

        return result

    def _extract_metrics(self, state: Dict) -> Dict:
        """Extract relevant metrics from system state."""
        return {
            "power_level": state.get("power", {}).get("battery_level_kwh", 0),
            "water_level": state.get("water", {}).get("reservoir_level_l", 0),
            "food_level": state.get("food", {}).get("total_kg", 0),
            "o2_level": state.get("atmosphere", {}).get("o2_pct", 21),
            "co2_level": state.get("atmosphere", {}).get("co2_pct", 0.04),
            "crew_health": state.get("crew", {}).get("avg_health", 1.0),
            "crew_morale": state.get("crew", {}).get("avg_morale", 0.8),
        }

    def _evaluate_results(
        self,
        scenario: StressTestScenario,
        final_state: Dict,
        metrics: Dict,
        failures: List[str],
    ) -> Tuple[bool, float]:
        """Evaluate if scenario passed and calculate score."""
        criteria = scenario.success_criteria
        passed = True
        scores = []

        for criterion, threshold in criteria.items():
            actual = self._get_criterion_value(criterion, final_state, metrics)

            if actual is None:
                continue

            if criterion.startswith("min_"):
                criterion_passed = actual >= threshold
            elif criterion.startswith("max_"):
                criterion_passed = actual <= threshold
            else:
                criterion_passed = actual >= threshold

            if not criterion_passed:
                passed = False
                logger.warning(f"Criterion failed: {criterion} "
                             f"(actual={actual}, threshold={threshold})")

            # Score based on how well criterion was met
            if threshold > 0:
                score = min(100, (actual / threshold) * 100)
            else:
                score = 100 if criterion_passed else 0
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0

        # Penalty for failures
        failure_penalty = len(failures) * 5
        final_score = max(0, avg_score - failure_penalty)

        return passed, final_score

    def _get_criterion_value(
        self,
        criterion: str,
        final_state: Dict,
        metrics: Dict,
    ) -> Optional[float]:
        """Get actual value for a criterion."""
        criterion_map = {
            "crew_survival": lambda: final_state.get("crew", {}).get("survival_rate", 1.0),
            "min_o2_level": lambda: min(
                m.get("o2_level", 21) for m in metrics.values() if isinstance(m, dict)
            ),
            "max_co2_pct": lambda: max(
                m.get("co2_level", 0) for m in metrics.values() if isinstance(m, dict)
            ),
            "min_water_reserve_l": lambda: min(
                m.get("water_level", 0) for m in metrics.values() if isinstance(m, dict)
            ),
            "earth_independence": lambda: final_state.get("earth_independence", 0),
            "system_uptime": lambda: final_state.get("system_uptime", 0),
        }

        getter = criterion_map.get(criterion)
        if getter:
            try:
                return getter()
            except Exception:
                return None

        return None

    def _calculate_recovery_time(self, metrics: Dict) -> int:
        """Calculate time to recover from stress event."""
        # Simple heuristic: find when metrics return to >90% of initial
        initial = metrics.get("tick_0", {})
        if not initial:
            return 0

        for tick_key in sorted(metrics.keys()):
            if not tick_key.startswith("tick_"):
                continue
            tick = int(tick_key.split("_")[1])
            current = metrics[tick_key]

            # Check if recovered
            recovered = True
            for key, initial_val in initial.items():
                if initial_val > 0:
                    current_val = current.get(key, 0)
                    if current_val < initial_val * 0.9:
                        recovered = False
                        break

            if recovered and tick > 0:
                return tick

        return -1  # Did not recover

    def get_summary(self) -> Dict:
        """Get summary of all test results."""
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r.passed)
        avg_score = sum(r.score for r in self.results.values()) / total if total > 0 else 0

        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "average_score": avg_score,
            "results": {
                s_id: {
                    "passed": r.passed,
                    "score": r.score,
                    "failures": len(r.failures),
                }
                for s_id, r in self.results.items()
            },
        }

    def generate_report(self) -> str:
        """Generate human-readable test report."""
        summary = self.get_summary()

        lines = [
            "=" * 70,
            "MARS TO TABLE - STRESS TEST REPORT",
            "=" * 70,
            "",
            f"Total Scenarios Run: {summary['total_scenarios']}",
            f"Passed: {summary['passed']}",
            f"Failed: {summary['failed']}",
            f"Pass Rate: {summary['pass_rate'] * 100:.1f}%",
            f"Average Score: {summary['average_score']:.1f}/100",
            "",
            "-" * 70,
            "DETAILED RESULTS",
            "-" * 70,
        ]

        for scenario_id, result in self.results.items():
            scenario = self.scenarios.get(scenario_id)
            status = "✓ PASS" if result.passed else "✗ FAIL"

            lines.extend([
                "",
                f"{status} {scenario.name if scenario else scenario_id}",
                f"   Category: {scenario.category.name if scenario else 'Unknown'}",
                f"   Severity: {scenario.severity.name if scenario else 'Unknown'}",
                f"   Score: {result.score:.1f}/100",
                f"   Recovery Time: {result.recovery_time_ticks} ticks",
            ])

            if result.failures:
                lines.append(f"   Failures: {len(result.failures)}")

        lines.extend([
            "",
            "=" * 70,
            f"OVERALL: {'PASS' if summary['pass_rate'] >= 0.9 else 'FAIL'}",
            "=" * 70,
        ])

        return "\n".join(lines)
