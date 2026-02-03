"""
Mars to Table — Crop Disease & Pest Failure Scenarios

Comprehensive crop failure modeling including:
- Disease outbreaks (fungal, bacterial, viral)
- Pest infestations (adapted to enclosed environment)
- Environmental stress failures
- Nutrient deficiencies
- Equipment malfunctions affecting crops
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from enum import Enum, auto
import random
import logging

logger = logging.getLogger(__name__)


class CropFailureType(Enum):
    """Types of crop failures."""
    # Diseases
    FUNGAL_INFECTION = auto()      # Powdery mildew, root rot, damping off
    BACTERIAL_INFECTION = auto()    # Bacterial wilt, soft rot
    VIRAL_INFECTION = auto()        # Mosaic viruses, stunting

    # Pests (can occur even in closed systems)
    APHID_INFESTATION = auto()
    SPIDER_MITE = auto()
    THRIPS = auto()
    FUNGUS_GNAT = auto()

    # Environmental
    HEAT_STRESS = auto()
    COLD_STRESS = auto()
    LIGHT_STRESS = auto()           # Too much or too little
    HUMIDITY_STRESS = auto()

    # Nutrient
    NITROGEN_DEFICIENCY = auto()
    PHOSPHORUS_DEFICIENCY = auto()
    POTASSIUM_DEFICIENCY = auto()
    MICRONUTRIENT_DEFICIENCY = auto()
    NUTRIENT_TOXICITY = auto()

    # Equipment
    IRRIGATION_FAILURE = auto()
    LIGHTING_FAILURE = auto()
    CO2_SYSTEM_FAILURE = auto()
    HVAC_FAILURE = auto()


class CropSeverity(Enum):
    """Severity levels for crop failures."""
    MINOR = auto()      # <10% yield loss
    MODERATE = auto()   # 10-30% yield loss
    SEVERE = auto()     # 30-60% yield loss
    CRITICAL = auto()   # 60-90% yield loss
    TOTAL = auto()      # 90-100% yield loss


@dataclass
class CropFailureEvent:
    """A crop failure event."""
    event_id: str
    failure_type: CropFailureType
    severity: CropSeverity
    affected_pods: List[str]
    affected_crops: List[str]
    start_tick: int
    duration_ticks: int
    yield_reduction: float  # 0-1
    spread_rate: float      # Rate of spread to adjacent crops/pods
    treatable: bool
    treatment_effectiveness: float
    detected: bool = False
    treated: bool = False
    contained: bool = False
    description: str = ""


@dataclass
class CropFailureResponse:
    """Response protocol for a crop failure."""
    isolation_required: bool
    quarantine_pods: List[str]
    treatment_method: str
    resource_requirements: Dict[str, float]
    recovery_time_ticks: int
    success_probability: float


class CropFailureGenerator:
    """
    Generates crop failure events based on environmental conditions.

    Accounts for:
    - Closed environment reducing but not eliminating pest/disease risk
    - Environmental control failures increasing disease pressure
    - Crop-specific vulnerabilities
    - Seasonal/cyclical patterns
    """

    # Crop vulnerabilities (0-1 scale)
    CROP_VULNERABILITIES = {
        "lettuce": {
            CropFailureType.FUNGAL_INFECTION: 0.7,
            CropFailureType.APHID_INFESTATION: 0.8,
            CropFailureType.HEAT_STRESS: 0.6,
        },
        "tomato": {
            CropFailureType.BACTERIAL_INFECTION: 0.6,
            CropFailureType.SPIDER_MITE: 0.7,
            CropFailureType.HUMIDITY_STRESS: 0.5,
        },
        "potato": {
            CropFailureType.FUNGAL_INFECTION: 0.8,
            CropFailureType.BACTERIAL_INFECTION: 0.5,
            CropFailureType.NITROGEN_DEFICIENCY: 0.4,
        },
        "wheat": {
            CropFailureType.FUNGAL_INFECTION: 0.6,
            CropFailureType.HEAT_STRESS: 0.5,
            CropFailureType.NITROGEN_DEFICIENCY: 0.5,
        },
        "soybean": {
            CropFailureType.APHID_INFESTATION: 0.6,
            CropFailureType.FUNGAL_INFECTION: 0.5,
            CropFailureType.IRON_DEFICIENCY if hasattr(CropFailureType, 'IRON_DEFICIENCY') else CropFailureType.MICRONUTRIENT_DEFICIENCY: 0.6,
        },
        "rice": {
            CropFailureType.FUNGAL_INFECTION: 0.7,
            CropFailureType.HUMIDITY_STRESS: 0.4,
            CropFailureType.NITROGEN_DEFICIENCY: 0.5,
        },
        "fodder": {  # Hay/fodder crops
            CropFailureType.FUNGAL_INFECTION: 0.5,
            CropFailureType.NITROGEN_DEFICIENCY: 0.6,
        },
    }

    # Base event probabilities per tick (adjusted by conditions)
    BASE_PROBABILITIES = {
        CropFailureType.FUNGAL_INFECTION: 0.0001,
        CropFailureType.BACTERIAL_INFECTION: 0.00005,
        CropFailureType.VIRAL_INFECTION: 0.00002,
        CropFailureType.APHID_INFESTATION: 0.00008,
        CropFailureType.SPIDER_MITE: 0.00005,
        CropFailureType.THRIPS: 0.00003,
        CropFailureType.FUNGUS_GNAT: 0.00006,
        CropFailureType.HEAT_STRESS: 0.0,  # Only from environmental conditions
        CropFailureType.COLD_STRESS: 0.0,
        CropFailureType.LIGHT_STRESS: 0.0,
        CropFailureType.HUMIDITY_STRESS: 0.0,
        CropFailureType.NITROGEN_DEFICIENCY: 0.00005,
        CropFailureType.PHOSPHORUS_DEFICIENCY: 0.00003,
        CropFailureType.POTASSIUM_DEFICIENCY: 0.00003,
        CropFailureType.MICRONUTRIENT_DEFICIENCY: 0.00004,
        CropFailureType.NUTRIENT_TOXICITY: 0.00002,
        CropFailureType.IRRIGATION_FAILURE: 0.00001,
        CropFailureType.LIGHTING_FAILURE: 0.00002,
        CropFailureType.CO2_SYSTEM_FAILURE: 0.00001,
        CropFailureType.HVAC_FAILURE: 0.00002,
    }

    def __init__(self, seed: int = None):
        if seed:
            random.seed(seed)
        self.next_event_id = 1
        self.active_events: Dict[str, CropFailureEvent] = {}
        self.event_history: List[CropFailureEvent] = []

    def check_for_failures(
        self,
        tick: int,
        pod_statuses: Dict[str, Dict],
        environmental_conditions: Dict[str, float],
    ) -> List[CropFailureEvent]:
        """
        Check for new crop failure events.

        Args:
            tick: Current simulation tick
            pod_statuses: Status of each crop POD (crops, health, age, etc.)
            environmental_conditions: Temperature, humidity, CO2, etc.

        Returns:
            List of new failure events generated
        """
        new_events = []

        for pod_name, pod_status in pod_statuses.items():
            crops = pod_status.get("crops", [])

            for crop in crops:
                crop_name = crop.get("name", "unknown")
                crop_health = crop.get("health", 1.0)
                crop_age_days = crop.get("age_days", 0)

                # Check each failure type
                for failure_type, base_prob in self.BASE_PROBABILITIES.items():
                    adjusted_prob = self._calculate_probability(
                        failure_type,
                        base_prob,
                        crop_name,
                        crop_health,
                        crop_age_days,
                        environmental_conditions,
                    )

                    if random.random() < adjusted_prob:
                        event = self._generate_event(
                            tick,
                            failure_type,
                            pod_name,
                            crop_name,
                            environmental_conditions,
                        )
                        new_events.append(event)
                        self.active_events[event.event_id] = event
                        self.event_history.append(event)

        return new_events

    def _calculate_probability(
        self,
        failure_type: CropFailureType,
        base_prob: float,
        crop_name: str,
        crop_health: float,
        crop_age_days: int,
        conditions: Dict[str, float],
    ) -> float:
        """Calculate adjusted probability for a failure type."""
        prob = base_prob

        # Crop vulnerability multiplier
        crop_vulns = self.CROP_VULNERABILITIES.get(crop_name, {})
        vuln_mult = crop_vulns.get(failure_type, 0.5)
        prob *= vuln_mult

        # Health factor (unhealthy plants more susceptible)
        health_factor = max(1.0, 2.0 - crop_health)
        prob *= health_factor

        # Age factor (very young and old plants more vulnerable)
        if crop_age_days < 7:
            prob *= 1.5  # Seedlings vulnerable
        elif crop_age_days > 60:
            prob *= 1.2  # Older plants

        # Environmental condition factors
        temp = conditions.get("temperature", 22)
        humidity = conditions.get("humidity", 0.6)
        co2 = conditions.get("co2_ppm", 800)

        # Temperature stress
        if failure_type in [CropFailureType.FUNGAL_INFECTION, CropFailureType.BACTERIAL_INFECTION]:
            if humidity > 0.8:
                prob *= 2.0  # High humidity increases disease
            if temp > 28 or temp < 15:
                prob *= 1.5  # Temperature stress

        if failure_type == CropFailureType.HEAT_STRESS:
            if temp > 35:
                prob = 0.1  # High chance if too hot
            elif temp > 30:
                prob = 0.01

        if failure_type == CropFailureType.COLD_STRESS:
            if temp < 10:
                prob = 0.1
            elif temp < 15:
                prob = 0.01

        # CO2 factors
        if failure_type == CropFailureType.CO2_SYSTEM_FAILURE:
            if co2 < 400 or co2 > 2000:
                prob *= 2.0  # System likely struggling

        return min(1.0, prob)

    def _generate_event(
        self,
        tick: int,
        failure_type: CropFailureType,
        pod_name: str,
        crop_name: str,
        conditions: Dict,
    ) -> CropFailureEvent:
        """Generate a crop failure event."""
        event_id = f"crop_fail_{self.next_event_id:05d}"
        self.next_event_id += 1

        # Determine severity based on type and conditions
        severity, yield_reduction = self._determine_severity(failure_type, conditions)

        # Duration varies by type
        duration_map = {
            CropFailureType.FUNGAL_INFECTION: random.randint(7 * 24, 21 * 24),
            CropFailureType.BACTERIAL_INFECTION: random.randint(5 * 24, 14 * 24),
            CropFailureType.VIRAL_INFECTION: random.randint(14 * 24, 42 * 24),
            CropFailureType.APHID_INFESTATION: random.randint(7 * 24, 28 * 24),
            CropFailureType.SPIDER_MITE: random.randint(7 * 24, 21 * 24),
            CropFailureType.HEAT_STRESS: random.randint(2 * 24, 7 * 24),
            CropFailureType.COLD_STRESS: random.randint(2 * 24, 7 * 24),
            CropFailureType.NITROGEN_DEFICIENCY: random.randint(14 * 24, 42 * 24),
            CropFailureType.IRRIGATION_FAILURE: random.randint(1 * 24, 3 * 24),
            CropFailureType.LIGHTING_FAILURE: random.randint(2 * 24, 7 * 24),
        }
        duration = duration_map.get(failure_type, random.randint(7 * 24, 21 * 24))

        # Spread rate
        spread_rates = {
            CropFailureType.FUNGAL_INFECTION: 0.05,
            CropFailureType.BACTERIAL_INFECTION: 0.03,
            CropFailureType.VIRAL_INFECTION: 0.08,
            CropFailureType.APHID_INFESTATION: 0.07,
            CropFailureType.SPIDER_MITE: 0.06,
        }
        spread_rate = spread_rates.get(failure_type, 0.0)

        # Treatability
        treatable_types = {
            CropFailureType.FUNGAL_INFECTION: (True, 0.7),
            CropFailureType.BACTERIAL_INFECTION: (True, 0.5),
            CropFailureType.VIRAL_INFECTION: (False, 0.0),
            CropFailureType.APHID_INFESTATION: (True, 0.85),
            CropFailureType.SPIDER_MITE: (True, 0.8),
            CropFailureType.NITROGEN_DEFICIENCY: (True, 0.9),
            CropFailureType.IRRIGATION_FAILURE: (True, 0.95),
        }
        treatable, effectiveness = treatable_types.get(failure_type, (True, 0.6))

        description = self._generate_description(failure_type, severity, crop_name)

        return CropFailureEvent(
            event_id=event_id,
            failure_type=failure_type,
            severity=severity,
            affected_pods=[pod_name],
            affected_crops=[crop_name],
            start_tick=tick,
            duration_ticks=duration,
            yield_reduction=yield_reduction,
            spread_rate=spread_rate,
            treatable=treatable,
            treatment_effectiveness=effectiveness,
            description=description,
        )

    def _determine_severity(
        self,
        failure_type: CropFailureType,
        conditions: Dict,
    ) -> tuple:
        """Determine severity and yield reduction for an event."""
        # Random severity weighted toward minor
        severity_roll = random.random()
        if severity_roll < 0.5:
            severity = CropSeverity.MINOR
            yield_reduction = random.uniform(0.02, 0.1)
        elif severity_roll < 0.8:
            severity = CropSeverity.MODERATE
            yield_reduction = random.uniform(0.1, 0.3)
        elif severity_roll < 0.95:
            severity = CropSeverity.SEVERE
            yield_reduction = random.uniform(0.3, 0.6)
        elif severity_roll < 0.99:
            severity = CropSeverity.CRITICAL
            yield_reduction = random.uniform(0.6, 0.9)
        else:
            severity = CropSeverity.TOTAL
            yield_reduction = random.uniform(0.9, 1.0)

        return severity, yield_reduction

    def _generate_description(
        self,
        failure_type: CropFailureType,
        severity: CropSeverity,
        crop_name: str,
    ) -> str:
        """Generate human-readable description of the event."""
        descriptions = {
            CropFailureType.FUNGAL_INFECTION: f"Fungal infection detected in {crop_name} crop. "
                                              f"White powdery spots and wilting observed.",
            CropFailureType.BACTERIAL_INFECTION: f"Bacterial infection in {crop_name}. "
                                                  f"Soft rot and discoloration spreading.",
            CropFailureType.VIRAL_INFECTION: f"Viral infection confirmed in {crop_name}. "
                                              f"Mosaic patterns and stunted growth evident.",
            CropFailureType.APHID_INFESTATION: f"Aphid colony discovered on {crop_name}. "
                                               f"Honeydew residue and curling leaves observed.",
            CropFailureType.SPIDER_MITE: f"Spider mite infestation on {crop_name}. "
                                          f"Fine webbing and stippled leaves detected.",
            CropFailureType.HEAT_STRESS: f"Heat stress affecting {crop_name}. "
                                          f"Wilting and leaf scorch developing.",
            CropFailureType.NITROGEN_DEFICIENCY: f"Nitrogen deficiency in {crop_name}. "
                                                  f"Yellowing of older leaves progressing.",
            CropFailureType.IRRIGATION_FAILURE: f"Irrigation system malfunction affecting {crop_name}. "
                                                 f"Water delivery compromised.",
        }

        base = descriptions.get(failure_type, f"Crop failure event affecting {crop_name}.")
        return f"[{severity.name}] {base}"

    def update_events(self, tick: int) -> Dict:
        """
        Update active events, handling spread and resolution.

        Returns summary of event changes.
        """
        resolved = []
        spread_events = []

        for event_id, event in list(self.active_events.items()):
            # Check if event has run its course
            if tick >= event.start_tick + event.duration_ticks:
                resolved.append(event_id)
                del self.active_events[event_id]
                continue

            # Check for spread (if not contained)
            if not event.contained and event.spread_rate > 0:
                if random.random() < event.spread_rate / 24:  # Per-tick chance
                    # Spread to another pod/crop
                    spread_events.append({
                        "source": event_id,
                        "type": event.failure_type.name,
                    })

        return {
            "resolved": resolved,
            "spread_events": spread_events,
            "active_count": len(self.active_events),
        }

    def treat_event(self, event_id: str) -> bool:
        """Attempt to treat a crop failure event."""
        event = self.active_events.get(event_id)
        if not event:
            return False

        if not event.treatable:
            logger.warning(f"Event {event_id} is not treatable (viral infection)")
            return False

        if event.treated:
            return True  # Already treated

        # Apply treatment
        if random.random() < event.treatment_effectiveness:
            event.treated = True
            event.contained = True
            event.yield_reduction *= 0.5  # Reduce impact
            event.duration_ticks = int(event.duration_ticks * 0.6)  # Faster recovery

            logger.info(f"Treatment successful for {event_id}")
            return True
        else:
            logger.warning(f"Treatment failed for {event_id}")
            return False

    def get_response_protocol(self, event: CropFailureEvent) -> CropFailureResponse:
        """Get the recommended response protocol for an event."""
        protocols = {
            CropFailureType.FUNGAL_INFECTION: CropFailureResponse(
                isolation_required=True,
                quarantine_pods=event.affected_pods,
                treatment_method="Apply biological fungicide (Bacillus subtilis), "
                                "reduce humidity, increase air circulation",
                resource_requirements={"fungicide_doses": 2.0, "labor_hours": 4.0},
                recovery_time_ticks=7 * 24,
                success_probability=0.7,
            ),
            CropFailureType.BACTERIAL_INFECTION: CropFailureResponse(
                isolation_required=True,
                quarantine_pods=event.affected_pods,
                treatment_method="Remove infected tissue, apply copper-based treatment, "
                                "sterilize tools and equipment",
                resource_requirements={"copper_treatment_l": 1.0, "labor_hours": 6.0},
                recovery_time_ticks=10 * 24,
                success_probability=0.5,
            ),
            CropFailureType.APHID_INFESTATION: CropFailureResponse(
                isolation_required=False,
                quarantine_pods=[],
                treatment_method="Release beneficial insects (ladybugs, lacewings), "
                                "apply insecticidal soap, physical removal",
                resource_requirements={"beneficial_insects": 100, "soap_solution_l": 2.0},
                recovery_time_ticks=5 * 24,
                success_probability=0.85,
            ),
            CropFailureType.NITROGEN_DEFICIENCY: CropFailureResponse(
                isolation_required=False,
                quarantine_pods=[],
                treatment_method="Supplement nitrogen via nutrient solution adjustment, "
                                "verify EC/pH levels, check root health",
                resource_requirements={"nitrogen_supplement_kg": 0.5, "labor_hours": 2.0},
                recovery_time_ticks=14 * 24,
                success_probability=0.9,
            ),
            CropFailureType.IRRIGATION_FAILURE: CropFailureResponse(
                isolation_required=False,
                quarantine_pods=[],
                treatment_method="Switch to backup irrigation system, repair primary system, "
                                "hand water affected crops immediately",
                resource_requirements={"spare_parts": 1, "labor_hours": 8.0, "water_l": 50.0},
                recovery_time_ticks=2 * 24,
                success_probability=0.95,
            ),
        }

        return protocols.get(
            event.failure_type,
            CropFailureResponse(
                isolation_required=True,
                quarantine_pods=event.affected_pods,
                treatment_method="General mitigation: isolate, assess, treat symptoms",
                resource_requirements={"labor_hours": 4.0},
                recovery_time_ticks=7 * 24,
                success_probability=0.6,
            ),
        )

    def calculate_yield_impact(self, pod_name: str) -> float:
        """
        Calculate total yield impact for a POD from all active events.

        Returns multiplier (0-1, where 1 is no impact).
        """
        total_reduction = 0.0

        for event in self.active_events.values():
            if pod_name in event.affected_pods:
                total_reduction += event.yield_reduction

        # Cap at 95% reduction (some yield always possible)
        return max(0.05, 1.0 - total_reduction)

    def get_status(self) -> Dict:
        """Get current crop failure status."""
        return {
            "active_events": len(self.active_events),
            "events_by_type": {
                ft.name: len([e for e in self.active_events.values() if e.failure_type == ft])
                for ft in CropFailureType
                if any(e.failure_type == ft for e in self.active_events.values())
            },
            "total_events_generated": len(self.event_history),
            "events_treated": len([e for e in self.event_history if e.treated]),
            "events_contained": len([e for e in self.event_history if e.contained]),
        }
