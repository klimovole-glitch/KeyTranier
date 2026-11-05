"""Ctrl+P должен ставить на паузу в любой раскладке клавиатуры."""

from types import SimpleNamespace

from keytrainer.controllers.training_controller import is_pause_key


def _event(keysym: str, char: str = "", keycode: int = 0):
    return SimpleNamespace(keysym=keysym, char=char, keycode=keycode)


def test_latin_and_russian_layouts():
    """P и З (одна и та же клавиша) обе ставят на паузу."""
    assert is_pause_key(_event("p"))
    assert is_pause_key(_event("P"))
    assert is_pause_key(_event("Cyrillic_ze"))


def test_control_character():
    """Windows может сообщать Ctrl+P как управляющий символ 0x10."""
    assert is_pause_key(_event("??", char="\x10"))


def test_other_keys_do_not_pause():
    """Ctrl+O не является паузой."""
    assert not is_pause_key(_event("o", char="\x0f", keycode=79))
