"""
Mars to Table — Simulation Package
Event injection, failure responses, resilience protocols, metrics,
livestock lifecycle, crop diseases, and human factors modeling.
"""

from .events import (
    EventGenerator,
    EventScheduler,
    BioSimEventAdapter,
    RandomEventGenerator,
    ScriptedEventGenerator,
)

from .responses import (
    ResponseHandler,
    ResponseManager,
    ResponseStrategy,
    PowerFailureResponse,
    WaterFailureResponse,
    PODFailureResponse,
    CrewChangeResponse,
)

from .protocols import (
    FailureProtocol,
    ProtocolManager,
    PowerOutageProtocol,
    PowerReductionProtocol,
    WaterInterruptionProtocol,
    WaterRestrictionProtocol,
    EmergencyWaterProtocol,
    GracefulDegradationProtocol,
)

from .metrics import (
    MetricCategory,
    FoodProductionMetrics,
    ResourceMetrics,
    SystemMetrics,
    CrewMetrics,
    MissionMetrics,
    MetricsCollector,
    MissionEvaluator,
)

from .lifecycle import (
    LifeStage,
    BreedingStatus,
    HealthEvent,
    BreedingRecord,
    HealthRecord,
    AnimalLifecycle,
    GoatLifecycleManager,
    ChickenLifecycleManager,
)

from .crop_failures import (
    CropFailureType,
    CropSeverity,
    CropFailureEvent,
    CropFailureResponse,
    CropFailureGenerator,
)

from .human_factors import (
    PsychologicalState,
    StressorType,
    CopingMechanism,
    MealSatisfaction,
    CrewMemberPsychology,
    CrewPsychologyManager,
)

from .stress_tests import (
    StressTestCategory,
    StressTestSeverity,
    StressTestScenario,
    StressTestResult,
    StressTestRunner,
    STRESS_TEST_SCENARIOS,
)

__all__ = [
    # Events
    "EventGenerator",
    "EventScheduler",
    "BioSimEventAdapter",
    "RandomEventGenerator",
    "ScriptedEventGenerator",
    # Responses
    "ResponseHandler",
    "ResponseManager",
    "ResponseStrategy",
    "PowerFailureResponse",
    "WaterFailureResponse",
    "PODFailureResponse",
    "CrewChangeResponse",
    # Protocols
    "FailureProtocol",
    "ProtocolManager",
    "PowerOutageProtocol",
    "PowerReductionProtocol",
    "WaterInterruptionProtocol",
    "WaterRestrictionProtocol",
    "EmergencyWaterProtocol",
    "GracefulDegradationProtocol",
    # Metrics
    "MetricCategory",
    "FoodProductionMetrics",
    "ResourceMetrics",
    "SystemMetrics",
    "CrewMetrics",
    "MissionMetrics",
    "MetricsCollector",
    "MissionEvaluator",
    # Livestock Lifecycle
    "LifeStage",
    "BreedingStatus",
    "HealthEvent",
    "BreedingRecord",
    "HealthRecord",
    "AnimalLifecycle",
    "GoatLifecycleManager",
    "ChickenLifecycleManager",
    # Crop Failures
    "CropFailureType",
    "CropSeverity",
    "CropFailureEvent",
    "CropFailureResponse",
    "CropFailureGenerator",
    # Human Factors
    "PsychologicalState",
    "StressorType",
    "CopingMechanism",
    "MealSatisfaction",
    "CrewMemberPsychology",
    "CrewPsychologyManager",
    # Stress Tests
    "StressTestCategory",
    "StressTestSeverity",
    "StressTestScenario",
    "StressTestResult",
    "StressTestRunner",
    "STRESS_TEST_SCENARIOS",
]
