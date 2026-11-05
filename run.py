"""Запустить KeyTrainer Analytics кнопкой Run в VS Code (▷).

То же, что ``py -m keytrainer``: папка проекта добавляется в путь
импорта, поэтому пакет находится при прямом запуске этого файла.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keytrainer.app import main  # noqa: E402

if __name__ == "__main__":
    main()
