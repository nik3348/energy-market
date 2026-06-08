"""
Plot widgets — matplotlib canvas classes for real-time simulation graphs.

Uses incremental line updates (set_data) instead of full clear+redraw
to keep the UI responsive as data grows.
"""

import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from simulation import SimulationResult


class BasePlot(FigureCanvasQTAgg):
    def __init__(self, title: str, ylabel: str, parent=None):
        self._fig = Figure(figsize=(12, 4))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_title(title)
        self._ax.set_ylabel(ylabel)
        self._ax.grid(True, alpha=0.3)
        self._title = title
        self._ylabel = ylabel
        self._date_axis_set_up = False
        super().__init__(self._fig)
        self._toolbar = None

    def _setup_date_axis(self) -> None:
        """Configure date axis formatting. Called once per clear cycle."""
        if not self._date_axis_set_up:
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
            self._ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self._fig.autofmt_xdate(rotation=45)
            self._date_axis_set_up = True

    def clear(self) -> None:
        self._ax.clear()
        self._ax.set_title(self._title)
        self._ax.set_ylabel(self._ylabel)
        self._ax.grid(True, alpha=0.3)
        self._date_axis_set_up = False
        self.draw_idle()

    def reset_view(self) -> None:
        self._ax.relim()
        self._ax.autoscale_view()
        self.draw_idle()

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
        if not result.timestamps:
            return

        if self._line_supply is None:
            (self._line_supply,) = self._ax.plot(
                result.timestamps,
                result.total_supply,
                label="Supply (MW)",
                color="#2ecc71",
                linewidth=0.8,
            )
            (self._line_demand,) = self._ax.plot(
                result.timestamps,
                result.total_demand,
                label="Demand (MW)",
                color="#e74c3c",
                linewidth=0.8,
                alpha=0.8,
            )
            self._ax.legend(loc="upper right")
            self._setup_date_axis()
            self._fig.tight_layout()
        else:
            self._line_supply.set_data(result.timestamps, result.total_supply)
            self._line_demand.set_data(result.timestamps, result.total_demand)
            self._ax.relim()
            self._ax.autoscale_view()

        self.draw_idle()

    def clear(self) -> None:
        self._line_supply = None
        self._line_demand = None
        super().clear()


class PricePlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Market Clearing Price", "Price ($/MWh)", parent)
        self._line_price = None

    def update_data(self, result: SimulationResult) -> None:
        if not result.timestamps:
            return

        if self._line_price is None:
            (self._line_price,) = self._ax.plot(
                result.timestamps,
                result.prices,
                label="Price ($/MWh)",
                color="#3498db",
                linewidth=0.8,
            )
            self._ax.legend(loc="upper right")
            self._setup_date_axis()
            self._fig.tight_layout()
        else:
            self._line_price.set_data(result.timestamps, result.prices)
            self._ax.relim()
            self._ax.autoscale_view()

        self.draw_idle()

    def clear(self) -> None:
        self._line_price = None
        super().clear()


class GeneratorOutputPlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Generator Output", "Power (MW)", parent)

    def update_data(self, result: SimulationResult) -> None:
        if not result.generator_outputs:
            return

        self._ax.clear()
        self._ax.set_title(self._title)
        self._ax.set_ylabel(self._ylabel)
        self._ax.grid(True, alpha=0.3)

        labels = list(result.generator_outputs.keys())
        data = [result.generator_outputs[k] for k in labels]
        self._ax.stackplot(result.timestamps, data, labels=labels, alpha=0.7)
        self._ax.legend(loc="upper right", ncol=2)
        self._setup_date_axis()

        self._fig.tight_layout()
        self.draw_idle()

    def clear(self) -> None:
        super().clear()


class StoragePlot(BasePlot):
    def __init__(self, parent=None):
        super().__init__("Storage State of Charge", "SoC", parent)
        self._lines: dict[str, Line2D] = {}
        self._legend_added = False

    def update_data(self, result: SimulationResult) -> None:
        if not result.storage_socs:
            return

        new_line = False
        for storage_id, soc_history in result.storage_socs.items():
            if storage_id not in self._lines:
                (line,) = self._ax.plot(
                    result.timestamps,
                    soc_history,
                    label=storage_id,
                    linewidth=0.8,
                )
                self._lines[storage_id] = line
                new_line = True
            else:
                self._lines[storage_id].set_data(result.timestamps, soc_history)

        if new_line and not self._legend_added:
            self._ax.legend(loc="upper right")
            self._legend_added = True
            self._setup_date_axis()
            self._fig.tight_layout()

        self._ax.set_ylim(0, 1)
        self._ax.relim()
        self._ax.autoscale_view()
        self.draw_idle()

    def clear(self) -> None:
        self._lines = {}
        self._legend_added = False
        super().clear()
