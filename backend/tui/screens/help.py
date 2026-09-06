"""Help — keybindings and glyph legend."""

from __future__ import annotations

from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .. import theme

KEYS = [
    ("space", "pause / resume the world"),
    ("s", "step one tick"),
    ("r", "reset — new seed, new world"),
    ("f", "fit world in view"),
    ("w", "toggle camera tracking for selected creature"),
    ("t", "cycle chronicle category filter"),
    ("a", "toggle ASCII map / half-block pixel map"),
    ("+ / -", "zoom in / out (mouse wheel works too)"),
    ("h j k l / arrows", "pan camera"),
    ("click", "select a creature"),
    ("enter / i", "inspect selected creature dossier"),
    ("c", "clan details & roster (or View Clan in Inspector)"),
    ("tab", "move focus between panels"),
    ("g", "god laws (set laws of nature)"),
    ("o", "chronicle: load older events"),
    ("1-9", "world speed presets"),
    ("?", "this help"),
    ("q", "quit"),
]

LEGEND = [
    ("creature", "soul-code glyph in caste color (see Overview chips)"),
    ("^ / h", "predator / wild herbivore"),
    (". * • ♣ ☠", "plants: sprout/mature grass, berry, mushroom, poisonous"),
    ("x", "corpse — scavengable until it decays"),
    ("- | + /", "house walls, corner, door (clan color; ruins are dim :) )"),
    ("@", "rock — blocks movement"),
    ("~", "river channel / water"),
    ("=", "wooden bridge across river"),
    ("H", "stone dam on river"),
    ("•", "clan boundary stone"),
    ("M", "neutral border trade market"),
    ("🌀", "discovered anomaly zone"),
    ("⚡", "lightning strike"),
    ("▲", "field campfire"),
    ("~ ripple", "signal ripple (food green, alarm/help red)"),
    ("&", "fire"),
    ("· ring", "territory border (dim clan color)"),
]


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss_screen", "Close")]

    DEFAULT_CSS = """
    HelpScreen { align: center middle; background: #0d1117cc; }
    #help-box { width: 72; height: auto; max-height: 90%; border: round #30363d;
                background: #161b22; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(self._render_keys(), markup=False)
            yield Static(self._render_legend(), markup=False)
            with Horizontal(classes="modal-actions"):
                yield Button("Close", variant="primary", id="btn-close")

    def _render_keys(self) -> Text:
        text = Text()
        text.append("Flatland TUI — keys\n\n", style="bold")
        for key, desc in KEYS:
            text.append(f"{key:<20}", style="bold #79c0ff")
            text.append(f"{desc}\n")
        return text

    def _render_legend(self) -> Text:
        text = Text()
        text.append("\nGlyphs\n\n", style="bold")
        for mark, desc in LEGEND:
            sample = theme.CASTE_COLORS["Soldier"]
            text.append(f"{mark:<20}", style=sample)
            text.append(f"{desc}\n")
        return text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
