"""
Plot widgets — matplotlib canvas classes for real-time simulation graphs.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from simulation import SimulationResult


class BasePlot(FigureCanvasQTAgg):
    def __init__(self, title: str, ylabel: str, parent=None):
        self._fig = Figure(figsize=(12, 4))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_title(title)
        self._ax.set_ylabel(ylabel)
        self._ax.grid(True, alpha=0.3)
        super().__init__(self._fig)
        self._toolbar = None

    def _setup_axis(self) -> None:
        self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        self._ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self._fig.autofmt_xdate(rotation=45)

    def clear(self) -> None:
        self._ax.clear()
        self._ax.set_title(self._ax.get_title())
        self._ax.set_ylabel(self._ax.get_ylabel())
        self._ax.grid(True, alpha=0.3)
        self.draw()

    def reset_view(self) -> None:
        self._ax.relim()
        self._ax.autoscale_view()
        self.draw()

    def enable_toolbar(self) -> None:
        if self._toolbar is None:
            from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
            self._toolbar = NavigationToolbar2QT(self, self)
            self._toolbar.hide()

    def show_toolbar(self) -> None:
        if self._toolbar:
            self._toolbar.show()

    def hide_toolbar(self) -> None:
        if self._toolbar:
            self._toolbar.hide()


class SupplyDemandPlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Supply vs Demand", "Power (MW)", parent)
        self._line_supply = None
        self._line_demand = None

    def update_data(self, result: SimulationResult) -> None:
        self._ax.clear()
        self._ax.set_title("Supply vs Demand")
        self._ax.set_ylabel("Power (MW)")
        self._ax.grid(True, alpha=0.3)

        if result.timestamps:
            self._ax.plot(
                result.timestamps, result.total_supply,
                label="Supply (MW)", color="#2ecc71", linewidth=0.8
            )
            self._ax.plot(
                result.timestamps, result.total_demand,
                label="Demand (MW)", color="#e74c3c", linewidth=0.8, alpha=0.8
            )
            self._ax.legend(loc="upper right")
            self._setup_axis()

        self._fig.tight_layout()
        self.draw()


class PricePlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Market Clearing Price", "Price ($/MWh)", parent)

    def update_data(self, result: SimulationResult) -> None:
        self._ax.clear()
        self._ax.set_title("Market Clearing Price")
        self._ax.set_ylabel("Price ($/MWh)")
        self._ax.grid(True, alpha=0.3)

        if result.timestamps:
            self._ax.plot(
                result.timestamps, result.prices,
                label="Price ($/MWh)", color="#3498db", linewidth=0.8
            )
            self._ax.legend(loc="upper right")
            self._setup_axis()

        self._fig.tight_layout()
        self.draw()


class GeneratorOutputPlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Generator Output", "Power (MW)", parent)

    def update_data(self, result: SimulationResult) -> None:
        self._ax.clear()
        self._ax.set_title("Generator Output")
        self._ax.set_ylabel("Power (MW)")
        self._ax.grid(True, alpha=0.3)

        if result.generator_outputs:
            labels = list(result.generator_outputs.keys())
            data = [result.generator_outputs[k] for k in labels]
            self._ax.stackplot(result.timestamps, data, labels=labels, alpha=0.7)
            self._ax.legend(loc="upper right", ncol=2)
            self._setup_axis()

        self._fig.tight_layout()
        self.draw()


class StoragePlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Storage State of Charge", "SoC", parent)

    def update_data(self, result: SimulationResult) -> None:
        self._ax.clear()
        self._ax.set_title("Storage State of Charge")
        self._ax.set_ylabel("State of Charge")
        self._ax.grid(True, alpha=0.3)

        if result.storage_socs:
            for storage_id, soc_history in result.storage_socs.items():
                self._ax.plot(
                    result.timestamps, soc_history,
                    label=storage_id, linewidth=0.8
                )
            self._ax.legend(loc="upper right")
            self._ax.set_ylim(0, 1)
            self._setup_axis()

        self._fig.tight_layout()
        self.draw()