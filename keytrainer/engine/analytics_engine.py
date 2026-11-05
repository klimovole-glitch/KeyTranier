from __future__ import annotations
"""Аналитика по клавишам: данные тепловой карты и проблемные клавиши (ТЗ, п. 4.2.1, 4.3.1).

Клавиша считается «проблемной», если доля ошибок или время реакции заметно
выше среднего у пользователя (ТЗ, п. 1.9). Клавиши, нажатые менее 5 раз,
дают слишком мало данных и показываются серым.
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
ERROR_SCALE_MAX = 30.0  # 30 % и больше — полностью красный (Figma, рисунок 8)
TOP_KEYS = 5
GREEN_HUE, RED_HUE = 120.0, 0.0


class Metric(str, Enum):
    """Что раскрашивает тепловая карта."""

    ERROR_RATE = "ERROR_RATE"
    LATENCY = "LATENCY"


class Period(str, Enum):
    """Период статистики."""

    LAST_SESSION = "LAST_SESSION"
    DAYS_7 = "DAYS_7"
    DAYS_30 = "DAYS_30"
    ALL = "ALL"


PERIOD_DAYS = {Period.DAYS_7: 7, Period.DAYS_30: 30}


@dataclass(frozen=True)
class KeyCell:
    """Статистика одной клавиши за выбранный период."""

    key: Key
    attempts: int
    errors: int
    avg_latency_ms: float | None

    @property
    def enough_data(self) -> bool:
        """``True``, если клавиша нажата не менее 5 раз."""
        return self.attempts >= MIN_ATTEMPTS

    @property
    def error_rate(self) -> float:
        """Доля ошибок на клавише в процентах."""
        return self.errors / self.attempts * 100 if self.attempts else 0.0

    def value(self, metric: Metric) -> float | None:
        """Значение выбранной метрики.

        Args:
            metric: Доля ошибок или время реакции.

        Returns:
            Значение или ``None``, если оно неизвестно.
        """
        if metric == Metric.ERROR_RATE:
            return self.error_rate
        return self.avg_latency_ms


@dataclass(frozen=True)
class HeatmapData:
    """Всё, что показывает экран статистики."""

    metric: Metric
    period: Period
    layout_name: str
    cells: dict[str, KeyCell]
    scale_min: float
    scale_max: float
    top: tuple[KeyCell, ...]
    sessions_found: bool

    def ratio(self, cell: KeyCell) -> float | None:
        """Положение клавиши на цветовой шкале.

        Args:
            cell: Статистика клавиши.

        Returns:
            Значение от 0 (зелёный) до 1 (красный), ``None`` для серых клавиш.
        """
        value = cell.value(self.metric)
        if not cell.enough_data or value is None:
            return None
        return heat_ratio(value, self.scale_min, self.scale_max)


def heat_ratio(value: float, low: float, high: float) -> float:
    """Привести значение к диапазону [0; 1] (ТЗ, п. 4.3.1).

    Args:
        value: Значение метрики.
        low: Значение, которое станет 0.
        high: Значение, которое станет 1.

    Returns:
        Нормализованное значение, ограниченное диапазоном [0; 1].
    """
    if high <= low:
        return 0.0
    return min(max((value - low) / (high - low), 0.0), 1.0)


def heat_color(ratio: float, saturation: float, brightness: float) -> str:
    """Преобразовать нормализованное значение в цвет от зелёного до красного (HSV).

    Args:
        ratio: 0 — зелёный, 1 — красный.
        saturation: Насыщенность HSV темы.
        brightness: Яркость (value) HSV темы.

    Returns:
        Цвет в формате ``#rrggbb``.
    """
    hue = (GREEN_HUE + (RED_HUE - GREEN_HUE) * ratio) / 360
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


class AnalyticsEngine:
    """Агрегирует ``tbl_key_stats`` для тепловой карты и режима слабых клавиш."""

    def __init__(
        self,
        key_stats: KeyStatRepository,
        keys: KeyRepository,
        sessions: SessionRepository,
    ) -> None:
        """Сохранить репозитории.

        Args:
            key_stats: Статистика по клавишам.
            keys: Клавиши раскладок.
            sessions: Сессии (для периода «последняя сессия»).
        """
        self._key_stats = key_stats
        self._keys = keys
        self._sessions = sessions

    @staticmethod
    def since_for(period: Period, now: datetime | None = None) -> str | None:
        """Начало периода в виде ISO-строки для SQL.

        Args:
            period: Период.
            now: Текущее время (для тестов).

        Returns:
            Дата и время в формате ISO или ``None`` для «всё время» и «последняя сессия».
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
        """Собрать статистику каждой клавиши для тепловой карты.

        Выполняется в фоновом потоке: здесь используются только репозитории.

        Args:
            user_id: Идентификатор профиля.
            layout_name: Показываемая раскладка.
            metric: Раскрашиваемая метрика.
            period: Период статистики.
            now: Текущее время (для тестов).

        Returns:
            Данные тепловой карты.
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
        """Выбрать цветовую шкалу.

        Ошибки: фиксированная 0-30 %. Время реакции: от самой быстрой до самой
        медленной клавиши с достаточным количеством данных.

        Args:
            cells: Статистика клавиш.
            metric: Выбранная метрика.

        Returns:
            Минимум и максимум шкалы.
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
        """Доли ошибок проблемных клавиш для режима «Работа над ошибками».

        Args:
            user_id: Идентификатор профиля.
            layout_name: Раскладка упражнения.

        Returns:
            Базовый символ -> доля ошибок, только клавиши с ошибками.
        """
        data = self.build_heatmap(user_id, layout_name, Metric.ERROR_RATE, Period.ALL)
        return {c.key.key_char: c.error_rate for c in data.top if c.errors}


def top_problem_keys(cells, metric: Metric, limit: int = TOP_KEYS) -> list[KeyCell]:
    """Ранжировать клавиши по выбранной метрике, худшие первыми.

    Участвуют только клавиши с достаточным количеством данных; пробел исключён.

    Args:
        cells: Статистика клавиш.
        metric: Метрика ранжирования.
        limit: Количество клавиш.

    Returns:
        До ``limit`` худших клавиш.
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
