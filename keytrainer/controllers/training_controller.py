"""Controller of the training and results screens.

Receives key events from the main window, filters them (ТЗ, п. 4.1.4),
passes printable characters to :class:`TypingSession`, repaints the view
and saves the finished session through :class:`SessionService`.
"""

import logging
import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from keytrainer.controllers.app_state import AppState
from keytrainer.data.keyboard_layouts import (
    FINGER_NAMES,
    LAYOUT_EN,
    LAYOUT_IDS,
    LAYOUT_RU,
    base_key_char,
    is_typeable,
)
from keytrainer.data.models import ExerciseMode, Key, User
from keytrainer.data.repositories import KeyRepository, TextRepository
from keytrainer.engine.exercise_generator import (
    Exercise,
    ExerciseGenerator,
    ExerciseParams,
)
from keytrainer.engine.session_service import SessionResult, SessionService
from keytrainer.engine.typing_session import SessionState, TypingSession
from keytrainer.views.dialogs.custom_text_dialog import CustomTextDialog
from keytrainer.views.screens.results_screen import ResultsScreen
from keytrainer.views.screens.training_screen import TrainingScreen

logger = logging.getLogger(__name__)

IGNORED_KEYSYMS = frozenset(
    {
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Caps_Lock",
        "Meta_L",
        "Meta_R",
        "Super_L",
        "Super_R",
        "Win_L",
        "Win_R",
        "ISO_Next_Group",
        "ISO_Prev_Group",
        "Num_Lock",
        "Menu",
    }
)
CONTROL_MASK = 0x0004
VK_P = 80  # Windows virtual key code of the P key
AUTOREPEAT_WINDOW_MS = 20
TICK_MS = 200
LAYOUT_BY_ID = {layout_id: name for name, layout_id in LAYOUT_IDS.items()}
WeakRatesProvider = Callable[[int, str], dict[str, float]]


def is_pause_key(event: tk.Event) -> bool:
    """Check for Ctrl+P in any keyboard layout.

    With the Russian layout the key P gives "з" (``Cyrillic_ze``), and on
    Windows Tk sometimes reports the control character instead of the
    letter, so the physical key code (VK_P = 80) is checked as well.

    Args:
        event: Tk key event with Ctrl pressed.

    Returns:
        ``True`` for Ctrl+P / Ctrl+З.
    """
    if event.keysym.lower() in ("p", "cyrillic_ze"):
        return True
    if event.char == "\x10":  # Ctrl+P as a control character
        return True
    return sys.platform == "win32" and event.keycode == VK_P


class TrainingController:
    """Life cycle of an exercise: generate, type, pause, finish, save."""

    def __init__(
        self,
        root: tk.Tk,
        view: TrainingScreen,
        state: AppState,
        generator: ExerciseGenerator,
        session_service: SessionService,
        keys: KeyRepository,
        texts: TextRepository,
    ) -> None:
        """Connect the view with the engine.

        Args:
            root: Tk root (timers and focus events).
            view: Training screen.
            state: Active profile.
            generator: Exercise generator.
            session_service: Saves sessions.
            keys: Key repository (on-screen keyboard and finger hints).
            texts: Text repository (user texts).
        """
        self.root = root
        self.view = view
        self.state = state
        self.generator = generator
        self.session_service = session_service
        self._keys_repo = keys
        self._texts = texts
        self.on_finished: Callable[[SessionResult], None] | None = None
        self.on_layout_changed: Callable[[str], None] | None = None
        self.weak_rates_provider: WeakRatesProvider | None = None
        self.params = self._params_for(state.user)
        self.exercise: Exercise | None = None
        self.typing: TypingSession | None = None
        self.started_at: datetime | None = None
        self._keys_cache: dict[str, dict[str, Key]] = {}
        self._held: set[int] = set()
        self._release_jobs: dict[int, str] = {}
        self._tick_job: str | None = None
        self._visible = False
        view.callbacks.update(
            mode=self.set_mode,
            layout=self.toggle_layout,
            length=self.set_length,
            toggle=self.toggle_option,
            level=self.set_level,
            start=self.start,
            abort=self.abort,
            new=self.new_exercise,
            resume=self.resume,
        )
        root.bind("<FocusOut>", self._on_focus_out, add="+")
        state.subscribe(self.apply_user)

    # ----------------------------------------------------------- params
    @staticmethod
    def _params_for(user: User) -> ExerciseParams:
        """Build default parameters from the profile settings.

        Args:
            user: Active profile.

        Returns:
            Parameters with the profile's layout and mode.
        """
        mode = user.default_mode
        if mode in (ExerciseMode.CUSTOM, ExerciseMode.WEAK_KEYS):
            mode = ExerciseMode.WORDS
        layout = LAYOUT_BY_ID.get(user.layout_id or 0, LAYOUT_RU)
        return ExerciseParams(mode=mode, layout_name=layout, word_count=25)

    def apply_user(self, user: User) -> None:
        """Reset parameters after a profile switch or new settings.

        Args:
            user: Active profile.
        """
        self.params = self._params_for(user)
        self.new_exercise()

    def _update_params(self, **changes) -> None:
        """Change parameters and generate a new exercise.

        Args:
            **changes: Fields of :class:`ExerciseParams`.
        """
        self.params = replace(self.params, **changes)
        self.new_exercise()

    def set_mode(self, mode: ExerciseMode) -> None:
        """Choose an exercise mode.

        Args:
            mode: New mode.
        """
        if mode == ExerciseMode.CUSTOM:
            self.ask_custom_text()
        elif mode == ExerciseMode.WEAK_KEYS:
            self.start_weak_keys()
        else:
            self._update_params(mode=mode)

    def toggle_layout(self) -> None:
        """Switch between ЙЦУКЕН and QWERTY."""
        layout = LAYOUT_EN if self.params.layout_name == LAYOUT_RU else LAYOUT_RU
        self._update_params(layout_name=layout, weak_key_rates={})
        if self.params.mode == ExerciseMode.WEAK_KEYS:
            self.start_weak_keys()

    def set_length(self, words: int | None, seconds: int | None) -> None:
        """Choose the length in words or the time limit.

        Args:
            words: Number of words, or ``None``.
            seconds: Time limit, or ``None``.
        """
        if words is not None:
            self._update_params(word_count=words, time_limit_sec=None)
        else:
            self._update_params(time_limit_sec=seconds)

    def toggle_option(self, name: str) -> None:
        """Switch capitals, digits or punctuation.

        Args:
            name: Field name of :class:`ExerciseParams`.
        """
        self._update_params(**{name: not getattr(self.params, name)})

    def set_level(self, level: int) -> None:
        """Choose the level of the "Изучение клавиш" mode.

        Args:
            level: Level 1-5.
        """
        self._update_params(level=level)

    def ask_custom_text(self) -> None:
        """Ask for the user's text, save it and start the exercise."""
        layout_id = LAYOUT_IDS[self.params.layout_name]
        saved = [t.title for t in self._texts.get_by_layout(layout_id, custom=True)]
        dialog = CustomTextDialog(self.root, self.view.theme, saved)
        dialog.show_modal()
        if dialog.result is None:
            return
        title, content = dialog.result
        self._texts.create(layout_id, title, content, is_custom=True)
        self._update_params(mode=ExerciseMode.CUSTOM, custom_text=content)

    def start_weak_keys(
        self, rates: dict[str, float] | None = None, layout_name: str | None = None
    ) -> None:
        """Start the "Работа над ошибками" mode.

        Args:
            rates: Error rate of problem keys; if ``None`` they are taken
                from the statistics through :attr:`weak_rates_provider`.
            layout_name: Layout of the exercise, ``None`` keeps the current one.
        """
        layout_name = layout_name or self.params.layout_name
        if rates is None and self.weak_rates_provider is not None:
            rates = self.weak_rates_provider(self.state.user.id, layout_name)
        self._update_params(
            mode=ExerciseMode.WEAK_KEYS,
            layout_name=layout_name,
            weak_key_rates=rates or {},
        )

    # --------------------------------------------------------- exercise
    def keys_by_char(self, layout_name: str) -> dict[str, Key]:
        """Return keys of a layout by their character (cached).

        Args:
            layout_name: Layout name.

        Returns:
            Map character -> key.
        """
        if layout_name not in self._keys_cache:
            keys = self._keys_repo.get_by_layout(LAYOUT_IDS[layout_name])
            self._keys_cache[layout_name] = {k.key_char: k for k in keys}
        return self._keys_cache[layout_name]

    def new_exercise(self) -> None:
        """Generate a new exercise with the current parameters."""
        self.exercise = self.generator.generate(self.params)
        self.params = self.exercise.params
        self.restart()
        self.view.show_message("; ".join(self.exercise.warnings))
        if self.on_layout_changed:
            self.on_layout_changed(self.params.layout_name)

    def restart(self) -> None:
        """Start the same text again (Tab)."""
        if self.exercise is None:
            return
        self._stop_tick()
        self.typing = TypingSession(
            self.exercise.text, self.params.layout_name, self.params.time_limit_sec
        )
        self.started_at = None
        view = self.view
        view.show_params(self.params)
        view.show_text(self.exercise.text)
        view.show_source(self.exercise.source)
        view.show_metrics(None)
        view.show_pause(False)
        view.set_running(False)
        show_digits = self.params.digits or any(c.isdigit() for c in self.exercise.text)
        keys = list(self.keys_by_char(self.params.layout_name).values())
        view.set_keyboard(keys, show_digits)
        view.show_message("")
        self._show_next_key()

    def start(self) -> None:
        """Button "старт": the timer starts with the first key press."""
        self.view.show_message("начинайте печатать — время пойдет с первой клавиши")

    def abort(self) -> None:
        """Button "прервать" / Enter: stop and save as not completed."""
        self._finish(completed=False)

    def _finish(self, completed: bool) -> None:
        """Finish the session, save it and show the results.

        Args:
            completed: Whether the exercise was fully done.
        """
        typing = self.typing
        if typing is None or typing.state == SessionState.READY:
            return
        self._stop_tick()
        typing.finish(completed)
        result = self.session_service.save(
            typing, self.state.user.id, self.params.mode, self.started_at
        )
        logger.info("Session %s saved", result.session.id)
        if completed and self.on_finished:
            self.on_finished(result)
        else:
            self.restart()
            self.view.show_message("сессия прервана и сохранена в истории")

    # ------------------------------------------------------------- keys
    def _is_autorepeat(self, keycode: int) -> bool:
        """Detect auto-repeat of a held key.

        Windows repeats KeyPress without KeyRelease; X11 sends a
        KeyRelease immediately followed by KeyPress. Both cases are
        recognized: a release is confirmed only after a short delay.

        Args:
            keycode: Hardware key code of the press.

        Returns:
            ``True`` if the press is an auto-repeat.
        """
        job = self._release_jobs.pop(keycode, None)
        if job is not None:
            self.root.after_cancel(job)
            return True
        if keycode in self._held:
            return True
        self._held.add(keycode)
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Confirm a key release after :data:`AUTOREPEAT_WINDOW_MS`.

        Args:
            event: Tk key event.
        """
        keycode = event.keycode

        def release() -> None:
            self._release_jobs.pop(keycode, None)
            self._held.discard(keycode)

        self._release_jobs[keycode] = self.root.after(AUTOREPEAT_WINDOW_MS, release)

    def handle_key(self, event: tk.Event) -> bool:
        """Process a key press on the training screen.

        Args:
            event: Tk key event.

        Returns:
            ``True`` if the key was consumed.
        """
        if self._is_autorepeat(event.keycode) or event.keysym in IGNORED_KEYSYMS:
            return True
        if event.state & CONTROL_MASK:
            if is_pause_key(event):
                self.toggle_pause()
            return True
        handlers = {"Tab": self.restart, "Return": self.abort, "KP_Enter": self.abort}
        if event.keysym in handlers:
            handlers[event.keysym]()
            return True
        if self.typing is None or self.typing.is_finished:
            return True
        if self.typing.state == SessionState.PAUSED:
            self.resume()  # the key that ends a pause is not counted
            return True
        if event.keysym == "BackSpace":
            self._backspace()
            return True
        if event.char and event.char.isprintable():
            self._type_char(event.char)
            return True
        return False

    def _type_char(self, char: str) -> None:
        """Pass a printable character to the session and repaint.

        Args:
            char: Typed character.
        """
        if not is_typeable(char, self.params.layout_name):
            self.view.show_message(
                "переключите раскладку ОС на "
                + ("русскую" if self.params.layout_name == LAYOUT_RU else "английскую"),
                is_error=True,
            )
            return
        if self.typing.state == SessionState.READY:
            self.started_at = datetime.now()
            self.view.set_running(True)
            self.view.show_message("")
            self._schedule_tick()
        result = self.typing.press(char)
        self.view.mark(result.position, result.is_correct)
        self.view.key_feedback(
            base_key_char(char, self.params.layout_name), result.is_correct
        )
        if not result.is_correct:
            self.view.error_feedback()
        if result.finished:
            self._finish(completed=True)
            return
        self.view.move_caret(self.typing.position)
        self._show_next_key()

    def _backspace(self) -> None:
        """Erase the last typed character on the screen."""
        position = self.typing.backspace()
        self.view.mark(position, None)
        self.view.move_caret(position)
        self._show_next_key()

    def _show_next_key(self) -> None:
        """Highlight the next key and the finger, if the hint is on."""
        typing = self.typing
        if typing is None or typing.is_finished or not self.state.user.show_finger_hint:
            self.view.show_next_key(None, None)
            return
        char = typing.text[typing.position]
        base = base_key_char(char, self.params.layout_name)
        key = self.keys_by_char(self.params.layout_name).get(base)
        if key is None:
            self.view.show_next_key(None, None)
            return
        finger = FINGER_NAMES[key.finger]
        if char != base:
            finger += " + Shift"
        self.view.show_next_key(base, finger)

    # ------------------------------------------------------ pause, time
    def toggle_pause(self) -> None:
        """Pause or resume the exercise (Ctrl+P)."""
        if self.typing is None:
            return
        if self.typing.state == SessionState.READY:
            self.view.show_message("пауза включается, когда упражнение уже идёт")
            return
        if self.typing.state == SessionState.RUNNING:
            self.typing.pause()
            self.view.show_pause(True)
        elif self.typing.state == SessionState.PAUSED:
            self.resume()

    def resume(self) -> None:
        """Continue after a pause."""
        if self.typing is not None and self.typing.state == SessionState.PAUSED:
            self.typing.resume()
            self.view.show_pause(False)

    def _on_focus_out(self, event: tk.Event) -> None:
        """Auto-pause when the window loses focus (profile setting).

        Args:
            event: Tk focus event.
        """
        if event.widget is not self.root:
            return
        self._held.clear()
        if (
            self._visible
            and self.state.user.auto_pause
            and self.typing is not None
            and self.typing.state == SessionState.RUNNING
        ):
            self.toggle_pause()

    def _schedule_tick(self) -> None:
        """Start the timer that refreshes metrics."""
        self._stop_tick()
        self._tick_job = self.root.after(TICK_MS, self._tick)

    def _stop_tick(self) -> None:
        """Stop the metrics timer."""
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None

    def _tick(self) -> None:
        """Refresh metrics; finish a timed exercise when time is over."""
        self._tick_job = None
        typing = self.typing
        if typing is None or typing.is_finished:
            return
        self.view.show_metrics(typing.snapshot())
        if typing.time_limit_sec:
            self.view.show_time_left(typing.time_limit_sec - typing.elapsed_sec)
            if typing.is_time_over:
                self._finish(completed=True)
                return
        self._tick_job = self.root.after(TICK_MS, self._tick)

    # ------------------------------------------------- ScreenController
    def on_show(self) -> None:
        """The training screen became visible."""
        self._visible = True
        self._held.clear()  # releases may have gone to another screen
        self.view.move_caret(self.typing.position if self.typing else 0)

    def on_hide(self) -> None:
        """Another screen is shown: pause a running exercise."""
        self._visible = False
        if self.typing is not None and self.typing.state == SessionState.RUNNING:
            self.toggle_pause()

    def status_hint(self) -> str:
        """Hot keys of the training screen.

        Returns:
            Hint text.
        """
        return "tab — заново   ·   enter — завершить   ·   ctrl+p — пауза"


class ResultsController:
    """Keys and buttons of the results card."""

    def __init__(
        self,
        view: ResultsScreen,
        training: TrainingController,
        show: Callable[[str], None],
    ) -> None:
        """Connect the card with the training controller.

        Args:
            view: Results screen.
            training: Training controller (repeat / new exercise).
            show: Function that switches screens.
        """
        self.view = view
        self.training = training
        self._show = show
        view.callbacks.update(repeat=self.repeat, new=self.new, stats=self.stats)

    def repeat(self) -> None:
        """Type the same text again."""
        self.training.restart()
        self._show("training")

    def new(self) -> None:
        """Generate a new exercise."""
        self.training.new_exercise()
        self._show("training")

    def stats(self) -> None:
        """Open the statistics screen."""
        self.training.new_exercise()
        self._show("stats")

    def on_show(self) -> None:
        """Start the appearance of the result buttons."""
        self.view.on_shown()

    def on_hide(self) -> None:
        """Nothing to clean up."""

    def handle_key(self, event: tk.Event) -> bool:
        """Tab — repeat, Enter — new exercise.

        Args:
            event: Tk key event.

        Returns:
            ``True`` if the key was consumed.
        """
        actions = {"Tab": self.repeat, "Return": self.new, "KP_Enter": self.new}
        if event.keysym in actions:
            actions[event.keysym]()
            return True
        return False

    def handle_key_release(self, event: tk.Event) -> None:
        """Key releases are not needed here.

        Args:
            event: Tk key event.
        """

    def status_hint(self) -> str:
        """Hot keys of the results card.

        Returns:
            Hint text.
        """
        return "tab — повторить   ·   enter — новое упражнение"
