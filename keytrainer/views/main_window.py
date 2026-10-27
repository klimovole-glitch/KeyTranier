"""Single main window: screens, side menu and status bar (ТЗ, п. 4.1.6).

Navigation follows the Figma prototype: the menu opens with Esc or a click
on the thin bar at the left edge; F1 opens "О программе".
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from keytrainer.views.theme import ThemeManager
from keytrainer.views.widgets.text_button import TextButton

MENU_WIDTH = 280


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

        handle = theme.label(root, "│", role="dim", font="title", cursor="hand2")
        handle.place(x=6, rely=0.5, anchor="w")
        handle.bind("<Button-1>", lambda _e: self.toggle_menu())

        status = theme.frame(root)
        status.pack(side="bottom", fill="x", padx=40, pady=(0, 18))
        self.status_left = theme.label(status, "", role="muted", font="tiny")
        self.status_left.pack(side="left")
        self.status_right = theme.label(status, "", role="muted", font="tiny")
        self.status_right.pack(side="right")

        self.content = theme.frame(root)
        self.content.pack(side="top", fill="both", expand=True, padx=(30, 0))
        handle.lift()

        self.menu = theme.frame(root, role="surface")
        self._menu_items = theme.frame(self.menu, role="surface")
        self._menu_items.pack(fill="both", expand=True, padx=34, pady=60)
        self.menu_visible = False

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
            self.current.frame.pack_forget()
            if self.current.controller:
                self.current.controller.on_hide()
        self.current = screen
        screen.frame.pack(fill="both", expand=True)
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
        ).pack(anchor="w", pady=(0, 30))
        items = [
            (s.title, lambda n=s.name: self.show(n))
            for s in self.screens.values()
            if s.in_menu
        ]
        items += [("о программе  F1", self._about), ("выход", self.root.destroy)]
        for caption, command in items:
            TextButton(
                self._menu_items,
                self.theme,
                caption,
                command,
                bg="surface",
                font="title",
            ).pack(anchor="w", pady=8)

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
            self.menu.place(x=0, y=0, relheight=1, width=MENU_WIDTH)
            self.menu.lift()
            self.menu_visible = True

    def hide_menu(self) -> None:
        """Close the side menu."""
        self.menu.place_forget()
        self.menu_visible = False

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
