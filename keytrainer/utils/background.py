"""Running slow work in a background thread (ТЗ, п. 4.1.1, асинхронность).

Tkinter widgets may be touched only from the main thread, so the worker
puts its result into a queue and the main thread polls the queue with
``after()`` and then calls the callback.
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
    """Run ``job`` in a thread and deliver its result to the main thread.

    Args:
        root: Any widget (for ``after``).
        job: Slow function without arguments.
        on_done: Called in the main thread with the result.
        on_error: Called in the main thread with the exception.

    Returns:
        Started daemon thread.
    """
    results: queue.Queue = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put((True, job()))
        except Exception as error:  # noqa: BLE001 - reported to the user
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
