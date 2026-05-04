"""
Energy Market Simulation — Main Entry Point.

Simulates an energy market with generators (solar, wind, thermal),
battery storage, and consumers over a customizable time period.

Usage:
    python main.py              # Run default 1-month simulation
    python main.py --days 365   # Run a full year
    python main.py --seed 42    # Reproducible randomness
"""

import argparse
from datetime import datetime, timedelta

from market.market import Market
from nodes.consumer import Consumer
from nodes.generator import SolarGenerator, ThermalGenerator, WindGenerator
from nodes.storage import BatteryStorage
from simulation import Simulation
from utils.demand_profiles import DemandProfile


def build_default_scenario() -> Simulation:
    """Build a realistic default scenario with diverse participants."""

    # --- Generators ---
    # Mix of zero-marginal-cost renewables and dispatchable thermal plants.
    # Renewables create price volatility: prices crash when sun/wind are abundant
    # and spike when thermal plants must cover the shortfall.
    generators = [
        SolarGenerator(
            generator_id="solar_farm_1",
            capacity_mw=350.0,  # Large solar — creates mid-day price dips
            marginal_cost_base=0.0,
            cloudiness=0.15,
        ),
        SolarGenerator(
            generator_id="solar_farm_2",
            capacity_mw=150.0,
            marginal_cost_base=0.0,
            cloudiness=0.20,
        ),
        WindGenerator(
            generator_id="wind_farm_1",
            capacity_mw=200.0,
            marginal_cost_base=0.0,
            volatility=0.30,
        ),
        WindGenerator(
            generator_id="wind_farm_2",
            capacity_mw=120.0,
            marginal_cost_base=0.0,
            volatility=0.35,
        ),
        ThermalGenerator(
            generator_id="gas_plant_1",
            capacity_mw=300.0,
            marginal_cost_base=45.0,
            forced_outage_rate=0.04,
        ),
        ThermalGenerator(
            generator_id="gas_plant_2",
            capacity_mw=200.0,
            marginal_cost_base=55.0,
            forced_outage_rate=0.04,
        ),
        ThermalGenerator(
            generator_id="coal_plant_1",
            capacity_mw=250.0,
            marginal_cost_base=35.0,
            forced_outage_rate=0.05,
        ),
    ]

    # --- Storage ---
    storages = [
        BatteryStorage(
            storage_id="bess_1",
            capacity_mwh=100.0,  # 100 MWh
            power_mw=50.0,  # 50 MW charge/discharge
            efficiency=0.90,
            initial_soc=0.5,
            buy_threshold=45.0,  # Charge when price dips below $45
            sell_threshold=65.0,  # Discharge when price spikes above $65
            soc_margin=0.20,
        ),
        BatteryStorage(
            storage_id="bess_2",
            capacity_mwh=60.0,
            power_mw=30.0,
            efficiency=0.88,
            initial_soc=0.4,
            buy_threshold=40.0,
            sell_threshold=70.0,
            soc_margin=0.20,
        ),
    ]

    # --- Consumers ---
    consumers = [
        Consumer(
            consumer_id="residential_1",
            profile=DemandProfile(
                base_demand_mw=400.0,
                price_sensitivity=0.8,
                max_price=500.0,
                min_demand_fraction=0.25,
            ),
            sector="residential",
        ),
        Consumer(
            consumer_id="commercial_1",
            profile=DemandProfile(
                base_demand_mw=250.0,
                price_sensitivity=1.2,
                max_price=400.0,
                min_demand_fraction=0.30,
            ),
            sector="commercial",
        ),
        Consumer(
            consumer_id="industrial_1",
            profile=DemandProfile(
                base_demand_mw=150.0,
                price_sensitivity=0.3,
                max_price=600.0,
                min_demand_fraction=0.50,
            ),
            sector="industrial",
        ),
    ]

    market = Market(price_cap=1000.0)
    return Simulation(generators, storages, consumers, market)


def main():
    parser = argparse.ArgumentParser(description="Energy Market Simulation")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to simulate (default: 30)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2025-06-01",
        help="Start date (YYYY-MM-DD, default: 2025-06-01)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print daily progress",
    )
    args = parser.parse_args()

    sim = build_default_scenario()

    if args.seed is not None:
        import random

        random.seed(args.seed)

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = start + timedelta(days=args.days)

    print("Running energy market simulation...")
    print(f"  Period: {start.date()} to {end.date()} ({args.days} days)")
    print(
        f"  Participants: {len(sim.generators)} generators, "
        f"{len(sim.storages)} storage, {len(sim.consumers)} consumers"
    )
    if args.seed is not None:
        print(f"  Seed: {args.seed}")
    print()

    sim.run(start, end, verbose=args.verbose)

    sim.print_summary()

    print("\nTip: Use --days 365 for a full year, --seed 42 for reproducibility")
    print("     Add --verbose for daily progress output")


if __name__ == "__main__":
    main()
