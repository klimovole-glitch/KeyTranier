"""Entry point: ``python -m keytrainer``.

On day 7 the entry point only prepares the database and prints a summary.
The Tkinter main window is attached on day 9.
"""

import logging

from keytrainer.config import DB_PATH, setup_logging
from keytrainer.data.database import Database
from keytrainer.data.repositories import (
    LayoutRepository,
    TextRepository,
    UserRepository,
    WordRepository,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize the database and print a short summary of its contents."""
    setup_logging()
    database = Database(DB_PATH)
    status = database.initialize()
    logger.info("Database ready: %s (%s)", DB_PATH, status.value)

    layouts = LayoutRepository(database)
    words = WordRepository(database)
    texts = TextRepository(database)
    users = UserRepository(database)

    print(f"База данных: {DB_PATH} [{status.value}]")
    for layout in layouts.get_all():
        print(
            f"  {layout.layout_name}: "
            f"{words.count_by_layout(layout.id)} слов, "
            f"{len(texts.get_by_layout(layout.id))} текстов"
        )
    print("Профили:", ", ".join(user.user_name for user in users.get_all()))


if __name__ == "__main__":
    main()
