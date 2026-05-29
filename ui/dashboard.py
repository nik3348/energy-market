"""
Energy Market Dashboard — PyQt desktop application.

Entry point for the interactive simulation dashboard.

Usage:
    python -m ui.dashboard            # Default 7-day simulation
    python -m ui.dashboard --days 30  # Custom duration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from PyQt5.QtWidgets import QApplication

from ui.dashboard_window import DashboardWindow


def main():
    parser = argparse.ArgumentParser(description="Energy Market Dashboard")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to simulate (default: 7)",
    )
    args = parser.parse_args()

    app = QApplication([])
    window = DashboardWindow(days=args.days)
    window.setWindowTitle("Energy Market Simulation Dashboard")
    window.resize(1280, 900)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()