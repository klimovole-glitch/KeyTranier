"""Controller of the statistics screen.

The heatmap is calculated in a background thread (ТЗ, п. 4.1.1), so the
window stays responsive even with thousands of sessions.
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
    """Filters, background calculation and the weak keys button."""

    def __init__(
        self,
        root: tk.Tk,
        view: StatsScreen,
        state: AppState,
        analytics: AnalyticsEngine,
        training: TrainingController,
        show: Callable[[str], None],
    ) -> None:
        """Connect the view with the analytics engine.

        Args:
            root: Tk root (for the background helper).
            view: Statistics screen.
            state: Active profile.
            analytics: Analytics engine.
            training: Training controller (starts the weak keys mode).
            show: Function that switches screens.
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
        """Choose the metric of the heatmap.

        Args:
            metric: New metric.
        """
        self.metric = metric
        self.refresh()

    def set_period(self, period: Period) -> None:
        """Choose the period.

        Args:
            period: New period.
        """
        self.period = period
        self.refresh()

    def set_layout(self, layout_name: str) -> None:
        """Choose the layout.

        Args:
            layout_name: New layout.
        """
        self.layout_name = layout_name
        self.refresh()

    def refresh(self) -> None:
        """Recalculate the heatmap in a background thread."""
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
        """Show calculated data unless a newer request was made.

        Args:
            request: Number of the request.
            data: Heatmap data.
        """
        if request != self._request:
            return  # the user changed filters while the thread was working
        self.data = data
        keys = list(self.training.keys_by_char(data.layout_name).values())
        self.view.show_data(data, keys)

    def train_weak_keys(self) -> None:
        """Start "Работа над ошибками" on the problem keys of the map."""
        if self.data is None or not any(c.errors for c in self.data.top):
            self.view.show_error("Пройдите несколько упражнений: ошибок пока нет")
            return
        rates = {c.key.key_char: c.error_rate for c in self.data.top if c.errors}
        self.training.start_weak_keys(rates, self.layout_name)
        self._show("training")

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """Recalculate the map every time the screen is opened."""
        self.layout_name = self.training.params.layout_name
        self.refresh()

    def on_hide(self) -> None:
        """Hide the tooltip."""
        self.view.tooltip.hide()

    def handle_key(self, event: tk.Event) -> bool:
        """The statistics screen has no own hot keys.

        Args:
            event: Tk key event.

        Returns:
            Always ``False``.
        """
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Key releases are not needed here.

        Args:
            event: Tk key event.
        """

    def status_hint(self) -> str:
        """Hints of the statistics screen.

        Returns:
            Hint text.
        """
        return "наведите на клавишу — подробности"
