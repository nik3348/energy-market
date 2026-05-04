"""
Market clearing engine.

Collects bids and offers from all participants, then finds the equilibrium
price and quantity where supply meets demand.

Uses a merit-order dispatch: generators are stacked from cheapest to most
expensive, and the clearing price is set by the marginal unit.
"""

from dataclasses import dataclass

from nodes.consumer import ConsumerBid
from nodes.generator import GeneratorOffer
from nodes.storage import StorageBid


@dataclass
class MarketResult:
    """Result of a single market clearing."""

    clearing_price: float  # $/MWh — uniform price all participants pay/receive
    total_supply_mw: float  # Total supply dispatched (MW)
    total_demand_mw: float  # Total demand served (MW)
    unserved_demand_mw: float  # Demand that could not be met (MW)
    generator_dispatch: dict[str, float]  # generator_id -> dispatched MW
    consumer_allocation: dict[str, float]  # consumer_id -> allocated MW
    storage_actions: list[dict]  # Details of storage charge/discharge

    @property
    def price(self) -> float:
        """Alias for clearing_price."""
        return self.clearing_price

    @property
    def surplus_mw(self) -> float:
        """Excess supply that went unused."""
        return max(0, self.total_supply_mw - self.total_demand_mw)


@dataclass
class _SortableSell:
    """Internal: a sell order sorted by price."""

    source_id: str
    source_type: str  # "generator" or "storage"
    quantity_mw: float
    price: float


@dataclass
class _SortableBuy:
    """Internal: a buy order sorted by price (descending)."""

    source_id: str
    source_type: str  # "consumer" or "storage"
    quantity_mw: float
    price: float
    consumer_id_for_tracking: str = ""  # original consumer for demand tracking


class Market:
    """
    Uniform-price energy market with merit-order dispatch.

    The market collects all offers (sells) and bids (buys), sorts them by price,
    and finds the intersection point. Storage units can participate on both sides
    but cannot charge and discharge simultaneously.
    """

    def __init__(self, price_cap: float = 1000.0):
        self.price_cap = price_cap

    def clear(
        self,
        generator_offers: list[GeneratorOffer],
        consumer_bids: list[ConsumerBid],
        storage_bids: list[StorageBid],
    ) -> MarketResult:
        """
        Clear the market for one time step.

        Algorithm:
        1. Build sell stack: generators (by marginal cost) + storage discharge (by ask)
        2. Build buy stack: consumers (by max price, descending) + storage charge (by bid)
        3. Find the price where cumulative supply crosses cumulative demand
        4. All cleared participants trade at the uniform clearing price
        """
        # --- Build sell orders ---
        sells: list[_SortableSell] = []

        for offer in generator_offers:
            if offer.quantity_mw > 0:
                sells.append(
                    _SortableSell(
                        source_id=offer.generator_id,
                        source_type="generator",
                        quantity_mw=offer.quantity_mw,
                        price=offer.marginal_cost,
                    )
                )

        for bid in storage_bids:
            if bid.action == "discharge" and bid.quantity_mw > 0:
                sells.append(
                    _SortableSell(
                        source_id=bid.storage_id,
                        source_type="storage",
                        quantity_mw=bid.quantity_mw,
                        price=bid.price,
                    )
                )

        # Sort by price ascending (cheapest first)
        sells.sort(key=lambda s: s.price)

        # --- Build buy orders ---
        buys: list[_SortableBuy] = []

        for bid in consumer_bids:
            if bid.quantity_mw > 0:
                buys.append(
                    _SortableBuy(
                        source_id=bid.consumer_id,
                        source_type="consumer",
                        quantity_mw=bid.quantity_mw,
                        price=bid.max_price,
                        consumer_id_for_tracking=bid.consumer_id,
                    )
                )

        for bid in storage_bids:
            if bid.action == "charge" and bid.quantity_mw > 0:
                buys.append(
                    _SortableBuy(
                        source_id=bid.storage_id,
                        source_type="storage",
                        quantity_mw=bid.quantity_mw,
                        price=bid.price,
                    )
                )

        # Sort by price descending (highest willingness-to-pay first)
        buys.sort(key=lambda b: b.price, reverse=True)

        # --- Merit-order intersection ---
        clearing_price = 0.0
        cleared_sells: list[tuple[_SortableSell, float]] = []  # (sell, cleared_qty)
        cleared_buys: list[tuple[_SortableBuy, float]] = []  # (buy, cleared_qty)

        sell_idx = 0
        buy_idx = 0
        cum_supply = 0.0
        cum_demand = 0.0

        while sell_idx < len(sells) and buy_idx < len(buys):
            sell = sells[sell_idx]
            buy = buys[buy_idx]

            # A trade can only happen if buy price >= sell price
            if buy.price >= sell.price:
                trade_qty = min(
                    sell.quantity_mw - cum_supply,
                    buy.quantity_mw - cum_demand,
                )
                if trade_qty <= 0:
                    # Move to next in whichever stack is exhausted
                    if cum_supply >= sell.quantity_mw:
                        sell_idx += 1
                        cum_supply = 0.0
                    if cum_demand >= buy.quantity_mw:
                        buy_idx += 1
                        cum_demand = 0.0
                    continue

                # The clearing price is set by the marginal sell unit
                clearing_price = sell.price

                cleared_sells.append((sell, trade_qty))
                cleared_buys.append((buy, trade_qty))

                cum_supply += trade_qty
                cum_demand += trade_qty

                if cum_supply >= sell.quantity_mw:
                    sell_idx += 1
                    cum_supply = 0.0
                if cum_demand >= buy.quantity_mw:
                    buy_idx += 1
                    cum_demand = 0.0
            else:
                # No more trades possible — buy price too low for cheapest remaining sell
                break

        # --- Build dispatch results ---
        generator_dispatch: dict[str, float] = {}
        consumer_allocation: dict[str, float] = {}
        raw_storage_actions: list[dict] = []
        total_supply = 0.0
        total_demand = 0.0

        for sell, qty in cleared_sells:
            total_supply += qty
            if sell.source_type == "generator":
                generator_dispatch[sell.source_id] = (
                    generator_dispatch.get(sell.source_id, 0.0) + qty
                )
            elif sell.source_type == "storage":
                raw_storage_actions.append(
                    {
                        "storage_id": sell.source_id,
                        "action": "discharge",
                        "quantity_mw": qty,
                        "price": clearing_price,
                    }
                )

        for buy, qty in cleared_buys:
            total_demand += qty
            if buy.source_type == "consumer":
                cid = buy.consumer_id_for_tracking or buy.source_id
                consumer_allocation[cid] = consumer_allocation.get(cid, 0.0) + qty
            elif buy.source_type == "storage":
                raw_storage_actions.append(
                    {
                        "storage_id": buy.source_id,
                        "action": "charge",
                        "quantity_mw": qty,
                        "price": clearing_price,
                    }
                )

        # --- Resolve storage conflicts ---
        # A storage unit cannot charge and discharge simultaneously.
        # If both actions cleared, net them: keep only the dominant direction.
        storage_actions = self._resolve_storage_conflicts(raw_storage_actions)

        # Adjust totals after conflict resolution
        for action in storage_actions:
            if action["action"] == "discharge":
                # Already counted in total_supply (no change needed unless netted)
                pass
            elif action["action"] == "charge":
                # Already counted in total_demand (no change needed unless netted)
                pass

        # Recalculate totals after conflict resolution
        final_supply = sum(
            q
            for a in storage_actions
            if a["action"] == "discharge"
            for q in [a["quantity_mw"]]
        ) + sum(generator_dispatch.values())
        final_demand = sum(
            q
            for a in storage_actions
            if a["action"] == "charge"
            for q in [a["quantity_mw"]]
        ) + sum(consumer_allocation.values())

        # Calculate unserved demand
        total_requested_demand = sum(b.quantity_mw for b in consumer_bids)
        unserved = max(0, total_requested_demand - final_demand)

        return MarketResult(
            clearing_price=clearing_price if total_supply > 0 else self.price_cap,
            total_supply_mw=final_supply,
            total_demand_mw=final_demand,
            unserved_demand_mw=unserved,
            generator_dispatch=generator_dispatch,
            consumer_allocation=consumer_allocation,
            storage_actions=storage_actions,
        )

    @staticmethod
    def _resolve_storage_conflicts(
        actions: list[dict],
    ) -> list[dict]:
        """
        A storage unit cannot charge and discharge in the same time step.
        If both occur, net them: keep only the dominant direction with the net quantity.
        """
        by_storage: dict[str, dict[str, float]] = {}
        for a in actions:
            sid = a["storage_id"]
            if sid not in by_storage:
                by_storage[sid] = {"charge": 0.0, "discharge": 0.0}
            by_storage[sid][a["action"]] += a["quantity_mw"]

        resolved: list[dict] = []
        for sid, qtys in by_storage.items():
            net = qtys["discharge"] - qtys["charge"]
            if net > 0.001:
                resolved.append(
                    {
                        "storage_id": sid,
                        "action": "discharge",
                        "quantity_mw": net,
                        "price": actions[0]["price"],
                    }
                )
            elif net < -0.001:
                resolved.append(
                    {
                        "storage_id": sid,
                        "action": "charge",
                        "quantity_mw": -net,
                        "price": actions[0]["price"],
                    }
                )
            # If net is ~0, both cancel out — no action for this storage

        return resolved
