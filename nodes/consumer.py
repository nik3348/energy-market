"""
Consumer nodes that demand energy.

Consumers have a demand profile that varies by time, season, and holidays.
They also have price sensitivity — demand drops as prices rise, but some
portion of demand is inelastic (essential load that must be served).
"""

from dataclasses import dataclass

from utils.demand_profiles import DemandProfile
from utils.time_utils import TimeContext


@dataclass
class ConsumerBid:
    """A bid to buy energy from the market."""

    consumer_id: str
    quantity_mw: float  # Desired power (MW)
    max_price: float  # Maximum willingness to pay ($/MWh)


class Consumer:
    """
    An energy consumer with a time-varying demand profile.

    The consumer's willingness to pay decreases linearly with quantity:
    they'll pay more for essential needs and less for discretionary use.
    """

    def __init__(
        self,
        consumer_id: str,
        profile: DemandProfile,
        sector: str = "residential",  # residential, commercial, industrial
    ):
        self.consumer_id = consumer_id
        self.profile = profile
        self.sector = sector

        # Tracking
        self.total_energy_consumed_mwh: float = 0.0
        self.total_spent: float = 0.0
        self.blackout_hours: int = 0

    def get_bids(self, ctx: TimeContext) -> list[ConsumerBid]:
        """
        Build a stepped demand curve as a list of bids.

        We approximate the demand curve by breaking it into 3 tranches:
        - Essential (inelastic): will pay up to max_price
        - Core: will pay up to 2/3 max_price
        - Discretionary: will pay up to 1/3 max_price
        """
        multiplier = ctx.demand_multiplier
        base = self.profile.base_demand_mw * multiplier

        essential_frac = self.profile.min_demand_fraction
        core_frac = 0.3
        discretionary_frac = 1.0 - essential_frac - core_frac

        bids = []
        if base * essential_frac > 0:
            bids.append(
                ConsumerBid(
                    consumer_id=self.consumer_id,
                    quantity_mw=base * essential_frac,
                    max_price=self.profile.max_price,
                )
            )
        if base * core_frac > 0:
            bids.append(
                ConsumerBid(
                    consumer_id=self.consumer_id,
                    quantity_mw=base * core_frac,
                    max_price=self.profile.max_price * 0.5,
                )
            )
        if base * discretionary_frac > 0:
            bids.append(
                ConsumerBid(
                    consumer_id=self.consumer_id,
                    quantity_mw=base * discretionary_frac,
                    max_price=self.profile.max_price * 0.15,
                )
            )
        return bids

    def record_consumption(self, energy_mwh: float, avg_price: float) -> None:
        """Record energy consumed and cost."""
        self.total_energy_consumed_mwh += energy_mwh
        self.total_spent += energy_mwh * avg_price

    def record_blackout(self) -> None:
        """Record an hour where demand could not be met."""
        self.blackout_hours += 1

    @property
    def avg_price_paid(self) -> float:
        """Average price paid per MWh."""
        if self.total_energy_consumed_mwh == 0:
            return 0.0
        return self.total_spent / self.total_energy_consumed_mwh
