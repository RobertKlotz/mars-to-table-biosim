"""
Mars to Table — Nutrient System
Nitrogen fixation, phosphorus recovery, and nutrient cycling.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto
import logging

from ..core.store import Store, StoreManager, ResourceType
from ..core.module import Module, ModuleSpec, ModuleState, ModuleManager, ResourceFlow
from ..config import NUTRIENTS, MISSION, Priority

logger = logging.getLogger(__name__)


class NutrientType(Enum):
    """Primary plant nutrients (N-P-K)."""
    NITROGEN = auto()
    PHOSPHORUS = auto()
    POTASSIUM = auto()


@dataclass
class NutrientState:
    """Current state of the nutrient system."""
    nitrogen_production_kg_per_day: float = 0.0
    phosphorus_recovery_kg_per_day: float = 0.0
    potassium_available_kg: float = 0.0
    biogas_production_m3_per_day: float = 0.0
    waste_processed_kg_per_day: float = 0.0
    nitrogen_store_kg: float = 0.0
    phosphorus_store_kg: float = 0.0
    potassium_store_kg: float = 0.0
    self_sufficiency_n: float = 0.0
    self_sufficiency_p: float = 0.0


class HaberBoschReactor(Module):
    """
    Haber-Bosch nitrogen fixation reactor.

    Converts atmospheric N2 + H2 -> NH3 (ammonia)

    Mars atmosphere is 2.7% N2, captured and processed.
    Requires high pressure and temperature.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 n2_capture_rate_kg_per_day: float = None):

        rate = n2_capture_rate_kg_per_day or NUTRIENTS.n2_capture_rate_kg_per_day

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=15.0,  # High energy process
            consumes=[
                # N2 from atmosphere capture
                ResourceFlow(ResourceType.NITROGEN, rate / 24, "Atmospheric_N2", required=True),
                # H2 for ammonia synthesis
                ResourceFlow(ResourceType.HYDROGEN, (rate * 0.3) / 24, "Hydrogen", required=True),
            ],
            produces=[
                # Output ammonia as nitrogen nutrient
                ResourceFlow(ResourceType.NUTRIENTS_N, 0.0, "Nutrients_N"),  # Calculated
            ],
            startup_ticks=4,  # Slow to warm up
            efficiency=NUTRIENTS.haber_bosch_efficiency
        )
        super().__init__(spec, store_manager)

        self.n2_capture_rate = rate
        self.ammonia_produced_total = 0.0

    @property
    def ammonia_rate_per_tick(self) -> float:
        """Ammonia production rate in kg/tick."""
        # N2 + 3H2 -> 2NH3
        # With 15% efficiency typical for small-scale
        n2_flow = next((f for f in self.spec.consumes
                       if f.resource_type == ResourceType.NITROGEN), None)
        if n2_flow:
            return n2_flow.rate_per_tick * self.effective_efficiency * 1.2  # NH3 mass gain
        return 0.0

    def process_tick(self) -> Dict:
        """Produce ammonia from N2 and H2."""
        # Check actual input flows
        n2_flow = next((f for f in self.spec.consumes
                       if f.resource_type == ResourceType.NITROGEN), None)
        h2_flow = next((f for f in self.spec.consumes
                       if f.resource_type == ResourceType.HYDROGEN), None)

        ammonia_produced = 0.0

        if n2_flow and h2_flow:
            # Production limited by lesser input
            n2_available = n2_flow.actual_flow
            h2_available = h2_flow.actual_flow

            # Stoichiometry: need 3 parts H2 to 1 part N2 by moles
            # By mass: ~0.18 kg H2 per kg N2
            h2_needed = n2_available * 0.18

            if h2_available >= h2_needed * 0.9:  # Allow 10% tolerance
                # Full production
                ammonia_produced = n2_available * self.effective_efficiency * 1.2
            else:
                # H2-limited production
                effective_n2 = h2_available / 0.18
                ammonia_produced = effective_n2 * self.effective_efficiency * 1.2

        self.ammonia_produced_total += ammonia_produced

        # Add to nitrogen nutrient store
        n_store = self.stores.get("Nutrients_N")
        if n_store and ammonia_produced > 0:
            # Ammonia is ~82% nitrogen by mass
            nitrogen_content = ammonia_produced * 0.82
            n_store.add(nitrogen_content)

        return {
            "ammonia_produced_kg": ammonia_produced,
            "nitrogen_content_kg": ammonia_produced * 0.82,
            "total_ammonia_kg": self.ammonia_produced_total,
            "efficiency": self.effective_efficiency,
        }


class WasteProcessor(Module):
    """
    Anaerobic digestion waste processor.

    Processes human and animal waste to:
    1. Biogas (methane for fuel)
    2. Digestate (phosphorus-rich fertilizer)

    Also handles inedible crop biomass.
    """

    def __init__(self, name: str, store_manager: StoreManager):
        # Daily waste inputs
        human_waste = NUTRIENTS.human_waste_kg_per_person_per_day * MISSION.crew_size
        animal_waste = NUTRIENTS.animal_waste_kg_per_day

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=10.0,
            consumes=[
                ResourceFlow(ResourceType.HUMAN_WASTE, human_waste / 24, "Human_Waste", required=False),
                ResourceFlow(ResourceType.ANIMAL_WASTE, animal_waste / 24, "Animal_Waste", required=False),
                ResourceFlow(ResourceType.BIOMASS_INEDIBLE, 5.0 / 24, "Crop_Waste", required=False),
            ],
            produces=[
                ResourceFlow(ResourceType.METHANE, 0.0, "Biogas"),  # Calculated
                ResourceFlow(ResourceType.NUTRIENTS_P, 0.0, "Nutrients_P"),  # Calculated
            ],
            startup_ticks=24,  # Digesters take time to establish
            efficiency=0.85
        )
        super().__init__(spec, store_manager)

        self.biogas_yield = NUTRIENTS.biogas_yield_m3_per_kg_waste
        self.phosphorus_recovery_rate = NUTRIENTS.phosphorus_recovery_rate

        self.total_waste_processed = 0.0
        self.total_biogas_produced = 0.0
        self.total_phosphorus_recovered = 0.0

    def process_tick(self) -> Dict:
        """Process waste to biogas and nutrients."""
        # Sum all waste inputs
        total_waste = sum(f.actual_flow for f in self.spec.consumes)
        self.total_waste_processed += total_waste

        # Biogas production
        biogas = total_waste * self.biogas_yield * self.effective_efficiency
        self.total_biogas_produced += biogas

        # Phosphorus recovery from digestate
        # ~0.5% of waste mass is phosphorus, recover 80%
        phosphorus = total_waste * 0.005 * self.phosphorus_recovery_rate * self.effective_efficiency
        self.total_phosphorus_recovered += phosphorus

        # Add to stores
        biogas_store = self.stores.get("Biogas")
        if biogas_store and biogas > 0:
            biogas_store.add(biogas)

        p_store = self.stores.get("Nutrients_P")
        if p_store and phosphorus > 0:
            p_store.add(phosphorus)

        return {
            "waste_processed_kg": total_waste,
            "biogas_produced_m3": biogas,
            "phosphorus_recovered_kg": phosphorus,
            "total_waste_kg": self.total_waste_processed,
            "total_biogas_m3": self.total_biogas_produced,
            "total_phosphorus_kg": self.total_phosphorus_recovered,
        }


class AtmosphereProcessor(Module):
    """
    Mars atmosphere processor.

    Captures and separates:
    - CO2 (95.3%) - for plant growth
    - N2 (2.7%) - for Haber-Bosch
    - Ar (1.6%) - waste
    - Other trace gases

    Uses MOXIE-style technology.
    """

    def __init__(self, name: str, store_manager: StoreManager,
                 processing_rate_kg_per_day: float = 50.0):

        spec = ModuleSpec(
            name=name,
            priority=Priority.MEDIUM,
            power_consumption_kw=8.0,
            produces=[
                # N2 output for Haber-Bosch (2.7% of intake)
                ResourceFlow(ResourceType.NITROGEN, (processing_rate_kg_per_day * 0.027) / 24, "Atmospheric_N2"),
                # CO2 for greenhouse enrichment
                ResourceFlow(ResourceType.CO2, (processing_rate_kg_per_day * 0.95) / 24, "CO2_Store"),
            ],
            efficiency=0.90
        )
        super().__init__(spec, store_manager)

        self.processing_rate = processing_rate_kg_per_day

    def process_tick(self) -> Dict:
        """Process Mars atmosphere."""
        # Production handled by parent class
        effective_rate = self.processing_rate * self.effective_efficiency

        return {
            "atmosphere_processed_kg": effective_rate / 24,
            "n2_extracted_kg": effective_rate * 0.027 / 24,
            "co2_extracted_kg": effective_rate * 0.95 / 24,
        }


class NutrientSystem:
    """
    Integrated nutrient management system.

    Manages the N-P-K nutrient cycle:
    - Nitrogen: 90% from Haber-Bosch, 10% from waste
    - Phosphorus: 80% recovered from waste, 20% from Earth supply
    - Potassium: Primarily from Earth supply + ash recovery

    Implements closed-loop nutrient cycling.
    """

    def __init__(self, store_manager: StoreManager, module_manager: ModuleManager):
        self.stores = store_manager
        self.modules = module_manager

        # System components
        self.haber_bosch: Optional[HaberBoschReactor] = None
        self.waste_processor: Optional[WasteProcessor] = None
        self.atmosphere_processor: Optional[AtmosphereProcessor] = None

        # State
        self.state = NutrientState()

        # Earth supplies (initial stock)
        self.potassium_from_earth = NUTRIENTS.potassium_from_earth_kg
        self.potassium_remaining = self.potassium_from_earth

        # Daily requirements (kg/day for 1805 m² crop area)
        self.nitrogen_requirement_kg_per_day = 2.0   # ~1.1 g/m²/day
        self.phosphorus_requirement_kg_per_day = 0.4  # ~0.2 g/m²/day
        self.potassium_requirement_kg_per_day = 1.5   # ~0.8 g/m²/day

        # History
        self.daily_nitrogen: List[float] = []
        self.daily_phosphorus: List[float] = []
        self.daily_potassium: List[float] = []

    def set_haber_bosch(self, reactor: HaberBoschReactor):
        """Set the Haber-Bosch reactor."""
        self.haber_bosch = reactor
        self.modules.add_module(reactor)

    def set_waste_processor(self, processor: WasteProcessor):
        """Set the waste processor."""
        self.waste_processor = processor
        self.modules.add_module(processor)

    def set_atmosphere_processor(self, processor: AtmosphereProcessor):
        """Set the atmosphere processor."""
        self.atmosphere_processor = processor
        self.modules.add_module(processor)

    def initialize_default_system(self):
        """Set up the default nutrient system from config."""
        # Create required stores first
        self._ensure_stores()

        # Atmosphere processor (feeds N2 to Haber-Bosch)
        atmo = AtmosphereProcessor("Atmosphere_Processor", self.stores)
        atmo.start()
        self.set_atmosphere_processor(atmo)

        # Haber-Bosch reactor
        haber = HaberBoschReactor("Haber_Bosch_Reactor", self.stores)
        haber.start()
        self.set_haber_bosch(haber)

        # Waste processor
        waste = WasteProcessor("Waste_Processor", self.stores)
        waste.start()
        self.set_waste_processor(waste)

        # Initialize potassium store with Earth supply
        k_store = self.stores.get("Nutrients_K")
        if k_store:
            k_store.add(self.potassium_from_earth)

        logger.info("Nutrient system initialized: Haber-Bosch + Waste Processing + Atmosphere")

    def _ensure_stores(self):
        """Ensure required nutrient stores exist."""
        required_stores = [
            ("Nutrients_N", ResourceType.NUTRIENTS_N, 500.0),
            ("Nutrients_P", ResourceType.NUTRIENTS_P, 200.0),
            ("Nutrients_K", ResourceType.NUTRIENTS_K, 300.0),
            ("Atmospheric_N2", ResourceType.NITROGEN, 100.0),
            ("CO2_Store", ResourceType.CO2, 500.0),
            ("Biogas", ResourceType.METHANE, 100.0),
            ("Human_Waste", ResourceType.HUMAN_WASTE, 50.0),
            ("Animal_Waste", ResourceType.ANIMAL_WASTE, 100.0),
            ("Crop_Waste", ResourceType.BIOMASS_INEDIBLE, 200.0),
        ]

        for name, rtype, capacity in required_stores:
            if not self.stores.get(name):
                store = Store(name, rtype, capacity, 0.0)
                self.stores.add_store(store)

    def get_nutrient_level(self, nutrient: NutrientType) -> float:
        """Get current level of a nutrient."""
        store_map = {
            NutrientType.NITROGEN: "Nutrients_N",
            NutrientType.PHOSPHORUS: "Nutrients_P",
            NutrientType.POTASSIUM: "Nutrients_K",
        }
        store = self.stores.get(store_map[nutrient])
        return store.current_level if store else 0.0

    def consume_nutrients(self, n_kg: float, p_kg: float, k_kg: float) -> Dict[str, float]:
        """
        Consume nutrients for crop growth.

        Returns actual amounts consumed.
        """
        consumed = {}

        n_store = self.stores.get("Nutrients_N")
        if n_store:
            consumed["nitrogen"] = n_store.remove(n_kg)

        p_store = self.stores.get("Nutrients_P")
        if p_store:
            consumed["phosphorus"] = p_store.remove(p_kg)

        k_store = self.stores.get("Nutrients_K")
        if k_store:
            consumed["potassium"] = k_store.remove(k_kg)

        return consumed

    def tick(self) -> NutrientState:
        """
        Execute one nutrient system tick.

        Updates state with current production rates and levels.
        """
        # Reset state
        self.state = NutrientState()

        # Get current nutrient levels
        self.state.nitrogen_store_kg = self.get_nutrient_level(NutrientType.NITROGEN)
        self.state.phosphorus_store_kg = self.get_nutrient_level(NutrientType.PHOSPHORUS)
        self.state.potassium_store_kg = self.get_nutrient_level(NutrientType.POTASSIUM)

        # Calculate production rates (extrapolate from tick to day)
        if self.haber_bosch and self.haber_bosch.is_operational:
            tick_rate = self.haber_bosch.ammonia_rate_per_tick * 0.82  # N content
            self.state.nitrogen_production_kg_per_day = tick_rate * 24

        if self.waste_processor and self.waste_processor.is_operational:
            # Get last tick's values
            self.state.waste_processed_kg_per_day = (
                self.waste_processor.total_waste_processed /
                max(1, self.waste_processor.ticks_operational) * 24
            )
            self.state.biogas_production_m3_per_day = (
                self.waste_processor.total_biogas_produced /
                max(1, self.waste_processor.ticks_operational) * 24
            )
            self.state.phosphorus_recovery_kg_per_day = (
                self.waste_processor.total_phosphorus_recovered /
                max(1, self.waste_processor.ticks_operational) * 24
            )

        # Calculate self-sufficiency
        if self.nitrogen_requirement_kg_per_day > 0:
            self.state.self_sufficiency_n = min(1.0,
                self.state.nitrogen_production_kg_per_day / self.nitrogen_requirement_kg_per_day
            )

        if self.phosphorus_requirement_kg_per_day > 0:
            self.state.self_sufficiency_p = min(1.0,
                self.state.phosphorus_recovery_kg_per_day / self.phosphorus_requirement_kg_per_day
            )

        # Update potassium tracking
        self.state.potassium_available_kg = self.state.potassium_store_kg

        return self.state

    def add_waste(self, human_kg: float = 0.0, animal_kg: float = 0.0, crop_kg: float = 0.0):
        """Add waste to processing stores."""
        if human_kg > 0:
            store = self.stores.get("Human_Waste")
            if store:
                store.add(human_kg)

        if animal_kg > 0:
            store = self.stores.get("Animal_Waste")
            if store:
                store.add(animal_kg)

        if crop_kg > 0:
            store = self.stores.get("Crop_Waste")
            if store:
                store.add(crop_kg)

    def get_days_of_supply(self) -> Dict[str, float]:
        """Calculate days of nutrient supply remaining."""
        return {
            "nitrogen": (self.state.nitrogen_store_kg / self.nitrogen_requirement_kg_per_day
                        if self.nitrogen_requirement_kg_per_day > 0 else float('inf')),
            "phosphorus": (self.state.phosphorus_store_kg / self.phosphorus_requirement_kg_per_day
                          if self.phosphorus_requirement_kg_per_day > 0 else float('inf')),
            "potassium": (self.state.potassium_store_kg / self.potassium_requirement_kg_per_day
                         if self.potassium_requirement_kg_per_day > 0 else float('inf')),
        }

    def get_status(self) -> Dict:
        """Get current nutrient system status."""
        days = self.get_days_of_supply()

        return {
            "nitrogen_store_kg": self.state.nitrogen_store_kg,
            "phosphorus_store_kg": self.state.phosphorus_store_kg,
            "potassium_store_kg": self.state.potassium_store_kg,
            "nitrogen_production_kg_per_day": self.state.nitrogen_production_kg_per_day,
            "phosphorus_recovery_kg_per_day": self.state.phosphorus_recovery_kg_per_day,
            "biogas_production_m3_per_day": self.state.biogas_production_m3_per_day,
            "waste_processed_kg_per_day": self.state.waste_processed_kg_per_day,
            "self_sufficiency_n": self.state.self_sufficiency_n,
            "self_sufficiency_p": self.state.self_sufficiency_p,
            "days_supply_n": days["nitrogen"],
            "days_supply_p": days["phosphorus"],
            "days_supply_k": days["potassium"],
            "haber_bosch_operational": self.haber_bosch.is_operational if self.haber_bosch else False,
            "waste_processor_operational": self.waste_processor.is_operational if self.waste_processor else False,
        }

    def handle_nutrient_shortage(self, nutrient: NutrientType):
        """Handle nutrient shortage situation."""
        logger.warning(f"Nutrient shortage: {nutrient.name}")

        if nutrient == NutrientType.NITROGEN:
            # Increase Haber-Bosch priority
            if self.haber_bosch:
                logger.info("Increasing Haber-Bosch production priority")

        elif nutrient == NutrientType.PHOSPHORUS:
            # Can't increase P production much - limited by waste
            logger.warning("Phosphorus shortage - reduce crop production or use Earth reserves")

        elif nutrient == NutrientType.POTASSIUM:
            # K is primarily Earth-supplied
            logger.warning("Potassium shortage - must use Earth reserves")
