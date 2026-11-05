from __future__ import annotations
"""Физическое описание поддерживаемых раскладок клавиатуры.

Модуль описывает, какой символ напечатан на каждой клавише, каким пальцем
её нужно нажимать и где клавиша рисуется на экранной клавиатуре и на
тепловой карте. Позиции измеряются в «единицах клавиши»: обычная клавиша 1x1.
"""

from dataclasses import dataclass

LAYOUT_RU = "RU_JCUKEN"
LAYOUT_EN = "EN_QWERTY"
LAYOUT_IDS = {LAYOUT_RU: 1, LAYOUT_EN: 2}

SPACE_CHAR = " "
SPACE_ROW = 4

# Ряд 0 - цифры, 1 - верхний, 2 - домашний, 3 - нижний (ТЗ, п. 4.3.2, tbl_keys.row_num).
_ROWS: dict[str, tuple[str, str, str, str]] = {
    LAYOUT_RU: ("ё1234567890-=", "йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю."),
    LAYOUT_EN: ("`1234567890-=", "qwertyuiop[]", "asdfghjkl;'", "zxcvbnm,./"),
}

# Горизонтальный сдвиг каждого ряда, как на настоящей ступенчатой клавиатуре.
_ROW_OFFSETS = (0.0, 1.5, 1.75, 2.25)

# Пальцы для столбцов буквенных рядов; столбцы 10+ относятся к правому мизинцу.
_LETTER_FINGERS = (
    "L_PINKY",
    "L_RING",
    "L_MIDDLE",
    "L_INDEX",
    "L_INDEX",
    "R_INDEX",
    "R_INDEX",
    "R_MIDDLE",
    "R_RING",
    "R_PINKY",
)

# Цифровой ряд сдвинут на один столбец: «ё/`» и «1» нажимаются левым мизинцем.
_DIGIT_FINGERS = ("L_PINKY",) + _LETTER_FINGERS

# Символы, вводимые с Shift -> клавиша, которая их выдаёт.
_SHIFT_MAP: dict[str, dict[str, str]] = {
    LAYOUT_RU: dict(zip('!"№;%:?*()_+,', "1234567890-=.")),
    LAYOUT_EN: dict(zip('~!@#$%^&*()_+{}:"<>?', "`1234567890-=[];',./")),
}


@dataclass(frozen=True)
class KeySpec:
    """Описание одной физической клавиши до сохранения в базе данных."""

    key_char: str
    row_num: int
    finger: str
    pos_x: float
    pos_y: float


def _finger_for(row_num: int, column: int) -> str:
    """Вернуть рекомендуемый палец для клавиши.

    Args:
        row_num: Ряд клавиатуры (0-3).
        column: Индекс клавиши внутри ряда.

    Returns:
        Код пальца, например ``"L_PINKY"``.
    """
    fingers = _DIGIT_FINGERS if row_num == 0 else _LETTER_FINGERS
    return fingers[column] if column < len(fingers) else "R_PINKY"


def build_key_specs(layout_name: str) -> list[KeySpec]:
    """Построить список клавиш раскладки, включая пробел.

    Args:
        layout_name: ``LAYOUT_RU`` или ``LAYOUT_EN``.

    Returns:
        Описания клавиш в порядке отрисовки.

    Raises:
        KeyError: Если раскладка неизвестна.
    """
    specs = []
    for row_num, row_chars in enumerate(_ROWS[layout_name]):
        for column, char in enumerate(row_chars):
            specs.append(
                KeySpec(
                    key_char=char,
                    row_num=row_num,
                    finger=_finger_for(row_num, column),
                    pos_x=_ROW_OFFSETS[row_num] + column,
                    pos_y=float(row_num),
                )
            )
    specs.append(KeySpec(SPACE_CHAR, SPACE_ROW, "THUMB", 4.0, float(SPACE_ROW)))
    return specs


def base_key_char(char: str, layout_name: str) -> str:
    """Сопоставить введённый символ клавише, которая его выдаёт.

    Заглавные буквы и символы с Shift учитываются на своей базовой клавише,
    поэтому статистика для «А» и «а» хранится вместе.

    Args:
        char: Символ из текста упражнения.
        layout_name: Раскладка, на которой набирается упражнение.

    Returns:
        Символ базовой клавиши (строчная буква или символ без Shift).
    """
    return _SHIFT_MAP[layout_name].get(char, char.lower())


def row_chars(layout_name: str, row_num: int) -> str:
    """Вернуть символы, напечатанные на одном ряду раскладки.

    Args:
        layout_name: ``LAYOUT_RU`` или ``LAYOUT_EN``.
        row_num: 0 - цифры, 1 - верхний, 2 - домашний, 3 - нижний.

    Returns:
        Символы ряда слева направо.
    """
    return _ROWS[layout_name][row_num]


def is_typeable(char: str, layout_name: str) -> bool:
    """Проверить, можно ли набрать символ на раскладке.

    Args:
        char: Один символ.
        layout_name: Раскладка упражнения.

    Returns:
        ``True`` для пробела, клавиш раскладки, их заглавных вариантов и
        символов с Shift.
    """
    if char == SPACE_CHAR:
        return True
    return any(base_key_char(char, layout_name) in row for row in _ROWS[layout_name])


FINGER_NAMES = {
    "L_PINKY": "левый мизинец",
    "L_RING": "левый безымянный",
    "L_MIDDLE": "левый средний",
    "L_INDEX": "левый указательный",
    "R_INDEX": "правый указательный",
    "R_MIDDLE": "правый средний",
    "R_RING": "правый безымянный",
    "R_PINKY": "правый мизинец",
    "THUMB": "большой палец",
}
