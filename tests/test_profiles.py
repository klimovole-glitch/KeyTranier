"""Правила профилей, проверка настроек и загрузка TXT (ТЗ, п. 4.2.1)."""

import pytest

from keytrainer.data.exceptions import DuplicateNameError, ValidationError
from keytrainer.data.repositories import SessionRepository, UserRepository
from keytrainer.engine.profile_service import ProfileService
from keytrainer.utils.text_files import read_text_file


@pytest.fixture
def profiles(database):
    """Сервис профилей поверх тестовой базы данных.

    Args:
        database: Инициализированная тестовая база данных.

    Returns:
        Сервис профилей.
    """
    return ProfileService(UserRepository(database), SessionRepository(database))


def test_profile_crud_rules(profiles):
    """Профили создаются, переименовываются, удаляются; последний остаётся."""
    olga = profiles.create("Ольга", 1)
    with pytest.raises(DuplicateNameError):
        profiles.create("Ольга", 1)
    profiles.rename(olga.id, "Ольга К.")
    guest_id = profiles.list_profiles()[0].user.id
    assert profiles.delete(guest_id, active_id=guest_id) == olga.id
    with pytest.raises(ValidationError):
        profiles.delete(olga.id, active_id=olga.id)


def test_settings_validation(profiles):
    """Размер шрифта вне диапазона 14-32 отклоняется; значения по умолчанию можно восстановить."""
    user = profiles.list_profiles()[0].user
    user.font_size = 50
    with pytest.raises(ValidationError):
        profiles.save_settings(user)
    restored = profiles.with_defaults(user)
    assert restored.font_size == 18 and restored.user_name == user.user_name


def test_txt_in_cp1251_is_read(tmp_path):
    """Файл, сохранённый Блокнотом Windows в cp1251, читается правильно."""
    path = tmp_path / "text.txt"
    path.write_bytes("Привет, мир".encode("cp1251"))
    assert read_text_file(path) == "Привет, мир"
