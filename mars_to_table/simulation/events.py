"""
Mars to Table — Event Injection System
Handles BioSim-compatible event generation and scheduling for resilience testing.

BioSim tests systems with:
- Intermittent power failures and outages
- Water restrictions or supply interruptions
- Variances in crew size and metabolic loads
- Equipment malfunctions
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum, auto
import random
import logging
import json

from ..core.simulation import Event, EventType, Simulation
from ..config import MISSION, FailureMode

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT SEVERITY LEVELS
# =============================================================================

class EventSeverity(Enum):
    """Standardized severity levels for events."""
    MINOR = 0.25      # 25% impact
    MODERATE = 0.50   # 50% impact
    SEVERE = 0.75     # 75% impact
    CRITICAL = 1.0    # 100% impact (total failure)


# =============================================================================
# EVENT TEMPLATES
# =============================================================================

@dataclass
class EventTemplate:
    """
    Template for generating events.

    Used by event generators to create consistent event instances.
    """
    event_type: EventType
    name: str
    description: str

    # Duration range (ticks)
    min_duration: int = 1
    max_duration: int = 24  # 1 sol
    default_duration: int = 12

    # Severity range
    min_severity: float = 0.1
    max_severity: float = 1.0
    default_severity: float = 0.5

    # Target modules (if applicable)
    valid_targets: List[str] = field(default_factory=list)

    # Probability weight for random generation
    probability_weight: float = 1.0

    # Cooldown (minimum ticks between events of this type)
    cooldown_ticks: int = 24

    def create_event(
        self,
        trigger_tick: int,
        duration: Optional[int] = None,
        severity: Optional[float] = None,
        target: Optional[str] = None,
        parameters: Optional[Dict] = None,
    ) -> Event:
        """Create an Event instance from this template."""
        return Event(
            event_type=self.event_type,
            trigger_tick=trigger_tick,
            duration_ticks=duration or self.default_duration,
            severity=severity or self.default_severity,
            target_module=target,
            parameters=parameters or {},
        )


# =============================================================================
# STANDARD EVENT TEMPLATES (BioSim Compatible)
# =============================================================================

STANDARD_EVENTS: Dict[str, EventTemplate] = {
    # Power Events
    "total_power_outage": EventTemplate(
        event_type=EventType.POWER_OUTAGE_TOTAL,
        name="Total Power Outage",
        description="Complete loss of power generation (solar array failure)",
        min_duration=1,
        max_duration=48,
        default_duration=24,
        min_severity=1.0,
        max_severity=1.0,
        default_severity=1.0,
        probability_weight=0.5,  # Rare
        cooldown_ticks=72,
    ),
    "partial_power_outage": EventTemplate(
        event_type=EventType.POWER_OUTAGE_PARTIAL,
        name="Partial Power Outage",
        description="Partial loss of power generation",
        min_duration=1,
        max_duration=24,
        default_duration=12,
        min_severity=0.3,
        max_severity=0.7,
        default_severity=0.5,
        probability_weight=1.0,
        cooldown_ticks=48,
    ),
    "power_reduction": EventTemplate(
        event_type=EventType.POWER_REDUCTION,
        name="Power Reduction",
        description="Reduced power availability (maintenance or efficiency loss)",
        min_duration=6,
        max_duration=48,
        default_duration=24,
        min_severity=0.1,
        max_severity=0.5,
        default_severity=0.25,
        probability_weight=2.0,  # More common
        cooldown_ticks=24,
    ),

    # Water Events
    "water_interruption": EventTemplate(
        event_type=EventType.WATER_SUPPLY_INTERRUPTION,
        name="Water Supply Interruption",
        description="RSV extraction failure or pipeline blockage",
        min_duration=1,
        max_duration=48,
        default_duration=12,
        min_severity=1.0,
        max_severity=1.0,
        default_severity=1.0,
        valid_targets=["RSV_POD_1", "RSV_POD_2"],
        probability_weight=0.8,
        cooldown_ticks=48,
    ),
    "water_restriction": EventTemplate(
        event_type=EventType.WATER_RESTRICTION,
        name="Water Restriction",
        description="Mandated reduction in water consumption",
        min_duration=24,
        max_duration=168,  # Up to 1 week
        default_duration=48,
        min_severity=0.2,
        max_severity=0.6,
        default_severity=0.4,
        probability_weight=1.5,
        cooldown_ticks=72,
    ),
    "water_contamination": EventTemplate(
        event_type=EventType.WATER_CONTAMINATION,
        name="Water Contamination",
        description="Water supply contaminated, requires treatment",
        min_duration=12,
        max_duration=72,
        default_duration=24,
        min_severity=0.5,
        max_severity=1.0,
        default_severity=0.7,
        probability_weight=0.3,
        cooldown_ticks=96,
    ),

    # Crew Events
    "crew_increase": EventTemplate(
        event_type=EventType.CREW_SIZE_INCREASE,
        name="Crew Size Increase",
        description="Additional crew members arrive",
        min_duration=1,
        max_duration=1,
        default_duration=1,  # Instant
        min_severity=1.0,
        max_severity=1.0,
        default_severity=1.0,
        probability_weight=0.2,
        cooldown_ticks=240,  # 10 sols
    ),
    "crew_decrease": EventTemplate(
        event_type=EventType.CREW_SIZE_DECREASE,
        name="Crew Size Decrease",
        description="Crew members depart or incapacitated",
        min_duration=1,
        max_duration=1,
        default_duration=1,
        min_severity=1.0,
        max_severity=1.0,
        default_severity=1.0,
        probability_weight=0.2,
        cooldown_ticks=240,
    ),
    "metabolic_increase": EventTemplate(
        event_type=EventType.CREW_METABOLIC_INCREASE,
        name="Metabolic Increase",
        description="Increased crew calorie requirements (EVA, illness)",
        min_duration=24,
        max_duration=72,
        default_duration=48,
        min_severity=0.1,
        max_severity=0.3,
        default_severity=0.2,  # 20% increase
        probability_weight=1.0,
        cooldown_ticks=48,
    ),
    "eva_day": EventTemplate(
        event_type=EventType.CREW_EVA_DAY,
        name="EVA Day",
        description="Scheduled EVA increases calorie needs",
        min_duration=8,
        max_duration=12,
        default_duration=10,
        min_severity=0.15,
        max_severity=0.25,
        default_severity=0.2,
        probability_weight=3.0,  # Common
        cooldown_ticks=24,
    ),

    # Equipment Events
    "pod_failure": EventTemplate(
        event_type=EventType.POD_FAILURE,
        name="POD Failure",
        description="Complete POD system failure",
        min_duration=24,
        max_duration=168,
        default_duration=72,
        min_severity=0.5,
        max_severity=1.0,
        default_severity=0.8,
        valid_targets=[
            "Food_POD_1", "Food_POD_2", "Food_POD_3", "Food_POD_4", "Food_POD_5",
            "Fodder_POD", "Grain_POD", "Livestock_POD",
            "RSV_POD_1", "RSV_POD_2",
            "Nutrient_POD", "Waste_POD", "HAB_POD",
        ],
        probability_weight=0.3,
        cooldown_ticks=120,
    ),
    "equipment_malfunction": EventTemplate(
        event_type=EventType.EQUIPMENT_MALFUNCTION,
        name="Equipment Malfunction",
        description="Specific equipment failure within a module",
        min_duration=6,
        max_duration=48,
        default_duration=24,
        min_severity=0.3,
        max_severity=0.7,
        default_severity=0.5,
        probability_weight=1.5,
        cooldown_ticks=24,
    ),
    "sensor_failure": EventTemplate(
        event_type=EventType.SENSOR_FAILURE,
        name="Sensor Failure",
        description="Environmental or monitoring sensor failure",
        min_duration=12,
        max_duration=72,
        default_duration=24,
        min_severity=0.2,
        max_severity=0.5,
        default_severity=0.3,
        probability_weight=2.0,
        cooldown_ticks=24,
    ),

    # Environmental Events
    "dust_storm": EventTemplate(
        event_type=EventType.DUST_STORM,
        name="Dust Storm",
        description="Mars dust storm reduces solar generation",
        min_duration=48,
        max_duration=480,  # Up to 20 sols
        default_duration=120,
        min_severity=0.3,
        max_severity=0.9,
        default_severity=0.6,
        probability_weight=0.4,
        cooldown_ticks=240,
    ),
    "radiation_event": EventTemplate(
        event_type=EventType.RADIATION_EVENT,
        name="Radiation Event",
        description="Solar particle event requiring shelter",
        min_duration=6,
        max_duration=24,
        default_duration=12,
        min_severity=0.5,
        max_severity=1.0,
        default_severity=0.7,
        probability_weight=0.2,
        cooldown_ticks=168,
    ),
}


# =============================================================================
# EVENT GENERATOR BASE CLASS
# =============================================================================

class EventGenerator(ABC):
    """
    Abstract base class for event generators.

    Event generators create events based on different strategies:
    - Random: Probabilistic events based on templates
    - Scripted: Pre-defined sequences for testing
    - BioSim: Events from BioSim server API
    """

    def __init__(self):
        self.events_generated: List[Event] = []
        self.last_event_tick: Dict[str, int] = {}  # Template name -> last trigger tick

    @abstractmethod
    def generate_events(self, current_tick: int, duration_ticks: int) -> List[Event]:
        """
        Generate events for the specified time window.

        Args:
            current_tick: Current simulation tick
            duration_ticks: Window to generate events for

        Returns:
            List of events to schedule
        """
        pass

    def can_generate(self, template_name: str, current_tick: int) -> bool:
        """Check if an event type is off cooldown."""
        template = STANDARD_EVENTS.get(template_name)
        if not template:
            return False

        last_tick = self.last_event_tick.get(template_name, -999999)
        return current_tick - last_tick >= template.cooldown_ticks

    def record_event(self, template_name: str, trigger_tick: int, event: Event):
        """Record that an event was generated."""
        self.last_event_tick[template_name] = trigger_tick
        self.events_generated.append(event)


# =============================================================================
# RANDOM EVENT GENERATOR
# =============================================================================

class RandomEventGenerator(EventGenerator):
    """
    Generates random events based on probability weights.

    Used for stress testing and Monte Carlo simulations.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        events_per_sol: float = 0.5,  # Average events per sol
        enabled_events: Optional[List[str]] = None,
    ):
        super().__init__()
        self.rng = random.Random(seed)
        self.events_per_sol = events_per_sol
        self.enabled_events = enabled_events or list(STANDARD_EVENTS.keys())

        # Calculate total weight for enabled events
        self.total_weight = sum(
            STANDARD_EVENTS[name].probability_weight
            for name in self.enabled_events
            if name in STANDARD_EVENTS
        )

    def generate_events(self, current_tick: int, duration_ticks: int) -> List[Event]:
        """Generate random events for the time window."""
        events = []

        # Calculate expected number of events
        sols = duration_ticks / MISSION.ticks_per_sol
        expected_events = sols * self.events_per_sol

        # Poisson-distributed number of events
        num_events = self._poisson(expected_events)

        for _ in range(num_events):
            # Select random event type
            template_name = self._select_event_type(current_tick)
            if not template_name:
                continue

            template = STANDARD_EVENTS[template_name]

            # Random trigger time within window
            trigger = current_tick + self.rng.randint(0, duration_ticks - 1)

            # Random parameters within template bounds
            duration = self.rng.randint(template.min_duration, template.max_duration)
            severity = self.rng.uniform(template.min_severity, template.max_severity)

            # Random target if applicable
            target = None
            if template.valid_targets:
                target = self.rng.choice(template.valid_targets)

            # Generate parameters based on event type
            params = self._generate_parameters(template, severity)

            event = template.create_event(
                trigger_tick=trigger,
                duration=duration,
                severity=severity,
                target=target,
                parameters=params,
            )

            self.record_event(template_name, trigger, event)
            events.append(event)

            logger.info(
                f"Generated random event: {template.name} at tick {trigger} "
                f"(severity {severity:.2f}, duration {duration})"
            )

        return events

    def _poisson(self, lam: float) -> int:
        """Generate Poisson-distributed random number."""
        if lam <= 0:
            return 0
        return self.rng.poisson(lam) if hasattr(self.rng, 'poisson') else int(self.rng.expovariate(1/lam))

    def _select_event_type(self, current_tick: int) -> Optional[str]:
        """Select a random event type weighted by probability."""
        available = [
            name for name in self.enabled_events
            if self.can_generate(name, current_tick)
        ]

        if not available:
            return None

        weights = [
            STANDARD_EVENTS[name].probability_weight
            for name in available
        ]

        total = sum(weights)
        r = self.rng.uniform(0, total)

        cumulative = 0
        for name, weight in zip(available, weights):
            cumulative += weight
            if r <= cumulative:
                return name

        return available[-1]

    def _generate_parameters(self, template: EventTemplate, severity: float) -> Dict:
        """Generate event-specific parameters."""
        params = {}

        if template.event_type == EventType.CREW_SIZE_INCREASE:
            params["count"] = self.rng.randint(1, 3)
        elif template.event_type == EventType.CREW_SIZE_DECREASE:
            params["count"] = self.rng.randint(1, 2)
        elif template.event_type == EventType.CREW_EVA_DAY:
            params["crew_count"] = self.rng.randint(2, 4)
            params["hours"] = self.rng.randint(4, 8)

        return params


# =============================================================================
# SCRIPTED EVENT GENERATOR
# =============================================================================

class ScriptedEventGenerator(EventGenerator):
    """
    Generates events from a pre-defined script.

    Used for:
    - Reproducible testing scenarios
    - BioSim validation scripts
    - Specific failure mode testing
    """

    def __init__(self, script: List[Dict]):
        """
        Initialize with an event script.

        Script format:
        [
            {
                "template": "total_power_outage",
                "trigger_tick": 100,
                "duration": 24,
                "severity": 1.0,
                "target": None,
                "parameters": {}
            },
            ...
        ]
        """
        super().__init__()
        self.script = script
        self.script_index = 0

    @classmethod
    def from_json(cls, filepath: str) -> "ScriptedEventGenerator":
        """Load script from JSON file."""
        with open(filepath, 'r') as f:
            script = json.load(f)
        return cls(script)

    @classmethod
    def from_biosim_scenario(cls, scenario_name: str) -> "ScriptedEventGenerator":
        """
        Create generator from standard BioSim test scenario.

        Standard scenarios:
        - "power_stress": Multiple power events
        - "water_stress": Water restrictions and interruptions
        - "full_resilience": All failure types
        - "crew_variance": Crew size changes
        """
        scenarios = {
            "power_stress": [
                {"template": "power_reduction", "trigger_tick": 24, "severity": 0.3},
                {"template": "partial_power_outage", "trigger_tick": 72, "severity": 0.5},
                {"template": "total_power_outage", "trigger_tick": 168, "duration": 12},
                {"template": "dust_storm", "trigger_tick": 240, "duration": 48, "severity": 0.5},
            ],
            "water_stress": [
                {"template": "water_restriction", "trigger_tick": 24, "severity": 0.3},
                {"template": "water_interruption", "trigger_tick": 96, "target": "RSV_POD_1"},
                {"template": "water_restriction", "trigger_tick": 168, "severity": 0.5},
                {"template": "water_contamination", "trigger_tick": 240, "severity": 0.5},
            ],
            "crew_variance": [
                {"template": "eva_day", "trigger_tick": 24},
                {"template": "metabolic_increase", "trigger_tick": 72, "severity": 0.2},
                {"template": "crew_increase", "trigger_tick": 168, "parameters": {"count": 2}},
                {"template": "crew_decrease", "trigger_tick": 336, "parameters": {"count": 1}},
            ],
            "full_resilience": [
                # Power events
                {"template": "power_reduction", "trigger_tick": 24, "severity": 0.25},
                {"template": "partial_power_outage", "trigger_tick": 96, "severity": 0.5},
                {"template": "total_power_outage", "trigger_tick": 240, "duration": 6},
                # Water events
                {"template": "water_restriction", "trigger_tick": 48, "severity": 0.3},
                {"template": "water_interruption", "trigger_tick": 168, "target": "RSV_POD_1"},
                # Equipment events
                {"template": "equipment_malfunction", "trigger_tick": 120, "target": "Food_POD_1"},
                {"template": "pod_failure", "trigger_tick": 288, "target": "Fodder_POD", "severity": 0.7},
                # Crew events
                {"template": "eva_day", "trigger_tick": 72},
                {"template": "metabolic_increase", "trigger_tick": 192, "severity": 0.15},
                # Environmental
                {"template": "dust_storm", "trigger_tick": 336, "duration": 72, "severity": 0.4},
            ],
        }

        script = scenarios.get(scenario_name, [])
        return cls(script)

    def generate_events(self, current_tick: int, duration_ticks: int) -> List[Event]:
        """Generate events from script that fall within the time window."""
        events = []
        window_end = current_tick + duration_ticks

        while self.script_index < len(self.script):
            item = self.script[self.script_index]
            trigger = item.get("trigger_tick", 0)

            # Stop if event is past window
            if trigger >= window_end:
                break

            # Skip if event is before current tick
            if trigger < current_tick:
                self.script_index += 1
                continue

            # Generate event
            template_name = item.get("template")
            if template_name not in STANDARD_EVENTS:
                logger.warning(f"Unknown event template: {template_name}")
                self.script_index += 1
                continue

            template = STANDARD_EVENTS[template_name]

            event = template.create_event(
                trigger_tick=trigger,
                duration=item.get("duration", template.default_duration),
                severity=item.get("severity", template.default_severity),
                target=item.get("target"),
                parameters=item.get("parameters", {}),
            )

            self.record_event(template_name, trigger, event)
            events.append(event)
            self.script_index += 1

            logger.info(f"Scripted event: {template.name} at tick {trigger}")

        return events

    def reset(self):
        """Reset script to beginning."""
        self.script_index = 0
        self.events_generated = []
        self.last_event_tick = {}


# =============================================================================
# BIOSIM EVENT ADAPTER
# =============================================================================

class BioSimEventAdapter(EventGenerator):
    """
    Adapter for receiving events from BioSim server.

    Translates BioSim malfunction injection commands to our event system.
    """

    # BioSim malfunction type to our event type mapping
    BIOSIM_MAPPING = {
        "PowerGeneratorMalfunction": EventType.POWER_OUTAGE_PARTIAL,
        "PowerStoreMalfunction": EventType.POWER_OUTAGE_TOTAL,
        "WaterRSMalfunction": EventType.WATER_SUPPLY_INTERRUPTION,
        "WaterStoreMalfunction": EventType.WATER_RESTRICTION,
        "FoodProcessorMalfunction": EventType.EQUIPMENT_MALFUNCTION,
        "CrewPersonMalfunction": EventType.CREW_SIZE_DECREASE,
        "InjectorMalfunction": EventType.EQUIPMENT_MALFUNCTION,
        "AccumulatorMalfunction": EventType.EQUIPMENT_MALFUNCTION,
    }

    def __init__(self):
        super().__init__()
        self.pending_events: List[Event] = []

    def inject_biosim_malfunction(
        self,
        malfunction_type: str,
        module_name: str,
        intensity: float,
        tick_length: int,
        current_tick: int,
    ) -> Optional[Event]:
        """
        Inject a BioSim-style malfunction.

        Args:
            malfunction_type: BioSim malfunction type string
            module_name: Target module name
            intensity: 0.0 to 1.0 malfunction intensity
            tick_length: Duration in ticks
            current_tick: Current simulation tick

        Returns:
            Generated Event or None if type unknown
        """
        event_type = self.BIOSIM_MAPPING.get(malfunction_type)
        if not event_type:
            logger.warning(f"Unknown BioSim malfunction type: {malfunction_type}")
            return None

        event = Event(
            event_type=event_type,
            trigger_tick=current_tick,
            duration_ticks=tick_length,
            severity=intensity,
            target_module=module_name,
            parameters={"biosim_type": malfunction_type},
        )

        self.pending_events.append(event)
        self.events_generated.append(event)

        logger.info(
            f"BioSim malfunction: {malfunction_type} on {module_name} "
            f"(intensity {intensity}, duration {tick_length})"
        )

        return event

    def generate_events(self, current_tick: int, duration_ticks: int) -> List[Event]:
        """Return pending BioSim events and clear queue."""
        events = self.pending_events.copy()
        self.pending_events = []
        return events


# =============================================================================
# EVENT SCHEDULER
# =============================================================================

class EventScheduler:
    """
    Coordinates event generation and scheduling with the simulation.

    Supports multiple event generators running simultaneously.
    """

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.generators: List[EventGenerator] = []
        self.generation_interval: int = 24  # Generate events every sol
        self.last_generation_tick: int = -999999

        # Statistics
        self.total_events_scheduled = 0
        self.events_by_type: Dict[str, int] = {}

    def add_generator(self, generator: EventGenerator):
        """Add an event generator."""
        self.generators.append(generator)

    def remove_generator(self, generator: EventGenerator):
        """Remove an event generator."""
        if generator in self.generators:
            self.generators.remove(generator)

    def update(self):
        """
        Check if it's time to generate new events.

        Called each tick by the simulation.
        """
        current_tick = self.simulation.current_tick

        if current_tick - self.last_generation_tick >= self.generation_interval:
            self._generate_and_schedule()
            self.last_generation_tick = current_tick

    def _generate_and_schedule(self):
        """Generate events from all generators and schedule them."""
        current_tick = self.simulation.current_tick

        for generator in self.generators:
            events = generator.generate_events(current_tick, self.generation_interval)

            for event in events:
                self.simulation.schedule_event(event)
                self.total_events_scheduled += 1

                type_name = event.event_type.name
                self.events_by_type[type_name] = self.events_by_type.get(type_name, 0) + 1

    def force_event(self, template_name: str, **kwargs) -> Optional[Event]:
        """
        Force immediate generation of a specific event.

        Args:
            template_name: Name of event template
            **kwargs: Override template defaults (trigger_tick, duration, severity, etc.)

        Returns:
            Generated Event or None if template unknown
        """
        if template_name not in STANDARD_EVENTS:
            logger.warning(f"Unknown event template: {template_name}")
            return None

        template = STANDARD_EVENTS[template_name]
        current_tick = self.simulation.current_tick

        event = template.create_event(
            trigger_tick=kwargs.get("trigger_tick", current_tick),
            duration=kwargs.get("duration"),
            severity=kwargs.get("severity"),
            target=kwargs.get("target"),
            parameters=kwargs.get("parameters"),
        )

        self.simulation.schedule_event(event)
        self.total_events_scheduled += 1

        logger.info(f"Forced event: {template.name}")
        return event

    def get_statistics(self) -> Dict:
        """Get event scheduling statistics."""
        return {
            "total_scheduled": self.total_events_scheduled,
            "by_type": dict(self.events_by_type),
            "active_generators": len(self.generators),
            "pending_events": len(self.simulation.scheduled_events),
            "active_events": len(self.simulation.active_events),
        }
