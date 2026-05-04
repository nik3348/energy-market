"""
Generator nodes that produce and sell energy into the market.

Each generator type has a different production profile and marginal cost structure.
"""

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from utils.time_utils import Season, TimeContext


@dataclass
class GeneratorOffer:
    """A price-quantity offer from a generator to the market."""

    generator_id: str
    quantity_mw: float  # How much power is available (MW)
    marginal_cost: float  # Minimum price the generator will accept ($/MWh)


class Generator(ABC):
    """Abstract base class for all energy generators."""

    def __init__(
        self, generator_id: str, capacity_mw: float, marginal_cost_base: float
    ):
        self.generator_id = generator_id
        self.capacity_mw = capacity_mw
        self.marginal_cost_base = marginal_cost_base  # $/MWh baseline

    @abstractmethod
    def available_capacity(self, ctx: TimeContext) -> float:
        """How much power (MW) this generator can produce right now."""
        ...

    def marginal_cost(self, ctx: TimeContext) -> float:
        """Marginal cost of production ($/MWh). Override for time-varying costs."""
        return self.marginal_cost_base

    def get_offer(self, ctx: TimeContext) -> GeneratorOffer:
        """Build a market offer for the current time step."""
        available = self.available_capacity(ctx)
        cost = self.marginal_cost(ctx)
        return GeneratorOffer(
            generator_id=self.generator_id,
            quantity_mw=available,
            marginal_cost=cost,
        )


class SolarGenerator(Generator):
    """
    Solar PV generator.

    Production follows a bell curve peaking at solar noon (~12:00),
    zero at night, and scales with season (more in summer, less in winter).
    Cloud cover is simulated with random noise.
    """

    def __init__(
        self,
        generator_id: str,
        capacity_mw: float,
        marginal_cost_base: float = 5.0,  # Very cheap — no fuel
        cloudiness: float = 0.2,  # Random reduction factor
    ):
        super().__init__(generator_id, capacity_mw, marginal_cost_base)
        self.cloudiness = cloudiness

    def available_capacity(self, ctx: TimeContext) -> float:
        hour = ctx.hour
        # Solar production: Gaussian centered at noon, width ~4 hours
        solar_factor = math.exp(-0.5 * ((hour - 12) / 4) ** 2)

        # Night time: essentially zero
        if hour < 6 or hour > 20:
            solar_factor *= 0.05  # Minimal diffuse light

        # Seasonal adjustment
        season_mult = {
            Season.SUMMER: 1.0,
            Season.SPRING: 0.75,
            Season.AUTUMN: 0.65,
            Season.WINTER: 0.40,
        }[ctx.season]

        # Random cloud cover
        cloud_factor = 1.0 - random.uniform(0, self.cloudiness)

        return self.capacity_mw * solar_factor * season_mult * cloud_factor


class WindGenerator(Generator):
    """
    Wind turbine generator.

    Production is stochastic with some seasonal and diurnal patterns.
    Wind tends to be stronger at night and in transition seasons.
    """

    def __init__(
        self,
        generator_id: str,
        capacity_mw: float,
        marginal_cost_base: float = 3.0,  # Very cheap — no fuel
        volatility: float = 0.35,
    ):
        super().__init__(generator_id, capacity_mw, marginal_cost_base)
        self.volatility = volatility
        self._prev_wind: float | None = None

    def available_capacity(self, ctx: TimeContext) -> float:
        # Base wind pattern: stronger at night and in spring/autumn
        hour_factor = 1.0 - 0.3 * math.exp(-0.5 * ((ctx.hour - 12) / 6) ** 2)
        # Actually wind is often stronger during daytime in some regions,
        # but we'll model it as slightly stronger at night for variety

        season_mult = {
            Season.SPRING: 1.0,
            Season.AUTUMN: 0.95,
            Season.WINTER: 0.85,
            Season.SUMMER: 0.60,
        }[ctx.season]

        # Mean-reverting random walk for wind speed
        if self._prev_wind is None:
            self._prev_wind = random.uniform(0.3, 0.8)

        mean_reversion = 0.5 * (0.5 - self._prev_wind)
        shock = random.gauss(0, self.volatility)
        wind = max(0.05, min(1.0, self._prev_wind + mean_reversion + shock))
        self._prev_wind = wind

        return self.capacity_mw * wind * hour_factor * season_mult


class ThermalGenerator(Generator):
    """
    Dispatchable thermal generator (gas, coal, nuclear).

    Always available at full capacity (minus random outages).
    Has a fuel-based marginal cost that can vary seasonally.
    """

    def __init__(
        self,
        generator_id: str,
        capacity_mw: float,
        marginal_cost_base: float = 50.0,
        forced_outage_rate: float = 0.03,  # 3% chance of being offline
    ):
        super().__init__(generator_id, capacity_mw, marginal_cost_base)
        self.forced_outage_rate = forced_outage_rate
        self._outage: bool = False

    def available_capacity(self, ctx: TimeContext) -> float:
        # Random forced outages
        if random.random() < self.forced_outage_rate:
            self._outage = True
        elif random.random() < 0.3:  # 30% chance of recovering each hour
            self._outage = False

        if self._outage:
            return 0.0
        return self.capacity_mw

    def marginal_cost(self, ctx: TimeContext) -> float:
        # Fuel costs can vary seasonally (e.g., natural gas more expensive in winter)
        season_mult = {
            Season.WINTER: 1.25,
            Season.SUMMER: 1.05,
            Season.SPRING: 0.90,
            Season.AUTUMN: 0.95,
        }[ctx.season]
        return self.marginal_cost_base * season_mult
