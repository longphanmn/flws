"""Chronicle — color-coded RichLog of world events (live feed + pagination)."""

from __future__ import annotations

from rich.text import Text

from textual.widgets import RichLog

from ..state import HistoryEvent, StateMessage
from .. import theme

MAX_LOG = 400

# High-frequency / low-value events never enter the terminal feed —
# blooms and withers churn by the tick, ruins are just old age for houses.
HIDDEN_EVENTS = {"bloom", "wither", "ruin"}

CATEGORIES = ["all", "birth", "death", "war", "politics", "settlement", "faith", "trade"]

EVENT_CATEGORIES: dict[str, set[str]] = {
    "birth": {"birth"},
    "death": {"death", "predation", "cannibalism", "clan_extinction", "extinction"},
    "war": {"war", "conquest", "takeover", "rivalry", "betrayal"},
    "politics": {
        "alliance", "rivalry", "coalition_formed", "coalition_joined",
        "coalition_dissolved", "peace", "tribute", "betrayal", "defection",
        "schism", "succession",
    },
    "settlement": {"settlement", "conquest", "takeover", "culture", "disaster", "fire", "outbreak", "recovery", "anomaly"},
    # §AP unified theology
    "faith": {"miracle", "sermon", "synod", "temple", "epiphany", "resonance", "omen"},
    # §AM agriculture + §AN trade & diplomacy
    "trade": {"raid", "hospitality", "peace_envoy", "market", "caravan", "herald",
              "banquet", "compost"},
}


class Chronicle(RichLog):
    DEFAULT_CSS = """
    Chronicle { border-title-color: #8b949e; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(markup=True, highlight=False, wrap=True, max_lines=MAX_LOG, **kwargs)
        self._seen: set[tuple] = set()
        self._all_events: list[tuple[HistoryEvent, dict]] = []
        self.filter_category = "all"

    def on_mount(self) -> None:
        self._update_title()

    def _update_title(self) -> None:
        self.border_title = f"Chronicle ({self.filter_category.upper()})"

    def cycle_filter(self) -> str:
        idx = CATEGORIES.index(self.filter_category)
        self.filter_category = CATEGORIES[(idx + 1) % len(CATEGORIES)]
        self._update_title()
        self._rebuild()
        return self.filter_category

    def _rebuild(self) -> None:
        self.clear()
        for ev, clans in self._all_events:
            if self._matches_filter(ev):
                self.write(format_event(ev, clans))

    def _matches_filter(self, ev: HistoryEvent) -> bool:
        if self.filter_category == "all":
            return True
        types = EVENT_CATEGORIES.get(self.filter_category, set())
        return ev.type in types

    def clear_events(self) -> None:
        self._seen.clear()
        self._all_events.clear()
        self.clear()

    def add_from_state(self, st: StateMessage) -> None:
        fresh = [
            ev for ev in st.events
            if ev.key not in self._seen and ev.type not in HIDDEN_EVENTS
        ]
        for ev in fresh:
            self._seen.add(ev.key)
            self._all_events.append((ev, st.clans or {}))
            if len(self._all_events) > MAX_LOG:
                self._all_events.pop(0)
            if self._matches_filter(ev):
                self.write(format_event(ev, st.clans))

    def add_fetched(self, events: list[dict], clans: dict | None = None) -> None:
        """Older events from GET /api/history (already oldest-first)."""
        for d in events:
            if d.get("type") in HIDDEN_EVENTS:
                continue
            ev = HistoryEvent.from_dict(d)
            if ev.key in self._seen:
                continue
            self._seen.add(ev.key)
            self._all_events.insert(0, (ev, clans or {}))
            if self._matches_filter(ev):
                self.write(format_event(ev, clans or {}))


def _clan_label(clans: dict, cid) -> str:
    try:
        info = clans.get(str(cid)) or {}
        name = info.get("name")
        if name:
            return f"{name} ({cid})"
    except Exception:
        pass
    return f"#{cid}"


def format_event(ev: HistoryEvent, clans: dict | None = None) -> Text:
    clans = clans or {}
    p = ev.payload or {}
    who = p.get("personal_name") or ev.caste or ""
    glyph = p.get("glyph") or ""
    mark = f"{who} {glyph}".strip() or f"#{ev.entity_id}"
    line = Text()
    color = theme.EVENT_COLORS.get(ev.type, "#8b949e")
    t = ev.type

    if t == "birth":
        line.append(f"{mark}", style="bold " + color)
        line.append(f" #{ev.entity_id} born to #{p.get('mother')} × #{p.get('father')}")
        line.append(f" gen {p.get('generation', '?')}", style="dim")
    elif t == "promotion":
        line.append(f"{mark} ", style=color)
        line.append(f"rose {p.get('from', 'Soldier')} → {p.get('to', ev.caste)}", style=color)
    elif t == "demotion":
        line.append(f"{mark} judged irregular and demoted", style=color)
    elif t == "predation":
        line.append(f"{mark} predated ", style=color)
        line.append(f"{p.get('prey_caste')} #{p.get('prey')}")
    elif t == "war":
        line.append(f"{mark} fell in clan war", style="bold " + color)
        if p.get("winner"):
            line.append(f" — winner #{p.get('winner')}", style="dim")
    elif t in ("alliance", "rivalry"):
        line.append(
            f"clans {_clan_label(clans, p.get('a'))} & {_clan_label(clans, p.get('b'))} {t}",
            style=color,
        )
        if p.get("score") is not None:
            line.append(f" (score {p.get('score')})", style="dim")
    elif t == "schism":
        line.append(f"schism: ", style=color)
        line.append(str(p.get("parent_name") or _clan_label(clans, p.get("parent"))))
        line.append(" → ")
        line.append(str(p.get("new_name") or _clan_label(clans, p.get("new_clan"))), style="bold " + color)
        members = p.get("members") or []
        line.append(f" ({len(members)} broke away)", style="dim")
    elif t == "conquest":
        line.append("conquest: ", style=color)
        line.append(_clan_label(clans, p.get("winner_clan")))
        line.append(f" seized house {p.get('house_id')} from ")
        line.append(_clan_label(clans, p.get("loser_clan")))
    elif t == "takeover":
        line.append("takeover: ", style=color)
        line.append(str(p.get("invader_name") or _clan_label(clans, p.get("invader_clan"))))
        line.append(f" moved into house {p.get('house_id')} left by ")
        line.append(str(p.get("victim_name") or _clan_label(clans, p.get("victim_clan"))))
    elif t == "succession":
        line.append(f"succession in ", style=color)
        line.append(_clan_label(clans, p.get("clan_id")))
        line.append(f": #{p.get('new_leader')} succeeds #{p.get('prev_leader')}", style="dim")
    elif t == "settlement":
        line.append("settlement founded", style=color)
        if p.get("clan_id"):
            line.append(f" by {_clan_label(clans, p.get('clan_id'))}", style="dim")
    elif t == "culture":
        line.append("clan ", style=color)
        line.append(_clan_label(clans, p.get("clan_id")))
        line.append(f" embraces a new tradition: {p.get('culture', '')}", style="bold " + color)
    elif t == "fire":
        line.append(f"fire {p.get('kind') or ''} at ({round(ev.x)}, {round(ev.y)})", style=color)
    elif t == "disaster":
        line.append(f"disaster {p.get('kind')} r{p.get('r', '')} at ({round(ev.x)}, {round(ev.y)})", style=color)
    elif t in ("coalition_formed", "coalition_joined", "coalition_dissolved"):
        label = {"coalition_formed": "coalition formed: ", "coalition_joined": "", "coalition_dissolved": ""}.get(t, t)
        if t == "coalition_joined":
            line.append(f"clan {_clan_label(clans, p.get('clan'))} joined ", style=color)
        elif t == "coalition_dissolved":
            line.append(f"coalition dissolved ({p.get('reason')}): ", style="dim")
        else:
            line.append(label, style=color)
        line.append(str(p.get("name") or f"coalition #{p.get('coalition')}"), style="bold " + color)
        members = p.get("members") or []
        if members:
            line.append(f" ({len(members)} clans)", style="dim")
    elif t == "peace":
        line.append("peace: ", style=color)
        line.append(_clan_label(clans, p.get("a")))
        line.append(" & ")
        line.append(_clan_label(clans, p.get("b")))
        line.append(" lay down arms")
    elif t == "tribute":
        line.append("tribute: ", style=color)
        line.append(_clan_label(clans, p.get("from")))
        line.append(f" pays {p.get('amount', '?')} to ")
        line.append(_clan_label(clans, p.get("to")))
    elif t == "betrayal":
        line.append("betrayal: ", style=color)
        line.append(_clan_label(clans, p.get("a")))
        line.append(" turns on ally ")
        line.append(_clan_label(clans, p.get("b")))
    elif t == "defection":
        line.append("defection: ", style=color)
        line.append(f"#{ev.entity_id} leaves ")
        line.append(_clan_label(clans, p.get("from")))
        line.append(" for ")
        line.append(_clan_label(clans, p.get("to")))
    elif t == "cannibalism":
        line.append(f"{mark} ate ", style=color)
        line.append(("kin " if p.get("kin") else "enemy ") + str(p.get("prey_caste")) + f" #{p.get('prey')}")
    elif t == "exile":
        line.append(f"{mark} exiled from ", style=color)
        line.append(str(p.get("former_name") or _clan_label(clans, p.get("former_clan"))))
    elif t == "miracle":
        line.append("miracle: the ", style=color)
        line.append(str(p.get("avatar") or "avatar"), style="bold " + color)
        line.append(" grants ")
        line.append(_clan_label(clans, p.get("clan_id")))
        line.append(" a bounty — food blooms around the shrine")
    elif t == "sermon":
        line.append("sermon: ", style=color)
        line.append(f"#{ev.entity_id} of ")
        line.append(str(p.get("clan_name") or _clan_label(clans, p.get("clan_id"))))
        laws = p.get("laws") or []
        line.append(f" interprets the law of {', '.join(map(str, laws[:3]))}", style="dim")
    elif t == "synod":
        clans_n = len(p.get("clans") or [])
        line.append(f"synod of the Sphere: priests of {clans_n} clans convene", style="bold " + color)
        line.append(f" — sacred truce during the {p.get('age', 'crisis')} age", style="dim")
    elif t == "temple":
        line.append("temple: ", style=color)
        line.append(str(p.get("clan_name") or _clan_label(clans, p.get("clan_id"))))
        line.append(" raises its shrine into a glowing Temple of the Sphere")
    elif t == "epiphany":
        line.append("epiphany: ", style=color)
        line.append(mark, style="bold " + color)
        line.append(" beholds the Sphere in three dimensions — strife stills")
    elif t == "resonance":
        laws = p.get("laws") or []
        line.append("resonance: shrines chime for ", style=color)
        line.append(", ".join(map(str, laws[:3])) or "the laws")
    elif t == "raid":
        line.append(f"raid: {p.get('a_name')} hauled {p.get('loot')} grain from {p.get('b_name')}", style="bold " + color)
    elif t == "banquet":
        line.append(f"banquet: {p.get('clan_name')} feasts on the overflowing granary", style=color)
    elif t == "compost":
        line.append(f"compost: #{ev.entity_id} enriched the fields", style=color)
    elif t == "hospitality":
        line.append(f"hospitality: bread broken between {p.get('a_name')} and {p.get('b_name')}", style=color)
    elif t == "peace_envoy":
        line.append(f"📜 envoy: {p.get('a_name')} delivered terms to {p.get('b_name')}", style=color)
    elif t == "market":
        line.append(f"market: neutral post between {p.get('a_name')} and {p.get('b_name')}", style=color)
    elif t == "caravan":
        line.append(f"🐫 caravan: {p.get('a_name')} ⇄ {p.get('b_name')}", style=color)
    elif t == "regicide":
        line.append(f"🗡 regicide: #{p.get('assassin')} of {p.get('assassin_clan')} murdered Chief #{p.get('victim')} of {p.get('victim_clan')}", style="bold " + color)
    elif t == "herald":
        line.append(f"📜 herald: {p.get('a_name')} sent terms to {p.get('b_name')}", style=color)
    elif t == "omen":
        line.append(f"omen: a priest foresees the {p.get('season')} for {p.get('clan_name')}", style="bold " + color)
    elif t == "clan_extinction":
        c_name = p.get("clan_name") or _clan_label(clans, p.get("clan_id"))
        line.append(f"clan extinction: {c_name} has fallen to the last soul", style="bold " + color)
    elif t == "extinction":
        line.append("extinction: all life in the world has ceased", style="bold " + color)
    elif t == "anomaly":
        line.append(f"anomaly discovered: {p.get('kind', 'strange zone')} at ({round(ev.x)}, {round(ev.y)})", style="bold " + color)
    elif t == "outbreak":
        line.append(f"{mark} outbreak", style=color)
    elif t == "recovery":
        line.append(f"{mark} recovered", style=color)
    else:
        # death and anything unlisted
        cause = f" of {ev.cause}" if ev.cause else ""
        label = {"death": "died"}.get(t, t)
        line.append(f"{mark} #{ev.entity_id} {label}{cause}", style=color)

    line.append(f"  ·{ev.tick}", style="dim")
    return line
