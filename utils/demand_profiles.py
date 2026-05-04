"""
Demand profile definitions for consumer nodes.

Demand profiles define how much energy a consumer wants at different
price points, modulated by temporal context.
"""

from dataclasses import dataclass


@dataclass
class DemandProfile:
    """
    Represents a consumer's demand curve.

    Attributes:
        base_demand_mw: Baseline power demand in MW (before temporal modulation).
        price_sensitivity: How much demand drops as price rises (MW per $/MWh).
        max_price: Maximum price the consumer is willing to pay ($/MWh).
        min_demand_fraction: Minimum demand as a fraction of base (inelastic portion).
    """

    base_demand_mw: float
    price_sensitivity: float = 0.5
    max_price: float = 500.0
    min_demand_fraction: float = 0.3

    def demand_at_price(self, price: float, multiplier: float = 1.0) -> float:
        """
        Calculate demand in MW at a given price, with an optional temporal multiplier.

        Linear demand curve: demand = base * multiplier - sensitivity * price,
        bounded between min_demand and base.
        """
        modulated_base = self.base_demand_mw * multiplier
        raw = modulated_base - self.price_sensitivity * price
        minimum = modulated_base * self.min_demand_fraction
        return max(minimum, min(modulated_base, raw))
