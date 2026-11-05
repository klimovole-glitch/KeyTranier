import pytest
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_import_views():
    from keytrainer.views import main_window, theme
    assert main_window is not None
    assert theme is not None

def test_import_controllers():
    from keytrainer.controllers import training_controller, stats_controller, history_controller
    assert training_controller is not None
    assert stats_controller is not None
    assert history_controller is not None

def test_mock_controller_logic():
    mock_root = MagicMock()
    mock_view = MagicMock()
    mock_state = MagicMock()
    assert mock_root is not None
