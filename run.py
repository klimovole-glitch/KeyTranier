"""Start KeyTrainer Analytics with the Run button of VS Code (▷).

The same as ``py -m keytrainer``: the project folder is put on the import
path, so the package is found when this file is run directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keytrainer.app import main  # noqa: E402

if __name__ == "__main__":
    main()
