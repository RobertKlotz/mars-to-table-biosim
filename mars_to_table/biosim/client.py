"""
Mars to Table — BioSim REST Client
HTTP client for communicating with NASA BioSim simulation server.

BioSim API Endpoints:
- POST /api/simulation/start          - Start simulation with XML config
- POST /api/simulation/{simID}/tick   - Advance one tick
- GET  /api/simulation/{simID}        - Get current state
- POST /api/simulation/{simID}/modules/{name}/malfunctions - Inject failures
- DELETE /api/simulation/{simID}      - End simulation

Reference: https://github.com/scottbell/biosim
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum, auto
import json
import logging
import time
from urllib.parse import urljoin

# Use standard library for HTTP to avoid external dependencies
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .xml_generator import BioSimXMLGenerator
from ..simulation.events import BioSimEventAdapter

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ConnectionError(Exception):
    """Failed to connect to BioSim server."""
    pass


class SimulationError(Exception):
    """Error during simulation execution."""
    pass


class AuthenticationError(Exception):
    """Authentication with BioSim server failed."""
    pass


# =============================================================================
# BIOSIM SESSION
# =============================================================================

@dataclass
class BioSimSession:
    """
    Represents an active BioSim simulation session.

    Tracks simulation ID, state, and provides methods for interaction.
    """
    simulation_id: str
    name: str = ""
    status: str = "created"

    # Simulation state
    current_tick: int = 0
    current_sol: int = 0

    # Server info
    server_url: str = ""

    # Tracking
    start_time: float = field(default_factory=time.time)
    tick_history: List[Dict] = field(default_factory=list)
    events_injected: List[Dict] = field(default_factory=list)

    def elapsed_time(self) -> float:
        """Get elapsed real time in seconds."""
        return time.time() - self.start_time

    def get_summary(self) -> Dict:
        """Get session summary."""
        return {
            "simulation_id": self.simulation_id,
            "name": self.name,
            "status": self.status,
            "current_tick": self.current_tick,
            "current_sol": self.current_sol,
            "elapsed_time_s": self.elapsed_time(),
            "ticks_recorded": len(self.tick_history),
            "events_injected": len(self.events_injected),
        }


# =============================================================================
# BIOSIM CLIENT
# =============================================================================

class BioSimClient:
    """
    REST client for NASA BioSim simulation server.

    Provides:
    - Connection management
    - Simulation lifecycle (start, tick, stop)
    - State querying
    - Malfunction injection
    - Event translation from our format to BioSim format
    """

    # Default BioSim server configuration
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 8080
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: int = DEFAULT_TIMEOUT,
        api_key: Optional[str] = None,
    ):
        """
        Initialize BioSim client.

        Args:
            host: BioSim server hostname
            port: BioSim server port
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.api_key = api_key

        self.base_url = f"http://{host}:{port}"
        self.active_session: Optional[BioSimSession] = None

        # Event adapter for translating malfunctions
        self.event_adapter = BioSimEventAdapter()

        # Callbacks
        self.on_tick_complete: Optional[Callable] = None
        self.on_event_received: Optional[Callable] = None
        self.on_simulation_end: Optional[Callable] = None

        logger.info(f"BioSim client initialized for {self.base_url}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        content_type: str = "application/json",
    ) -> Dict:
        """
        Make HTTP request to BioSim server.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Request body data
            content_type: Content type header

        Returns:
            Response data as dictionary

        Raises:
            ConnectionError: If server is unreachable
            SimulationError: If request fails
        """
        url = urljoin(self.base_url, endpoint)

        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = None
        if data:
            if content_type == "application/json":
                body = json.dumps(data).encode('utf-8')
            elif content_type == "application/xml":
                body = data.encode('utf-8') if isinstance(data, str) else str(data).encode('utf-8')

        try:
            request = Request(url, data=body, headers=headers, method=method)
            response = urlopen(request, timeout=self.timeout)
            response_data = response.read().decode('utf-8')

            if response_data:
                return json.loads(response_data)
            return {}

        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            logger.error(f"HTTP {e.code} from BioSim: {error_body}")
            raise SimulationError(f"BioSim request failed: {e.code} {e.reason}")

        except URLError as e:
            logger.error(f"Failed to connect to BioSim: {e.reason}")
            raise ConnectionError(f"Cannot connect to BioSim server at {url}: {e.reason}")

        except Exception as e:
            logger.error(f"Request error: {e}")
            raise SimulationError(f"Request failed: {e}")

    def test_connection(self) -> bool:
        """
        Test connection to BioSim server.

        Returns:
            True if server is reachable and responding
        """
        try:
            response = self._make_request("GET", "/api/health")
            return response.get("status") == "ok"
        except (ConnectionError, SimulationError):
            return False

    def get_server_info(self) -> Dict:
        """Get BioSim server information."""
        return self._make_request("GET", "/api/info")

    # =========================================================================
    # SIMULATION LIFECYCLE
    # =========================================================================

    def start_simulation(
        self,
        xml_config: Optional[str] = None,
        name: str = "MarsToTable",
    ) -> BioSimSession:
        """
        Start a new simulation on the BioSim server.

        Args:
            xml_config: XML configuration string (generates default if None)
            name: Simulation name for identification

        Returns:
            BioSimSession object for the new simulation
        """
        if self.active_session and self.active_session.status == "running":
            logger.warning("Stopping existing simulation before starting new one")
            self.stop_simulation()

        # Generate default config if not provided
        if xml_config is None:
            generator = BioSimXMLGenerator()
            xml_config = generator.generate_xml()

        # Start simulation
        response = self._make_request(
            "POST",
            "/api/simulation/start",
            data=xml_config,
            content_type="application/xml",
        )

        sim_id = response.get("simulationId", response.get("simId", "unknown"))

        self.active_session = BioSimSession(
            simulation_id=sim_id,
            name=name,
            status="running",
            server_url=self.base_url,
        )

        logger.info(f"Started BioSim simulation: {sim_id}")
        return self.active_session

    def tick(self) -> Dict:
        """
        Advance simulation by one tick.

        Returns:
            Tick result data from BioSim

        Raises:
            SimulationError: If no active simulation or tick fails
        """
        if not self.active_session:
            raise SimulationError("No active simulation")

        sim_id = self.active_session.simulation_id
        response = self._make_request(
            "POST",
            f"/api/simulation/{sim_id}/tick",
        )

        # Update session state
        self.active_session.current_tick = response.get("tick", self.active_session.current_tick + 1)
        self.active_session.current_sol = self.active_session.current_tick // 24

        # Record history
        self.active_session.tick_history.append({
            "tick": self.active_session.current_tick,
            "timestamp": time.time(),
            "response": response,
        })

        # Check for events/malfunctions from server
        if "malfunctions" in response:
            for malfunction in response["malfunctions"]:
                self._handle_malfunction(malfunction)

        # Callback
        if self.on_tick_complete:
            self.on_tick_complete(response)

        return response

    def run_ticks(self, count: int, delay: float = 0.0) -> List[Dict]:
        """
        Run multiple ticks.

        Args:
            count: Number of ticks to run
            delay: Delay between ticks in seconds (for pacing)

        Returns:
            List of tick results
        """
        results = []

        for i in range(count):
            result = self.tick()
            results.append(result)

            if delay > 0 and i < count - 1:
                time.sleep(delay)

        return results

    def run_sol(self, delay: float = 0.0) -> List[Dict]:
        """Run one complete sol (24 ticks)."""
        return self.run_ticks(24, delay)

    def get_state(self) -> Dict:
        """
        Get current simulation state.

        Returns:
            Complete state from BioSim server
        """
        if not self.active_session:
            raise SimulationError("No active simulation")

        sim_id = self.active_session.simulation_id
        return self._make_request("GET", f"/api/simulation/{sim_id}")

    def get_module_state(self, module_name: str) -> Dict:
        """Get state of a specific module."""
        if not self.active_session:
            raise SimulationError("No active simulation")

        sim_id = self.active_session.simulation_id
        return self._make_request(
            "GET",
            f"/api/simulation/{sim_id}/modules/{module_name}",
        )

    def get_store_state(self, store_name: str) -> Dict:
        """Get state of a specific store."""
        if not self.active_session:
            raise SimulationError("No active simulation")

        sim_id = self.active_session.simulation_id
        return self._make_request(
            "GET",
            f"/api/simulation/{sim_id}/stores/{store_name}",
        )

    def stop_simulation(self) -> Dict:
        """
        Stop the active simulation.

        Returns:
            Final simulation state/summary
        """
        if not self.active_session:
            return {}

        sim_id = self.active_session.simulation_id

        try:
            response = self._make_request(
                "DELETE",
                f"/api/simulation/{sim_id}",
            )
        except SimulationError:
            response = {}

        self.active_session.status = "stopped"

        if self.on_simulation_end:
            self.on_simulation_end(self.active_session.get_summary())

        logger.info(f"Stopped BioSim simulation: {sim_id}")

        final_session = self.active_session
        self.active_session = None

        return {
            "session": final_session.get_summary(),
            "response": response,
        }

    # =========================================================================
    # MALFUNCTION INJECTION
    # =========================================================================

    def inject_malfunction(
        self,
        module_name: str,
        malfunction_type: str,
        intensity: float = 1.0,
        duration_ticks: int = 24,
    ) -> Dict:
        """
        Inject a malfunction into a module.

        Args:
            module_name: Name of the module to affect
            malfunction_type: Type of malfunction (BioSim malfunction type)
            intensity: Malfunction intensity (0.0 to 1.0)
            duration_ticks: Duration in ticks

        Returns:
            Response from BioSim
        """
        if not self.active_session:
            raise SimulationError("No active simulation")

        sim_id = self.active_session.simulation_id

        response = self._make_request(
            "POST",
            f"/api/simulation/{sim_id}/modules/{module_name}/malfunctions",
            data={
                "type": malfunction_type,
                "intensity": intensity,
                "durationTicks": duration_ticks,
            },
        )

        # Record event
        self.active_session.events_injected.append({
            "tick": self.active_session.current_tick,
            "module": module_name,
            "type": malfunction_type,
            "intensity": intensity,
            "duration": duration_ticks,
        })

        # Translate to our event system
        self.event_adapter.inject_biosim_malfunction(
            malfunction_type=malfunction_type,
            module_name=module_name,
            intensity=intensity,
            tick_length=duration_ticks,
            current_tick=self.active_session.current_tick,
        )

        logger.info(f"Injected malfunction: {malfunction_type} on {module_name}")
        return response

    def inject_power_failure(
        self,
        severity: float = 1.0,
        duration_ticks: int = 24,
    ) -> Dict:
        """Inject power generation failure."""
        return self.inject_malfunction(
            module_name="SolarArray",
            malfunction_type="PowerGeneratorMalfunction",
            intensity=severity,
            duration_ticks=duration_ticks,
        )

    def inject_water_failure(
        self,
        rsv_pod: int = 1,
        duration_ticks: int = 24,
    ) -> Dict:
        """Inject water extraction failure."""
        return self.inject_malfunction(
            module_name=f"RSV_Extractor_{rsv_pod}",
            malfunction_type="WaterRSMalfunction",
            intensity=1.0,
            duration_ticks=duration_ticks,
        )

    def inject_food_production_failure(
        self,
        pod_number: int = 1,
        severity: float = 0.5,
        duration_ticks: int = 48,
    ) -> Dict:
        """Inject food production failure."""
        return self.inject_malfunction(
            module_name=f"FoodPOD_{pod_number}",
            malfunction_type="FoodProcessorMalfunction",
            intensity=severity,
            duration_ticks=duration_ticks,
        )

    def _handle_malfunction(self, malfunction: Dict):
        """Handle malfunction received from BioSim server."""
        if self.on_event_received:
            self.on_event_received(malfunction)

        # Translate to our event format
        event = self.event_adapter.inject_biosim_malfunction(
            malfunction_type=malfunction.get("type", "Unknown"),
            module_name=malfunction.get("module", "Unknown"),
            intensity=malfunction.get("intensity", 1.0),
            tick_length=malfunction.get("duration", 24),
            current_tick=self.active_session.current_tick if self.active_session else 0,
        )

        logger.warning(f"Received malfunction from BioSim: {malfunction}")

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def run_full_simulation(
        self,
        xml_config: Optional[str] = None,
        name: str = "MarsToTable",
        progress_callback: Optional[Callable] = None,
        sol_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        Run complete 500-sol simulation.

        Args:
            xml_config: XML configuration (generates default if None)
            name: Simulation name
            progress_callback: Called every tick with (tick, total_ticks)
            sol_callback: Called at end of each sol with sol summary

        Returns:
            Final simulation results
        """
        total_ticks = 500 * 24  # 500 sols * 24 ticks/sol

        self.start_simulation(xml_config, name)

        try:
            for tick in range(total_ticks):
                result = self.tick()

                if progress_callback:
                    progress_callback(tick, total_ticks)

                # End of sol
                if (tick + 1) % 24 == 0:
                    sol = (tick + 1) // 24
                    if sol_callback:
                        sol_callback(sol, self.get_state())

                    # Log progress
                    if sol % 50 == 0:
                        logger.info(f"Simulation progress: Sol {sol}/500")

        except KeyboardInterrupt:
            logger.warning("Simulation interrupted by user")

        return self.stop_simulation()

    def export_session_log(self, filepath: str):
        """Export session history to JSON file."""
        if not self.active_session:
            logger.warning("No active session to export")
            return

        with open(filepath, 'w') as f:
            json.dump({
                "session": self.active_session.get_summary(),
                "tick_history": self.active_session.tick_history,
                "events": self.active_session.events_injected,
            }, f, indent=2)

        logger.info(f"Session log exported to {filepath}")


# =============================================================================
# MOCK CLIENT FOR TESTING
# =============================================================================

class MockBioSimClient(BioSimClient):
    """
    Mock BioSim client for testing without a server.

    High-fidelity simulation of BioSim responses including:
    - Realistic resource consumption curves
    - Crew metabolism and activity cycles
    - Crop growth stages and yields
    - Environmental control dynamics
    - Malfunction effects on systems
    """

    def __init__(self):
        super().__init__()
        self._mock_tick = 0
        self._malfunctions = []

        # Initialize realistic store levels
        self._mock_stores = {
            # Power (kWh)
            "PowerStore": 5000.0,
            "BiogasStore": 200.0,  # m³

            # Water (L)
            "PotableWaterStore": 15000.0,
            "GreyWaterStore": 2000.0,
            "BlackWaterStore": 500.0,

            # Atmosphere (mol)
            "O2Store": 50000.0,
            "CO2Store": 2000.0,
            "N2Store": 200000.0,

            # Food (kg)
            "FreshFoodStore": 800.0,
            "DriedFoodStore": 2000.0,
            "MilkStore": 50.0,
            "EggStore": 30.0,
            "CheeseStore": 20.0,
            "MeatStore": 100.0,

            # Nutrients (kg)
            "NitrogenStore": 500.0,
            "PhosphorusStore": 200.0,
            "PotassiumStore": 300.0,

            # Waste
            "SolidWasteStore": 100.0,
            "FodderStore": 300.0,
        }

        # Store capacities
        self._store_capacities = {
            "PowerStore": 10000.0,
            "PotableWaterStore": 30000.0,
            "FreshFoodStore": 2000.0,
            "DriedFoodStore": 5000.0,
            "O2Store": 100000.0,
        }

        # Module states
        self._modules = {
            "SolarArray_1": {"power_output_kw": 100.0, "efficiency": 0.95, "status": "nominal"},
            "SolarArray_2": {"power_output_kw": 100.0, "efficiency": 0.95, "status": "nominal"},
            "FuelCell_1": {"power_output_kw": 50.0, "efficiency": 0.60, "status": "standby"},
            "RSV_Extractor_1": {"extraction_rate_l_hr": 100.0, "status": "nominal"},
            "RSV_Extractor_2": {"extraction_rate_l_hr": 100.0, "status": "nominal"},
            "HVAC_Main": {"status": "nominal", "power_draw_kw": 15.0},
        }

        # Crop growth tracking (kg biomass per POD)
        self._crop_growth = {
            "FoodPOD_1": {"crop": "lettuce", "biomass_kg": 50.0, "growth_rate": 0.02, "stage": "mature"},
            "FoodPOD_2": {"crop": "tomato", "biomass_kg": 100.0, "growth_rate": 0.015, "stage": "flowering"},
            "FoodPOD_3": {"crop": "potato", "biomass_kg": 150.0, "growth_rate": 0.018, "stage": "vegetative"},
            "GrainPOD_1": {"crop": "wheat", "biomass_kg": 200.0, "growth_rate": 0.012, "stage": "grain_fill"},
            "GrainPOD_2": {"crop": "rice", "biomass_kg": 180.0, "growth_rate": 0.011, "stage": "vegetative"},
        }

        # Crew metabolism (15 crew members)
        self._crew = {
            "count": 15,
            "avg_metabolism_kj_hr": 350,  # ~8400 kJ/day = 2000 kcal
            "water_consumption_l_hr": 0.125,  # 3L/day
            "o2_consumption_mol_hr": 1.0,
            "co2_production_mol_hr": 0.8,
        }

        # Livestock tracking
        self._livestock = {
            "goats": {"count": 8, "milk_production_l_day": 8.0, "feed_consumption_kg_day": 16.0},
            "chickens": {"count": 22, "egg_production_day": 17, "feed_consumption_kg_day": 2.6},
        }

        # Environmental conditions
        self._environment = {
            "temperature_c": 22.0,
            "humidity_pct": 55.0,
            "co2_ppm": 800,
            "pressure_kpa": 101.3,
        }

    def test_connection(self) -> bool:
        return True

    def _make_request(self, method: str, endpoint: str, data: Any = None, **kwargs) -> Dict:
        """Mock server responses with high-fidelity simulation."""
        import math
        import random

        # Start simulation
        if endpoint == "/api/simulation/start":
            return {"simulationId": f"mock-{int(time.time())}"}

        # Tick - main simulation loop
        if "/tick" in endpoint:
            self._mock_tick += 1
            return self._simulate_tick()

        # Get state
        if method == "GET" and "/simulation/" in endpoint:
            return self._get_full_state()

        # Stop
        if method == "DELETE":
            return {"status": "stopped", "finalTick": self._mock_tick}

        # Malfunction injection
        if "/malfunctions" in endpoint and data:
            self._inject_malfunction_internal(data)
            return {"status": "injected", "tick": self._mock_tick}

        # Health check
        if endpoint == "/api/health":
            return {"status": "ok"}

        return {}

    def _simulate_tick(self) -> Dict:
        """Simulate one tick with realistic resource dynamics."""
        import math
        import random

        hour_of_day = self._mock_tick % 24
        sol = self._mock_tick // 24

        # === POWER DYNAMICS ===
        # Solar varies with Mars day (simplified sinusoidal)
        solar_factor = max(0, math.sin(math.pi * hour_of_day / 24))

        total_solar = 0
        for name, mod in self._modules.items():
            if "SolarArray" in name and mod["status"] == "nominal":
                output = mod["power_output_kw"] * mod["efficiency"] * solar_factor
                # Add dust degradation (0.1% per sol)
                dust_factor = max(0.7, 1.0 - (sol * 0.001))
                output *= dust_factor
                total_solar += output

        # Base power consumption (varies with activity)
        activity_factor = 1.0 + 0.3 * math.sin(2 * math.pi * (hour_of_day - 8) / 24)
        power_consumption = 80 * activity_factor  # Base ~80 kW

        # Apply malfunctions
        for malf in self._malfunctions:
            if malf["module"] == "SolarArray":
                total_solar *= (1 - malf["intensity"])

        power_delta = total_solar - power_consumption
        self._mock_stores["PowerStore"] = max(0, min(
            self._store_capacities.get("PowerStore", 10000),
            self._mock_stores["PowerStore"] + power_delta
        ))

        # === WATER DYNAMICS ===
        # RSV extraction
        water_extracted = 0
        for name, mod in self._modules.items():
            if "RSV_Extractor" in name and mod["status"] == "nominal":
                water_extracted += mod["extraction_rate_l_hr"]

        # Crew water consumption
        crew_water = self._crew["count"] * self._crew["water_consumption_l_hr"]

        # Crop water (varies by growth stage)
        crop_water = 0
        for pod, data in self._crop_growth.items():
            base_rate = 2.0  # L/hr base
            if data["stage"] in ["flowering", "fruiting"]:
                base_rate *= 1.5
            crop_water += base_rate

        # Livestock water
        livestock_water = (self._livestock["goats"]["count"] * 0.17 +
                          self._livestock["chickens"]["count"] * 0.01)

        water_delta = water_extracted - crew_water - crop_water - livestock_water
        self._mock_stores["PotableWaterStore"] = max(0, min(
            self._store_capacities.get("PotableWaterStore", 30000),
            self._mock_stores["PotableWaterStore"] + water_delta
        ))

        # === ATMOSPHERE DYNAMICS ===
        # O2 production from crops (photosynthesis during "day")
        o2_production = 0
        if solar_factor > 0.1:
            for pod, data in self._crop_growth.items():
                o2_production += data["biomass_kg"] * 0.001 * solar_factor

        # O2 consumption (crew + livestock)
        o2_consumption = (self._crew["count"] * self._crew["o2_consumption_mol_hr"] +
                         self._livestock["goats"]["count"] * 0.5 +
                         self._livestock["chickens"]["count"] * 0.05)

        self._mock_stores["O2Store"] += o2_production - o2_consumption

        # CO2 dynamics (inverse of O2)
        co2_production = (self._crew["count"] * self._crew["co2_production_mol_hr"] +
                         self._livestock["goats"]["count"] * 0.4 +
                         self._livestock["chickens"]["count"] * 0.04)
        co2_consumption = o2_production * 0.8  # Photosynthesis
        self._mock_stores["CO2Store"] += co2_production - co2_consumption

        # Update environmental CO2 ppm
        self._environment["co2_ppm"] = 400 + (self._mock_stores["CO2Store"] / 100)

        # === FOOD PRODUCTION ===
        # Crop growth (daily harvest at hour 6)
        if hour_of_day == 6:
            for pod, data in self._crop_growth.items():
                if data["stage"] == "mature":
                    # Harvest
                    harvest_kg = data["biomass_kg"] * 0.1  # 10% daily harvest
                    self._mock_stores["FreshFoodStore"] = min(
                        self._store_capacities.get("FreshFoodStore", 2000),
                        self._mock_stores["FreshFoodStore"] + harvest_kg
                    )
                # Growth
                data["biomass_kg"] += data["growth_rate"] * data["biomass_kg"]

        # Livestock production (daily at hour 8)
        if hour_of_day == 8:
            # Milk
            milk = self._livestock["goats"]["milk_production_l_day"]
            self._mock_stores["MilkStore"] = min(100, self._mock_stores["MilkStore"] + milk * 0.7)
            self._mock_stores["CheeseStore"] = min(50, self._mock_stores["CheeseStore"] + milk * 0.03)  # 30% to cheese

            # Eggs
            eggs = self._livestock["chickens"]["egg_production_day"]
            self._mock_stores["EggStore"] = min(60, self._mock_stores["EggStore"] + eggs * 0.05)  # ~50g/egg

        # === FOOD CONSUMPTION ===
        # Crew eats 3 meals/day (hours 7, 12, 18)
        if hour_of_day in [7, 12, 18]:
            meal_size_kg = 0.8  # ~800g per meal per person
            total_food = self._crew["count"] * meal_size_kg

            # Consume from various stores
            fresh = min(total_food * 0.4, self._mock_stores["FreshFoodStore"])
            self._mock_stores["FreshFoodStore"] -= fresh

            dried = min(total_food * 0.3, self._mock_stores["DriedFoodStore"])
            self._mock_stores["DriedFoodStore"] -= dried

            dairy = min(total_food * 0.15, self._mock_stores["MilkStore"] + self._mock_stores["CheeseStore"])
            self._mock_stores["MilkStore"] = max(0, self._mock_stores["MilkStore"] - dairy * 0.7)
            self._mock_stores["CheeseStore"] = max(0, self._mock_stores["CheeseStore"] - dairy * 0.3)

        # === WASTE PRODUCTION ===
        waste_rate = self._crew["count"] * 0.02  # ~0.5 kg/person/day
        self._mock_stores["SolidWasteStore"] += waste_rate

        # === MALFUNCTION DECAY ===
        self._malfunctions = [m for m in self._malfunctions if m["end_tick"] > self._mock_tick]

        # === RANDOM EVENTS (low probability) ===
        events = []
        if random.random() < 0.0005:  # ~0.05% per tick
            event_types = ["dust_storm", "equipment_degradation", "solar_flare"]
            events.append({
                "type": random.choice(event_types),
                "tick": self._mock_tick,
                "severity": random.uniform(0.1, 0.3),
            })

        return {
            "tick": self._mock_tick,
            "sol": sol,
            "hour": hour_of_day,
            "status": "ok",
            "stores": dict(self._mock_stores),
            "environment": dict(self._environment),
            "power": {
                "solar_output_kw": total_solar,
                "consumption_kw": power_consumption,
                "battery_level_kwh": self._mock_stores["PowerStore"],
            },
            "water": {
                "extraction_rate_l_hr": water_extracted,
                "consumption_rate_l_hr": crew_water + crop_water + livestock_water,
                "reservoir_level_l": self._mock_stores["PotableWaterStore"],
            },
            "food": {
                "fresh_food_kg": self._mock_stores["FreshFoodStore"],
                "dried_food_kg": self._mock_stores["DriedFoodStore"],
                "dairy_kg": self._mock_stores["MilkStore"] + self._mock_stores["CheeseStore"],
            },
            "crew": {
                "count": self._crew["count"],
                "calorie_consumption_kcal": self._crew["count"] * 2000 / 24,
            },
            "events": events,
            "active_malfunctions": len(self._malfunctions),
        }

    def _get_full_state(self) -> Dict:
        """Get complete simulation state."""
        return {
            "tick": self._mock_tick,
            "sol": self._mock_tick // 24,
            "stores": dict(self._mock_stores),
            "modules": dict(self._modules),
            "environment": dict(self._environment),
            "crops": dict(self._crop_growth),
            "livestock": dict(self._livestock),
            "crew": dict(self._crew),
            "malfunctions": self._malfunctions,
        }

    def _inject_malfunction_internal(self, data: Dict):
        """Inject a malfunction into the mock simulation."""
        module = data.get("module", "Unknown")
        intensity = data.get("intensity", 1.0)
        duration = data.get("durationTicks", 24)

        self._malfunctions.append({
            "module": module,
            "type": data.get("type", "Generic"),
            "intensity": intensity,
            "start_tick": self._mock_tick,
            "end_tick": self._mock_tick + duration,
        })

        # Apply immediate effect
        if module in self._modules:
            if intensity >= 0.8:
                self._modules[module]["status"] = "failed"
            elif intensity >= 0.4:
                self._modules[module]["status"] = "degraded"

        logger.info(f"Mock: Injected {data.get('type')} on {module} (intensity={intensity})")
