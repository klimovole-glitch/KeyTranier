"""Per-key analytics: heatmap data and problem keys (ТЗ, п. 4.2.1, 4.3.1).

A key is "problem" when its error rate or reaction time is noticeably
higher than the user's average (ТЗ, п. 1.9). Keys pressed fewer than 5
times have too little data and are shown in grey.
"""

import colorsys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from keytrainer.data.keyboard_layouts import LAYOUT_IDS, SPACE_CHAR
from keytrainer.data.models import Key
from keytrainer.data.repositories import (
    KeyRepository,
    KeyStatRepository,
    SessionRepository,
)

MIN_ATTEMPTS = 5
ERROR_SCALE_MAX = 30.0  # 30 % and more is fully red (Figma, рисунок 8)
TOP_KEYS = 5
GREEN_HUE, RED_HUE = 120.0, 0.0


class Metric(str, Enum):
    """What the heatmap colors."""

    ERROR_RATE = "ERROR_RATE"
    LATENCY = "LATENCY"


class Period(str, Enum):
    """Period of the statistics."""

    LAST_SESSION = "LAST_SESSION"
    DAYS_7 = "DAYS_7"
    DAYS_30 = "DAYS_30"
    ALL = "ALL"


PERIOD_DAYS = {Period.DAYS_7: 7, Period.DAYS_30: 30}


@dataclass(frozen=True)
class KeyCell:
    """Statistics of one key for the chosen period."""

    key: Key
    attempts: int
    errors: int
    avg_latency_ms: float | None

    @property
    def enough_data(self) -> bool:
        """``True`` if the key was pressed at least 5 times."""
        return self.attempts >= MIN_ATTEMPTS

    @property
    def error_rate(self) -> float:
        """Error rate of the key in percent."""
        return self.errors / self.attempts * 100 if self.attempts else 0.0

    def value(self, metric: Metric) -> float | None:
        """Value of the chosen metric.

        Args:
            metric: Error rate or reaction time.

        Returns:
            Value or ``None`` if unknown.
        """
        if metric == Metric.ERROR_RATE:
            return self.error_rate
        return self.avg_latency_ms


@dataclass(frozen=True)
class HeatmapData:
    """Everything the statistics screen shows."""

    metric: Metric
    period: Period
    layout_name: str
    cells: dict[str, KeyCell]
    scale_min: float
    scale_max: float
    top: tuple[KeyCell, ...]
    sessions_found: bool

    def ratio(self, cell: KeyCell) -> float | None:
        """Position of a key on the color scale.

        Args:
            cell: Key statistics.

        Returns:
            Value from 0 (green) to 1 (red), ``None`` for grey keys.
        """
        value = cell.value(self.metric)
        if not cell.enough_data or value is None:
            return None
        return heat_ratio(value, self.scale_min, self.scale_max)


def heat_ratio(value: float, low: float, high: float) -> float:
    """Bring a value to the range [0; 1] (ТЗ, п. 4.3.1).

    Args:
        value: Metric value.
        low: Value that becomes 0.
        high: Value that becomes 1.

    Returns:
        Normalized value clamped to [0; 1].
    """
    if high <= low:
        return 0.0
    return min(max((value - low) / (high - low), 0.0), 1.0)


def heat_color(ratio: float, saturation: float, brightness: float) -> str:
    """Convert a normalized value to a color from green to red (HSV).

    Args:
        ratio: 0 — green, 1 — red.
        saturation: HSV saturation of the theme.
        brightness: HSV value of the theme.

    Returns:
        Hex color ``#rrggbb``.
    """
    hue = (GREEN_HUE + (RED_HUE - GREEN_HUE) * ratio) / 360
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


class AnalyticsEngine:
    """Aggregates ``tbl_key_stats`` for the heatmap and the weak keys mode."""

    def __init__(
        self,
        key_stats: KeyStatRepository,
        keys: KeyRepository,
        sessions: SessionRepository,
    ) -> None:
        """Store repositories.

        Args:
            key_stats: Per-key statistics.
            keys: Keys of the layouts.
            sessions: Sessions (for the "last session" period).
        """
        self._key_stats = key_stats
        self._keys = keys
        self._sessions = sessions

    @staticmethod
    def since_for(period: Period, now: datetime | None = None) -> str | None:
        """Start of a period as an ISO string for SQL.

        Args:
            period: Period.
            now: Current time (for tests).

        Returns:
            ISO date-time or ``None`` for "all time" and "last session".
        """
        days = PERIOD_DAYS.get(period)
        if days is None:
            return None
        start = (now or datetime.now()) - timedelta(days=days)
        return start.isoformat(timespec="seconds")

    def build_heatmap(
        self,
        user_id: int,
        layout_name: str,
        metric: Metric,
        period: Period,
        now: datetime | None = None,
    ) -> HeatmapData:
        """Collect statistics of every key for the heatmap.

        Runs in a background thread: only repositories are used here.

        Args:
            user_id: Profile id.
            layout_name: Layout to show.
            metric: Metric to color.
            period: Period of the statistics.
            now: Current time (for tests).

        Returns:
            Heatmap data.
        """
        layout_id = LAYOUT_IDS[layout_name]
        session_id = None
        if period == Period.LAST_SESSION:
            last = self._sessions.get_last(user_id, layout_id)
            session_id = last.id if last else -1
        aggregates = {
            a.key_id: a
            for a in self._key_stats.aggregate(
                user_id, layout_id, self.since_for(period, now), session_id
            )
        }
        cells = {}
        for key in self._keys.get_by_layout(layout_id):
            agg = aggregates.get(key.id)
            cells[key.key_char] = KeyCell(
                key=key,
                attempts=agg.attempts if agg else 0,
                errors=agg.errors if agg else 0,
                avg_latency_ms=agg.avg_latency_ms if agg else None,
            )
        low, high = self._scale(cells.values(), metric)
        return HeatmapData(
            metric=metric,
            period=period,
            layout_name=layout_name,
            cells=cells,
            scale_min=low,
            scale_max=high,
            top=tuple(top_problem_keys(cells.values(), metric)),
            sessions_found=bool(aggregates),
        )

    @staticmethod
    def _scale(cells, metric: Metric) -> tuple[float, float]:
        """Choose the color scale.

        Errors: fixed 0-30 %. Reaction time: from the fastest to the slowest
        key with enough data.

        Args:
            cells: Key statistics.
            metric: Chosen metric.

        Returns:
            Scale minimum and maximum.
        """
        if metric == Metric.ERROR_RATE:
            return 0.0, ERROR_SCALE_MAX
        values = [
            c.avg_latency_ms
            for c in cells
            if c.enough_data and c.avg_latency_ms is not None
        ]
        return (min(values), max(values)) if values else (0.0, 1.0)

    def weak_key_rates(self, user_id: int, layout_name: str) -> dict[str, float]:
        """Error rates of the problem keys for the "Работа над ошибками" mode.

        Args:
            user_id: Profile id.
            layout_name: Layout of the exercise.

        Returns:
            Base character -> error rate, only keys with errors.
        """
        data = self.build_heatmap(user_id, layout_name, Metric.ERROR_RATE, Period.ALL)
        return {c.key.key_char: c.error_rate for c in data.top if c.errors}


def top_problem_keys(cells, metric: Metric, limit: int = TOP_KEYS) -> list[KeyCell]:
    """Rank keys by the chosen metric, worst first.

    Only keys with enough data take part; the space bar is excluded.

    Args:
        cells: Key statistics.
        metric: Ranking metric.
        limit: Number of keys.

    Returns:
        Up to ``limit`` worst keys.
    """
    candidates = [
        c
        for c in cells
        if c.enough_data
        and c.key.key_char != SPACE_CHAR
        and c.value(metric) is not None
    ]
    candidates.sort(key=lambda c: c.value(metric), reverse=True)
    return candidates[:limit]
