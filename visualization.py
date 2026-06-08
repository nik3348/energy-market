"""
Visualization module for energy market simulation results.

Plot functions are split into drawing helpers (_draw_*) that accept an
Axes object, and display helpers (plot_*) that create a figure and show it.
This eliminates the duplication between interactive plots and file saving.
"""

import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from simulation import SimulationResult


def _format_date_axis(ax) -> None:
    """Apply consistent date-axis formatting."""
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=45)


def _draw_supply_demand(ax, result: SimulationResult) -> None:
    ax.plot(
        result.timestamps,
        result.total_supply,
        label="Supply (MW)",
        color="#2ecc71",
        linewidth=0.8,
    )
    ax.plot(
        result.timestamps,
        result.total_demand,
        label="Demand (MW)",
        color="#e74c3c",
        linewidth=0.8,
        alpha=0.8,
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Power (MW)")
    ax.set_title("Energy Supply vs Demand Over Time")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    _format_date_axis(ax)


def _draw_price(ax, result: SimulationResult) -> None:
    ax.plot(
        result.timestamps,
        result.prices,
        label="Price ($/MWh)",
        color="#3498db",
        linewidth=0.8,
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Price ($/MWh)")
    ax.set_title("Market Clearing Price Over Time")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    _format_date_axis(ax)


def _draw_generator_outputs(ax, result: SimulationResult) -> None:
    if not result.generator_outputs:
        return
    labels = list(result.generator_outputs.keys())
    data = [result.generator_outputs[k] for k in labels]
    ax.stackplot(result.timestamps, data, labels=labels, alpha=0.7)
    ax.set_xlabel("Time")
    ax.set_ylabel("Power (MW)")
    ax.set_title("Generator Output Over Time")
    ax.legend(loc="upper right", ncol=2)
    ax.grid(True, alpha=0.3)
    _format_date_axis(ax)


def _draw_storage_soc(ax, result: SimulationResult) -> None:
    if not result.storage_socs:
        return
    for storage_id, soc_history in result.storage_socs.items():
        ax.plot(result.timestamps, soc_history, label=storage_id, linewidth=0.8)
    ax.set_xlabel("Time")
    ax.set_ylabel("State of Charge")
    ax.set_title("Storage State of Charge Over Time")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1)
    _format_date_axis(ax)


# (name, draw_function, empty_check) — used by save_all
_PLOTTERS = [
    ("supply_demand", _draw_supply_demand, lambda r: bool(r.timestamps)),
    ("price", _draw_price, lambda r: bool(r.prices)),
    ("generator_outputs", _draw_generator_outputs, lambda r: bool(r.generator_outputs)),
    ("storage_soc", _draw_storage_soc, lambda r: bool(r.storage_socs)),
]


def plot_supply_demand(result: SimulationResult) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    _draw_supply_demand(ax, result)
    plt.tight_layout()
    plt.show()


def plot_price(result: SimulationResult) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    _draw_price(ax, result)
    plt.tight_layout()
    plt.show()


def plot_generator_outputs(result: SimulationResult) -> None:
    if not result.generator_outputs:
        return
    fig, ax = plt.subplots(figsize=(14, 6))
    _draw_generator_outputs(ax, result)
    plt.tight_layout()
    plt.show()


def plot_storage_soc(result: SimulationResult) -> None:
    if not result.storage_socs:
        return
    fig, ax = plt.subplots(figsize=(14, 6))
    _draw_storage_soc(ax, result)
    plt.tight_layout()
    plt.show()


def plot_all(result: SimulationResult) -> None:
    plot_supply_demand(result)
    plot_price(result)
    plot_generator_outputs(result)
    plot_storage_soc(result)


def save_all(result: SimulationResult, output_dir: str = "outputs") -> None:
    """Save all plots as PNG files to the specified directory."""
    os.makedirs(output_dir, exist_ok=True)
    for name, draw_fn, has_data in _PLOTTERS:
        if not has_data(result):
            continue
        fig, ax = plt.subplots(figsize=(14, 6))
        draw_fn(ax, result)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, f"{name}.png"), dpi=150)
        plt.close(fig)
    print(f"Plots saved to {output_dir}/")
