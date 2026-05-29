"""
Main simulation runner.

Orchestrates the time-stepped energy market simulation, collecting
bids and offers from all participants, clearing the market, and
recording results.
"""

import random
from datetime import datetime, timedelta

from market.market import Market, MarketResult
from nodes.consumer import Consumer
from nodes.generator import Generator
from nodes.storage import BatteryStorage
from utils.time_utils import TimeContext


class SimulationResult:
    """Holds the full time-series results of a simulation run."""

    def __init__(self):
        self.timestamps: list[datetime] = []
        self.prices: list[float] = []
        self.total_supply: list[float] = []
        self.total_demand: list[float] = []
        self.unserved_demand: list[float] = []
        self.generator_outputs: dict[str, list[float]] = {}
        self.consumer_demands: dict[str, list[float]] = {}
        self.storage_socs: dict[str, list[float]] = {}
        self.storage_profits: dict[str, list[float]] = {}

    def record(
        self,
        dt: datetime,
        result: MarketResult,
        generators: list[Generator],
        consumers: list[Consumer],
        storages: list[BatteryStorage],
    ) -> None:
        """Record one time step."""
        self.timestamps.append(dt)
        self.prices.append(result.clearing_price)
        self.total_supply.append(result.total_supply_mw)
        self.total_demand.append(result.total_demand_mw)
        self.unserved_demand.append(result.unserved_demand_mw)

        for gen in generators:
            if gen.generator_id not in self.generator_outputs:
                self.generator_outputs[gen.generator_id] = []
            dispatched = result.generator_dispatch.get(gen.generator_id, 0.0)
            self.generator_outputs[gen.generator_id].append(dispatched)

        for con in consumers:
            if con.consumer_id not in self.consumer_demands:
                self.consumer_demands[con.consumer_id] = []
            allocated = result.consumer_allocation.get(con.consumer_id, 0.0)
            self.consumer_demands[con.consumer_id].append(allocated)

        for stor in storages:
            if stor.storage_id not in self.storage_socs:
                self.storage_socs[stor.storage_id] = []
                self.storage_profits[stor.storage_id] = []
            self.storage_socs[stor.storage_id].append(stor.soc)
            self.storage_profits[stor.storage_id].append(stor.profit)


class Simulation:
    """
    Energy market simulation.

    Runs a time-stepped market simulation over a configurable period
    with a collection of generators, storage units, and consumers.
    """

    def __init__(
        self,
        generators: list[Generator],
        storages: list[BatteryStorage],
        consumers: list[Consumer],
        market: Market | None = None,
        seed: int | None = None,
        price_ema_alpha: float = 0.3,  # Smoothing factor for expected price
    ):
        self.generators = generators
        self.storages = storages
        self.consumers = consumers
        self.market = market or Market()
        self.result = SimulationResult()
        self.price_ema_alpha = price_ema_alpha
        self._expected_price: float | None = None
        self._current: datetime | None = None
        self._ctx: TimeContext | None = None
        self._last_result: MarketResult | None = None

        if seed is not None:
            random.seed(seed)

    def run(
        self,
        start: datetime,
        end: datetime,
        step: timedelta = timedelta(hours=1),
        verbose: bool = False,
    ) -> SimulationResult:
        """
        Run the simulation from `start` to `end` with time steps of `step`.

        Returns a SimulationResult with the full time series.
        """
        current = start
        step_num = 0

        while current < end:
            ctx = TimeContext.from_datetime(current)

            # 1. Collect generator offers
            gen_offers = [g.get_offer(ctx) for g in self.generators]

            # 2. Estimate expected price (exponential moving average)
            if self._expected_price is None:
                self._expected_price = 50.0  # Initial guess
            if self.result.prices:
                self._expected_price = (
                    self.price_ema_alpha * self.result.prices[-1]
                    + (1 - self.price_ema_alpha) * self._expected_price
                )
            expected_price = self._expected_price

            # 3. Collect storage bids
            storage_bids = []
            for s in self.storages:
                storage_bids.extend(s.get_bids(ctx, expected_price))

            # 4. Collect consumer bids
            consumer_bids = []
            for c in self.consumers:
                consumer_bids.extend(c.get_bids(ctx))

            # 5. Clear the market
            market_result = self.market.clear(gen_offers, consumer_bids, storage_bids)

            # 6. Execute trades on storage
            for action in market_result.storage_actions:
                stor = next(
                    (s for s in self.storages if s.storage_id == action["storage_id"]),
                    None,
                )
                if stor:
                    if action["action"] == "charge":
                        stor.execute_charge(action["quantity_mw"], action["price"])
                    elif action["action"] == "discharge":
                        stor.execute_discharge(action["quantity_mw"], action["price"])

            # 7. Record consumption
            for con in self.consumers:
                allocated = market_result.consumer_allocation.get(con.consumer_id, 0.0)
                if allocated > 0:
                    con.record_consumption(allocated, market_result.clearing_price)
                elif market_result.unserved_demand_mw > 0:
                    # Check if this consumer had unserved demand
                    total_bid = sum(b.quantity_mw for b in con.get_bids(ctx))
                    if total_bid > 0 and allocated == 0:
                        con.record_blackout()

            # 8. Record results
            self.result.record(
                current, market_result, self.generators, self.consumers, self.storages
            )

            if verbose and step_num % 24 == 0:
                print(
                    f"  Day {step_num // 24 + 1}: "
                    f"price=${market_result.clearing_price:.1f}/MWh, "
                    f"supply={market_result.total_supply_mw:.0f}MW, "
                    f"demand={market_result.total_demand_mw:.0f}MW"
                )

            current += step
            step_num += 1

        return self.result

    def reset(self, start: datetime, end: datetime, step: timedelta = timedelta(hours=1)) -> None:
        """Re-initialize simulation to run from start to end."""
        self._expected_price = None
        self._current = start
        self._end = end
        self._step = step
        self._last_result = None
        self.result = SimulationResult()

    @property
    def total_steps(self) -> int:
        if self._current is None or self._end is None:
            return 0
        return int((self._end - self._current).total_seconds() / 3600)

    @property
    def completed_steps(self) -> int:
        return len(self.result.prices)

    @property
    def current_time(self) -> datetime | None:
        if self._current is None:
            return None
        return self._current - self._step + self._step

    @property
    def is_complete(self) -> bool:
        if self._current is None:
            return True
        return self._current >= self._end

    def step(self) -> MarketResult | None:
        """Run one time step. Returns MarketResult or None if done."""
        if self._current is None or self._end is None:
            return None
        if self._current >= self._end:
            return None

        ctx = TimeContext.from_datetime(self._current)
        self._ctx = ctx

        gen_offers = [g.get_offer(ctx) for g in self.generators]

        if self._expected_price is None:
            self._expected_price = 50.0
        if self.result.prices:
            self._expected_price = (
                self.price_ema_alpha * self.result.prices[-1]
                + (1 - self.price_ema_alpha) * self._expected_price
            )
        expected_price = self._expected_price

        storage_bids = []
        for s in self.storages:
            storage_bids.extend(s.get_bids(ctx, expected_price))

        consumer_bids = []
        for c in self.consumers:
            consumer_bids.extend(c.get_bids(ctx))

        market_result = self.market.clear(gen_offers, consumer_bids, storage_bids)
        self._last_result = market_result

        for action in market_result.storage_actions:
            stor = next(
                (s for s in self.storages if s.storage_id == action["storage_id"]),
                None,
            )
            if stor:
                if action["action"] == "charge":
                    stor.execute_charge(action["quantity_mw"], action["price"])
                elif action["action"] == "discharge":
                    stor.execute_discharge(action["quantity_mw"], action["price"])

        for con in self.consumers:
            allocated = market_result.consumer_allocation.get(con.consumer_id, 0.0)
            if allocated > 0:
                con.record_consumption(allocated, market_result.clearing_price)
            elif market_result.unserved_demand_mw > 0:
                total_bid = sum(b.quantity_mw for b in con.get_bids(ctx))
                if total_bid > 0 and allocated == 0:
                    con.record_blackout()

        self.result.record(
            self._current, market_result, self.generators, self.consumers, self.storages
        )

        self._current += self._step
        return market_result

    def print_summary(self) -> None:
        """Print a summary of the simulation results."""
        result = self.result
        if not result.prices:
            print("No simulation data.")
            return

        print("\n" + "=" * 60)
        print("ENERGY MARKET SIMULATION SUMMARY")
        print("=" * 60)

        print(f"\nTimesteps: {len(result.prices)}")
        print(f"Period: {result.timestamps[0]} to {result.timestamps[-1]}")

        print("\n--- Prices ---")
        print(f"  Average: ${sum(result.prices) / len(result.prices):.2f}/MWh")
        print(f"  Min:     ${min(result.prices):.2f}/MWh")
        print(f"  Max:     ${max(result.prices):.2f}/MWh")

        print("\n--- Supply & Demand ---")
        print(f"  Total supply:   {sum(result.total_supply):.0f} MWh")
        print(f"  Total demand:   {sum(result.total_demand):.0f} MWh")
        print(f"  Unserved:       {sum(result.unserved_demand):.0f} MWh")
        print(f"  Blackout hours: {sum(1 for u in result.unserved_demand if u > 0.1)}")

        print("\n--- Generators ---")
        for gen in self.generators:
            outputs = result.generator_outputs.get(gen.generator_id, [])
            revenue = sum(mw * price for mw, price in zip(outputs, result.prices))
            print(
                f"  {gen.generator_id}: "
                f"{sum(outputs):.0f} MWh produced, "
                f"${revenue:,.0f} revenue"
            )

        print("\n--- Consumers ---")
        for con in self.consumers:
            print(
                f"  {con.consumer_id} ({con.sector}): "
                f"{con.total_energy_consumed_mwh:.0f} MWh consumed, "
                f"${con.total_spent:,.0f} spent, "
                f"avg ${con.avg_price_paid:.2f}/MWh, "
                f"{con.blackout_hours}h blackouts"
            )

        print("\n--- Storage ---")
        for stor in self.storages:
            print(
                f"  {stor.storage_id}: "
                f"charged {stor.total_energy_charged_mwh:.0f} MWh, "
                f"discharged {stor.total_energy_discharged_mwh:.0f} MWh, "
                f"profit ${stor.profit:,.0f}, "
                f"final SoC {stor.soc:.1%}"
            )

        print("=" * 60)
