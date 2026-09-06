"""GodLaws — grouped form over POST /api/laws (Apply = current world, Save =
current + future worlds) plus preset bundles."""

from __future__ import annotations

from typing import Any

from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Collapsible, Input, Label, Select, Static

# Mirrors GodPanel.tsx SLIDERS/GROUP_ORDER. (key, label)
NUMBER_LAWS: dict[str, list[tuple[str, str]]] = {
    "Food & Energy": [
        ("food_count", "Food abundance"),
        ("energy_max", "Max energy"),
        ("energy_decay_per_tick", "Energy decay / tick"),
        ("energy_from_food", "Energy from food"),
    ],
    "Ecosystem": [
        ("plant_growth_rate", "Plant growth / tick"),
        ("plant_spread_rate", "Plant spread chance"),
        ("nutrient_cycle_rate", "Nutrient cycle ×"),
        ("poison_rate", "Poison sprout chance"),
        ("food_lifespan_ticks", "Food lifespan (ticks)"),
        ("granary_capacity", "Granary capacity"),
    ],
    "Hunger & Sight": [
        ("hungry_ratio", "Hungry threshold (NN slot 0)"),
        ("starving_ratio", "Starving threshold"),
        ("perceive_radius", "Base sight radius"),
        ("eat_radius", "Eat radius"),
    ],
    "Movement": [
        ("steer_turn", "Turning agility"),
    ],
    "Life & Death": [
        ("lifespan_mult", "Lifespan ×"),
    ],
    "Reproduction": [
        ("adult_age", "Adult age"),
        ("birth_rate", "Birth rate"),
        ("carrying_capacity", "Carrying capacity"),
        ("max_population", "Hard pop cap"),
        ("mutation_rate", "Caste mutation rate"),
        ("sex_ratio", "Son probability"),
        ("max_sides", "Max caste sides"),
        ("euthanasia_threshold", "Euthanasia ≥"),
    ],
    "Extinction Safeguards": [
        ("safeguard_critical_pop", "Emergency pop floor (Kcrit)"),
        ("safeguard_relief_ratio", "Relief threshold ratio (Ksafe)"),
        ("safeguard_genesis_batch", "Genesis miracle batch"),
        ("safeguard_max_miracles", "Max miracles"),
    ],
    "Density Soft-Cap Damping": [
        ("damping_steepness", "Damping steepness"),
        ("crowding_stress_mult", "Crowding stress mult"),
        ("resource_strain_mult", "Resource strain mult"),
    ],
    "Boom Periods": [
        ("boom_ramp_days", "Boom ramp days"),
        ("boom_birth_floor", "Boom birth floor"),
        ("boom_cooldown_mult", "Boom cooldown mult"),
        ("boom_energy_mult", "Boom energy mult"),
    ],
    "Neuroevolution": [
        ("mutation_sigma", "NN mutation σ"),
        ("crossover_rate", "NN crossover rate"),
    ],
    "Morphology": [
        ("annealing_start_generation", "Morphology start gen"),
        ("annealing_decay_generations", "Morphology decay gens"),
        ("morph_lambda_override", "Manual lambda override"),
        ("vertex_mutation_std", "Vertex jitter"),
        ("angle_mutation_std", "Angle jitter"),
        ("topological_mutation_rate", "Topo mutation rate"),
    ],
    "Disease": [
        ("disease_outbreak_rate", "Outbreak rate / tick"),
        ("disease_rate", "Contagion chance"),
        ("disease_energy_drain", "Energy drain / tick"),
        ("disease_lethality", "Lethality"),
    ],
    "Sky & Seasons": [
        ("day_length", "Day length (ticks)"),
        ("season_length", "Season length (ticks)"),
        ("winter_food_mult", "Winter food ×"),
        ("night_sight_mult", "Night sight ×"),
        ("weather_change_rate", "Weather turn chance"),
    ],
    "Shelter": [
        ("exposure_drain", "Exposure drain / tick"),
        ("house_capacity", "House capacity"),
        ("house_decay_ticks", "House decay ticks"),
        ("rest_recovery_mult", "Rest healing ×"),
    ],
    "Weather Sickness": [
        ("chill_drain", "Chill drain / tick"),
    ],
    "Territory": [
        ("territory_radius", "Territory radius"),
        ("trespass_decay", "Trespass decay / tick"),
    ],
    "Clan": [
        ("max_clans", "Max clans"),
    ],
    "Trade & Diplomacy": [
        ("coalition_min_size", "Coalition min size"),
        ("alliance_threshold", "Alliance threshold"),
        ("rivalry_threshold", "Rivalry threshold"),
        ("aid_rate", "Aid rate"),
    ],
    "Politics": [
        ("larder_capacity", "Larder capacity"),
        ("coalition_threshold", "Coalition threshold"),
    ],
    "Rebellion": [
        ("schism_threshold", "Schism threshold"),
    ],
    "Predation": [
        ("predator_ratio", "Predator ratio"),
        ("hunt_radius", "Hunt radius"),
        ("bite_damage", "Bite damage"),
        ("energy_from_prey", "Energy from prey"),
        ("fear_radius", "Fear radius"),
    ],
    "Clan War": [
        ("attack_damage", "Attack damage"),
    ],
    "Desperation": [
        ("cannibalism_energy", "Energy per kill"),
    ],
    "Theology": [
        ("tithe_rate", "Tithe rate"),
        ("temple_faith_cost", "Temple faith cost"),
    ],
    "Ages": [
        ("age_length", "Age length (ticks)"),
    ],
    "Culture": [
        ("culture_spread_rate", "Culture spread / tick"),
    ],
    "Wildfire & Disasters": [
        ("fire_rate", "Fire ignite / tick"),
        ("disaster_rate", "Disaster / tick"),
    ],
    "Rivers": [
        ("river_count", "River count"),
    ],
    "Terrain": [],
    "Materials": [],
    "Communication": [],
    "Seismic & Waves": [
        ("earthquake_rate", "Quake rate / tick"),
    ],
    "Electrostatics": [
        ("lightning_strike_rate", "Bolt rate / storm tick"),
    ],
    "Cosmology": [
        ("anomaly_count", "Anomaly zones"),
    ],
    "Bodies & Houses": [
        ("door_clearance", "Door clearance ×"),
    ],
}

BOOL_LAWS: dict[str, list[tuple[str, str]]] = {
    "Reproduction": [("birth_enabled", "Births enabled")],
    "Extinction Safeguards": [
        ("safeguard_enabled", "Safeguards enabled"),
        ("safeguard_morph_mercy", "Morphology mercy"),
    ],
    "Density Soft-Cap Damping": [
        ("soft_cap_enabled", "Soft-cap damping enabled"),
    ],
    "Disease": [("disease_enabled", "Plagues enabled")],
    "Life & Death": [("corpses_enabled", "Corpses remain")],
    "Morphology": [("morphology_annealing_enabled", "Morphology annealing")],
    "Sky & Seasons": [
        ("weather_enabled", "Weather allowed"),
        ("sleep_enabled", "Night rest"),
    ],
    "Shelter": [
        ("shelter_enabled", "Shelter law"),
        ("hearths_enabled", "Hearths in homes"),
        ("house_claim_enabled", "House claiming"),
    ],
    "Territory": [("territory_enabled", "Territory law")],
    "Clan": [
        ("totems_enabled", "Sacred Avatars"),
        ("succession_enabled", "Succession"),
    ],
    "Trade & Diplomacy": [
        ("markets_enabled", "Border trade markets"),
        ("envoys_enabled", "Diplomatic envoys"),
        ("banquets_enabled", "Clan banquets"),
        ("betrayal_enabled", "Betrayal allowed"),
        ("defection_enabled", "Defection allowed"),
        ("tribute_enabled", "Tribute system"),
    ],
    "Communication": [
        ("communication_enabled", "Communication & signals"),
        ("knowledge_enabled", "Knowledge sharing"),
        ("scent_enabled", "Scent trails"),
        ("vocalizations_enabled", "Vocalizations"),
        ("dialect_drift_enabled", "Dialect drift"),
        ("help_call_enabled", "Help calls"),
    ],
    "Rebellion": [("schism_enabled", "Schism")],
    "Ages": [("age_enabled", "World ages")],
    "Culture": [("culture_enabled", "Culture drift")],
    "Wildfire & Disasters": [
        ("wildfire_enabled", "Wildfire"),
        ("disaster_enabled", "Disasters"),
    ],
    "Rivers": [("rivers_enabled", "Rivers")],
    "Terrain": [("relief_enabled", "Relief (height field)")],
    "Materials": [
        ("structural_enabled", "Structural integrity"),
        ("rubble_blocking_enabled", "Rubble blocks path"),
    ],
    "Seismic & Waves": [("earthquake_enabled", "Earthquakes")],
    "Electrostatics": [("lightning_enabled", "Storm lightning")],
    "Ecosystem": [
        ("plant_variants_enabled", "Plant variants"),
        ("food_decay_enabled", "Food decay"),
        ("agriculture_enabled", "Agriculture"),
        ("granaries_enabled", "Granaries"),
        ("soil_depletion_enabled", "Soil depletion"),
    ],
    "Weather Sickness": [("weather_sickness_enabled", "Weather sickness")],
    "Predation": [("predation_enabled", "Predation")],
    "Clan War": [("war_enabled", "Clan war")],
    "Politics": [
        ("coalitions_enabled", "Coalitions"),
        ("leader_decisions_enabled", "Leader decisions"),
        ("resource_sharing_enabled", "Resource sharing"),
    ],
    "Desperation": [
        ("cannibalism_enabled", "Cannibalism"),
        ("eat_kin_enabled", "Eat kin"),
        ("eat_enemy_enabled", "Eat fallen enemies"),
        ("exile_on_kin_eat", "Exile on cannibalism"),
    ],
    "Theology": [
        ("theology_enabled", "Theology of the Sphere"),
        ("omens_enabled", "Priest omens"),
    ],
}

GROUP_ORDER = list(NUMBER_LAWS.keys())

PRESETS = ["balance", "sustainable", "theocracy", "warlords", "chaos", "extinction", "boom"]


def _slug(group: str) -> str:
    return group.lower().replace(" & ", "-and-").replace(" ", "-").replace("ii", "2")


class GodLawsScreen(ModalScreen):
    """Grouped laws form. Apply touches the living world; Save also pins the baseline."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+s", "save_laws", "Save"),
        ("ctrl+a", "apply_laws", "Apply"),
    ]

    DEFAULT_CSS = """
    GodLawsScreen { align: center middle; background: #0d1117ee; }
    #laws-box { width: 92; height: 92%; border: round #30363d; background: #161b22; }
    #laws-toolbar { height: auto; padding: 0 1; }
    #laws-scroll { height: 1fr; }
    .law-row { height: auto; margin-bottom: 0; }
    .law-row Label { width: 1fr; padding-top: 1; }
    .law-row Input { width: 22; }
    .law-group-title { text-style: bold; color: #79c0ff; }
    #laws-actions { height: auto; align-horizontal: right; padding: 0 1; }
    #laws-note { height: auto; padding: 0 1; color: #8b949e; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._original: dict[str, Any] = {}
        self._loaded = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="laws-box"):
            yield Static("laws of nature — god sets rules, never touches a life", id="laws-note")
            with Horizontal(id="laws-toolbar"):
                yield Input(placeholder="filter laws…", id="law-filter")
                yield Select(
                    [(p, p) for p in PRESETS],
                    prompt="preset…",
                    allow_blank=True,
                    id="law-preset",
                )
            with VerticalScroll(id="laws-scroll"):
                for group in GROUP_ORDER:
                    with Collapsible(title=group, collapsed=True, id=f"group-{_slug(group)}"):
                        for key, label in NUMBER_LAWS[group]:
                            with Horizontal(classes="law-row", id=f"row-{key}"):
                                yield Label(label, classes="law-label")
                                yield Input(id=f"num-{key}", name=key)
                        for key, label in BOOL_LAWS.get(group, []):
                            with Horizontal(classes="law-row", id=f"row-{key}"):
                                yield Label(label, classes="law-label")
                                yield Checkbox(label="", id=f"bool-{key}", name=key)
            with Horizontal(id="laws-actions"):
                yield Button("Apply (this world)", variant="default", id="btn-apply")
                yield Button("Save (persist)", variant="primary", id="btn-save")

    async def on_mount(self) -> None:
        await self.load_laws()

    async def load_laws(self) -> None:
        try:
            self._original = await self.app.rest.laws()  # type: ignore[attr-defined]
        except Exception:
            self.query_one("#laws-note", Static).update(
                "could not reach REST API — laws unavailable"
            )
            return
        for key, value in self._original.items():
            num = self.query_one_optional(f"#num-{key}", Input)
            if num is not None:
                num.value = self._fmt(value)
                continue
            chk = self.query_one_optional(f"#bool-{key}", Checkbox)
            if chk is not None:
                chk.value = bool(value)
        self._loaded = True

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

    def _collect_changes(self) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        original = self._original
        for key, base in original.items():
            num = self.query_one_optional(f"#num-{key}", Input)
            if num is not None and self._loaded:
                raw = num.value.strip()
                if raw == "":
                    continue
                if base is None:
                    try:
                        val = int(raw) if "." not in raw else float(raw)
                    except ValueError:
                        val = raw
                    changes[key] = val
                    continue
                try:
                    val = type(base)(raw) if isinstance(base, (int, float)) else raw
                except ValueError:
                    continue
                if isinstance(base, (int, float)) and isinstance(val, (int, float)):
                    changed = abs(float(val) - float(base)) > 1e-9
                else:
                    changed = val != base
                if changed:
                    changes[key] = val
                continue
            chk = self.query_one_optional(f"#bool-{key}", Checkbox)
            if chk is not None and isinstance(base, bool) and chk.value != bool(base):
                changes[key] = chk.value
        return changes

    async def _submit(self, persist: bool) -> None:
        changes = self._collect_changes()
        note = self.query_one("#laws-note", Static)
        if not changes:
            note.update("no changes to apply")
            return
        try:
            result = await self.app.rest.set_laws(changes, persist=persist)  # type: ignore[attr-defined]
        except ValueError as exc:
            note.update(f"rejected: {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            note.update(f"failed: {type(exc).__name__}: {exc}")
            return
        verb = "saved" if persist else "applied"
        note.update(f"{verb}: {', '.join(sorted(changes))}")
        self._original = result or self._original
        # refresh inputs against authoritative values
        for key, value in self._original.items():
            num = self.query_one_optional(f"#num-{key}", Input)
            if num is not None:
                num.value = self._fmt(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            self.run_worker(self._submit(persist=False), exclusive=False)
        elif event.button.id == "btn-save":
            self.run_worker(self._submit(persist=True), exclusive=False)

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "law-preset" or event.value is None:
            return
        preset = str(event.value)
        if preset not in PRESETS:
            return
        note = self.query_one("#laws-note", Static)
        note.update(f"applying preset {preset}…")
        try:
            await self.app.rest.apply_preset(preset, persist=True, reset=False)  # type: ignore[attr-defined]
            note.update(f"preset {preset} applied")
        except Exception as exc:  # noqa: BLE001
            note.update(f"preset failed: {exc}")
        event.select.clear()
        await self.load_laws()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "law-filter":
            return
        needle = event.value.strip().lower()
        for group in GROUP_ORDER:
            entries = [(k, lbl) for k, lbl in NUMBER_LAWS[group]] + [
                (k, lbl) for k, lbl in BOOL_LAWS.get(group, [])
            ]
            coll = self.query_one_optional(f"#group-{_slug(group)}", Collapsible)
            group_hit = not needle
            for key, label in entries:
                hit = not needle or needle in key or needle in label.lower()
                group_hit = group_hit or hit
                row = self.query_one_optional(f"#row-{key}", Horizontal)
                if row is not None:
                    row.display = bool(hit)
            if coll is not None:
                coll.collapsed = not (needle and group_hit) if needle else True
                coll.display = group_hit

    def action_close(self) -> None:
        self.dismiss()

    async def action_save_laws(self) -> None:
        await self._submit(persist=True)

    async def action_apply_laws(self) -> None:
        await self._submit(persist=False)
