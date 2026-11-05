"""Импорт истории из CSV (круговой обмен с экспортом)."""

import pytest

from keytrainer.data.demo_data import generate
from keytrainer.data.exceptions import ValidationError
from keytrainer.data.repositories import SessionRepository
from keytrainer.engine.csv_exporter import ENCODING, HEADER, export_sessions
from keytrainer.engine.csv_importer import read_sessions
from keytrainer.engine.history_service import HistoryService


def _service(database):
    return HistoryService(SessionRepository(database))


def test_export_then_import_restores_sessions(database, tmp_path):
    """Сессии, экспортированные из одного профиля, импортируются в пустой."""
    source = generate(database, "Источник", 8)
    repo = SessionRepository(database)
    path = tmp_path / "история.csv"
    export_sessions(path, repo.get_by_user(source))
    target = generate(database, "Цель", 0)
    summary = _service(database).import_csv(path, target, 1)
    assert (summary.added, summary.duplicates, summary.invalid) == (8, 0, 0)
    original = {s.started_at[:16]: s for s in repo.get_by_user(source)}
    for session in repo.get_by_user(target):
        twin = original[session.started_at[:16]]
        assert session.exercise_mode == twin.exercise_mode
        assert session.wpm == pytest.approx(twin.wpm, abs=0.05)
        assert session.errors_count == twin.errors_count


def test_second_import_skips_duplicates(database, tmp_path):
    """Повторный импорт того же файла во второй раз ничего не добавляет."""
    user = generate(database, "Тест", 5)
    path = tmp_path / "история.csv"
    export_sessions(path, SessionRepository(database).get_by_user(user))
    summary = _service(database).import_csv(path, user, 1)
    assert (summary.added, summary.duplicates) == (0, 5)


def test_broken_rows_are_counted_not_fatal(database, tmp_path):
    """Плохая строка пропускается, хорошие строки всё равно импортируются."""
    path = tmp_path / "x.csv"
    good = "01.11.2026 10:00;случайные слова;40,5;200,0;2,0;3;60,0;300;да"
    bad = "вчера;случайные слова;abc;1;1;1;1;1;да"
    path.write_text(
        ";".join(HEADER) + f"\n{good}\n{bad}\n\n", encoding=ENCODING
    )
    user = generate(database, "Тест", 0)
    result = read_sessions(path, user, 1)
    assert len(result.sessions) == 1 and result.invalid == 1
    assert result.sessions[0].wpm == 40.5


def test_foreign_file_is_rejected(database, tmp_path):
    """CSV с другими заголовками вызывает ValidationError."""
    path = tmp_path / "other.csv"
    path.write_text("a;b;c\n1;2;3\n", encoding=ENCODING)
    with pytest.raises(ValidationError):
        read_sessions(path, 1, 1)
