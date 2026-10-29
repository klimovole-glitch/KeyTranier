"""Ctrl+P must pause in any keyboard layout."""

from types import SimpleNamespace

from keytrainer.controllers.training_controller import is_pause_key


def _event(keysym: str, char: str = "", keycode: int = 0):
    return SimpleNamespace(keysym=keysym, char=char, keycode=keycode)


def test_latin_and_russian_layouts():
    """P and З (the same key) both pause."""
    assert is_pause_key(_event("p"))
    assert is_pause_key(_event("P"))
    assert is_pause_key(_event("Cyrillic_ze"))


def test_control_character():
    """Windows may report Ctrl+P as the control character 0x10."""
    assert is_pause_key(_event("??", char="\x10"))


def test_other_keys_do_not_pause():
    """Ctrl+O is not a pause."""
    assert not is_pause_key(_event("o", char="\x0f", keycode=79))
