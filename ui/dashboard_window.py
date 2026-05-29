"""
DashboardWindow — main PyQt window with control panel and simulation graphs.
"""

from datetime import datetime, timedelta

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QGroupBox, QScrollArea, QFrame,
    QTabWidget,
)
from PyQt5.QtGui import QFont

from main import build_default_scenario
from ui.simulation_thread import SimulationThread, SimState
from ui.plots import SupplyDemandPlot, PricePlot, GeneratorOutputPlot, StoragePlot


class DashboardWindow(QFrame):
    def __init__(self, days: int = 7, parent=None):
        super().__init__(parent)
        self._days = days
        self._start = datetime(2025, 6, 1)
        self._end = self._start + timedelta(days=days)

        sim = build_default_scenario()
        sim.reset(self._start, self._end)
        self._thread = SimulationThread(sim, self._start, self._end)

        self._plot_supply = SupplyDemandPlot()
        self._plot_price = PricePlot()
        self._plot_generators = GeneratorOutputPlot()
        self._plot_storage = StoragePlot()

        self._setup_ui()
        self._connect_signals()
        self._set_state(SimState.IDLE)

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        control_panel = self._build_control_panel()
        main_layout.addWidget(control_panel, stretch=0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(900)

        tabs = QTabWidget()
        tabs.addTab(self._plot_supply, "Supply & Demand")
        tabs.addTab(self._plot_price, "Price")
        tabs.addTab(self._plot_generators, "Generator Output")
        tabs.addTab(self._plot_storage, "Storage SoC")

        scroll.setWidget(tabs)
        main_layout.addWidget(scroll, stretch=1)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)

        title = QLabel("Energy Market")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        sim_info = QLabel(f"{self._days}-day simulation")
        layout.addWidget(sim_info)

        layout.addWidget(self._make_divider())

        state_group = QGroupBox("Controls")
        state_layout = QVBoxLayout(state_group)
        state_layout.setSpacing(10)

        self._btn_play = QPushButton("Play")
        self._btn_play.setFixedHeight(36)
        state_layout.addWidget(self._btn_play)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setFixedHeight(36)
        state_layout.addWidget(self._btn_stop)

        layout.addWidget(state_group)

        speed_group = QGroupBox("Speed")
        speed_layout = QVBoxLayout(speed_group)

        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setMinimum(1)
        self._speed_slider.setMaximum(100)
        self._speed_slider.setValue(50)
        self._speed_slider.setTickPosition(QSlider.TicksBelow)
        self._speed_slider.setTickInterval(20)
        speed_layout.addWidget(self._speed_slider)

        self._speed_label = QLabel("Speed: 50 (100ms/step)")
        speed_layout.addWidget(self._speed_label)

        layout.addWidget(speed_group)

        layout.addWidget(self._make_divider())

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)

        self._status_label = QLabel("Ready")
        self._status_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self._status_label)

        self._progress_label = QLabel("Day 0 / 7")
        self._progress_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self._progress_label)

        layout.addWidget(status_group)

        layout.addStretch()

        self._btn_reset_view = QPushButton("Reset View")
        self._btn_reset_view.setFixedHeight(32)
        layout.addWidget(self._btn_reset_view)

        return panel

    def _make_divider(self) -> QFrame:
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #cccccc;")
        return div

    def _connect_signals(self) -> None:
        self._btn_play.clicked.connect(self._on_play_clicked)
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        self._btn_reset_view.clicked.connect(self._on_reset_view)

        self._thread.step_complete.connect(self._on_step_complete)
        self._thread.status_update.connect(self._on_status_update)
        self._thread.simulation_complete.connect(self._on_simulation_complete)

    def _on_play_clicked(self) -> None:
        state = self._thread.state
        if state == SimState.IDLE or state == SimState.STOPPED:
            self._thread.play()
            self._set_state(SimState.RUNNING)
        elif state == SimState.RUNNING:
            self._thread.pause()
            self._set_state(SimState.PAUSED)
        elif state == SimState.PAUSED:
            self._thread.play()
            self._set_state(SimState.RUNNING)

    def _on_stop_clicked(self) -> None:
        self._thread.stop()
        self._set_state(SimState.IDLE)
        self._clear_plots()

    def _on_speed_changed(self, value: int) -> None:
        delay_ms = int(2010 - value * 20)
        self._thread.delay_ms = delay_ms
        self._speed_label.setText(f"Speed: {value} ({delay_ms}ms/step)")

    def _on_reset_view(self) -> None:
        self._plot_supply.reset_view()
        self._plot_price.reset_view()
        self._plot_generators.reset_view()
        self._plot_storage.reset_view()

    def _on_step_complete(self, result) -> None:
        self._plot_supply.update_data(result)
        self._plot_price.update_data(result)
        self._plot_generators.update_data(result)
        self._plot_storage.update_data(result)

    def _on_status_update(self, status: str) -> None:
        self._progress_label.setText(status)

    def _on_simulation_complete(self) -> None:
        self._set_state(SimState.STOPPED)
        self._status_label.setText("Complete")

    def _set_state(self, state: SimState) -> None:
        self._state = state
        if state == SimState.IDLE:
            self._btn_play.setText("Play")
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(False)
            self._status_label.setText("Ready")
            self._hide_all_toolbars()
        elif state == SimState.RUNNING:
            self._btn_play.setText("Pause")
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(True)
            self._status_label.setText("Running...")
            self._hide_all_toolbars()
        elif state == SimState.PAUSED:
            self._btn_play.setText("Resume")
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(True)
            self._status_label.setText("Paused")
            self._show_all_toolbars()
        elif state == SimState.STOPPED:
            self._btn_play.setText("Play")
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(False)
            self._status_label.setText("Stopped")
            self._show_all_toolbars()

    def _show_all_toolbars(self) -> None:
        for plot in [self._plot_supply, self._plot_price,
                     self._plot_generators, self._plot_storage]:
            plot.show_toolbar()

    def _hide_all_toolbars(self) -> None:
        for plot in [self._plot_supply, self._plot_price,
                     self._plot_generators, self._plot_storage]:
            plot.hide_toolbar()

    def _clear_plots(self) -> None:
        self._plot_supply.clear()
        self._plot_price.clear()
        self._plot_generators.clear()
        self._plot_storage.clear()
        self._progress_label.setText(f"Day 0 / {self._days}")