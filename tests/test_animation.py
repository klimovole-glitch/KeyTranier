"""Tests of the animation helpers (no window is needed)."""

from datetime import datetime, timedelta

import pytest

from keytrainer.engine.history_service import ChartData
from keytrainer.views.animation import (
    ease_in_out,
    ease_out,
    lerp,
    mix_colors,
    shake_offset,
)
from keytrainer.views.screens.history_screen import grow_series


@pytest.mark.parametrize("curve", [ease_out, ease_in_out])
def test_easing_starts_at_zero_and_ends_at_one(curve):
    """Every curve goes from 0 to 1 and never backwards."""
    values = [curve(i / 20) for i in range(21)]
    assert values[0] == pytest.approx(0)
    assert values[-1] == pytest.approx(1)
    assert values == sorted(values)


def test_easing_clamps_progress():
    """Progress outside 0..1 does not break the curve."""
    assert ease_out(-1) == 0
    assert ease_out(2) == 1


def test_mix_colors_ends_and_middle():
    """Blending black and white gives grey in the middle."""
    assert mix_colors("#000000", "#ffffff", 0) == "#000000"
    assert mix_colors("#000000", "#ffffff", 1) == "#ffffff"
    assert mix_colors("#000000", "#ffffff", 0.5) == "#808080"


def test_lerp():
    """Interpolation of numbers."""
    assert lerp(10, 20, 0.25) == 12.5


def test_shake_returns_to_place():
    """The shake starts and ends without an offset and decays."""
    assert shake_offset(0) == pytest.approx(0)
    assert shake_offset(1) == pytest.approx(0, abs=1e-9)
    first = max(abs(shake_offset(i / 100)) for i in range(0, 34))
    last = max(abs(shake_offset(i / 100)) for i in range(67, 100))
    assert first > last


def _chart(count: int) -> ChartData:
    start = datetime(2026, 10, 1)
    return ChartData(
        dates=[start + timedelta(days=i) for i in range(count)],
        wpm=[30.0 + i for i in range(count)],
        error_rate=[5.0] * count,
    )


def test_grow_series_full_and_partial():
    """The chart line grows smoothly with an interpolated last point."""
    data = _chart(5)
    xs, wpm, _errors = grow_series(data, 1.0)
    assert len(xs) == 5 and wpm[-1] == 34
    xs, wpm, _errors = grow_series(data, 0.5)
    assert len(xs) == 3 and wpm[-1] == 32
    xs, wpm, _errors = grow_series(data, 0.6)
    assert len(xs) == 4
    assert wpm[-1] == pytest.approx(32.4)
