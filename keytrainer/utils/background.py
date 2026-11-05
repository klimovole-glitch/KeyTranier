from __future__ import annotations
"""Запуск медленной работы в фоновом потоке (ТЗ, п. 4.1.1, асинхронность).

К виджетам Tkinter можно обращаться только из главного потока, поэтому
рабочий поток кладёт результат в очередь, а главный поток опрашивает
очередь через ``after()`` и затем вызывает обратный вызов.
"""

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)
POLL_MS = 40


def run_in_background(
    root: tk.Misc,
    job: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[Exception], None],
) -> threading.Thread:
    """Выполнить ``job`` в потоке и передать результат главному потоку.

    Args:
        root: Любой виджет (для ``after``).
        job: Медленная функция без аргументов.
        on_done: Вызывается в главном потоке с результатом.
        on_error: Вызывается в главном потоке с исключением.

    Returns:
        Запущенный поток-демон.
    """
    results: queue.Queue = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put((True, job()))
        except Exception as error:  # noqa: BLE001 - сообщается пользователю
            logger.exception("Background job failed")
            results.put((False, error))

    def poll() -> None:
        try:
            ok, value = results.get_nowait()
        except queue.Empty:
            root.after(POLL_MS, poll)
            return
        (on_done if ok else on_error)(value)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    root.after(POLL_MS, poll)
    return thread
