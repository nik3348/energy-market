"""
Visualization module for energy market simulation results.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from simulation import SimulationResult


def plot_supply_demand(result: SimulationResult, title: str = "Energy Supply vs Demand Over Time") -> None:
    """
    Plot a time series graph showing total supply and total demand over the simulation period.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(result.timestamps, result.total_supply, label="Supply (MW)", color="#2ecc71", linewidth=0.8)
    ax.plot(result.timestamps, result.total_demand, label="Demand (MW)", color="#e74c3c", linewidth=0.8, alpha=0.8)

    ax.set_xlabel("Time")
    ax.set_ylabel("Power (MW)")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_price(result: SimulationResult, title: str = "Market Clearing Price Over Time") -> None:
    """
    Plot a time series graph of the market clearing price.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(result.timestamps, result.prices, label="Price ($/MWh)", color="#3498db", linewidth=0.8)

    ax.set_xlabel("Time")
    ax.set_ylabel("Price ($/MWh)")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_generator_outputs(result: SimulationResult, title: str = "Generator Output Over Time") -> None:
    """
    Plot stacked area chart showing generation by each generator over time.
    """
    if not result.generator_outputs:
        return

    fig, ax = plt.subplots(figsize=(14, 6))

    labels = list(result.generator_outputs.keys())
    data = [result.generator_outputs[k] for k in labels]

    ax.stackplot(result.timestamps, data, labels=labels, alpha=0.7)

    ax.set_xlabel("Time")
    ax.set_ylabel("Power (MW)")
    ax.set_title(title)
    ax.legend(loc="upper right", ncol=2)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_storage_soc(result: SimulationResult, title: str = "Storage State of Charge Over Time") -> None:
    """
    Plot state of charge for each storage device over time.
    """
    if not result.storage_socs:
        return

    fig, ax = plt.subplots(figsize=(14, 6))

    for storage_id, soc_history in result.storage_socs.items():
        ax.plot(result.timestamps, soc_history, label=storage_id, linewidth=0.8)

    ax.set_xlabel("Time")
    ax.set_ylabel("State of Charge")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_all(result: SimulationResult) -> None:
    """
    Display all available plots.
    """
    plot_supply_demand(result)
    plot_price(result)
    plot_generator_outputs(result)
    plot_storage_soc(result)


def save_all(result: SimulationResult, output_dir: str = "outputs") -> None:
    """
    Save all plots as PNG files to the specified output directory.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    plots = [
        ("supply_demand", plot_supply_demand),
        ("price", plot_price),
        ("generator_outputs", plot_generator_outputs),
        ("storage_soc", plot_storage_soc),
    ]

    for name, plot_fn in plots:
        fig, ax = plt.subplots(figsize=(14, 6))
        # Re-create the plot on the axes
        if name == "supply_demand":
            ax.plot(result.timestamps, result.total_supply, label="Supply (MW)", color="#2ecc71", linewidth=0.8)
            ax.plot(result.timestamps, result.total_demand, label="Demand (MW)", color="#e74c3c", linewidth=0.8, alpha=0.8)
            ax.set_ylabel("Power (MW)")
        elif name == "price":
            ax.plot(result.timestamps, result.prices, label="Price ($/MWh)", color="#3498db", linewidth=0.8)
            ax.set_ylabel("Price ($/MWh)")
        elif name == "generator_outputs":
            if result.generator_outputs:
                labels = list(result.generator_outputs.keys())
                data = [result.generator_outputs[k] for k in labels]
                ax.stackplot(result.timestamps, data, labels=labels, alpha=0.7)
                ax.set_ylabel("Power (MW)")
        elif name == "storage_soc":
            if result.storage_socs:
                for storage_id, soc_history in result.storage_socs.items():
                    ax.plot(result.timestamps, soc_history, label=storage_id, linewidth=0.8)
                ax.set_ylim(0, 1)
                ax.set_ylabel("State of Charge")

        ax.set_xlabel("Time")
        ax.set_title(name.replace("_", " ").title())
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        plt.tight_layout()
        fig.savefig(os.path.join(output_dir, f"{name}.png"), dpi=150)
        plt.close(fig)

    print(f"Plots saved to {output_dir}/")