from __future__ import annotations
"""Контроллер экрана статистики.

Тепловая карта вычисляется в фоновом потоке (ТЗ, п. 4.1.1), поэтому окно
остаётся отзывчивым даже при тысячах сессий.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.controllers.app_state import AppState
from keytrainer.controllers.training_controller import TrainingController
from keytrainer.engine.analytics_engine import (
    AnalyticsEngine,
    HeatmapData,
    Metric,
    Period,
)
from keytrainer.utils.background import run_in_background
from keytrainer.views.screens.stats_screen import StatsScreen


class StatsController:
    """Фильтры, фоновое вычисление и кнопка слабых клавиш."""

    def __init__(
        self,
        root: tk.Tk,
        view: StatsScreen,
        state: AppState,
        analytics: AnalyticsEngine,
        training: TrainingController,
        show: Callable[[str], None],
    ) -> None:
        """Связать представление с движком аналитики.

        Args:
            root: Корневое окно Tk (для фонового помощника).
            view: Экран статистики.
            state: Активный профиль.
            analytics: Движок аналитики.
            training: Контроллер тренировки (запускает режим слабых клавиш).
            show: Функция переключения экранов.
        """
        self.root = root
        self.view = view
        self.state = state
        self.analytics = analytics
        self.training = training
        self._show = show
        self.metric = Metric.ERROR_RATE
        self.period = Period.ALL
        self.layout_name = training.params.layout_name
        self.data: HeatmapData | None = None
        self._request = 0
        view.callbacks.update(
            metric=self.set_metric,
            period=self.set_period,
            layout=self.set_layout,
            train=self.train_weak_keys,
        )
        training.weak_rates_provider = analytics.weak_key_rates

    def set_metric(self, metric: Metric) -> None:
        """Выбрать метрику тепловой карты.

        Args:
            metric: Новая метрика.
        """
        self.metric = metric
        self.refresh()

    def set_period(self, period: Period) -> None:
        """Выбрать период.

        Args:
            period: Новый период.
        """
        self.period = period
        self.refresh()

    def set_layout(self, layout_name: str) -> None:
        """Выбрать раскладку.

        Args:
            layout_name: Новая раскладка.
        """
        self.layout_name = layout_name
        self.refresh()

    def refresh(self) -> None:
        """Пересчитать тепловую карту в фоновом потоке."""
        self.view.show_filters(self.metric, self.period, self.layout_name)
        self.view.show_loading()
        self._request += 1
        request = self._request
        user_id = self.state.user.id
        metric, period, layout = self.metric, self.period, self.layout_name

        def job() -> HeatmapData:
            return self.analytics.build_heatmap(user_id, layout, metric, period)

        run_in_background(
            self.root,
            job,
            lambda data: self._on_data(request, data),
            lambda error: self.view.show_error(f"Не удалось построить карту: {error}"),
        )

    def _on_data(self, request: int, data: HeatmapData) -> None:
        """Показать вычисленные данные, если не был сделан более новый запрос.

        Args:
            request: Номер запроса.
            data: Данные тепловой карты.
        """
        if request != self._request:
            return  # пользователь изменил фильтры, пока работал поток
        self.data = data
        keys = list(self.training.keys_by_char(data.layout_name).values())
        self.view.show_data(data, keys)

    def train_weak_keys(self) -> None:
        """Запустить «Работа над ошибками» на проблемных клавишах карты."""
        if self.data is None or not any(c.errors for c in self.data.top):
            self.view.show_error("Пройдите несколько упражнений: ошибок пока нет")
            return
        rates = {c.key.key_char: c.error_rate for c in self.data.top if c.errors}
        self.training.start_weak_keys(rates, self.layout_name)
        self._show("training")

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Пересчитывать карту при каждом открытии экрана."""
        self.layout_name = self.training.params.layout_name
        self.refresh()

    def on_hide(self) -> None:
        """Скрыть всплывающую подсказку."""
        self.view.tooltip.hide()

    def handle_key(self, event: tk.Event) -> bool:
        """У экрана статистики нет собственных горячих клавиш.

        Args:
            event: Событие клавиши Tk.

        Returns:
            Всегда ``False``.
        """
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Отпускание клавиш здесь не нужно.

        Args:
            event: Событие клавиши Tk.
        """

    def status_hint(self) -> str:
        """Подсказки экрана статистики.

        Returns:
            Текст подсказки.
        """
        return "наведите на клавишу — подробности"
