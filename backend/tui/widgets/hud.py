"""Hud — status line: run control state, clock, population, selection."""

from __future__ import annotations

import math
from rich.text import Text

from textual.widget import Widget

from ..state import StateMessage
from .. import theme


class Hud(Widget):
    DEFAULT_CSS = """
    Hud { height: auto; padding: 0 1; background: #161b22; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state: StateMessage | None = None
        self.paused = False
        self.speed = 10.0
        self.status = "connecting…"
        self.selected_line = ""

    def update_state(self, st: StateMessage | None) -> None:
        self._state = st
        if st is not None:
            self.paused = st.paused
        self.refresh()

    def update_status(self, status: str, paused: bool, speed: float) -> None:
        self.status = status
        self.paused = paused
        self.speed = speed
        self.refresh()

    def update_selection(self, line: str) -> None:
        self.selected_line = line
        self.refresh()

    def render(self) -> Text:
        st = self._state
        text = Text()
        if st is None:
            text.append(f"◌ {self.status}", style="dim")
            return text
        is_paused = self.paused or getattr(st, "paused", False)
        play = "‖" if is_paused else "▶"
        text.append(f"{play} ", style="bold red" if is_paused else "bold green")
        text.append(f"tick {st.tick}", style="bold")
        text.append(" · ")
        text.append(f"alive {st.creatures_alive}", style="#3fb950")
        text.append(f" · dead {st.creatures_dead}", style="dim")
        # Web parity: hungry / starving / infected / chilled / exposed
        hungry = sum(1 for e in st.entities if e.status == "hungry")
        starving = sum(1 for e in st.entities if e.status == "starving")
        chilled = sum(1 for e in st.entities if (e.chill or 0) >= 12)
        # exposed = raining + outdoors + not sleeping + not infected (web logic)
        raining = st.weather in ("rain", "storm")
        exposed = 0
        if raining:
            exposed = sum(1 for e in st.entities if e.kind == "creature" and not e.sleeping and not e.indoors and not e.infected)
        if hungry:
            text.append(f" · hungry {hungry}", style="#d29922")
        if starving:
            text.append(f" · starving {starving}", style="bold #f85149")
        if st.infected_count:
            text.append(f" · infected {st.infected_count}", style="#d29922")
        if chilled:
            text.append(f" · chilled {chilled}", style="#79c0ff")
        if exposed:
            text.append(f" · exposed {exposed}", style="#f85149")
        night = st.time_of_day < 0.2 or st.time_of_day > 0.8
        sky = "🌙" if night else "☀"
        text.append(f" · {sky} day {st.day} {theme.SEASON_ICONS.get(st.season, '')}{st.season}")
        text.append(f" · {theme.WEATHER_ICONS.get(st.weather, '')} {st.weather}")
        if getattr(st, "wind", None) and st.wind.get("speed", 0) > 0.05:
            w_speed = st.wind.get("speed", 0.0)
            w_ang = st.wind.get("angle", 0.0)
            deg = math.degrees(w_ang) % 360
            arrows = ["→", "↘", "↓", "↙", "←", "↖", "↑", "↗"]
            idx = int((deg + 22.5) // 45) % 8
            text.append(f" · {arrows[idx]} {w_speed:.1f}", style="cyan")
        if st.age:
            text.append(f" · age: {st.age} day {st.age_day}/{st.age_total_days}", style="magenta")
        # caste counts, colored
        castes = [
            (k, v)
            for k, v in sorted(st.population.items(), key=lambda kv: -kv[1])
            if k in theme.CASTE_COLORS or k in ("Food", "House", "Corpse")
        ]
        creature_chips = [c for c in castes if c[0] in theme.CASTE_COLORS]
        object_chips = [c for c in castes if c[0] not in theme.CASTE_COLORS]
        line2 = Text()
        for i, (k, v) in enumerate(creature_chips[:8]):
            if i:
                line2.append(" ")
            line2.append(f"{k} {v}", style=theme.caste_color(k))
        for k, v in object_chips:
            line2.append(f"  {k.lower()} {v}", style="dim")
        text.append("\n")
        text.append_text(line2)
        text.append(f"\n{self.status}", style="dim")
        if self.selected_line:
            text.append(f" · {self.selected_line}")
        return text
