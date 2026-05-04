"""
Time-related utilities for the energy market simulation.

Handles seasons, holidays, weekends, and time-of-day factors that affect
both generation (solar, wind patterns) and consumption (demand profiles).
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum


class Season(Enum):
    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"


def get_season(d: date) -> Season:
    """Return the meteorological season for a given date."""
    m = d.month
    if m in (12, 1, 2):
        return Season.WINTER
    elif m in (3, 4, 5):
        return Season.SPRING
    elif m in (6, 7, 8):
        return Season.SUMMER
    else:
        return Season.AUTUMN


# Major US holidays (month, day) — simple fixed-date list
_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),  # New Year's Day
    (7, 4),  # Independence Day
    (12, 25),  # Christmas Day
}


def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _memorial_day(year: int) -> date:
    """Last Monday of May."""
    d = date(year, 5, 31)
    while d.weekday() != 0:  # Monday
        d -= timedelta(days=1)
    return d


def _labor_day(year: int) -> date:
    """First Monday of September."""
    d = date(year, 9, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def _thanksgiving(year: int) -> date:
    """Fourth Thursday of November."""
    d = date(year, 11, 1)
    thursdays = 0
    while thursdays < 4:
        if d.weekday() == 3:  # Thursday
            thursdays += 1
            if thursdays == 4:
                return d
        d += timedelta(days=1)
    return d


def is_holiday(d: date) -> bool:
    """Check if a date is a major US holiday."""
    # Fixed-date holidays
    if (d.month, d.day) in _HOLIDAYS:
        return True

    # Floating holidays
    year = d.year
    if d == _memorial_day(year):
        return True
    if d == _labor_day(year):
        return True
    if d == _thanksgiving(year):
        return True

    # Easter is not a federal holiday but often affects behavior
    # We skip it here but include Thanksgiving + day after
    thanksgiving = _thanksgiving(year)
    if d == thanksgiving + timedelta(days=1):  # Black Friday
        return True

    return False


def is_weekend(d: date) -> bool:
    """Check if a date falls on a weekend (Saturday or Sunday)."""
    return d.weekday() >= 5


def hour_of_day_factor(hour: int) -> float:
    """
    Return a factor [0, 1] representing typical relative demand/generation
    for a given hour of the day. Peaks at morning (~8h) and evening (~19h),
    troughs in the early morning (~3h).

    This is a simplified model using a sum of two Gaussian-like curves.
    """
    # Morning peak centered at hour 8, evening peak at hour 19
    morning = math.exp(-0.5 * ((hour - 8) / 3) ** 2)
    evening = math.exp(-0.5 * ((hour - 19) / 3.5) ** 2)
    night_trough = 0.4 + 0.6 * max(morning, evening)
    return max(0.2, min(1.0, night_trough))


def season_factor(season: Season) -> float:
    """
    Return a seasonal multiplier for energy demand.
    Summer and winter are highest (cooling/heating), spring/autumn lower.
    """
    return {
        Season.WINTER: 1.15,
        Season.SUMMER: 1.20,
        Season.SPRING: 0.85,
        Season.AUTUMN: 0.80,
    }[season]


@dataclass
class TimeContext:
    """Bundled temporal context for a single simulation tick."""

    dt: datetime
    season: Season
    holiday: bool
    weekend: bool
    hour: int  # 0-23

    @classmethod
    def from_datetime(cls, dt: datetime) -> "TimeContext":
        return cls(
            dt=dt,
            season=get_season(dt.date()),
            holiday=is_holiday(dt.date()),
            weekend=is_weekend(dt.date()),
            hour=dt.hour,
        )

    @property
    def demand_multiplier(self) -> float:
        """Overall demand multiplier combining all temporal effects."""
        base = hour_of_day_factor(self.hour) * season_factor(self.season)
        if self.holiday:
            base *= 0.65  # Lower demand on holidays
        elif self.weekend:
            base *= 0.80  # Lower demand on weekends
        return base
