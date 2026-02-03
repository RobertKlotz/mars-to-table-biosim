"""
Mars to Table — BioSim XML Configuration Generator
Generates XML configuration files compatible with NASA BioSim simulation server.

BioSim XML format defines:
- Simulation parameters (duration, tick rate)
- Modules (producers, consumers, stores)
- Crew configuration
- Initial resource levels
- Connections between modules

Reference: https://github.com/scottbell/biosim
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from xml.etree import ElementTree as ET
from xml.dom import minidom
import logging
from datetime import datetime

from ..config import MISSION, POWER, WATER, FOOD, LIVESTOCK, NUTRIENTS, POD

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION DATA CLASSES
# =============================================================================

@dataclass
class StoreConfig:
    """Configuration for a BioSim store (resource container)."""
    name: str
    module_type: str  # BioSim module type
    capacity: float
    initial_level: float = 0.0
    overflow_to: Optional[str] = None
    description: str = ""

    def to_xml(self, parent: ET.Element) -> ET.Element:
        """Generate XML element for this store."""
        store = ET.SubElement(parent, "BioModule")
        store.set("name", self.name)
        store.set("moduleType", self.module_type)

        ET.SubElement(store, "capacity").text = str(self.capacity)
        ET.SubElement(store, "currentLevel").text = str(self.initial_level)

        if self.overflow_to:
            ET.SubElement(store, "overflowTo").text = self.overflow_to

        if self.description:
            store.append(ET.Comment(self.description))

        return store


@dataclass
class ModuleConfig:
    """Configuration for a BioSim module (producer/consumer)."""
    name: str
    module_type: str  # BioSim module type
    power_consumption: float = 0.0

    # Input/output connections
    inputs: Dict[str, str] = field(default_factory=dict)  # resource -> store name
    outputs: Dict[str, str] = field(default_factory=dict)  # resource -> store name

    # Module-specific parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    description: str = ""

    def to_xml(self, parent: ET.Element) -> ET.Element:
        """Generate XML element for this module."""
        module = ET.SubElement(parent, "BioModule")
        module.set("name", self.name)
        module.set("moduleType", self.module_type)

        if self.power_consumption > 0:
            ET.SubElement(module, "powerConsumption").text = str(self.power_consumption)

        # Input connections
        if self.inputs:
            inputs_elem = ET.SubElement(module, "inputs")
            for resource, store in self.inputs.items():
                conn = ET.SubElement(inputs_elem, "connection")
                conn.set("resource", resource)
                conn.set("store", store)

        # Output connections
        if self.outputs:
            outputs_elem = ET.SubElement(module, "outputs")
            for resource, store in self.outputs.items():
                conn = ET.SubElement(outputs_elem, "connection")
                conn.set("resource", resource)
                conn.set("store", store)

        # Custom parameters
        for key, value in self.parameters.items():
            ET.SubElement(module, key).text = str(value)

        if self.description:
            module.append(ET.Comment(self.description))

        return module


@dataclass
class CrewConfig:
    """Configuration for BioSim crew."""
    crew_size: int = 15
    schedule_type: str = "StandardSchedule"
    activity_level: str = "MODERATE"

    # Per-person requirements
    calories_per_day: float = 3035.0
    water_per_day: float = 3.0
    oxygen_per_day: float = 0.84  # kg O2/person/day

    def to_xml(self, parent: ET.Element) -> ET.Element:
        """Generate XML element for crew configuration."""
        crew = ET.SubElement(parent, "CrewGroup")
        crew.set("name", "MarsHabitatCrew")

        ET.SubElement(crew, "crewSize").text = str(self.crew_size)
        ET.SubElement(crew, "scheduleType").text = self.schedule_type
        ET.SubElement(crew, "activityLevel").text = self.activity_level

        requirements = ET.SubElement(crew, "requirements")
        ET.SubElement(requirements, "caloriesPerPersonPerDay").text = str(self.calories_per_day)
        ET.SubElement(requirements, "waterPerPersonPerDay").text = str(self.water_per_day)
        ET.SubElement(requirements, "oxygenPerPersonPerDay").text = str(self.oxygen_per_day)

        return crew


@dataclass
class SimulationConfig:
    """Top-level simulation configuration."""
    name: str = "MarsToTable"
    description: str = "sTARS Integrated Food Ecosystem"
    duration_ticks: int = 12000  # 500 sols * 24 ticks
    ticks_per_sol: int = 24
    log_level: str = "INFO"

    def to_xml(self, parent: ET.Element) -> ET.Element:
        """Generate XML element for simulation config."""
        config = ET.SubElement(parent, "SimulationConfig")

        ET.SubElement(config, "name").text = self.name
        ET.SubElement(config, "description").text = self.description
        ET.SubElement(config, "durationTicks").text = str(self.duration_ticks)
        ET.SubElement(config, "ticksPerSol").text = str(self.ticks_per_sol)
        ET.SubElement(config, "logLevel").text = self.log_level

        return config


# =============================================================================
# BIOSIM XML GENERATOR
# =============================================================================

class BioSimXMLGenerator:
    """
    Generates BioSim-compatible XML configuration for the Mars to Table system.

    Creates configuration for:
    - 13 POD modules (Food, Fodder, Grain, Livestock, RSV, Nutrient, Waste, HAB)
    - Resource stores (power, water, gases, food)
    - Crew configuration
    - Module connections
    """

    def __init__(self):
        self.stores: List[StoreConfig] = []
        self.modules: List[ModuleConfig] = []
        self.crew = CrewConfig()
        self.sim_config = SimulationConfig()

        # Build default configuration
        self._build_default_config()

    def _build_default_config(self):
        """Build default configuration based on Mars to Table design."""
        self._create_stores()
        self._create_power_modules()
        self._create_water_modules()
        self._create_food_modules()
        self._create_crew_modules()
        self._create_nutrient_modules()

    def _create_stores(self):
        """Create resource stores."""
        # Power
        self.stores.append(StoreConfig(
            name="PowerStore",
            module_type="GenericStore",
            capacity=5000.0,  # kWh
            initial_level=1000.0,
            description="Main power storage",
        ))

        # Water stores
        self.stores.append(StoreConfig(
            name="PotableWaterStore",
            module_type="WaterStore",
            capacity=WATER.total_tank_storage_l,
            initial_level=WATER.total_tank_storage_l * 0.8,
            description="Potable water from RSV extraction",
        ))

        self.stores.append(StoreConfig(
            name="GreyWaterStore",
            module_type="WaterStore",
            capacity=2000.0,
            initial_level=0.0,
            description="Recycled grey water",
        ))

        self.stores.append(StoreConfig(
            name="WallWaterReserve",
            module_type="WaterStore",
            capacity=WATER.distributed_wall_storage_l,
            initial_level=WATER.distributed_wall_storage_l,
            description="Emergency reserve in POD walls",
        ))

        # Gas stores
        self.stores.append(StoreConfig(
            name="OxygenStore",
            module_type="GasStore",
            capacity=5000.0,  # kg
            initial_level=2000.0,
            description="Oxygen for crew and fuel cells",
        ))

        self.stores.append(StoreConfig(
            name="CO2Store",
            module_type="GasStore",
            capacity=1000.0,
            initial_level=0.0,
            description="CO2 for crop growth",
        ))

        self.stores.append(StoreConfig(
            name="HydrogenStore",
            module_type="GasStore",
            capacity=POWER.h2_storage_kg * 2,  # Both RSV PODs
            initial_level=POWER.h2_storage_kg * 2,
            description="H2 for fuel cells and emergency water",
        ))

        self.stores.append(StoreConfig(
            name="NitrogenStore",
            module_type="GasStore",
            capacity=500.0,
            initial_level=100.0,
            description="N2 from Haber-Bosch",
        ))

        self.stores.append(StoreConfig(
            name="BiogasStore",
            module_type="GasStore",
            capacity=200.0,
            initial_level=50.0,
            description="Biogas from waste processing",
        ))

        # Food stores
        self.stores.append(StoreConfig(
            name="FreshFoodStore",
            module_type="FoodStore",
            capacity=1000.0,  # kg
            initial_level=100.0,
            description="Fresh vegetables and produce",
        ))

        self.stores.append(StoreConfig(
            name="ProcessedFoodStore",
            module_type="FoodStore",
            capacity=500.0,
            initial_level=50.0,
            description="Flour, cheese, processed foods",
        ))

        self.stores.append(StoreConfig(
            name="EarthFoodStore",
            module_type="FoodStore",
            capacity=2000.0,
            initial_level=1500.0,
            description="Pre-packaged Earth supplies",
        ))

        self.stores.append(StoreConfig(
            name="LivestockFeedStore",
            module_type="FoodStore",
            capacity=500.0,
            initial_level=100.0,
            description="Fodder for goats and chickens",
        ))

        # Nutrient stores
        self.stores.append(StoreConfig(
            name="NitrogenNutrientStore",
            module_type="GenericStore",
            capacity=100.0,
            initial_level=50.0,
            description="Plant-available nitrogen",
        ))

        self.stores.append(StoreConfig(
            name="PhosphorusStore",
            module_type="GenericStore",
            capacity=50.0,
            initial_level=25.0,
            description="Recovered phosphorus",
        ))

        # Waste stores
        self.stores.append(StoreConfig(
            name="SolidWasteStore",
            module_type="GenericStore",
            capacity=200.0,
            initial_level=0.0,
            description="Human and animal solid waste",
        ))

        self.stores.append(StoreConfig(
            name="BiomassWasteStore",
            module_type="GenericStore",
            capacity=500.0,
            initial_level=0.0,
            description="Inedible plant biomass",
        ))

    def _create_power_modules(self):
        """Create power generation modules."""
        # Solar Array
        self.modules.append(ModuleConfig(
            name="SolarArray",
            module_type="PowerGenerator",
            outputs={"power": "PowerStore"},
            parameters={
                "peakOutput": POWER.peak_solar_kw,
                "efficiency": POWER.solar_efficiency,
                "dayFraction": POWER.solar_day_fraction,
            },
            description="iROSA solar arrays",
        ))

        # RSV Fuel Cells (x2)
        for i in range(1, 3):
            self.modules.append(ModuleConfig(
                name=f"RSV_FuelCell_{i}",
                module_type="FuelCell",
                inputs={
                    "hydrogen": "HydrogenStore",
                    "oxygen": "OxygenStore",
                },
                outputs={
                    "power": "PowerStore",
                    "water": "PotableWaterStore",  # Byproduct
                },
                parameters={
                    "maxOutput": POWER.fuel_cell_capacity_kw,
                    "efficiency": POWER.fuel_cell_efficiency,
                },
                description=f"RSV POD {i} fuel cell backup",
            ))

        # Biogas SOFC
        self.modules.append(ModuleConfig(
            name="BiogasSOFC",
            module_type="PowerGenerator",
            inputs={"biogas": "BiogasStore"},
            outputs={"power": "PowerStore"},
            parameters={
                "maxOutput": POWER.biogas_capacity_kw,
                "efficiency": 0.55,
            },
            description="Biogas solid oxide fuel cell",
        ))

    def _create_water_modules(self):
        """Create water extraction and recycling modules."""
        # RSV Extractors (x2)
        for i in range(1, 3):
            self.modules.append(ModuleConfig(
                name=f"RSV_Extractor_{i}",
                module_type="WaterExtractor",
                power_consumption=POWER.rsv_pod_load_kw,
                outputs={"water": "PotableWaterStore"},
                parameters={
                    "extractionRate": WATER.ice_extraction_rate_l_per_day,
                },
                description=f"RSV POD {i} ice extraction",
            ))

        # Water Recycler
        self.modules.append(ModuleConfig(
            name="WaterRecycler",
            module_type="WaterProcessor",
            power_consumption=10.0,
            inputs={"greyWater": "GreyWaterStore"},
            outputs={"potableWater": "PotableWaterStore"},
            parameters={
                "recyclingEfficiency": WATER.recycling_efficiency,
            },
            description="Grey water recycling system",
        ))

        # Emergency H2 Combuster
        self.modules.append(ModuleConfig(
            name="H2Combuster",
            module_type="EmergencyWaterGenerator",
            inputs={
                "hydrogen": "HydrogenStore",
                "oxygen": "OxygenStore",
            },
            outputs={"water": "PotableWaterStore"},
            parameters={
                "h2ToWaterRatio": WATER.h2_to_water_ratio,
            },
            description="Emergency: burn H2 for water (1kg H2 → 9kg H2O)",
        ))

    def _create_food_modules(self):
        """Create food production modules."""
        # Food PODs 1-5
        for i in range(1, 6):
            self.modules.append(ModuleConfig(
                name=f"FoodPOD_{i}",
                module_type="BiomassProducer",
                power_consumption=POWER.food_pod_load_kw,
                inputs={
                    "water": "PotableWaterStore",
                    "nitrogen": "NitrogenNutrientStore",
                    "phosphorus": "PhosphorusStore",
                    "co2": "CO2Store",
                },
                outputs={
                    "food": "FreshFoodStore",
                    "oxygen": "OxygenStore",
                    "biomassWaste": "BiomassWasteStore",
                },
                parameters={
                    "growingArea": FOOD.growing_area_per_pod_m2,
                    "lightingLevel": "HIGH",
                },
                description=f"Food POD {i} - human crop production",
            ))

        # Fodder POD
        self.modules.append(ModuleConfig(
            name="FodderPOD",
            module_type="BiomassProducer",
            power_consumption=POWER.food_pod_load_kw,
            inputs={
                "water": "PotableWaterStore",
                "nitrogen": "NitrogenNutrientStore",
            },
            outputs={
                "fodder": "LivestockFeedStore",
                "biomassWaste": "BiomassWasteStore",
            },
            parameters={
                "growingArea": FOOD.fodder_area_m2,
                "yieldRate": FOOD.fodder_yield_kg_per_m2_per_day,
            },
            description="POD 6 - livestock fodder production",
        ))

        # Grain POD
        self.modules.append(ModuleConfig(
            name="GrainPOD",
            module_type="BiomassProducer",
            power_consumption=POWER.food_pod_load_kw,
            inputs={
                "water": "PotableWaterStore",
                "nitrogen": "NitrogenNutrientStore",
            },
            outputs={
                "flour": "ProcessedFoodStore",
                "biomassWaste": "BiomassWasteStore",
            },
            parameters={
                "growingArea": FOOD.grain_area_m2,
                "flourYield": FOOD.flour_yield_kg_per_day,
            },
            description="POD 7 - grain and flour production",
        ))

        # Livestock POD
        self.modules.append(ModuleConfig(
            name="LivestockPOD",
            module_type="LivestockProducer",
            power_consumption=POWER.livestock_pod_load_kw,
            inputs={
                "feed": "LivestockFeedStore",
                "water": "PotableWaterStore",
            },
            outputs={
                "milk": "ProcessedFoodStore",
                "eggs": "FreshFoodStore",
                "cheese": "ProcessedFoodStore",
                "meat": "ProcessedFoodStore",
                "manure": "SolidWasteStore",
            },
            parameters={
                "goats": LIVESTOCK.total_goats,
                "chickens": LIVESTOCK.total_chickens,
                "dailyMilk": LIVESTOCK.daily_milk_l,
                "dailyEggs": LIVESTOCK.daily_eggs,
            },
            description="POD 8 - goats and chickens",
        ))

    def _create_crew_modules(self):
        """Create crew-related modules."""
        # Crew Consumer
        self.modules.append(ModuleConfig(
            name="CrewConsumer",
            module_type="CrewGroup",
            inputs={
                "food": "FreshFoodStore",
                "processedFood": "ProcessedFoodStore",
                "earthFood": "EarthFoodStore",
                "water": "PotableWaterStore",
                "oxygen": "OxygenStore",
            },
            outputs={
                "co2": "CO2Store",
                "greyWater": "GreyWaterStore",
                "solidWaste": "SolidWasteStore",
            },
            parameters={
                "crewSize": MISSION.crew_size,
                "caloriesPerDay": MISSION.base_calories_per_crew_per_day,
                "waterPerDay": WATER.crew_consumption_l_per_person,
            },
            description="15-person crew consumption",
        ))

        # HAB/LAB POD (kitchen, dining)
        self.modules.append(ModuleConfig(
            name="HAB_POD",
            module_type="HabitatModule",
            power_consumption=POWER.hab_pod_load_kw,
            inputs={
                "food": "FreshFoodStore",
                "processedFood": "ProcessedFoodStore",
            },
            outputs={
                "preparedMeals": "FreshFoodStore",  # Simplified
            },
            parameters={
                "kitchenCapacity": 15,
            },
            description="Habitat - kitchen and dining",
        ))

    def _create_nutrient_modules(self):
        """Create nutrient cycling modules."""
        # Haber-Bosch Reactor
        self.modules.append(ModuleConfig(
            name="HaberBoschReactor",
            module_type="ChemicalProcessor",
            power_consumption=20.0,
            inputs={"nitrogen_gas": "NitrogenStore"},
            outputs={"nitrogen_nutrient": "NitrogenNutrientStore"},
            parameters={
                "captureRate": NUTRIENTS.n2_capture_rate_kg_per_day,
                "efficiency": NUTRIENTS.haber_bosch_efficiency,
            },
            description="N2 fixation for plant nutrients",
        ))

        # Waste Processor
        self.modules.append(ModuleConfig(
            name="WasteProcessor",
            module_type="WasteProcessor",
            power_consumption=POWER.processing_pod_load_kw,
            inputs={
                "solidWaste": "SolidWasteStore",
                "biomassWaste": "BiomassWasteStore",
            },
            outputs={
                "biogas": "BiogasStore",
                "phosphorus": "PhosphorusStore",
                "nitrogen": "NitrogenNutrientStore",
            },
            parameters={
                "biogasYield": NUTRIENTS.biogas_yield_m3_per_kg_waste,
                "phosphorusRecovery": NUTRIENTS.phosphorus_recovery_rate,
            },
            description="Anaerobic digestion and nutrient recovery",
        ))

    def generate_xml(self) -> str:
        """
        Generate complete BioSim XML configuration.

        Returns:
            Formatted XML string
        """
        # Create root element
        root = ET.Element("BioSimConfig")
        root.set("xmlns", "http://biosim.nasa.gov/schema")
        root.set("version", "1.0")

        # Add header comment
        root.append(ET.Comment(f"""
    Mars to Table - sTARS Integrated Food Ecosystem
    Generated: {datetime.now().isoformat()}
    Team: Bueché-Labs LLC
    Challenge: NASA Deep Space Food Challenge

    System Overview:
    - 5 Food PODs (human crops)
    - 1 Fodder POD (livestock feed)
    - 1 Grain POD (flour production)
    - 1 Livestock POD (goats + chickens)
    - 2 RSV PODs (water extraction + power backup)
    - 1 Nutrient POD (Haber-Bosch)
    - 1 Waste POD (biogas + nutrient recovery)
    - 1 HAB POD (kitchen, dining)

    Target: 84% Earth Independence for 15 crew over 500 sols
    """))

        # Add simulation config
        self.sim_config.to_xml(root)

        # Add stores section
        stores_section = ET.SubElement(root, "Stores")
        stores_section.append(ET.Comment("Resource storage containers"))
        for store in self.stores:
            store.to_xml(stores_section)

        # Add modules section
        modules_section = ET.SubElement(root, "Modules")
        modules_section.append(ET.Comment("Production and consumption modules"))
        for module in self.modules:
            module.to_xml(modules_section)

        # Add crew section
        crew_section = ET.SubElement(root, "Crew")
        self.crew.to_xml(crew_section)

        # Format output
        xml_string = ET.tostring(root, encoding='unicode')
        pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")

        # Remove extra blank lines
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        return '\n'.join(lines)

    def save_xml(self, filepath: str):
        """Save XML configuration to file."""
        xml_content = self.generate_xml()

        with open(filepath, 'w') as f:
            f.write(xml_content)

        logger.info(f"BioSim XML configuration saved to {filepath}")

    def get_module_list(self) -> List[str]:
        """Get list of all module names."""
        return [m.name for m in self.modules]

    def get_store_list(self) -> List[str]:
        """Get list of all store names."""
        return [s.name for s in self.stores]

    def add_custom_module(self, config: ModuleConfig):
        """Add a custom module configuration."""
        self.modules.append(config)

    def add_custom_store(self, config: StoreConfig):
        """Add a custom store configuration."""
        self.stores.append(config)

    def set_simulation_duration(self, sols: int):
        """Set simulation duration in sols."""
        self.sim_config.duration_ticks = sols * self.sim_config.ticks_per_sol

    def set_crew_size(self, size: int):
        """Set crew size."""
        self.crew.crew_size = size
        # Update crew consumer module
        for module in self.modules:
            if module.name == "CrewConsumer":
                module.parameters["crewSize"] = size
