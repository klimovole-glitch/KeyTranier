"""Drop-down list in the style of the mockups (Figma: 01c, 01e, 01f).

The system ``tk.Menu`` cannot be styled or animated, so the list is an
ordinary frame placed over the window: it unfolds downwards, the chosen
item is marked with "✓", the item under the mouse is highlighted.
Only one list can be open; a click outside it or any key closes it.
"""

import tkinter as tk
from collections.abc import Callable

from keytrainer.views.animation import Animator, mix_colors
from keytrainer.views.display import px
from keytrainer.views.theme import ThemeManager

OPEN_MS = 180
CHECK = "✓ "
NO_CHECK = "   "

_roots_with_handler: set[str] = set()


class Dropdown:
    """List of options attached to an anchor widget."""

    active: "Dropdown | None" = None

    def __init__(
        self,
        anchor: tk.Widget,
        theme: ThemeManager,
        items: list[tuple[str, Callable[[], None]]],
        selected: str | None = None,
    ) -> None:
        """Remember what to show; the list is built by :meth:`open`.

        Args:
            anchor: Widget under which the list opens.
            theme: Theme manager.
            items: Captions and commands.
            selected: Caption of the chosen item (gets a check mark).
        """
        self.anchor = anchor
        self.theme = theme
        self.items = items
        self.selected = selected
        self.frame: tk.Frame | None = None

    # ------------------------------------------------------------ class
    @classmethod
    def close_active(cls) -> bool:
        """Close the open list, if any.

        Returns:
            ``True`` if a list was open.
        """
        if cls.active is None:
            return False
        cls.active.close()
        return True

    @staticmethod
    def _install_click_handler(root: tk.Misc) -> None:
        """Bind one click handler per window that closes lists on outside clicks.

        Every widget has its toplevel in its bind tags, so a binding on the
        window sees clicks on all widgets.

        Args:
            root: Toplevel window.
        """
        if str(root) in _roots_with_handler:
            return
        _roots_with_handler.add(str(root))

        def on_click(event: tk.Event) -> None:
            if Dropdown.active is not None:
                Dropdown.active._click_outside(event)

        root.bind("<Button-1>", on_click, add="+")

    # ------------------------------------------------------------- open
    def open(self) -> None:
        """Show the list under the anchor (a second click closes it)."""
        if Dropdown.active is not None:
            same = Dropdown.active.anchor is self.anchor
            Dropdown.close_active()
            if same:
                return
        root = self.anchor.winfo_toplevel()
        self._install_click_handler(root)
        palette = self.theme.palette
        frame = tk.Frame(
            root,
            bd=0,
            bg=palette.surface,
            highlightthickness=1,
            highlightbackground=palette.border,
        )
        rows = []
        for caption, command in self.items:
            mark = CHECK if caption == self.selected else NO_CHECK
            row = tk.Label(
                frame,
                text=mark + caption,
                anchor="w",
                bd=0,
                padx=px(14),
                pady=px(8),
                cursor="hand2",
                font=self.theme.fonts["ui"],
                bg=palette.surface,
                fg=palette.surface,
            )
            row.pack(fill="x", padx=px(6), pady=px(1))
            row.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
            row.bind("<Leave>", lambda _e, r=row: self._hover(r, False))
            row.bind("<ButtonRelease-1>", lambda _e, c=command: self._choose(c))
            rows.append(row)
        frame.update_idletasks()
        width = max(frame.winfo_reqwidth(), self.anchor.winfo_width() + px(40))
        height = frame.winfo_reqheight()
        x = self.anchor.winfo_rootx() - root.winfo_rootx() - px(14)
        y = self.anchor.winfo_rooty() - root.winfo_rooty() + self.anchor.winfo_height()
        frame.place(x=max(x, 0), y=y + px(6), width=width, height=1)
        frame.lift()
        self.frame = frame
        self.rows = rows
        Dropdown.active = self
        animator = Animator(frame)
        self._animator = animator
        animator.run(
            "unfold",
            OPEN_MS,
            lambda t: frame.place_configure(height=max(1, round(height * t))),
        )
        for index, row in enumerate(rows):
            target = (
                palette.text if row.cget("text").startswith(CHECK) else palette.muted
            )
            animator.fade(
                f"row{index}", row, "fg", palette.surface, target, 200, 40 + index * 25
            )

    def _hover(self, row: tk.Label, inside: bool) -> None:
        """Highlight the row under the mouse.

        Args:
            row: Row label.
            inside: ``True`` when the mouse enters.
        """
        palette = self.theme.palette
        start = row.cget("bg")
        end = palette.surface_active if inside else palette.surface
        self._animator.fade(f"hover{id(row)}", row, "bg", start, end, 120)
        row.configure(
            fg=(
                palette.text
                if inside or row.cget("text").startswith(CHECK)
                else palette.muted
            )
        )

    def _choose(self, command: Callable[[], None]) -> None:
        """Close the list and run the command of the chosen row.

        Args:
            command: Command of the row.
        """
        self.close()
        command()

    def _click_outside(self, event: tk.Event) -> None:
        """Close the list when the click was not on it or on its anchor.

        Args:
            event: Tk click event.
        """
        widget = event.widget
        while widget is not None:
            if widget is self.frame or widget is self.anchor:
                return
            widget = getattr(widget, "master", None)
        self.close()

    def close(self) -> None:
        """Fold the list and destroy it."""
        if Dropdown.active is self:
            Dropdown.active = None
        frame, self.frame = self.frame, None
        if frame is None or not frame.winfo_exists():
            return
        height = frame.winfo_height()
        palette = self.theme.palette
        for row in self.rows:
            row.configure(fg=mix_colors(palette.muted, palette.surface, 0.5))
        self._animator.run(
            "unfold",
            110,
            lambda t: frame.place_configure(height=max(1, round(height * (1 - t)))),
            done=frame.destroy,
        )
