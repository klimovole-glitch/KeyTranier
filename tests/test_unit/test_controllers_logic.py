import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_training_controller_init():
    from keytrainer.controllers.training_controller import TrainingController
    
    # Создаем 7 моков (все аргументы, которые нужны контроллеру)
    mock_root = MagicMock()
    mock_view = MagicMock()
    mock_state = MagicMock()
    mock_generator = MagicMock()
    mock_session_service = MagicMock()
    mock_keys = MagicMock()
    mock_texts = MagicMock()
    
    # Передаем все 7 аргументов
    controller = TrainingController(
        mock_root, mock_view, mock_state, mock_generator, mock_session_service, mock_keys, mock_texts
    )
    assert controller is not None

def test_history_controller_init():
    from keytrainer.controllers.history_controller import HistoryController
    mock_root = MagicMock()
    mock_view = MagicMock()
    mock_state = MagicMock()
    mock_service = MagicMock()
    controller = HistoryController(mock_root, mock_view, mock_state, mock_service)
    assert controller is not None

def test_stats_controller_init():
    from keytrainer.controllers.stats_controller import StatsController
    mock_root = MagicMock()
    mock_view = MagicMock()
    mock_state = MagicMock()
    mock_analytics = MagicMock()
    mock_training = MagicMock()
    mock_show = MagicMock()
    controller = StatsController(mock_root, mock_view, mock_state, mock_analytics, mock_training, mock_show)
    assert controller is not None
