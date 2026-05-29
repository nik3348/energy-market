"""
SimulationThread — runs the energy market simulation step-by-step in a background thread.
"""

from datetime import datetime, timedelta
from enum import Enum

from PyQt5.QtCore import QThread, pyqtSignal

from simulation import Simulation


class SimState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class SimulationThread(QThread):
    step_complete = pyqtSignal(object)
    status_update = pyqtSignal(str)
    simulation_complete = pyqtSignal()

    def __init__(self, sim: Simulation, start: datetime, end: datetime, parent=None):
        super().__init__(parent)
        self._sim = sim
        self._start = start
        self._end = end
        self._delay_ms = 100
        self._state = SimState.IDLE
        self._pause_event = False

    @property
    def state(self) -> SimState:
        return self._state

    @property
    def delay_ms(self) -> int:
        return self._delay_ms

    @delay_ms.setter
    def delay_ms(self, value: int) -> None:
        self._delay_ms = max(10, min(2000, value))

    def play(self) -> None:
        if self._state in (SimState.IDLE, SimState.STOPPED):
            self._sim.reset(self._start, self._end)
            self._state = SimState.RUNNING
            self.start()
        elif self._state == SimState.PAUSED:
            self._state = SimState.RUNNING

    def pause(self) -> None:
        if self._state == SimState.RUNNING:
            self._state = SimState.PAUSED

    def stop(self) -> None:
        self._state = SimState.STOPPED
        self.wait()
        self._state = SimState.IDLE
        self._sim.reset(self._start, self._end)

    def run(self) -> None:
        while self._state == SimState.RUNNING:
            result = self._sim.step()
            if result is None:
                self._state = SimState.STOPPED
                self.simulation_complete.emit()
                return
            self.step_complete.emit(self._sim.result)
            current_day = self._sim.completed_steps // 24 + 1
            total_days = self._sim.total_steps // 24 + 1
            self.status_update.emit(f"Day {current_day} / {total_days}")
            self.msleep(self._delay_ms)