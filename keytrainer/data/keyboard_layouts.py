"""Physical description of the supported keyboard layouts.

The module describes which character is printed on every key, which finger
should press it and where the key is drawn on the on-screen keyboard and on
the heatmap. Positions are measured in "key units": a regular key is 1x1.
"""

from dataclasses import dataclass

LAYOUT_RU = "RU_JCUKEN"
LAYOUT_EN = "EN_QWERTY"
LAYOUT_IDS = {LAYOUT_RU: 1, LAYOUT_EN: 2}

SPACE_CHAR = " "
SPACE_ROW = 4

# Row 0 - digits, 1 - top, 2 - home, 3 - bottom (ТЗ, п. 4.3.2, tbl_keys.row_num).
_ROWS: dict[str, tuple[str, str, str, str]] = {
    LAYOUT_RU: ("ё1234567890-=", "йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю."),
    LAYOUT_EN: ("`1234567890-=", "qwertyuiop[]", "asdfghjkl;'", "zxcvbnm,./"),
}

# Horizontal shift of each row, as on a real staggered keyboard.
_ROW_OFFSETS = (0.0, 1.5, 1.75, 2.25)

# Fingers for columns of the letter rows; columns 10+ belong to the right pinky.
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

# The digit row is shifted by one column: "ё/`" and "1" both use the left pinky.
_DIGIT_FINGERS = ("L_PINKY",) + _LETTER_FINGERS

# Characters typed with Shift -> the key that produces them.
_SHIFT_MAP: dict[str, dict[str, str]] = {
    LAYOUT_RU: dict(zip('!"№;%:?*()_+,', "1234567890-=.")),
    LAYOUT_EN: dict(zip('~!@#$%^&*()_+{}:"<>?', "`1234567890-=[];',./")),
}


@dataclass(frozen=True)
class KeySpec:
    """Description of one physical key before it is stored in the database."""

    key_char: str
    row_num: int
    finger: str
    pos_x: float
    pos_y: float


def _finger_for(row_num: int, column: int) -> str:
    """Return the recommended finger for a key.

    Args:
        row_num: Keyboard row (0-3).
        column: Index of the key inside its row.

    Returns:
        Finger code such as ``"L_PINKY"``.
    """
    fingers = _DIGIT_FINGERS if row_num == 0 else _LETTER_FINGERS
    return fingers[column] if column < len(fingers) else "R_PINKY"


def build_key_specs(layout_name: str) -> list[KeySpec]:
    """Build the list of keys for a layout, including the space bar.

    Args:
        layout_name: ``LAYOUT_RU`` or ``LAYOUT_EN``.

    Returns:
        Key specifications in drawing order.

    Raises:
        KeyError: If the layout is unknown.
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
    """Map a typed character to the key that produces it.

    Capital letters and Shift symbols are counted on their base key, so
    statistics for "А" and "а" are stored together.

    Args:
        char: Character from the exercise text.
        layout_name: Layout the exercise is typed on.

    Returns:
        Character of the base key (lowercase letter or unshifted symbol).
    """
    return _SHIFT_MAP[layout_name].get(char, char.lower())


def row_chars(layout_name: str, row_num: int) -> str:
    """Return characters printed on one row of a layout.

    Args:
        layout_name: ``LAYOUT_RU`` or ``LAYOUT_EN``.
        row_num: 0 - digits, 1 - top, 2 - home, 3 - bottom.

    Returns:
        Characters of the row from left to right.
    """
    return _ROWS[layout_name][row_num]


def is_typeable(char: str, layout_name: str) -> bool:
    """Check that a character can be typed on a layout.

    Args:
        char: One character.
        layout_name: Layout of the exercise.

    Returns:
        ``True`` for the space, keys of the layout, their capitals and
        Shift symbols.
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
