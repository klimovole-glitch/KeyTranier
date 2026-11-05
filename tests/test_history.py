"""История сессий и экспорт в CSV (ТЗ, п. 4.2.1, 6.1)."""

import csv
import time

from keytrainer.data.demo_data import generate
from keytrainer.data.repositories import SessionRepository
from keytrainer.engine.csv_exporter import ENCODING, HEADER, export_sessions
from keytrainer.engine.history_service import HistoryService


def test_history_summary_and_chart(database):
    """Сводка и график строятся по завершённым сессиям."""
    user_id = generate(database, "Тест", 30)
    data = HistoryService(SessionRepository(database)).load(user_id, "wpm", True)
    assert data.summary.total_sessions == 30
    assert data.summary.best_wpm == data.sessions[0].wpm
    assert len(data.chart.wpm) == 30
    assert list(data.chart.dates) == sorted(data.chart.dates)


def test_history_of_10000_sessions_loads_fast(database):
    """История из 10 000 сессий читается менее чем за 1 с (ТЗ, п. 6.1)."""
    user_id = generate(database, "Нагрузка", 10_000)
    start = time.perf_counter()
    data = HistoryService(SessionRepository(database)).load(user_id, "started_at", True)
    assert len(data.sessions) == 10_000
    assert time.perf_counter() - start < 1.0


def test_csv_opens_in_excel(database, tmp_path):
    """В CSV есть BOM, точки с запятой и русские заголовки."""
    user_id = generate(database, "Тест", 5)
    sessions = SessionRepository(database).get_by_user(user_id)
    path = tmp_path / "история.csv"
    assert export_sessions(path, sessions) == 5
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding=ENCODING, newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert tuple(rows[0]) == HEADER and len(rows) == 6
    assert "," in rows[1][2]  # десятичная запятая для русского Excel
