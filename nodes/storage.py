"""
Battery storage nodes that buy low and sell high.

Storage acts as both a consumer (when charging) and a generator (when discharging).
Key dynamics: capacity, charge/discharge efficiency, max power rating, and
strategy for when to charge vs discharge.
"""

from dataclasses import dataclass

from utils.time_utils import TimeContext


@dataclass
class StorageBid:
    """A bid to buy energy (charge) or offer to sell energy (discharge)."""

    storage_id: str
    action: str  # "charge" or "discharge"
    quantity_mw: float
    price: float  # Bid price for charging, ask price for discharging ($/MWh)


class BatteryStorage:
    """
    A battery energy storage system (BESS).

    The battery's strategy:
    - Charges when the market price is below its 'buy threshold'
    - Discharges when the market price is above its 'sell threshold'
    - The thresholds adapt based on current state of charge (SoC):
      * When nearly empty, it's more eager to buy
      * When nearly full, it's more eager to sell

    Round-trip efficiency means that buying 1 MWh only yields `efficiency` MWh
    available for discharge. This creates a natural spread between buy/sell prices.
    """

    def __init__(
        self,
        storage_id: str,
        capacity_mwh: float,  # Total energy capacity (MWh)
        power_mw: float,  # Max charge/discharge rate (MW)
        efficiency: float = 0.90,  # Round-trip efficiency (0-1)
        initial_soc: float = 0.5,  # Initial state of charge (0-1)
        buy_threshold: float = 40.0,  # $/MWh — charge when price below this
        sell_threshold: float = 80.0,  # $/MWh — discharge when price above this
        soc_margin: float = 0.15,  # How much SoC affects thresholds
    ):
        self.storage_id = storage_id
        self.capacity_mwh = capacity_mwh
        self.power_mw = power_mw
        self.efficiency = efficiency
        self.soc = initial_soc  # State of charge, 0-1
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.soc_margin = soc_margin

        # Tracking
        self.total_energy_charged_mwh: float = 0.0
        self.total_energy_discharged_mwh: float = 0.0
        self.total_revenue: float = 0.0
        self.total_cost: float = 0.0

    @property
    def energy_stored_mwh(self) -> float:
        """Current energy stored in MWh."""
        return self.soc * self.capacity_mwh

    @property
    def available_charge_capacity_mw(self) -> float:
        """How much power we can still absorb (MW)."""
        energy_headroom = self.capacity_mwh - self.energy_stored_mwh
        power_headroom = energy_headroom  # over 1 hour: MW = MWh
        return min(self.power_mw, power_headroom)

    @property
    def available_discharge_capacity_mw(self) -> float:
        """How much power we can deliver (MW)."""
        return min(self.power_mw, self.energy_stored_mwh)

    def _adaptive_buy_threshold(self, expected_price: float) -> float:
        """
        Adjust buy threshold based on SoC.
        When SoC is low, raise the threshold (more willing to buy at higher prices).
        When SoC is high, lower the threshold (only buy if very cheap).
        """
        soc_effect = (0.5 - self.soc) * self.soc_margin * expected_price
        return self.buy_threshold + soc_effect

    def _adaptive_sell_threshold(self, expected_price: float) -> float:
        """
        Adjust sell threshold based on SoC.
        When SoC is high, lower the threshold (more willing to sell).
        When SoC is low, raise the threshold (only sell if very expensive).
        The efficiency spread means we need to sell at a higher price than we bought.
        """
        soc_effect = (self.soc - 0.5) * self.soc_margin * expected_price
        return self.sell_threshold - soc_effect

    def get_bids(self, ctx: TimeContext, expected_price: float) -> list[StorageBid]:
        """
        Determine what the storage wants to do this time step.

        Returns a list with 0, 1, or 2 bids (can't charge and discharge simultaneously
        in a single market clearing, but we submit intent for both and the market
        will determine which is profitable).
        """
        bids: list[StorageBid] = []

        buy_at = self._adaptive_buy_threshold(expected_price)
        sell_at = self._adaptive_sell_threshold(expected_price)

        # Efficiency-adjusted sell price: we need to recover the buy price / efficiency
        # If we bought at $40/MWh with 90% efficiency, effective cost is $44.44/MWh
        effective_sell_min = buy_at / self.efficiency
        sell_at = max(sell_at, effective_sell_min)

        # Charge bid: willing to buy up to available capacity at buy_threshold
        charge_qty = self.available_charge_capacity_mw
        if charge_qty > 0.01:
            bids.append(
                StorageBid(
                    storage_id=self.storage_id,
                    action="charge",
                    quantity_mw=charge_qty,
                    price=buy_at,
                )
            )

        # Discharge offer: willing to sell at sell_threshold
        discharge_qty = self.available_discharge_capacity_mw
        if discharge_qty > 0.01:
            bids.append(
                StorageBid(
                    storage_id=self.storage_id,
                    action="discharge",
                    quantity_mw=discharge_qty,
                    price=sell_at,
                )
            )

        return bids

    def execute_charge(self, energy_mwh: float, price: float) -> None:
        """Record a charge action: buy energy_mwh at price $/MWh."""
        # Apply efficiency loss
        stored = energy_mwh * self.efficiency
        self.soc = min(1.0, self.soc + stored / self.capacity_mwh)
        cost = energy_mwh * price
        self.total_energy_charged_mwh += energy_mwh
        self.total_cost += cost

    def execute_discharge(self, energy_mwh: float, price: float) -> None:
        """Record a discharge action: sell energy_mwh at price $/MWh."""
        # We discharge exactly what was requested (already within limits)
        self.soc = max(0.0, self.soc - energy_mwh / self.capacity_mwh)
        revenue = energy_mwh * price
        self.total_energy_discharged_mwh += energy_mwh
        self.total_revenue += revenue

    @property
    def profit(self) -> float:
        """Total profit from trading."""
        return self.total_revenue - self.total_cost

    @property
    def round_trip_efficiency_realized(self) -> float:
        """Actual round-trip efficiency observed."""
        if self.total_energy_charged_mwh == 0:
            return 0.0
        return self.total_energy_discharged_mwh / self.total_energy_charged_mwh
