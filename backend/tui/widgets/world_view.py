"""WorldView — renders the world on a character grid using half blocks.

Each terminal cell paints two world "pixels" stacked vertically via the
▀ upper-half block: foreground = top pixel, background = bottom pixel,
giving a 2:1 vertical squeeze that compensates for tall terminal glyphs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rich.segment import Segment
from rich.style import Style
from textual.message import Message
from textual.strip import Strip

from textual import events
from textual.widget import Widget

from ..state import EntityState, StateMessage
from .. import theme


@dataclass(slots=True)
class Cell:
    char: str | None = None
    fg: str | None = None
    bg: str | None = None
    prio: int = 0
    entity_id: int = 0


class WorldView(Widget, can_focus=True):
    """Camera + glyph renderer. Click selects a creature; Enter inspects it."""

    class CreaturePicked(Message):
        """Posted when the user clicks the world view."""

        def __init__(self, entity: EntityState | None) -> None:
            self.entity = entity
            super().__init__()

    DEFAULT_CSS = """
    WorldView { background: #0d1117; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state: StateMessage | None = None
        # §AV T-1: flat list cell buffer — row-major 1D array avoids tuple-key dict overhead
        self._grid_cols: int = 0
        self._grid_rows: int = 0
        self._grid: list[Cell | None] = []
        self._prev_strips: list[Strip | None] = []  # §AV T-1 dirty-row cache
        self._sel_cell: tuple[int, int] | None = None
        # camera: center in world coords; zoom = world units per column
        self.cam_cx = 100.0
        self.cam_cy = 100.0
        self.zoom = 2.0
        self._fitted = False
        # ascii mode: one glyph per terminal cell (roguelike map). Off = the
        # half-block pixel renderer that stacks two world rows per cell.
        self.ascii_mode: bool = True
        self.follow_selected: bool = False
        self.selected_id: int | None = None

    def _row_factor(self) -> int:
        """Terminal rows per... rather, world sub-rows shown per terminal row."""
        return 1 if self.ascii_mode else 2

    # ------------------------------------------------------------- updates
    def set_state(self, st: StateMessage) -> None:
        self._state = st
        if self.follow_selected and self.selected_id:
            target = next((e for e in st.entities if e.id == self.selected_id), None)
            if target:
                self.cam_cx = target.x
                self.cam_cy = target.y
        self._fit_once()
        self._repaint()
        self.refresh()

    def _fit_once(self) -> None:
        """Fit the camera the first time we have both state and a real size."""
        if not self._fitted and self._state is not None and self.size.width > 10:
            self.fit()
            self._fitted = True

    def _on_resize(self, event: events.Resize) -> None:
        self._fit_once()

    @property
    def state(self) -> StateMessage | None:
        return self._state

    def fit(self) -> None:
        st = self._state
        if not st:
            return
        f = self._row_factor()
        w = max(self.size.width, 20)
        h = max(self.size.height, 8)
        zw = st.width / w
        zh = st.height / (f * h)
        self.zoom = max(zw, zh)
        self.cam_cx = st.width / 2
        self.cam_cy = st.height / 2
        self.refresh()

    def zoom_by(self, factor: float) -> None:
        st = self._state
        if not st:
            return
        f = self._row_factor()
        min_zoom = min(st.width / max(self.size.width, 1), st.height / (f * max(self.size.height, 1))) * 0.25
        new_z = min(40.0, max(min_zoom, self.zoom * factor))
        if new_z != self.zoom:
            self.zoom = new_z
            self._clamp_camera()
            self.refresh()

    def pan(self, dx_cols: int, dy_rows: int) -> None:
        step_x = 6 * self.zoom
        step_y = 6 * self.zoom  # a row is ~2*zoom tall; 3 rows ≈ same distance
        self.cam_cx += dx_cols * step_x
        self.cam_cy += dy_rows * step_y
        self._clamp_camera()
        self.refresh()

    def _clamp_camera(self) -> None:
        st = self._state
        if not st:
            return
        if st.boundary == "wrap":
            self.cam_cx %= st.width
            self.cam_cy %= st.height
        else:
            self.cam_cx = min(max(self.cam_cx, 0.0), st.width)
            self.cam_cy = min(max(self.cam_cy, 0.0), st.height)

    # ------------------------------------------------------------ painting
    def _origin(self) -> tuple[int, int]:
        f = self._row_factor()
        left = self.cam_cx - self.size.width * self.zoom / 2
        top = self.cam_cy - self.size.height * self.zoom * f / 2
        return math.floor(left / self.zoom), math.floor(top / self.zoom)

    def world_to_cell(self, wx: float, wy: float) -> tuple[int, int]:
        return math.floor(wx / self.zoom), math.floor(wy / self.zoom)

    def cell_to_world_center(self, col: int, row: int) -> tuple[float, float]:
        z = self.zoom
        return (col + 0.5) * z, (row + 0.5) * z

    def _repaint(self) -> None:
        st = self._state
        grid: dict[tuple[int, int], Cell] = {}
        self._grid = grid
        self._sel_cell = None
        if not st:
            return
        z = max(self.zoom, 1e-6)

        def put(wx: float, wy: float, *, char=None, fg=None, bg=None, prio=0, eid=0) -> None:
            key = (math.floor(wx / z), math.floor(wy / z))
            cur = grid.get(key)
            if cur is None or prio > cur.prio or (
                prio == cur.prio and char is not None and cur.char is None
            ):
                grid[key] = Cell(char=char, fg=fg, bg=bg, prio=prio, entity_id=eid)

        # --- rivers (horizontal channels) ---
        for riv in getattr(st, "rivers", []) or []:
            cy = riv.get("cy", 0.0)
            hw = riv.get("hw", 4.0)
            flood = bool(riv.get("flood", False))
            bg_color = "#1c3050" if flood else "#122036"
            fg_color = "#58a6ff" if flood else "#388bfd"
            row0 = max(0, math.floor((cy - hw) / z))
            row1 = min(math.floor(st.height / z), math.floor((cy + hw) / z))
            col1 = math.floor(st.width / z)
            for row in range(row0, row1 + 1):
                wy = (row + 0.5) * z
                for col in range(0, col1 + 1):
                    wx = (col + 0.5) * z
                    put(wx, wy, char=theme.GLYPH_RIVER, fg=fg_color, bg=bg_color, prio=-3)

        # --- bridges & dams crossing rivers ---
        for b in getattr(st, "bridges", []) or []:
            bx = b.get("x", 0.0)
            bcy = b.get("cy", 0.0)
            rv = next((r for r in getattr(st, "rivers", []) if abs(r.get("cy", 0.0) - bcy) < 1.0), None)
            hw = (rv.get("hw", 4.0) if rv else 4.0)
            row0 = max(0, math.floor((bcy - hw) / z))
            row1 = min(math.floor(st.height / z), math.floor((bcy + hw) / z))
            col = math.floor(bx / z)
            wx = (col + 0.5) * z
            for row in range(row0, row1 + 1):
                wy = (row + 0.5) * z
                put(wx, wy, char=theme.GLYPH_BRIDGE, fg="#d29922", bg="#2a1f10", prio=1)

        for d in getattr(st, "dams", []) or []:
            dx = d.get("x", 0.0)
            dcy = d.get("cy", 0.0)
            col = math.floor(dx / z)
            row = math.floor(dcy / z)
            wx = (col + 0.5) * z
            wy = (row + 0.5) * z
            put(wx, wy, char=theme.GLYPH_DAM, fg="#8b949e", bg="#21262d", prio=2)

        # --- boundary stones & neutral trade markets ---
        for bs in getattr(st, "boundary_stones", []) or []:
            cid = str(bs.get("clan_id"))
            color = (st.clans.get(cid) or {}).get("color", "#8b949e")
            put(bs.get("x", 0.0), bs.get("y", 0.0), char=theme.GLYPH_BOUNDARY_STONE, fg=color, prio=1)

        for m in getattr(st, "markets", []) or []:
            put(m.get("x", 0.0), m.get("y", 0.0), char=theme.GLYPH_MARKET, fg="#e3b341", bg="#302008", prio=3)

        # --- discovered anomaly zones ---
        for an in getattr(st, "anomalies", []) or []:
            akind = an.get("kind", "heavy")
            acolor = "#56d364" if akind == "fertile" else ("#d2a8ff" if akind == "heavy" else "#79c0ff")
            put(an.get("x", 0.0), an.get("y", 0.0), char=theme.GLYPH_ANOMALY, fg=acolor, prio=1)

        # --- terrain: fertile ground tint + rock bodies ---
        for patch in st.terrain_fertile:
            self._paint_disc(put, patch["x"], patch["y"], patch["r"], bg="#12261a", ring_bg="#16301f")
        for rock in st.terrain_rocks:
            self._paint_rock(put, rock["x"], rock["y"], rock["r"])

        # --- territory rings (§P): faint clan-colored band around each claimed house ---
        all_houses = [e for e in st.entities if e.kind == "house"]
        if st.clans and all_houses:
            for h in all_houses:
                if h.clan_id and not h.is_ruin:
                    color = h.clan_color or theme.DEFAULT_CREATURE_COLOR
                    r = max(h.size or 6, 6) * 2.0
                    self._paint_ring(put, h.x, h.y, r, dim(color))

        # --- houses: box outline in clan color, door gap marked ---
        for h in all_houses:
            self._paint_house(put, h)

        # --- entities ---
        for e in st.entities:
            if e.kind == "food":
                color = theme.VARIANT_COLORS.get(e.variant or "grass", "#d29922")
                mature = (e.growth or 0) >= 0.5
                put(
                    e.x,
                    e.y,
                    char=theme.GLYPH_FOOD_MATURE if mature else theme.GLYPH_FOOD_SPROUT,
                    fg=color,
                    prio=2,
                    eid=e.id,
                )
            elif e.kind == "corpse":
                put(e.x, e.y, char=theme.GLYPH_CORPSE, fg="#8b949e", prio=3, eid=e.id)
            elif e.kind == "creature":
                self._paint_creature(put, e)

        # --- transient signals & fires ---
        for sg in st.signals:
            color = theme.SIGNAL_COLORS.get(sg.get("kind") or "", "#f85149")
            put(sg.get("x", 0), sg.get("y", 0), char=theme.GLYPH_SIGNAL, fg=color, prio=7)
        for fire in st.fires:
            put(fire.get("x", 0), fire.get("y", 0), char=theme.GLYPH_FIRE, fg="#ff6b35", prio=6)
        # §AO E: field campfires — warm dots in the dark
        for cf in getattr(st, "campfires", []) or []:
            put(cf.get("x", 0), cf.get("y", 0), char=theme.GLYPH_CAMPFIRE, fg="#ff8c42", prio=6)
        # §AQ PH-9: lightning bolts
        for bolt in getattr(st, "lightning", []) or []:
            put(bolt.get("x", 0.0), bolt.get("y", 0.0), char=theme.GLYPH_LIGHTNING, fg="#ffff88", prio=7)

    def _paint_disc(self, put, cx: float, cy: float, r: float, *, bg: str, ring_bg: str | None = None) -> None:
        # §AV T-1: clamp to the visible viewport before any distance math
        z = max(self.zoom, 1e-6)
        col0 = max(0, math.floor((cx - r) / z))
        col1 = min(self._grid_cols - 1, math.floor((cx + r) / z))
        row0 = max(0, math.floor((cy - r) / z))
        row1 = min(self._grid_rows - 1, math.floor((cy + r) / z))
        for row in range(row0, row1 + 1):
            wy = (row + 0.5) * z
            for col in range(col0, col1 + 1):
                wx = (col + 0.5) * z
                d2 = (wx - cx) ** 2 + (wy - cy) ** 2
                if d2 <= r * r:
                    put(wx, wy, bg=bg, prio=-2)

    def _paint_ring(self, put, cx: float, cy: float, r: float, color: str) -> None:
        z = max(self.zoom, 1e-6)
        band = max(z, r * 0.06)
        col0, col1 = math.floor((cx - r - band) / z), math.floor((cx + r + band) / z)
        row0, row1 = math.floor((cy - r - band) / z), math.floor((cy + r + band) / z)
        inner2, outer2 = (r - band) ** 2, (r + band) ** 2
        for row in range(row0, row1 + 1):
            wy = (row + 0.5) * z
            dy = wy - cy
            for col in range(col0, col1 + 1):
                wx = (col + 0.5) * z
                d2 = (wx - cx) ** 2 + dy * dy
                if inner2 <= d2 <= outer2:
                    put(wx, wy, char="·", fg=color, prio=-1)

    def _paint_rock(self, put, cx: float, cy: float, r: float) -> None:
        z = max(self.zoom, 1e-6)
        self._paint_disc(put, cx, cy, r, bg="#21262d")
        # rim
        band = max(z, r * 0.15)
        col0, col1 = math.floor((cx - r) / z), math.floor((cx + r) / z)
        row0, row1 = math.floor((cy - r) / z), math.floor((cy + r) / z)
        inner2 = max(0.0, (r - band)) ** 2
        outer2 = (r + band) ** 2
        for row in range(row0, row1 + 1):
            wy = (row + 0.5) * z
            dy = wy - cy
            for col in range(col0, col1 + 1):
                wx = (col + 0.5) * z
                d2 = (wx - cx) ** 2 + dy * dy
                if inner2 <= d2 <= outer2:
                    put(wx, wy, char=theme.GLYPH_ROCK, fg="#6e7681", prio=1)

    def _paint_house(self, put, h: EntityState) -> None:
        size = h.size or 6.0
        half = size / 2
        x0, x1 = h.x - half, h.x + half
        y0, y1 = h.y - half, h.y + half
        z = max(self.zoom, 1e-6)
        color = "#8b949e" if h.is_ruin else (h.clan_color or "#d29922")
        if h.is_ruin:
            # crumbled footprint
            for row in range(math.floor(y0 / z), math.floor(y1 / z) + 1):
                for col in range(math.floor(x0 / z), math.floor(x1 / z) + 1):
                    wx, wy = (col + 0.5) * z, (row + 0.5) * z
                    if x0 <= wx <= x1 and y0 <= wy <= y1:
                        put(wx, wy, char=":", fg="#4a5158", prio=1)
            return
        door_w = h.door_width or 1.5
        side = h.door_side or "south"
        offset = h.door_offset or 0.0
        segs = _wall_segments(x0, y0, x1, y1, side, door_w, offset)
        for ax, ay, bx, by in segs:
            length = math.hypot(bx - ax, by - ay)
            steps = max(int(length / (z / 2)), 1)
            for i in range(steps + 1):
                t = i / steps
                wx = ax + (bx - ax) * t
                wy = ay + (by - ay) * t
                horizontal = abs(by - ay) < abs(bx - ax)
                put(
                    wx,
                    wy,
                    char=theme.GLYPH_HOUSE_WALL_H if horizontal else theme.GLYPH_HOUSE_WALL_V,
                    fg=color,
                    prio=2,
                )
        # corner marks over walls
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            put(cx, cy, char=theme.GLYPH_HOUSE_CORNER, fg=color, prio=2)
        # door marker
        if side == "north":
            dx, dy = h.x + offset, y0
        elif side == "south":
            dx, dy = h.x + offset, y1
        elif side == "west":
            dx, dy = x0, h.y + offset
        else:
            dx, dy = x1, h.y + offset
        put(dx, dy, char=theme.GLYPH_HOUSE_DOOR, fg="#e6edf3", prio=3)

        # Chieftain Main House crown mark
        if getattr(h, "is_main", False) and not h.is_ruin:
            put(h.x, h.y, char="★", fg="#ffd166", prio=4)

    def _paint_creature(self, put, e: EntityState) -> None:
        if e.is_predator:
            char, color = theme.GLYPH_PREDATOR, theme.CASTE_COLORS["Predator"]
        elif e.is_herbivore:
            char, color = theme.GLYPH_HERBIVORE, theme.CASTE_COLORS["Herbivore"]
        else:
            char = e.glyph or theme.FALLBACK_GLYPHS.get(e.caste or "", "?")
            color = theme.caste_color(e.caste)
        dim_style = False
        if e.stage == "elder":
            dim_style = True
        if e.sleeping:
            dim_style = True
        if e.clan_color and not e.is_predator and not e.is_herbivore and e.glyph is None:
            color = e.clan_color
        prio = 5
        put(e.x, e.y, char=char, fg=color if not dim_style else dim(color), prio=prio, eid=e.id)

        # Emote thoughts above head
        if e.emote and self.zoom <= 4.0:
            emote_char = {
                "hungry": "🍖",
                "love": "♥",
                "combat": "⚔",
                "panic": "!",
                "heal": "🌿",
                "cheer": "★",
                "sleep": "z",
                "craft": "🧺",
                "grief": "✝",
                "fear": "❗",
            }.get(e.emote, "·")
            put(e.x, e.y - self.zoom * 0.8, char=emote_char, fg="#ffd166", prio=8)

    # ------------------------------------------------------------- picking
    def pick(self, sx: int, sy: int) -> EntityState | None:
        """Nearest creature to widget-local cell coords (within pick radius)."""
        st = self._state
        if not st:
            return None
        f = self._row_factor()
        col0, row0 = self._origin()
        col, row = col0 + sx, row0 + sy * f
        z = self.zoom
        wx = (col + 0.5) * z
        wy = (row + f / 2.0) * z
        radius = max(4.0, z * 2.5)
        best: EntityState | None = None
        best_d2 = radius * radius
        for e in st.entities:
            if e.kind != "creature":
                continue
            d2 = (e.x - wx) ** 2 + (e.y - wy) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best = e
        return best

    def select_entity(self, e: EntityState | None) -> None:
        self._sel_cell = self.world_to_cell(e.x, e.y) if e else None

    # -------------------------------------------------------------- render
    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if self._state is None:
            return Strip.blank(width, self.rich_style)
        col0, row0 = self._origin()
        sel = self._sel_cell
        if self.ascii_mode:
            return self._render_line_ascii(y, col0, row0, width, sel)
        segments: list[Segment] = []
        buf: list[str] = []
        cur_style: str | None = None

        def flush() -> None:
            nonlocal buf, cur_style
            if buf:
                segments.append(
                    Segment("".join(buf), style=Style.parse(cur_style) if cur_style else None)
                )
                buf = []
                cur_style = None

        for x in range(width):
            col = col0 + x
            top = self._grid.get((col, row0 + y * 2))
            bot = self._grid.get((col, row0 + y * 2 + 1))
            style = _cell_style(top, bot, selected=sel is not None and col == sel[0] and row0 + y * 2 == sel[1])
            if style != cur_style:
                flush()
                cur_style = style
            buf.append(_cell_char(top, bot))
        flush()
        if not segments:
            segments.append(Segment(" " * width))
        return Strip(segments, cell_length=width)

    def _render_line_ascii(
        self, y: int, col0: int, row0: int, width: int, sel: tuple[int, int] | None
    ) -> Strip:
        """One glyph per cell — the classic ASCII map."""
        row = row0 + y
        segments: list[Segment] = []
        buf: list[str] = []
        cur_style: str | None = None

        def flush() -> None:
            nonlocal buf, cur_style
            if buf:
                segments.append(
                    Segment("".join(buf), style=Style.parse(cur_style) if cur_style else None)
                )
                buf = []
                cur_style = None

        for x in range(width):
            col = col0 + x
            cell = self._grid.get((col, row))
            selected = sel is not None and (col, row) == sel
            char = cell.char if cell is not None and cell.char else " "
            style = f"#0d1117 on #e6edf3" if selected else _ascii_cell_style(cell)
            if style != cur_style:
                flush()
                cur_style = style
            buf.append(char)
        flush()
        if not segments:
            segments.append(Segment(" " * width))
        return Strip(segments, cell_length=width)

    # --------------------------------------------------------------- input
    def _on_mouse_up(self, event: events.MouseUp) -> None:
        picked = self.pick(event.x, event.y)
        self.select_entity(picked)
        self.refresh()
        self.post_message(self.CreaturePicked(picked))

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.zoom_by(1 / 1.2)

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.zoom_by(1.2)


def _cell_char(top: Cell | None, bot: Cell | None) -> str:
    has_top = top is not None and top.char is not None
    has_bot = bot is not None and bot.char is not None
    if has_top and has_bot:
        return "▀"
    if has_top:
        return "▀"
    if has_bot:
        return "▄"
    return " "


def _ascii_cell_style(cell: Cell | None) -> str:
    """fg = glyph color, bg = terrain tint (ASCII mode: one glyph per cell)."""
    if cell is None:
        return ""
    parts: list[str] = []
    if cell.fg:
        parts.append(cell.fg)
    if cell.bg:
        parts.append(f"on {cell.bg}")
    return " ".join(parts)


def _cell_style(top: Cell | None, bot: Cell | None, *, selected: bool) -> str:
    if selected:
        return "#0d1117 on #e6edf3"
    parts: list[str] = []
    has_top = top is not None and top.char is not None
    has_bot = bot is not None and bot.char is not None
    fg = None
    if has_top:
        fg = top.fg  # type: ignore[union-attr]
    elif has_bot:
        fg = bot.fg  # type: ignore[union-attr]
    if fg:
        parts.append(fg)
    bg = None
    if top is not None and top.bg:
        bg = top.bg
    elif bot is not None and bot.bg:
        bg = bot.bg
    if bg:
        parts.append(f"on {bg}")
    return " ".join(parts)


def dim(hex_color: str) -> str:
    """Blend a hex color halfway toward black for elder/sleeping/territory."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
    except (ValueError, IndexError):
        return hex_color
    return f"#{r // 2:02x}{g // 2:02x}{b // 2:02x}"


def _wall_segments(
    x0: float, y0: float, x1: float, y1: float, side: str, door_w: float, offset: float
) -> list[tuple[float, float, float, float]]:
    """Mirror of frontend houseWallSegments (types.ts)."""
    d = door_w / 2
    if side == "north":
        cx, cy = (x0 + x1) / 2 + offset, y0
        return [
            (x0, y0, cx - d, y0),
            (cx + d, y0, x1, y0),
            (x0, y0, x0, y1),
            (x1, y0, x1, y1),
            (x0, y1, x1, y1),
        ]
    if side == "west":
        cx, cy = x0, (y0 + y1) / 2 + offset
        return [
            (x0, y0, x1, y0),
            (x0, y1, x1, y1),
            (x1, y0, x1, y1),
            (x0, y0, x0, cy - d),
            (x0, cy + d, x0, y1),
        ]
    if side == "east":
        cx, cy = x1, (y0 + y1) / 2 + offset
        return [
            (x0, y0, x1, y0),
            (x0, y0, x0, y1),
            (x0, y1, x1, y1),
            (x1, y0, x1, cy - d),
            (x1, cy + d, x1, y1),
        ]
    # south (default)
    cx, cy = (x0 + x1) / 2 + offset, y1
    return [
        (x0, y0, x1, y0),
        (x0, y0, x0, y1),
        (x1, y0, x1, y1),
        (x0, y1, cx - d, y1),
        (cx + d, y1, x1, y1),
    ]
