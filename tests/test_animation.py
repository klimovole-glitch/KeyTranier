"""Tests of the animation helpers (no window is needed)."""

import pytest

from keytrainer.views.animation import (
    ease_in_out,
    ease_out,
    lerp,
    mix_colors,
    shake_offset,
)


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
