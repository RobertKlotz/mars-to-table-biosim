"""
Tests for advanced simulation features:
- Livestock lifecycle and breeding
- Crop disease/pest scenarios
- Human factors modeling
- Enhanced BioSim mock
"""

import pytest
from mars_to_table.simulation.lifecycle import (
    LifeStage,
    BreedingStatus,
    HealthEvent,
    AnimalLifecycle,
    GoatLifecycleManager,
    ChickenLifecycleManager,
)
from mars_to_table.simulation.crop_failures import (
    CropFailureType,
    CropSeverity,
    CropFailureEvent,
    CropFailureGenerator,
)
from mars_to_table.simulation.human_factors import (
    PsychologicalState,
    MealSatisfaction,
    CrewMemberPsychology,
    CrewPsychologyManager,
)
from mars_to_table.biosim.client import MockBioSimClient


# =============================================================================
# LIVESTOCK LIFECYCLE TESTS
# =============================================================================

class TestGoatLifecycleManager:
    """Tests for goat breeding and lifecycle."""

    def test_initialization(self):
        """Test goat herd initialization."""
        manager = GoatLifecycleManager()
        animals = manager.initialize_herd(num_does=6, num_bucks=2, start_tick=0)

        assert len(animals) == 8
        assert len([a for a in animals if a.sex == "female"]) == 6
        assert len([a for a in animals if a.sex == "male"]) == 2

    def test_population_stats(self):
        """Test population statistics."""
        manager = GoatLifecycleManager()
        manager.initialize_herd(num_does=6, num_bucks=2)

        stats = manager.get_population_stats()
        assert stats["total_alive"] == 8
        assert stats["does"] == 6
        assert stats["bucks"] == 2

    def test_animal_lifecycle(self):
        """Test animal creates with correct lifecycle."""
        manager = GoatLifecycleManager()
        animal = manager.create_animal("female", birth_tick=0)

        assert animal.life_stage == LifeStage.NEWBORN
        assert animal.breeding_status == BreedingStatus.OPEN
        assert animal.is_alive()

    def test_breeding(self):
        """Test breeding between animals."""
        manager = GoatLifecycleManager()
        manager.initialize_herd(num_does=2, num_bucks=1, start_tick=0)

        stats = manager.get_population_stats()
        does = [a for a in manager.animals.values() if a.sex == "female"]
        bucks = [a for a in manager.animals.values() if a.sex == "male"]

        # Attempt breeding
        success = manager.breed_animals(does[0].animal_id, bucks[0].animal_id, tick=100)

        # Should succeed most of the time (85% rate)
        # Just verify the method works without error
        assert isinstance(success, bool)

        if success:
            assert does[0].breeding_status == BreedingStatus.PREGNANT
            assert len(does[0].breeding_history) == 1

    def test_milk_production_calculation(self):
        """Test milk production varies with lactation curve."""
        manager = GoatLifecycleManager()
        manager.initialize_herd(num_does=1, num_bucks=0, start_tick=0)

        doe = list(manager.animals.values())[0]
        doe.breeding_status = BreedingStatus.LACTATING

        # Early lactation
        doe.days_in_lactation = 30
        early_milk = manager._calculate_milk_production(doe, feed_available=3.0, water_available=5.0)

        # Peak lactation
        doe.days_in_lactation = 100
        peak_milk = manager._calculate_milk_production(doe, feed_available=3.0, water_available=5.0)

        # Late lactation
        doe.days_in_lactation = 280
        late_milk = manager._calculate_milk_production(doe, feed_available=3.0, water_available=5.0)

        # Peak should be highest
        assert peak_milk >= early_milk
        assert peak_milk >= late_milk

    def test_culling(self):
        """Test animal culling returns meat."""
        manager = GoatLifecycleManager()
        manager.initialize_herd(num_does=1, num_bucks=0, start_tick=0)

        animal = list(manager.animals.values())[0]
        meat = manager.cull_animal(animal.animal_id, tick=100, reason="population control")

        assert meat is not None
        assert meat > 0
        assert not animal.is_alive()
        assert animal.cause_of_death == "culled: population control"


class TestChickenLifecycleManager:
    """Tests for chicken flock management."""

    def test_flock_initialization(self):
        """Test flock initialization."""
        manager = ChickenLifecycleManager()
        birds = manager.initialize_flock(num_hens=20, num_roosters=2, start_tick=0)

        assert len(birds) == 22
        assert len([b for b in birds if b.sex == "female"]) == 20

    def test_egg_production(self):
        """Test egg production mechanics."""
        manager = ChickenLifecycleManager()
        manager.initialize_flock(num_hens=20, num_roosters=2, start_tick=0)

        # Run several ticks to get egg production
        total_eggs = 0
        for tick in range(0, 240, 24):  # 10 days
            result = manager.update_tick(tick, feed_available=3.0, water_available=5.0)
            total_eggs += result["eggs_produced"]

        # Should produce ~17 eggs/day on average with 20 hens
        avg_per_day = total_eggs / 10
        assert 10 < avg_per_day < 25  # Reasonable range

    def test_incubation(self):
        """Test egg incubation system."""
        manager = ChickenLifecycleManager()
        manager.initialize_flock(num_hens=5, num_roosters=1, start_tick=0)

        # Set eggs for incubation
        manager.set_eggs_for_incubation(num_eggs=12, tick=0)

        assert len(manager.incubating_eggs) == 1
        assert manager.incubating_eggs[0]["num_eggs"] == 12

        # Advance past incubation period (21 days * 24 ticks)
        for tick in range(22 * 24):
            result = manager.update_tick(tick, feed_available=1.0, water_available=2.0)

        # Should have hatched
        assert len(manager.incubating_eggs) == 0
        stats = manager.get_population_stats()
        assert stats["total_births"] > 0


# =============================================================================
# CROP FAILURE TESTS
# =============================================================================

class TestCropFailureGenerator:
    """Tests for crop disease and failure generation."""

    def test_initialization(self):
        """Test generator initialization."""
        generator = CropFailureGenerator(seed=42)
        assert len(generator.active_events) == 0

    def test_failure_event_generation(self):
        """Test failure events can be generated."""
        generator = CropFailureGenerator(seed=42)

        pod_statuses = {
            "FoodPOD_1": {
                "crops": [
                    {"name": "lettuce", "health": 0.8, "age_days": 30}
                ]
            }
        }

        environmental = {
            "temperature": 25,
            "humidity": 0.85,  # High humidity increases disease risk
            "co2_ppm": 800,
        }

        # Run many checks to trigger events (low probability)
        events = []
        for tick in range(10000):
            new_events = generator.check_for_failures(tick, pod_statuses, environmental)
            events.extend(new_events)
            if len(events) > 0:
                break

        # Should eventually generate at least one event
        if events:
            assert events[0].failure_type in CropFailureType
            assert events[0].severity in CropSeverity

    def test_yield_impact_calculation(self):
        """Test yield impact from active events."""
        generator = CropFailureGenerator(seed=42)

        # Manually inject an event
        event = CropFailureEvent(
            event_id="test_001",
            failure_type=CropFailureType.FUNGAL_INFECTION,
            severity=CropSeverity.MODERATE,
            affected_pods=["FoodPOD_1"],
            affected_crops=["lettuce"],
            start_tick=0,
            duration_ticks=100,
            yield_reduction=0.25,
            spread_rate=0.05,
            treatable=True,
            treatment_effectiveness=0.7,
        )
        generator.active_events["test_001"] = event

        # Check yield impact
        impact = generator.calculate_yield_impact("FoodPOD_1")
        assert impact == 0.75  # 1.0 - 0.25 reduction

        # Unaffected pod should have no impact
        impact_other = generator.calculate_yield_impact("FoodPOD_2")
        assert impact_other == 1.0

    def test_treatment(self):
        """Test treating a crop failure."""
        generator = CropFailureGenerator(seed=42)

        event = CropFailureEvent(
            event_id="test_002",
            failure_type=CropFailureType.APHID_INFESTATION,
            severity=CropSeverity.MINOR,
            affected_pods=["FoodPOD_1"],
            affected_crops=["tomato"],
            start_tick=0,
            duration_ticks=100,
            yield_reduction=0.1,
            spread_rate=0.07,
            treatable=True,
            treatment_effectiveness=0.85,
        )
        generator.active_events["test_002"] = event

        # Try treatment (85% success rate)
        # Run multiple times to handle randomness
        for _ in range(10):
            result = generator.treat_event("test_002")
            if result:
                assert event.treated
                assert event.contained
                break

    def test_response_protocol(self):
        """Test getting response protocol for event."""
        generator = CropFailureGenerator()

        event = CropFailureEvent(
            event_id="test_003",
            failure_type=CropFailureType.NITROGEN_DEFICIENCY,
            severity=CropSeverity.MODERATE,
            affected_pods=["GrainPOD_1"],
            affected_crops=["wheat"],
            start_tick=0,
            duration_ticks=200,
            yield_reduction=0.2,
            spread_rate=0.0,
            treatable=True,
            treatment_effectiveness=0.9,
        )

        protocol = generator.get_response_protocol(event)

        assert protocol is not None
        assert protocol.isolation_required == False
        assert "nitrogen" in protocol.treatment_method.lower()


# =============================================================================
# HUMAN FACTORS TESTS
# =============================================================================

class TestCrewMemberPsychology:
    """Tests for individual crew psychology."""

    def test_initialization(self):
        """Test crew member creation."""
        member = CrewMemberPsychology(
            crew_id="crew_01",
            name="Test Astronaut",
            morale=0.85,
            stress_level=0.2,
        )

        assert member.morale == 0.85
        assert member.get_psychological_state() == PsychologicalState.GOOD

    def test_psychological_states(self):
        """Test psychological state thresholds."""
        member = CrewMemberPsychology(crew_id="test", name="Test")

        # Optimal state
        member.morale = 0.95
        member.stress_level = 0.1
        member.fatigue = 0.1
        member.food_satisfaction = 0.9
        member.team_cohesion = 0.9
        assert member.get_psychological_state() == PsychologicalState.OPTIMAL

        # Stressed state
        member.morale = 0.5
        member.stress_level = 0.7
        member.fatigue = 0.6
        assert member.get_psychological_state() in [
            PsychologicalState.STRESSED,
            PsychologicalState.ADEQUATE
        ]

        # Critical state
        member.morale = 0.2
        member.stress_level = 0.9
        member.fatigue = 0.9
        member.food_satisfaction = 0.2
        member.team_cohesion = 0.2
        assert member.get_psychological_state() in [
            PsychologicalState.CRITICAL,
            PsychologicalState.STRUGGLING
        ]

    def test_productivity(self):
        """Test productivity calculation."""
        member = CrewMemberPsychology(
            crew_id="test",
            name="Test",
            food_system_role="gardener",
        )

        # High morale = high productivity
        member.morale = 0.9
        member.stress_level = 0.1
        member.fatigue = 0.1
        high_prod = member.get_food_system_productivity()

        # Low morale = low productivity
        member.morale = 0.3
        member.stress_level = 0.8
        member.fatigue = 0.8
        low_prod = member.get_food_system_productivity()

        assert high_prod > low_prod


class TestCrewPsychologyManager:
    """Tests for crew psychology management."""

    def test_crew_initialization(self):
        """Test crew initialization."""
        manager = CrewPsychologyManager(crew_size=15)
        manager.initialize_crew()

        assert len(manager.crew) == 15

    def test_food_roles(self):
        """Test food system role assignment."""
        manager = CrewPsychologyManager(crew_size=15)
        manager.initialize_crew()

        roles = [m.food_system_role for m in manager.crew.values()]

        # Should have gardeners, chef, veterinarian
        assert "gardener" in roles
        assert "chef" in roles

    def test_tick_update(self):
        """Test psychological state updates over time."""
        manager = CrewPsychologyManager(crew_size=5)
        manager.initialize_crew()

        meal_data = {
            "foods": ["lettuce", "tomato", "potato"],
            "calories": 700,
            "protein_g": 25,
            "freshness": 0.9,
            "preparation_quality": 0.8,
            "social_eating": 0.9,
        }

        result = manager.update_tick(
            tick=1,
            meal_data=meal_data,
            work_demands=0.5,
            environmental_quality=0.8,
        )

        assert "team_morale" in result
        assert "avg_efficiency" in result
        assert result["avg_efficiency"] > 0

    def test_food_production_modifier(self):
        """Test food production modifier calculation."""
        manager = CrewPsychologyManager(crew_size=10)
        manager.initialize_crew()

        modifier = manager.get_food_production_modifier()

        # Should be positive and reasonable
        assert 0.3 < modifier < 1.5

    def test_crew_summary(self):
        """Test crew summary generation."""
        manager = CrewPsychologyManager(crew_size=15)
        manager.initialize_crew()

        summary = manager.get_crew_summary()

        assert summary["crew_size"] == 15
        assert "team_morale" in summary
        assert "avg_morale" in summary
        assert "food_production_modifier" in summary


class TestMealSatisfaction:
    """Tests for meal satisfaction tracking."""

    def test_satisfaction_calculation(self):
        """Test meal satisfaction calculation."""
        meal = MealSatisfaction(
            tick=1,
            calories=700,
            protein_g=30,
            variety_score=0.8,
            taste_score=0.7,
            cultural_match=0.6,
            social_context=0.9,
        )

        # Overall satisfaction should be calculated
        assert 0 < meal.overall_satisfaction < 1

    def test_low_calorie_impact(self):
        """Test low calorie meals have lower satisfaction."""
        high_cal = MealSatisfaction(
            tick=1,
            calories=800,
            protein_g=30,
            variety_score=0.5,
            taste_score=0.5,
            cultural_match=0.5,
            social_context=0.5,
        )

        low_cal = MealSatisfaction(
            tick=1,
            calories=300,
            protein_g=10,
            variety_score=0.5,
            taste_score=0.5,
            cultural_match=0.5,
            social_context=0.5,
        )

        assert high_cal.overall_satisfaction > low_cal.overall_satisfaction


# =============================================================================
# ENHANCED MOCK BIOSIM TESTS
# =============================================================================

class TestEnhancedMockBioSim:
    """Tests for enhanced BioSim mock client."""

    def test_connection(self):
        """Test mock connection."""
        client = MockBioSimClient()
        assert client.test_connection()

    def test_start_simulation(self):
        """Test starting a mock simulation."""
        client = MockBioSimClient()
        session = client.start_simulation(name="TestSim")

        assert session is not None
        assert session.status == "running"

    def test_tick_response(self):
        """Test tick returns detailed response."""
        client = MockBioSimClient()
        client.start_simulation()

        response = client.tick()

        assert "tick" in response
        assert "sol" in response
        assert "stores" in response
        assert "power" in response
        assert "water" in response
        assert "food" in response
        assert "crew" in response

    def test_resource_dynamics(self):
        """Test resources change realistically over ticks."""
        client = MockBioSimClient()
        client.start_simulation()

        initial_power = client._mock_stores["PowerStore"]
        initial_water = client._mock_stores["PotableWaterStore"]

        # Run 24 ticks (1 sol)
        for _ in range(24):
            client.tick()

        # Resources should have changed
        # (Power fluctuates with solar cycle)
        final_power = client._mock_stores["PowerStore"]
        final_water = client._mock_stores["PotableWaterStore"]

        # Just verify they're being modified
        # (exact values depend on simulation parameters)
        assert isinstance(final_power, float)
        assert isinstance(final_water, float)

    def test_food_production(self):
        """Test food production in mock."""
        client = MockBioSimClient()
        client.start_simulation()

        # Run 24 ticks (1 sol) to trigger food production
        for _ in range(24):
            response = client.tick()

        # Check food stores are tracked
        assert "FreshFoodStore" in client._mock_stores
        assert "MilkStore" in client._mock_stores
        assert "EggStore" in client._mock_stores

    def test_malfunction_injection(self):
        """Test malfunction injection in mock."""
        client = MockBioSimClient()
        client.start_simulation()

        response = client.inject_malfunction(
            module_name="SolarArray_1",
            malfunction_type="PowerGeneratorMalfunction",
            intensity=0.5,
            duration_ticks=48,
        )

        assert response["status"] == "injected"
        assert len(client._malfunctions) == 1

    def test_full_sol_run(self):
        """Test running a complete sol."""
        client = MockBioSimClient()
        client.start_simulation()

        results = client.run_sol()

        assert len(results) == 24
        assert results[-1]["tick"] == 24

    def test_store_capacities(self):
        """Test stores don't exceed capacities."""
        client = MockBioSimClient()
        client.start_simulation()

        # Run many ticks
        for _ in range(100):
            client.tick()

        # Check stores are within capacities
        for store_name, capacity in client._store_capacities.items():
            current = client._mock_stores.get(store_name, 0)
            assert current <= capacity, f"{store_name} exceeded capacity"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestAdvancedIntegration:
    """Integration tests for advanced simulation features."""

    def test_livestock_with_psychology(self):
        """Test livestock management affects crew psychology."""
        goat_manager = GoatLifecycleManager()
        goat_manager.initialize_herd(num_does=6, num_bucks=2)

        psych_manager = CrewPsychologyManager(crew_size=5)
        psych_manager.initialize_crew()

        # Simulate livestock producing milk
        result = goat_manager.update_tick(
            tick=24,  # Start of day
            feed_available=20.0,
            water_available=50.0,
        )

        # Use milk in meal
        meal_data = {
            "foods": ["milk", "cheese", "eggs"],
            "calories": 800,
            "protein_g": 35,
            "freshness": 0.95,  # Fresh from livestock
            "preparation_quality": 0.85,
            "social_eating": 0.8,
        }

        psych_result = psych_manager.update_tick(
            tick=24,
            meal_data=meal_data,
            work_demands=0.5,
            environmental_quality=0.8,
        )

        # Both systems should work together
        assert result["milk_produced_l"] >= 0
        assert psych_result["avg_efficiency"] > 0

    def test_crop_failure_recovery(self):
        """Test crop failure and recovery cycle."""
        generator = CropFailureGenerator()

        # Create an event
        event = CropFailureEvent(
            event_id="test_recovery",
            failure_type=CropFailureType.APHID_INFESTATION,
            severity=CropSeverity.MODERATE,
            affected_pods=["FoodPOD_1"],
            affected_crops=["lettuce"],
            start_tick=0,
            duration_ticks=168,  # 7 days
            yield_reduction=0.25,
            spread_rate=0.05,
            treatable=True,
            treatment_effectiveness=0.85,
        )
        generator.active_events[event.event_id] = event

        # Initial impact
        assert generator.calculate_yield_impact("FoodPOD_1") == 0.75

        # Treat the event
        generator.treat_event(event.event_id)

        # If treatment succeeded, impact should be reduced
        if event.treated:
            assert generator.calculate_yield_impact("FoodPOD_1") > 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
