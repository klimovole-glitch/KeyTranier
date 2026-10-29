"""Single main window: screens, side menu and status bar (ТЗ, п. 4.1.6).

Navigation follows the Figma prototype: the side panel (300 px) slides out
in 0.38 s with Esc, a click or simply by moving the mouse to the left edge
(a 28 px zone with a thin bar); it covers the content without moving it.
A new screen slides up a little when it appears. F1 opens "О программе".
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from keytrainer.views.animation import PANEL_MS, SCREEN_MS, Animator
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.dropdown import Dropdown
from keytrainer.views.widgets.text_button import TextButton

MENU_WIDTH = 300
HOVER_ZONE = 28
HOVER_DELAY_MS = 140
SCREEN_SHIFT = 22


class ScreenController(Protocol):
    """What the main window expects from a screen controller."""

    def on_show(self) -> None:
        """Called when the screen becomes visible."""

    def on_hide(self) -> None:
        """Called when another screen is shown."""

    def handle_key(self, event: tk.Event) -> bool:
        """Handle a key press; return ``True`` if it was consumed."""

    def handle_key_release(self, event: tk.Event) -> None:
        """Handle a key release."""

    def status_hint(self) -> str:
        """Return hot key hints for the right part of the status bar."""


@dataclass
class Screen:
    """A registered screen."""

    name: str
    title: str
    frame: tk.Frame
    controller: ScreenController | None
    in_menu: bool


class MainWindow:
    """Owns the root window layout and switches screens."""

    def __init__(self, root: tk.Tk, theme: ThemeManager) -> None:
        """Create the layout: menu bar, content area, status bar, side menu.

        Args:
            root: Tk root window.
            theme: Theme manager.
        """
        self.root = root
        self.theme = theme
        root.configure(bg=theme.palette.bg)
        self.screens: dict[str, Screen] = {}
        self.current: Screen | None = None
        self.on_about: Callable[[], None] | None = None

        self.animator = Animator(root)

        status = theme.frame(root)
        status.pack(side="bottom", fill="x", padx=px(40), pady=px((0, 18)))
        self.status_left = theme.label(status, "", role="muted", font="tiny")
        self.status_left.pack(side="left")
        self.status_right = theme.label(status, "", role="muted", font="tiny")
        self.status_right.pack(side="right")

        self.content = theme.frame(root)
        self.content.pack(side="top", fill="both", expand=True, padx=px((30, 0)))

        zone = theme.frame(root, width=px(HOVER_ZONE), cursor="hand2")
        zone.place(x=0, y=0, relheight=1, width=px(HOVER_ZONE))
        self.handle = theme.frame(zone, role="dim", width=px(2), height=px(44))
        self.handle.place(x=px(8), rely=0.5, anchor="w")
        for widget in (zone, self.handle):
            widget.bind("<Button-1>", lambda _e: self.toggle_menu())
            widget.bind("<Enter>", self._zone_enter)
            widget.bind("<Leave>", lambda _e: self.animator.cancel("hover_open"))

        self.menu = theme.frame(root, role="surface")
        self._menu_items = theme.frame(self.menu, role="surface")
        self._menu_items.pack(fill="both", expand=True, padx=px(34), pady=px(60))
        self.menu.bind("<Leave>", self._menu_leave)
        self.menu_visible = False
        self._menu_x = -px(MENU_WIDTH)
        self._menu_buttons: list[TextButton] = []

        root.bind("<Button-1>", self._click_outside_menu, add="+")
        root.bind("<KeyPress>", self._on_key)
        root.bind("<KeyRelease>", self._on_key_release)

    # ---------------------------------------------------------- screens
    def add_screen(
        self,
        name: str,
        title: str,
        frame: tk.Frame,
        controller: ScreenController | None = None,
        in_menu: bool = True,
    ) -> None:
        """Register a screen.

        Args:
            name: Internal name ("training").
            title: Caption in the side menu.
            frame: Screen widget (child of :attr:`content`).
            controller: Controller that receives keys and show events.
            in_menu: Whether the screen has a menu item.
        """
        self.screens[name] = Screen(name, title, frame, controller, in_menu)
        self._rebuild_menu()

    def has_screen(self, name: str) -> bool:
        """Check that a screen is registered.

        Args:
            name: Screen name.

        Returns:
            ``True`` if it exists.
        """
        return name in self.screens

    def show(self, name: str) -> None:
        """Show a screen and hide the others.

        Args:
            name: Screen name.
        """
        self.hide_menu()
        screen = self.screens[name]
        if self.current is screen:
            return
        if self.current is not None:
            self.current.frame.place_forget()
            if self.current.controller:
                self.current.controller.on_hide()
        self.current = screen
        frame = screen.frame
        shift = px(SCREEN_SHIFT)
        frame.place(x=0, y=shift, relwidth=1, relheight=1)
        self.animator.run(
            "screen",
            SCREEN_MS,
            lambda t: frame.place_configure(y=round(shift * (1 - t))),
        )
        self.root.focus_set()  # keys must not stay in an entry of a hidden screen
        if screen.controller:
            screen.controller.on_show()
        self.refresh_status_hint()

    # ------------------------------------------------------------- menu
    def _rebuild_menu(self) -> None:
        """Recreate menu items for the registered screens."""
        for child in self._menu_items.winfo_children():
            child.destroy()
        self.theme.label(
            self._menu_items, "keytrainer", role="muted", font="small", bg="surface"
        ).pack(anchor="w", pady=px((0, 30)))
        items = [
            (s.title, lambda n=s.name: self.show(n))
            for s in self.screens.values()
            if s.in_menu
        ]
        items += [("о программе  F1", self._about), ("выход", self.root.destroy)]
        self._menu_buttons = []
        for caption, command in items:
            button = TextButton(
                self._menu_items,
                self.theme,
                caption,
                command,
                bg="surface",
                font="title",
            )
            button.pack(anchor="w", pady=px(8))
            self._menu_buttons.append(button)

    def _about(self) -> None:
        """Open the "О программе" dialog."""
        self.hide_menu()
        if self.on_about:
            self.on_about()

    def toggle_menu(self) -> None:
        """Open or close the side menu."""
        if self.menu_visible:
            self.hide_menu()
        else:
            self.show_menu()

    def _slide_menu(self, target: int, duration_ms: int, done=None) -> None:
        """Move the side panel horizontally.

        Args:
            target: Final x of the panel (0 — open, ``-MENU_WIDTH`` — closed).
            duration_ms: Length of the animation.
            done: Called at the end.
        """
        start = self._menu_x

        def step(t: float) -> None:
            self._menu_x = round(start + (target - start) * t)
            self.menu.place_configure(x=self._menu_x)

        self.animator.run("menu", duration_ms, step, done)

    def show_menu(self) -> None:
        """Slide the side menu out (0.38 s)."""
        if self.menu_visible:
            return
        Dropdown.close_active()
        self.menu_visible = True
        self.menu.place(x=self._menu_x, y=0, relheight=1, width=px(MENU_WIDTH))
        self.menu.lift()
        self._slide_menu(0, PANEL_MS)
        for index, button in enumerate(self._menu_buttons):
            button.fade_in(delay_ms=90 + index * 45)

    def hide_menu(self) -> None:
        """Slide the side menu back."""
        if not self.menu_visible:
            return
        self.menu_visible = False
        self.animator.cancel("hover_open")
        self._slide_menu(
            -px(MENU_WIDTH), round(PANEL_MS * 0.7), done=self.menu.place_forget
        )

    def _zone_enter(self, _event: tk.Event) -> None:
        """Open the menu when the mouse rests at the left edge.

        Args:
            _event: Tk event (unused).
        """
        self.animator.later("hover_open", HOVER_DELAY_MS, self.show_menu)

    def _click_outside_menu(self, event: tk.Event) -> None:
        """Close the menu on a click to the right of it.

        Args:
            event: Tk click event.
        """
        if self.menu_visible and event.x_root - self.root.winfo_rootx() > px(
            MENU_WIDTH
        ):
            self.hide_menu()

    def _menu_leave(self, _event: tk.Event) -> None:
        """Close the menu when the mouse leaves it to the right.

        ``<Leave>`` also fires when the mouse moves onto a child widget,
        so the pointer position is checked a moment later.

        Args:
            _event: Tk event (unused).
        """

        def check() -> None:
            x = self.root.winfo_pointerx() - self.root.winfo_rootx()
            if self.menu_visible and x > px(MENU_WIDTH) + 4:
                self.hide_menu()

        self.animator.later("menu_leave", 220, check)

    # ------------------------------------------------------- status bar
    def set_status(self, text: str) -> None:
        """Show the profile and the layout in the status bar.

        Args:
            text: Left part of the status bar.
        """
        self.status_left.configure(text=text)

    def refresh_status_hint(self) -> None:
        """Show hot keys of the current screen."""
        hint = "esc — меню"
        if self.current and self.current.controller:
            own = self.current.controller.status_hint()
            hint = f"{own}   ·   {hint}" if own else hint
        self.status_right.configure(text=hint)

    # ------------------------------------------------------------- keys
    def _on_key(self, event: tk.Event) -> str | None:
        """Route a key press: global keys first, then the current screen.

        Args:
            event: Tk key event.

        Returns:
            ``"break"`` if the key was consumed.
        """
        if Dropdown.close_active():
            return "break"
        if event.keysym == "Escape":
            self.toggle_menu()
            return "break"
        if event.keysym == "F1":
            self._about()
            return "break"
        if self.menu_visible or self.current is None or not self.current.controller:
            return None
        if self.current.controller.handle_key(event):
            return "break"
        return None

    def _on_key_release(self, event: tk.Event) -> None:
        """Pass a key release to the current screen.

        Args:
            event: Tk key event.
        """
        if self.current and self.current.controller:
            self.current.controller.handle_key_release(event)
