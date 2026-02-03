"""
Mars to Table — Store Class
Tracks resource storage with capacity, levels, and flow rates.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Callable
from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources tracked in the simulation."""
    # Gases
    OXYGEN = auto()
    CO2 = auto()
    NITROGEN = auto()
    HYDROGEN = auto()
    METHANE = auto()  # Biogas
    
    # Liquids
    POTABLE_WATER = auto()
    GREY_WATER = auto()
    WASTE_WATER = auto()
    MILK = auto()
    
    # Solids - Food
    BIOMASS_EDIBLE = auto()  # General edible plant matter
    POTATOES = auto()
    VEGETABLES = auto()
    LEGUMES = auto()
    GRAIN_FLOUR = auto()
    FODDER = auto()
    EGGS = auto()
    CHEESE = auto()
    MEAT = auto()
    EARTH_FOOD = auto()  # Pre-packaged from Earth
    
    # Solids - Other
    BIOMASS_INEDIBLE = auto()  # Crop waste
    HUMAN_WASTE = auto()
    ANIMAL_WASTE = auto()
    NUTRIENTS_N = auto()
    NUTRIENTS_P = auto()
    NUTRIENTS_K = auto()
    
    # Energy
    ELECTRICAL_POWER = auto()  # kWh
    THERMAL_ENERGY = auto()
    
    # Abstract
    CALORIES = auto()  # kcal for food tracking


@dataclass
class Store:
    """
    A resource store that tracks capacity, current level, and flow.
    
    Supports:
    - Capacity limits with overflow handling
    - Reserve levels (emergency buffer)
    - Flow tracking (in/out per tick)
    - Callbacks for low/empty/full states
    """
    
    name: str
    resource_type: ResourceType
    capacity: float
    current_level: float = 0.0
    reserve_level: float = 0.0  # Emergency minimum
    
    # Flow tracking (reset each tick)
    inflow_this_tick: float = 0.0
    outflow_this_tick: float = 0.0
    overflow_this_tick: float = 0.0
    shortfall_this_tick: float = 0.0
    
    # Historical tracking
    total_inflow: float = 0.0
    total_outflow: float = 0.0
    total_overflow: float = 0.0
    total_shortfall: float = 0.0
    
    # Callbacks
    on_empty: Optional[Callable] = None
    on_low: Optional[Callable] = None  # Below reserve
    on_full: Optional[Callable] = None
    
    def __post_init__(self):
        """Validate initial state."""
        if self.current_level > self.capacity:
            logger.warning(f"{self.name}: Initial level {self.current_level} exceeds capacity {self.capacity}")
            self.current_level = self.capacity
        if self.reserve_level > self.capacity:
            logger.warning(f"{self.name}: Reserve {self.reserve_level} exceeds capacity {self.capacity}")
            self.reserve_level = self.capacity * 0.1
    
    @property
    def available(self) -> float:
        """Amount available above reserve."""
        return max(0.0, self.current_level - self.reserve_level)
    
    @property
    def available_including_reserve(self) -> float:
        """Total amount available (including reserve for emergencies)."""
        return self.current_level
    
    @property
    def free_capacity(self) -> float:
        """Space available for storage."""
        return self.capacity - self.current_level
    
    @property
    def fill_fraction(self) -> float:
        """Current level as fraction of capacity."""
        if self.capacity == 0:
            return 0.0
        return self.current_level / self.capacity
    
    @property
    def is_empty(self) -> bool:
        return self.current_level <= 0.0
    
    @property
    def is_low(self) -> bool:
        return self.current_level <= self.reserve_level
    
    @property
    def is_full(self) -> bool:
        return self.current_level >= self.capacity
    
    def add(self, amount: float) -> float:
        """
        Add resource to store.
        
        Returns:
            Amount actually added (may be less if capacity exceeded).
        """
        if amount < 0:
            raise ValueError(f"Cannot add negative amount: {amount}")
        
        space = self.free_capacity
        actual_add = min(amount, space)
        overflow = amount - actual_add
        
        self.current_level += actual_add
        self.inflow_this_tick += actual_add
        self.total_inflow += actual_add
        
        if overflow > 0:
            self.overflow_this_tick += overflow
            self.total_overflow += overflow
            logger.debug(f"{self.name}: Overflow {overflow:.2f} (capacity reached)")
        
        if self.is_full and self.on_full:
            self.on_full(self)
        
        return actual_add
    
    def remove(self, amount: float, allow_reserve: bool = False) -> float:
        """
        Remove resource from store.
        
        Args:
            amount: Amount requested
            allow_reserve: If True, can draw from reserve; if False, stops at reserve level
            
        Returns:
            Amount actually removed (may be less if insufficient).
        """
        if amount < 0:
            raise ValueError(f"Cannot remove negative amount: {amount}")
        
        if allow_reserve:
            available = self.current_level
        else:
            available = self.available
        
        actual_remove = min(amount, available)
        shortfall = amount - actual_remove
        
        self.current_level -= actual_remove
        self.outflow_this_tick += actual_remove
        self.total_outflow += actual_remove
        
        if shortfall > 0:
            self.shortfall_this_tick += shortfall
            self.total_shortfall += shortfall
            logger.debug(f"{self.name}: Shortfall {shortfall:.2f} (insufficient supply)")
        
        # Check callbacks
        if self.is_empty and self.on_empty:
            self.on_empty(self)
        elif self.is_low and self.on_low:
            self.on_low(self)
        
        return actual_remove
    
    def transfer_to(self, target: 'Store', amount: float, allow_reserve: bool = False) -> float:
        """
        Transfer resource to another store.
        
        Returns:
            Amount actually transferred.
        """
        removed = self.remove(amount, allow_reserve)
        added = target.add(removed)
        
        # If target couldn't accept all, return excess to source
        excess = removed - added
        if excess > 0:
            self.add(excess)
            return added
        
        return removed
    
    def reset_tick_counters(self):
        """Reset per-tick flow counters (call at start of each tick)."""
        self.inflow_this_tick = 0.0
        self.outflow_this_tick = 0.0
        self.overflow_this_tick = 0.0
        self.shortfall_this_tick = 0.0
    
    def get_status(self) -> dict:
        """Get current status as dictionary."""
        return {
            "name": self.name,
            "resource_type": self.resource_type.name,
            "current_level": self.current_level,
            "capacity": self.capacity,
            "fill_fraction": self.fill_fraction,
            "reserve_level": self.reserve_level,
            "available": self.available,
            "is_low": self.is_low,
            "is_empty": self.is_empty,
            "inflow_this_tick": self.inflow_this_tick,
            "outflow_this_tick": self.outflow_this_tick,
            "shortfall_this_tick": self.shortfall_this_tick,
        }
    
    def __repr__(self) -> str:
        return f"Store({self.name}: {self.current_level:.1f}/{self.capacity:.1f} {self.resource_type.name})"


class StoreManager:
    """
    Manages multiple stores and provides convenient access.
    """
    
    def __init__(self):
        self.stores: dict[str, Store] = {}
        self._by_type: dict[ResourceType, List[Store]] = {}
    
    def add_store(self, store: Store):
        """Register a store."""
        self.stores[store.name] = store
        
        if store.resource_type not in self._by_type:
            self._by_type[store.resource_type] = []
        self._by_type[store.resource_type].append(store)
    
    def get(self, name: str) -> Optional[Store]:
        """Get store by name."""
        return self.stores.get(name)
    
    def get_by_type(self, resource_type: ResourceType) -> List[Store]:
        """Get all stores of a given type."""
        return self._by_type.get(resource_type, [])
    
    def total_level(self, resource_type: ResourceType) -> float:
        """Get total current level across all stores of a type."""
        return sum(s.current_level for s in self.get_by_type(resource_type))
    
    def total_capacity(self, resource_type: ResourceType) -> float:
        """Get total capacity across all stores of a type."""
        return sum(s.capacity for s in self.get_by_type(resource_type))
    
    def reset_all_tick_counters(self):
        """Reset tick counters on all stores."""
        for store in self.stores.values():
            store.reset_tick_counters()
    
    def get_all_status(self) -> dict:
        """Get status of all stores."""
        return {name: store.get_status() for name, store in self.stores.items()}
    
    def get_low_stores(self) -> List[Store]:
        """Get all stores that are below reserve level."""
        return [s for s in self.stores.values() if s.is_low]
    
    def get_empty_stores(self) -> List[Store]:
        """Get all stores that are empty."""
        return [s for s in self.stores.values() if s.is_empty]
