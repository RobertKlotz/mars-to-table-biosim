"""
Mars to Table — BioSim Simulation Model
Deep Space Food Challenge: Mars to Table
Team: Bueché-Labs LLC

An integrated food ecosystem simulation achieving 84% Earth-independence
for a 15-person crew over 500+ sols on Mars.
"""

__version__ = "1.0.0"
__author__ = "Bueché-Labs LLC"
__challenge__ = "NASA Deep Space Food Challenge: Mars to Table"

from .config import (
    MISSION,
    POD,
    POWER,
    WATER,
    FOOD,
    LIVESTOCK,
    NUTRIENTS,
    MissionConfig,
    Priority,
    FailureMode,
)

from .core import (
    Store,
    StoreManager,
    ResourceType,
    Module,
    ModuleManager,
    ModuleSpec,
    ModuleState,
    ResourceFlow,
    Simulation,
    SimulationState,
    Event,
    EventType,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__challenge__",
    
    # Config
    "MISSION",
    "POD",
    "POWER",
    "WATER",
    "FOOD",
    "LIVESTOCK",
    "NUTRIENTS",
    "MissionConfig",
    "Priority",
    "FailureMode",
    
    # Core classes
    "Store",
    "StoreManager",
    "ResourceType",
    "Module",
    "ModuleManager",
    "ModuleSpec",
    "ModuleState",
    "ResourceFlow",
    "Simulation",
    "SimulationState",
    "Event",
    "EventType",
]
