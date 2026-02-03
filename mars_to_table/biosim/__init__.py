"""
Mars to Table — BioSim Integration Package
XML configuration generation and REST client for NASA BioSim server.

BioSim is a life support simulation platform developed at NASA Johnson Space Center.
Repository: https://github.com/scottbell/biosim

Our integration:
1. Generate XML configuration files for BioSim
2. Communicate with BioSim server via REST API
3. Translate between our simulation model and BioSim format
"""

from .xml_generator import (
    BioSimXMLGenerator,
    ModuleConfig,
    StoreConfig,
    CrewConfig,
    SimulationConfig,
)

from .client import (
    BioSimClient,
    BioSimSession,
    ConnectionError,
    SimulationError,
)

__all__ = [
    # XML Generator
    "BioSimXMLGenerator",
    "ModuleConfig",
    "StoreConfig",
    "CrewConfig",
    "SimulationConfig",
    # Client
    "BioSimClient",
    "BioSimSession",
    "ConnectionError",
    "SimulationError",
]
