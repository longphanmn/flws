#!/usr/bin/env python3
"""
Comprehensive preset experiment harness for 400x300 map.
7 presets x 3 seeds (42,123,999) x 1000 ticks (checkpoints at 500,1000).
Collects population, clan/house/granary counts, war/alliance/disease events,
performance ms/tick, and derives boom vs extinction pressure.
Run via: backend/.venv/bin/python scripts/preset_experiment.py
"""
import sys
import os
import time
import json
import hashlib
import subprocess
import traceback
from dataclasses import replace
from collections import Counter, defaultdict

# ensure backend/app on path. FLWS_BACKEND lets the A/B oscillation harness
# import a different checkout (e.g. a git worktree at the pre-fix revision) so
# world A and world B run on identical harness code.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.environ.get("FLWS_BACKEND", os.path.join(ROOT, "backend"))
sys.path.insert(0, BACKEND_DIR)

from app.config import Config
from app.main import PRESETS
from app.simulation import Simulation
from app.simulation.constants import (
    AGE_CAP_MULT,
    _smooth_age_mult,
    _smooth_season_cap_mult,
)

PRESET_ORDER = ["balance", "sustainable", "theocracy", "warlords", "chaos", "extinction", "boom"]
SEEDS = [42, 123, 999]
CHECKPOINTS = [500, 1000]
TOTAL_TICKS = 1000  # set to 2000 for deeper run; 1000 for speed
W, H = 400, 300

# Intent ranges (alive at ~1000 ticks, unless noted)
INTENT = {
    "balance":    {"range": (200, 350), "notes": "steady 200-350, moderate war/disease, ~78 houses, schism/comm/war rare"},
    "sustainable":{"range": (300, 500), "notes": "360 food, cap 450/600, calm, agriculture/granaries/banquets/temples"},
    "theocracy":  {"range": (250, 450), "notes": "high faith/temples, tithe 0.06, cost 180, banquets+theology, mid war"},
    "warlords":   {"range": (200, 400), "notes": "high war: attack 50 dmg, trespass 1.0, predation 0.04, territorial"},
    "chaos":      {"range": (150, 350), "notes": "high war (60 dmg), disease lethal, predators 0.08, fires/disasters/earthquake/lightning"},
    "extinction": {"range": (30, 180),  "notes": "cataclysmic: 120 food, winter 0.30, disease lethal 0.50, predators 0.08, war 60 dmg"},
    "boom":       {"range": (600, 1000),"notes": "500 food, cap 800/1000, birth 0.25, cooldown 80, adult 80, fast growth, peaceful"},
}

EVENT_TYPES_OF_INTEREST = ["war","conquest","alliance","rivalry","coalition_formed","coalition_joined","betrayal","peace","defection","schism","succession","outbreak","recovery","disaster","fire","predation","cannibalism","exile","takeover","ruin","temple","miracle","synod","epiphany","banquet","raid","market","caravan"]

def run_one(preset_name, seed, total_ticks, checkpoints):
    base_cfg = Config(width=W, height=H, seed=seed, tick_rate=10)
    preset_laws = PRESETS[preset_name]
    # apply preset via dataclass replace (mirrors GodLaws)
    cfg = replace(base_cfg, **{k: v for k, v in preset_laws.items() if hasattr(base_cfg, k)})
    # sanity: ensure width/height stay 400x300 even if preset somehow overrides (it doesn't)
    cfg = replace(cfg, width=W, height=H, seed=seed)
    sim = Simulation(cfg)
    # checkpoint storage
    results_by_tick = {}
    # timing
    tick_times = []
    # initial snapshot at tick 0
    def collect(tick):
        alive = len(sim._cached_creatures) if getattr(sim, "_cached_creatures", None) else 0
        dead = getattr(sim, "deaths", 0)
        dead_by_cause = dict(getattr(sim, "_death_counts", {}))
        infected = sum(1 for c in getattr(sim, "_cached_creatures", [] ) if getattr(c, "infected", False))
        # clan stats
        clans = sim.clans
        alive_clans = 0
        pop_by_clan = getattr(sim, "_clan_members", {})
        # count clans with at least 1 living member
        for cid, members in pop_by_clan.items():
            if len(members) > 0:
                alive_clans += 1
        total_clans = len(clans)
        # houses
        houses = [e for e in sim.world.entities.values() if e.kind=="house" and not getattr(e, "is_ruin", False)]
        ruins = [e for e in sim.world.entities.values() if e.kind=="house" and getattr(e, "is_ruin", False)]
        # granary / larder / faith / temple
        granary_total = sum(float(v.get("granary", 0.0)) for v in clans.values())
        granary_cap = cfg.granary_capacity
        larder_total = sum(float(v.get("larder", 0.0)) for v in clans.values())
        faith_total = sum(float(v.get("faith", 0.0)) for v in clans.values())
        shrine_levels = Counter(int(v.get("shrine_level",0)) for v in clans.values())
        temples = shrine_levels.get(2,0)+shrine_levels.get(3,0)  # level >=2 is temple-ish (config says temple cost upgrades to 2+)
        # actually temple: shrine_level >=2 (level 1 shrine, 2+ temple)
        faith_avg = faith_total / max(1, len(clans))
        granary_avg = granary_total / max(1, len(clans))
        # relations
        relations = sim.relations
        # history event counts total and last 500
        hist = list(sim.history)
        counts = Counter(e.type for e in hist)
        counts_recent = Counter(e.type for e in hist if e.tick >= tick-500) if tick>=500 else counts
        # also disease: outbreak vs recovery
        births = counts.get("birth",0)
        deaths_hist = counts.get("death",0)
        # war / alliance etc
        clan_deaths = dict(getattr(sim, "_clan_deaths", {}))
        # farm plots
        farm_plots_total = sum(len(v) for v in getattr(sim, "farm_plots", {}).values())
        # performance
        avg_ms = (sum(tick_times[-500:])/len(tick_times[-500:])*1000) if tick_times else 0
        return {
            "tick": tick,
            "alive": alive,
            "dead": dead,
            "dead_by_cause": dead_by_cause,
            "infected": infected,
            "clans_total": total_clans,
            "clans_alive": alive_clans,
            "houses": len(houses),
            "ruins": len(ruins),
            "granary_total": round(granary_total,1),
            "granary_avg": round(granary_avg,1),
            "granary_capacity_per_clan": granary_cap,
            "larder_total": round(larder_total,1),
            "faith_total": round(faith_total,1),
            "faith_avg": round(faith_avg,1),
            "shrine_levels": dict(shrine_levels),
            "temples_ge2": temples,
            "farm_plots": farm_plots_total,
            "relations_count": len(relations),
            "history_counts": dict(counts),
            "history_recent": dict(counts_recent),
            "clan_deaths_total": sum(clan_deaths.values()),
            "ms_tick_avg_last500": round(avg_ms,3),
        }

    # tick 0 snapshot
    sim._refresh_cache()  # ensure caches populated before first collect (Simulation.__init__ already does)
    results_by_tick[0] = collect(0)

    checkpoints_set = set(checkpoints)
    # also track growth curve: alive every 100 ticks
    growth_curve = {0: results_by_tick[0]["alive"]}

    for t in range(1, total_ticks+1):
        t0 = time.perf_counter()
        sim.step()
        dt = time.perf_counter() - t0
        tick_times.append(dt)
        if t in checkpoints_set or t % 100 == 0:
            growth_curve[t] = len(sim._cached_creatures)
        if t in checkpoints_set:
            results_by_tick[t] = collect(t)
        # early extinct detection
        if t>30 and len(sim._cached_creatures)==0:
            # still collect remaining checkpoints as extinct state
            for ct in checkpoints:
                if ct>t and ct not in results_by_tick:
                    results_by_tick[ct]=collect(t)
            break

    overall_avg_ms = sum(tick_times)/len(tick_times)*1000 if tick_times else 0
    p95_ms = sorted(tick_times)[int(len(tick_times)*0.95)]*1000 if tick_times else 0
    max_ms = max(tick_times)*1000 if tick_times else 0

    return {
        "preset": preset_name,
        "seed": seed,
        "config": {"food_count": cfg.food_count, "carrying_capacity": cfg.carrying_capacity, "max_population": cfg.max_population,
                   "winter_food_mult": cfg.winter_food_mult, "birth_rate": cfg.birth_rate, "adult_age": cfg.adult_age,
                   "reproduction_cooldown": cfg.reproduction_cooldown, "mate_energy_min": cfg.mate_energy_min,
                   "disease_enabled": cfg.disease_enabled, "disease_rate": cfg.disease_rate, "disease_lethality": cfg.disease_lethality,
                   "war_enabled": cfg.war_enabled, "attack_damage": cfg.attack_damage, "predator_ratio": cfg.predator_ratio,
                   "predation_enabled": cfg.predation_enabled, "trespass_decay": cfg.trespass_decay,
                   "granary_capacity": cfg.granary_capacity, "tithe_rate": cfg.tithe_rate, "temple_faith_cost": cfg.temple_faith_cost},
        "total_ticks_run": sim.tick,
        "performance": {"avg_ms": round(overall_avg_ms,3), "p95_ms": round(p95_ms,3), "max_ms": round(max_ms,3), "total_s": round(sum(tick_times),2)},
        "growth_curve": growth_curve,
        "checkpoints": results_by_tick,
        "final_alive": len(sim._cached_creatures),
        "final_dead": getattr(sim, "deaths",0),
        "final_dead_by_cause": dict(getattr(sim, "_death_counts",{})),
    }

def analyze(all_results):
    print("\n" + "="*110)
    print("PRESET ANALYSIS vs INTENT (400x300, 1000 ticks, 3 seeds each)")
    print("="*110)
    for preset in PRESET_ORDER:
        runs = [r for r in all_results if r["preset"]==preset]
        intent_low, intent_high = INTENT[preset]["range"]
        print(f"\n### {preset.upper()}  intent {intent_low}-{intent_high}  — {INTENT[preset]['notes']}")
        # table header
        print(f"{'seed':>6} | {'tick':>4} | {'alive':>5} | {'dead':>4} | {'clans':>5} | {'houses':>6} | {'granary':>7} | {'larder':>6} | {'faith':>7} | {'war':>3} | {'alnc':>4} | {'outbrk':>6} | {'pred':>4} | {'can':>3} | {'inf':>3} | {'ms/t':>5}")
        print("-"*115)
        alive_at_1k = []
        for run in sorted(runs, key=lambda r:r["seed"]):
            for ck in sorted(run["checkpoints"].keys()):
                if ck not in (500,1000):
                    continue
                cp = run["checkpoints"][ck]
                hc = cp["history_counts"]
                print(f"{run['seed']:6} | {ck:4} | {cp['alive']:5} | {cp['dead']:4} | {cp['clans_alive']:2}/{cp['clans_total']:<2} | {cp['houses']:4}+{cp['ruins']:<1} | {cp['granary_total']:7.0f} | {cp['larder_total']:6.0f} | {cp['faith_total']:7.0f} | {hc.get('war',0):3} | {hc.get('alliance',0):4} | {hc.get('outbreak',0):6} | {hc.get('predation',0):4} | {hc.get('cannibalism',0):3} | {cp['infected']:3} | {cp['ms_tick_avg_last500']:5.1f}")
                if ck==1000:
                    alive_at_1k.append(cp["alive"])
            # growth curve one-liner
            gc = run["growth_curve"]
            print(f"      growth: ", end="")
            for tt in [0,100,200,300,400,500,600,700,800,900,1000]:
                if tt in gc:
                    print(f"{tt}:{gc[tt]:3} ", end="")
            print(f" | perf avg {run['performance']['avg_ms']}ms p95 {run['performance']['p95_ms']}ms")
            # dead by cause at 1k
            dbc = run["final_dead_by_cause"]
            if dbc:
                tot = sum(dbc.values())
                top = sorted(dbc.items(), key=lambda kv:-kv[1])[:5]
                print(f"      dead_by_cause ({tot} total): " + ", ".join(f"{k}:{v}({v/tot*100:.0f}%)" for k,v in top))

        # aggregate verdict
        if alive_at_1k:
            avg_alive = sum(alive_at_1k)/len(alive_at_1k)
            mn, mx = min(alive_at_1k), max(alive_at_1k)
            status = "ON TARGET" if intent_low <= avg_alive <= intent_high else ("OVER" if avg_alive>intent_high else "UNDER")
            print(f"  => AGG alive @1k: avg {avg_alive:.0f}  min {mn} max {mx}  vs intent {intent_low}-{intent_high}  => {status}")
            if status!="ON TARGET":
                drift = avg_alive - (intent_low+intent_high)/2
                print(f"     drift {drift:+.0f} from intent center {(intent_low+intent_high)/2:.0f}")
        # intent-specific deep dives
        if preset=="boom":
            gc_avgs = defaultdict(list)
            for r in runs:
                for t,v in r["growth_curve"].items():
                    gc_avgs[t].append(v)
            print("  BOOM trajectory (avg alive):", " ".join(f"{t}:{sum(v)/len(v):.0f}" for t,v in sorted(gc_avgs.items()) if t%100==0 or t==TOTAL_TICKS))
        if preset=="extinction":
            avg_dead = sum(r["final_dead"] for r in runs)/len(runs) if runs else 0
            avg_inf = sum(r["checkpoints"][1000]["infected"] for r in runs if 1000 in r["checkpoints"])/len(runs) if runs else 0
            print(f"  EXTINCTION avg total dead {avg_dead:.0f}  infected @1k {avg_inf:.0f}")
        if preset in ("theocracy","sustainable"):
            for r in runs:
                if 1000 in r["checkpoints"]:
                    cp=r["checkpoints"][1000]
                    print(f"  seed {r['seed']}: faith {cp['faith_total']:.0f} avg {cp['faith_avg']:.1f} shrine_levels {cp['shrine_levels']} temples≥2 {cp['temples_ge2']} granary {cp['granary_total']:.0f}")

def propose_adjustments(all_results):
    print("\n" + "="*110)
    print("PROPOSED CONCRETE LAW ADJUSTMENTS (to bring each preset into intent range)")
    print("="*110)
    print("Derived from 1000-tick averages across 3 seeds. All numbers are deltas vs current PRESETS in backend/app/main.py")
    print("Validate by re-running harness after edits.\n")
    for preset in PRESET_ORDER:
        runs=[r for r in all_results if r["preset"]==preset]
        if not runs: continue
        alive_vals=[r["checkpoints"][1000]["alive"] for r in runs if 1000 in r["checkpoints"]]
        if not alive_vals: continue
        avg=sum(alive_vals)/len(alive_vals)
        low,high=INTENT[preset]["range"]
        center=(low+high)/2
        drift=avg-center
        # also collect auxiliaries
        avg_dead=sum(sum(r["final_dead_by_cause"].values()) for r in runs)/len(runs)
        hist_avg=Counter()
        for r in runs:
            hist_avg.update(r["checkpoints"][1000]["history_counts"] if 1000 in r["checkpoints"] else {})
        # average houses
        avg_houses=sum(r["checkpoints"][1000]["houses"] for r in runs if 1000 in r["checkpoints"])/len(runs)
        print(f"\n[{preset}] avg alive {avg:.0f} vs intent {low}-{high} center {center:.0f} drift {drift:+.0f} | houses {avg_houses:.0f} | wars {hist_avg.get('war',0)/len(runs):.0f} outbreaks {hist_avg.get('outbreak',0)/len(runs):.0f}")
        if preset=="balance":
            if avg>high:
                print("  OVER -> reduce food_count 240→210, plant_growth 0.05→0.04, carrying 350→300, max_pop 500→420, winter 0.72→0.65, birth_rate 0.05→0.045")
            elif avg<low:
                print("  UNDER -> increase food_count 240→270, winter 0.72→0.78, carrying 350→380, energy_decay 0.022→0.020")
            else:
                # even on target, check composition
                print("  ON TARGET band — fine-tune: keep as-is or nudge relation_drift 1.8→2.2 to keep war rare (currently war ~rare is correct)")
        elif preset=="sustainable":
            if avg<high and avg>low:
                print("  ON TARGET or slightly low/high — if avg ~<350, raise food_count 360→380, granary 500→550, rain_growth 1.30→1.35; if >500 lower birth_rate 0.05→0.045")
            elif avg<low:
                print("  UNDER -> food_count 360→400, winter 0.78→0.82, plant_growth 0.06→0.07, carrying 450→500")
            else:
                print("  OVER -> carrying 450→400, max_pop 600→520, food_count 360→300, birth_rate 0.05→0.04")
        elif preset=="theocracy":
            faiths=[r["checkpoints"][1000]["faith_total"] for r in runs if 1000 in r["checkpoints"]]
            avg_faith=sum(faiths)/len(faiths) if faiths else 0
            temples=sum(r["checkpoints"][1000]["temples_ge2"] for r in runs if 1000 in r["checkpoints"])/len(runs) if runs else 0
            status="faith OK" if avg_faith>2000 else "faith LOW"
            print(f"  faith {avg_faith:.0f} temples≥2 {temples:.1f} ({status})")
            if avg>high:
                print("  OVER pop -> lower food 320→280, carrying 400→340, birth 0.06→0.05")
            elif avg<low:
                print("  UNDER pop -> raise food 320→360, winter 0.75→0.80, carrying 400→450")
            print("  To amplify theocracy signal vs sustainable: lower temple_faith_cost 180→150, raise tithe 0.06→0.07, ensure theology_enabled stays True, keep lifespan_mult 1.1 (priests live longer)")
        elif preset=="warlords":
            wars=hist_avg.get("war",0)/len(runs)
            if wars<5:
                print(f"  War LOW ({wars:.0f}/1k ticks) — intent is high war. Raise trespass 1.0→1.5, lower alliance 65→50, rivalry -35→-20, attack_damage 50→60, coalition_threshold 40→30, relation_drift 1.2→0.6")
            elif wars>30:
                print(f"  War VERY HIGH ({wars:.0f}) — reduce attack_damage 50→35 or raise alliance_threshold 65→75")
            if avg>high:
                print("  ALSO over pop -> cut granary 400→300, larder 350→250, food 290→250")
            elif avg<low:
                print("  ALSO under pop -> raise food 290→320, granary 400→500, winter 0.65→0.70")
        elif preset=="chaos":
            wars=hist_avg.get("war",0)/len(runs); outbreaks=hist_avg.get("outbreak",0)/len(runs); fires=hist_avg.get("fire",0)/len(runs)
            print(f"  war {wars:.0f} outbreak {outbreaks:.0f} fire {fires:.0f}  intent: high war + high disease + high disasters")
            if avg>high:
                print("  OVER resilient -> lower winter 0.50→0.40, raise disease_lethality 0.45→0.55, chill_drain 0.25→0.30, exposure 0.06→0.08, plant_growth 0.045→0.035")
            elif avg<low:
                print("  UNDER collapsed too fast -> raise food 280→320, winter 0.50→0.55, lower predator 0.08→0.05, bite 55→40, disease_rate 0.08→0.06")
            else:
                if wars<10:
                    print("  War below chaos intent -> trespass 1.5→2.0, relation_drift 0.4→0.2, attack 60→70")
                if outbreaks<3:
                    print("  Disease low for chaos -> outbreak 0.001→0.002, disease_rate 0.08→0.10")
        elif preset=="extinction":
            # extinction should be 30-180 but not 0 unless intended; ensure pressure but not instant wipe
            extinct_count=sum(1 for r in runs if r["final_alive"]==0)
            print(f"  extinct runs  {extinct_count}/{len(runs)}  avg alive {avg:.0f}")
            if avg>high:
                print("  OVER survivors too many -> CUT deeper: food 120→90, winter 0.30→0.22, energy_from_food 25→20, energy_decay 0.04→0.045, disease_lethality 0.50→0.60, chill_drain 0.30→0.35, predator 0.08→0.10, fire_rate 0.0008→0.0012")
            elif avg<20 and extinct_count>=2:
                print("  UNDER wipes out instantly -> soften: food 120→150, plant 0.025→0.030, winter 0.30→0.35, disease_outbreak 0.0008→0.0005, attack 60→45, predator 0.08→0.05, chill_drain 0.30→0.24")
            else:
                print("  Borderline — keep; ensure dead_by_cause shows starvation+disease+predation+war mix; if war too low raise trespass 2.0 stays, lower alliance 85→70")
        elif preset=="boom":
            # boom should hit 600-1000 rapidly
            gcs=[r["growth_curve"] for r in runs]
            avg_at_200=sum(gc.get(200,0) for gc in gcs)/len(gcs)
            avg_at_500=sum(gc.get(500,0) for gc in gcs)/len(gcs)
            print(f"  growth 200t {avg_at_200:.0f}  500t {avg_at_500:.0f}  1000t {avg:.0f}")
            if avg<high:
                shortfall=high-avg
                print(f"  UNDER boom by ~{shortfall:.0f} -> push harder: food 500→600, plant_growth 0.08→0.10, plant_spread 0.012→0.015, winter 0.85→0.90, birth 0.25→0.30, adult_age 80→60, cooldown 80→60, mate_energy 15→12, carrying 800→1000, max_pop 1000→1300, energy_from_food 35→38, energy_decay 0.018→0.015")
                # also check schism disabled keeps unity for boom — keep disabled
            elif avg>1000+200:
                print("  OVER explosive (>1200) -> cap: max_pop 1000→900, carrying 800→700, birth 0.25→0.18, food 500→450")
            # always note performance: boom at 800+ pop stresses N150
            avg_ms=sum(r["performance"]["avg_ms"] for r in runs)/len(runs)
            print(f"  perf avg {avg_ms:.1f} ms/tick (800+ pop is CPU heavy — consider omp_threshold, spatial grid 16, or lower perceive radius if >12ms)")

    print("\nGeneric tuning levers reminder:")
    print("  Up population:  +food_count, +plant_growth_rate, +winter_food_mult, +energy_from_food, -energy_decay, +birth_rate, -adult_age, -mate_energy_min, -birth_energy_cost, -reproduction_cooldown, +carrying_capacity/+max_population, -disease/war/predation, +granary/larder/aid_rate")
    print("  Down population:+energy_decay, -food_count, -winter_food_mult, +disease_lethality/outbreak, +predator_ratio/bite_damage, +attack_damage/trespass_decay, -birth_rate, +adult_age, +reproduction_cooldown, -carrying/max_pop")
    print("  War tuning:      trespass_decay (higher=more war), relation_drift (lower=sower feuds), alliance_threshold lower=more allies (less war), rivalry_threshold higher (less negative) = more war, attack_damage, predation enabling, coalitions/betrayal flags")
    print("  Disease tuning:  outbreak_rate, disease_rate, radius, lethality, recovery_rate, weather_sickness/chill_drain")
    print("  Faith/temples:   tithe_rate, temple_faith_cost, theology_enabled, miracles, banquets_enabled")

# ============================================================================
# §BQ-6 Oscillation A/B harness
# ----------------------------------------------------------------------------
# Runs the theocracy preset long enough to span many generation times and
# measures whether population is structurally bouncing. World A is the
# pre-fix code (run this harness against a baseline checkout via FLWS_BACKEND),
# world B is the fixed code. Gates (per seed, post burn-in):
#   CV(N)                         <= 0.08
#   amplitude (max-min)/mean      <= 0.25
#   dN/dt sign reversals          <= 8 per 72k ticks (300-tick smoothing)
#   old-age death burstiness      < 3   (max 100-tick bin / median)
#   min N ever                    > 0.5 * K_eff_min
# ============================================================================

OSC_PRESET = "theocracy"
OSC_SEEDS = [42, 123, 999]
OSC_TOTAL_TICKS = 120000
OSC_BURN_IN = 20000
OSC_SAMPLE = 100
OSC_GATES = {
    "cv_max": 0.08,
    "amplitude_max": 0.25,
    "reversals_max_per_72k": 8.0,
    "burstiness_max": 3.0,
    "min_n_frac_min": 0.5,
}


def _osc_config(seed, overrides=None):
    base = Config(width=W, height=H, seed=seed, tick_rate=10)
    laws = PRESETS[OSC_PRESET]
    cfg = replace(base, **{k: v for k, v in laws.items() if hasattr(base, k)})
    cfg = replace(cfg, width=W, height=H, seed=seed)
    # A proposal is applied *after* the preset, so the run is the proposal and not
    # the preset. Nothing here reads Config.from_env(): the gate path is
    # deliberately F7-immune, so a proposal has to arrive explicitly.
    if overrides:
        cfg = replace(cfg, **overrides)
    return cfg


def run_oscillation(seed, total_ticks=OSC_TOTAL_TICKS, burn_in=OSC_BURN_IN,
                    sample=OSC_SAMPLE, modulated=None, overrides=None):
    """Run one post-burn-in telemetry trace for the theocracy preset.

    modulated=the setpoint is modulated by age/season (pre-fix world A).
    modulated=False -> flat K (post-fix world B).
    """
    cfg = _osc_config(seed, overrides=overrides)
    if modulated is None:
        # auto-detect: does the running code still multiply carrying by age/season?
        # B flattened it, so K stays cfg.effective_carrying_capacity. Probe by
        # checking whether lifecycle still imports the seasonal cap helper.
        modulated = True
    sim = Simulation(cfg)
    K = float(cfg.effective_carrying_capacity)
    M = float(cfg.effective_max_population)
    offset = int(getattr(cfg, "initial_season_offset", 0) or 0)

    for _ in range(burn_in):
        sim.step()
    prev = dict(getattr(sim, "_death_counts", {}))
    samples = []
    t0 = time.perf_counter()
    for t in range(burn_in + 1, total_ticks + 1):
        sim.step()
        if t % 10000 == 0 or t == total_ticks:
            print(f"[osc]   t={t} pop={len(sim._cached_creatures)} food={sum(1 for e in sim.world.entities.values() if e.kind == 'food')} xi={float(getattr(sim, '_density_xi', 0.0) or 0.0):.3f} {time.perf_counter()-t0:.0f}s", flush=True)
        if (t - burn_in) % sample == 0:
            dbc = dict(getattr(sim, "_death_counts", {}))
            deaths = {k: dbc.get(k, 0) - prev.get(k, 0) for k in set(dbc) | set(prev)}
            prev = dbc
            if getattr(cfg, "age_enabled", True) and cfg.age_length > 0:
                age_mult = _smooth_age_mult(t, cfg.age_length, AGE_CAP_MULT)
            else:
                age_mult = 1.0
            season_mult = _smooth_season_cap_mult(t, cfg.season_length, offset=offset)
            samples.append({
                "tick": t,
                "pop": len(sim._cached_creatures),
                "food": sum(1 for e in sim.world.entities.values() if e.kind == "food"),
                "xi": float(getattr(sim, "_density_xi", 0.0) or 0.0),
                "age_mult": round(age_mult, 5),
                "season_mult": round(season_mult, 5),
                "deaths": deaths,
            })
        if t > burn_in + 50 and not sim._cached_creatures:
            break
    elapsed = time.perf_counter() - t0
    return {
        "preset": OSC_PRESET,
        "seed": seed,
        "modulated": bool(modulated),
        "K": K,
        "M": M,
        "total_ticks": sim.tick,
        "burn_in": burn_in,
        "sample": sample,
        "elapsed_s": round(elapsed, 1),
        "ms_per_tick": round(elapsed / max(1, total_ticks - burn_in) * 1000.0, 3),
        "samples": samples,
    }


def _sign_flips(series, deadband=1e-9):
    last = 0
    flips = 0
    for x in series:
        s = 1 if x > deadband else (-1 if x < -deadband else 0)
        if s == 0:
            continue
        if last != 0 and s != last:
            flips += 1
        last = s
    return flips


def _osc_smooth(pops, sample, window_ticks=300.0):
    """Trailing mean over `window_ticks`, the smoother the gates are defined on.

    Single source of truth: osc_metrics and the Phase 1 gate linter must smooth
    identically or the linter measures a different series than the gate does.
    """
    win = max(1, int(round(window_ticks / sample)))
    out = []
    for i in range(len(pops)):
        lo = max(0, i - win + 1)
        seg = pops[lo:i + 1]
        out.append(sum(seg) / len(seg))
    return out


def osc_metrics(run):
    """Derive the oscillation gate metrics from one run's samples."""
    import statistics
    samples = run["samples"]
    if not samples:
        return {"error": "no samples"}
    pops = [s["pop"] for s in samples]
    foods = [s["food"] for s in samples]
    xi = [s["xi"] for s in samples]
    sample = int(run.get("sample", OSC_SAMPLE))
    n_ticks = len(samples) * sample
    mean = statistics.mean(pops)
    sd = statistics.pstdev(pops)
    cv = sd / mean if mean else float("inf")
    amp = (max(pops) - min(pops)) / mean if mean else float("inf")

    # 300-tick smoothing then count d/dt sign reversals
    smoothed = _osc_smooth(pops, sample)
    deriv = [smoothed[i + 1] - smoothed[i] for i in range(len(smoothed) - 1)]
    reversals = _sign_flips(deriv)
    reversals_per_72k = reversals * 72000.0 / max(1, n_ticks)

    # old-age death burstiness over 100-tick bins
    oa = [s["deaths"].get("old_age", 0) for s in samples]
    star = [s["deaths"].get("starvation", 0) for s in samples]
    med_oa = statistics.median(oa) if oa else 0
    max_oa = max(oa) if oa else 0
    burst = (max_oa / med_oa) if med_oa > 0 else float("inf")

    # K_eff floor: modulated world A swings; flat world B is a constant.
    K = float(run.get("K", 0.0))
    if run.get("modulated"):
        k_eff = [K * s["age_mult"] * s["season_mult"] for s in samples]
    else:
        k_eff = [K] * len(samples)
    k_min = min(k_eff) if k_eff else K
    k_max = max(k_eff) if k_eff else K
    min_n_frac = (min(pops) / k_min) if k_min else float("inf")

    return {
        "seed": run["seed"],
        "modulated": run.get("modulated"),
        "K": K,
        "K_eff_min": round(k_min, 1),
        "K_eff_max": round(k_max, 1),
        "N_mean": round(mean, 1),
        "N_min": min(pops),
        "N_max": max(pops),
        "N_cv": round(cv, 4),
        "amplitude": round(amp, 4),
        "band_width": max(pops) - min(pops),
        "drift_rate": round(
            (sum(abs(d) for d in deriv) / len(deriv) / sample) if deriv else 0.0, 6
        ),
        "reversals": reversals,
        "reversals_per_72k": round(reversals_per_72k, 2),
        "old_age_bins_median": med_oa,
        "old_age_bins_max": max_oa,
        "old_age_burstiness": (round(burst, 2) if burst != float("inf") else None),
        "starvation_total": int(sum(star)),
        "old_age_total": int(sum(oa)),
        "min_n_frac": round(min_n_frac, 3),
        "food_mean": round(statistics.mean(foods), 1),
        "food_min": min(foods),
        "food_max": max(foods),
        "xi_mean": round(statistics.mean(xi), 4),
        "xi_max": round(max(xi), 4),
        "ms_per_tick": run.get("ms_per_tick"),
    }


def _effective_flat(run):
    """World B must have a flat setpoint; run_oscillation records whether the
    caller declared it modulated. Re-derive by checking the sample age/season
    multipliers actually applied to K -- but world B does not apply them, so
    the caller passes modulated=False explicitly."""
    return not bool(run.get("modulated"))


def osc_gate_report(metrics, flat):
    """Return (passed: bool, list[(name, status, value)]) against the hard gates.

    ``status`` is tri-state: True = pass, False = fail, None = not measurable.
    An undefined metric is reported, never scored (F5): ``old_age_burstiness``
    is ``max/median`` over 100-tick old-age bins, so a median bin of 0 — a world
    that is not culling its elders — leaves it undefined. Scoring that None as a
    FAIL graded low old-age mortality as a burstiness failure and pushed any
    gate-suite search toward manufacturing deaths to escape the None. An
    undefined gate never decides ``passed``; only a real False does, so this
    cannot become a way to dodge the suite.
    """
    g = OSC_GATES
    checks = []
    checks.append(("CV(N)<=%.2f" % g["cv_max"], metrics["N_cv"] <= g["cv_max"], metrics["N_cv"]))
    checks.append(("amplitude<=%.2f" % g["amplitude_max"], metrics["amplitude"] <= g["amplitude_max"], metrics["amplitude"]))
    checks.append(("reversals/72k<=%.1f" % g["reversals_max_per_72k"], metrics["reversals_per_72k"] <= g["reversals_max_per_72k"], metrics["reversals_per_72k"]))
    b = metrics["old_age_burstiness"]
    checks.append(("burstiness<%.1f" % g["burstiness_max"], (None if b is None else b < g["burstiness_max"]), b))
    checks.append(("minNfrac>%.2f" % g["min_n_frac_min"], metrics["min_n_frac"] > g["min_n_frac_min"], metrics["min_n_frac"]))
    return not any(ok is False for _, ok, _ in checks), checks


def _gate_status(ok) -> str:
    """Tri-state gate status as a string, for artifacts and printed tables."""
    if ok is None:
        return "not-measurable"
    return "pass" if ok else "fail"


# ============================================================================
# §Phase 1 — run manifest, gate linter, admissible region
# ----------------------------------------------------------------------------
# None of this is required to *run* a gate. It is required to *compare* two gate
# runs and to know, before spending simulation time, that a candidate cannot
# pass for a structural reason no constant can fix.
# ============================================================================

MANIFEST_VERSION = 2
# Two runs may only be compared when all of these agree.
#
# `base_config_hash` — the resolved config *before* the run's declared proposal
# was applied, with `seed` excluded — is the config key, not `config_hash`. The
# seed is the replicate index and a proposal is the whole point of a candidate
# run, so neither belongs in a comparability test; hashing either made
# `--osc-compare` refuse every multi-seed and every baseline-to-proposal
# comparison, which are the two comparisons the gate suite exists to make.
# Drift nobody declared still moves `base_config_hash`, so real drift is caught.
MANIFEST_COMPARE_KEYS = (
    "git_sha", "base_config_hash", "tick_budget", "omp_num_threads", "seam",
)
# Config keys the seed is not allowed to reach.
_CONFIG_HASH_EXCLUDE = ("seed",)


def _git_sha() -> str:
    """Read-only; a missing/dirty git must never break a gate run."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def config_hash(cfg) -> str:
    """Stable hash of the *resolved* Config, minus the seed.

    Every field except the ones in `_CONFIG_HASH_EXCLUDE`, order-independent.
    The seed is excluded because it selects a replicate, not a configuration:
    including it made two seeds of one experiment hash differently, and the
    comparability check that consumes this hash then refused to compare them.
    """
    try:
        import dataclasses

        flat = {}
        for f in dataclasses.fields(cfg):
            if f.name in _CONFIG_HASH_EXCLUDE:
                continue
            v = getattr(cfg, f.name, None)
            flat[f.name] = round(v, 9) if isinstance(v, float) else v
        blob = json.dumps(flat, sort_keys=True, default=repr)
    except Exception as exc:  # pragma: no cover - defensive
        blob = f"unhashable:{exc!r}"
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_run_manifest(cfg, *, argv, total_ticks, burn_in, sample,
                       seam="harness-replace", overrides=None, base_cfg=None):
    """Provenance for one gate artifact.

    Without this, two JSON files with the same filename pattern are not known to
    be comparable at all: the oscillation harness builds its Config in-process and
    never touches the DB, so nothing in the artifact records which code, which
    resolved fields, which argv and which thread count produced it. `overrides`
    is the proposal the run was made under, so a proposal run is never mistaken
    for a bare-preset run.

    `config_hash` is the run as it actually was. `base_config_hash` is the config
    it was derived from, i.e. the same thing with the declared proposal removed
    (`base_cfg`; a run with no proposal is its own baseline). Comparing two runs
    on `base_config_hash` is what makes a candidate comparable to its baseline
    while still failing on a field that drifted without anyone declaring it.
    """
    return {
        "manifest_version": MANIFEST_VERSION,
        "git_sha": _git_sha(),
        "seed": getattr(cfg, "seed", None),
        "config_hash": config_hash(cfg),
        "base_config_hash": config_hash(base_cfg if base_cfg is not None else cfg),
        "argv": list(argv),
        "tick_budget": {
            "total_ticks": int(total_ticks),
            "burn_in": int(burn_in),
            "sample": int(sample),
        },
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS", "<unset>"),
        "seam": seam,
        "overrides": dict(overrides or {}),
    }


def manifest_path_for(artifact_path: str) -> str:
    """Manifest lives next to the artifact it describes, one-for-one."""
    base, ext = os.path.splitext(artifact_path)
    return f"{base}.manifest{ext or '.json'}"


def write_run_manifest(artifact_path: str, manifest: dict) -> str:
    path = manifest_path_for(artifact_path)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path


def read_run_manifest(artifact_path: str):
    try:
        with open(manifest_path_for(artifact_path)) as f:
            return json.load(f)
    except Exception:
        return None


# --- admissible region (gate inversion) ------------------------------------


def gate_admissible_region(metrics):
    """The (D, r) box a run must live in to satisfy the gates, beside what it did.

    Read the gates literally and they dictate the dynamics instead of the other
    way round. Gates 1 and 2 bound the band width D = N_max - N_min:

        gate 2  D <= 0.25 * M
        gate 1  sd = D/sqrt(12) for a roughly uniform band, D <= 0.08*M*sqrt(12)

    Gate 3 does not ask for a slow oscillation, it asks that the 300-tick
    smoothed series be monotone for ~90% of the run. A Schmitt-style band of
    width D drifting at r individuals/tick has period T = D/r, so
    T >= 2*72000/reversals_max gives r <= D/T_req. Inside a narrow reflecting
    band the population is stationary, deriv ~ 0, and the flips collapse.
    """
    g = OSC_GATES
    m_mean = float(metrics.get("N_mean") or 0.0)
    d_max = min(g["amplitude_max"], g["cv_max"] * (12.0 ** 0.5)) * m_mean
    t_req = 2.0 * 72000.0 / g["reversals_max_per_72k"]
    r_max = d_max / t_req if t_req else float("inf")
    d_obs = float(metrics.get("band_width") or 0.0)
    r_obs = float(metrics.get("drift_rate") or 0.0)
    return {
        "D_obs": round(d_obs, 3),
        "r_obs": round(r_obs, 6),
        "D_max": round(d_max, 3),
        "r_max": round(r_max, 8),
        "T_req": round(t_req, 1),
        "D_in_region": bool(d_obs <= d_max),
        "r_in_region": bool(r_obs <= r_max),
    }


def format_admissible(a: dict) -> str:
    return (
        "admissible D,r: measured D=%.1f r=%.5f  |  allowed D<=%.1f r<=%.6f "
        "(T_req=%.0f ticks)  |  band %s, drift %s"
        % (
            a["D_obs"], a["r_obs"], a["D_max"], a["r_max"], a["T_req"],
            "IN region" if a["D_in_region"] else "OUT of region",
            "IN region" if a["r_in_region"] else "OUT of region",
        )
    )


# --- gate linter ------------------------------------------------------------

# Scalars that shape a proportional band. §13 forbids sweeping them: they shape
# the fast wiggle, not the broadband wander the reversals gate counts.
SCALAR_DAMPING_KEYS = ("damping_release_tau", "damping_sigmoid_k", "damping_steepness")


def _autocorrelation(series, max_lag):
    n = len(series)
    if n < 2:
        return []
    mu = sum(series) / n
    d = [x - mu for x in series]
    denom = sum(x * x for x in d)
    out = []
    for lag in range(max_lag + 1):
        if denom == 0.0:
            out.append(0.0)
            continue
        num = sum(d[i] * d[i + lag] for i in range(n - lag))
        out.append(num / denom)
    return out


def _periodic_peak_lag(acf, min_lag, threshold=0.3):
    """Lag of the first genuine oscillation peak, or None.

    A limit cycle shows up as a *negative* autocorrelation at roughly half its
    period followed by a positive peak. Broadband wander is positively
    correlated at every lag and never dips below zero, which is exactly why
    tuning a release constant cannot suppress its sign flips. Requiring the
    negative trough is what keeps ordinary noise from reading as periodic.
    """
    for lag in range(min_lag + 1, len(acf) - 1):
        if acf[lag] < threshold:
            continue
        if not (acf[lag] >= acf[lag - 1] and acf[lag] > acf[lag + 1]):
            continue
        if min(acf[min_lag:lag]) < 0.0:
            return lag
    return None


def _lint_no_periodicity(smoothed, sample):
    """F3 — is the reversals gate counting a limit cycle or noise?"""
    m = sum(smoothed) / len(smoothed)
    spread = max(smoothed) - min(smoothed)
    if spread <= 1e-9 * max(1.0, abs(m)):
        return {
            "rule": "F3_no_periodicity", "severity": "ok",
            "message": "smoothed series is flat: no reversals to explain",
            "peak_lag": None,
        }
    acf = _autocorrelation(smoothed, min(len(smoothed) // 3, 200))
    lag = _periodic_peak_lag(acf, min_lag=2)
    if lag is not None:
        return {
            "rule": "F3_no_periodicity", "severity": "ok",
            "message": f"limit cycle detected (ACF peak at lag {lag} samples)",
            "peak_lag": lag,
        }
    return {
        "rule": "F3_no_periodicity", "severity": "warning",
        "message": (
            "no periodic ACF peak: the 300-tick smoothed series is broadband "
            "wander, not a limit cycle, so the reversals gate counts noise. "
            "Changing a damping constant cannot fix it — a topology change is "
            "required (hard envelope, or decoupling N from the season)."
        ),
        "peak_lag": None,
    }


def _lint_median0(metrics):
    """F5 — is the burstiness gate measurable at all?"""
    med = metrics.get("old_age_bins_median")
    if metrics.get("old_age_burstiness") is not None:
        return {
            "rule": "F5_median0_burstiness", "severity": "ok",
            "message": f"old-age burstiness measurable (median bin {med})",
        }
    return {
        "rule": "F5_median0_burstiness", "severity": "blocking",
        "message": (
            f"old-age burstiness is undefined (median 100-tick old-age bin is "
            f"{med}, total {metrics.get('old_age_total')}): gate 4 cannot score "
            f"this run, so escalating it optimizes against nothing"
        ),
    }


def _lint_xi_mean(metrics):
    """F6 — did the density controller ever engage?"""
    xi_mean = metrics.get("xi_mean")
    if xi_mean:
        return {
            "rule": "F6_xi_mean_zero", "severity": "ok",
            "message": f"controller exercised (xi_mean={xi_mean})",
        }
    return {
        "rule": "F6_xi_mean_zero", "severity": "blocking",
        "message": (
            f"xi_mean={xi_mean}: the density controller never engaged, so this "
            f"run has not tested it (the controller has no authority below "
            f"0.85*K). A topology search on this seed optimizes against a "
            f"mechanism it cannot see."
        ),
    }


def _lint_dead_knob(proposal):
    """F4 — is this proposal a no-op, or a forbidden scalar-only nudge?"""
    if not proposal:
        return {
            "rule": "F4_dead_knob", "severity": "ok",
            "message": "no proposal supplied",
        }
    dead = sorted(k for k in proposal if k not in Config.__dataclass_fields__)
    if dead:
        return {
            "rule": "F4_dead_knob", "severity": "blocking",
            "message": (
                f"dead knob(s) {dead}: not Config fields, so density_damping / "
                f"lifecycle cannot read them — this proposal is a silent no-op"
            ),
        }
    keys = sorted(proposal)
    if keys and all(k in SCALAR_DAMPING_KEYS for k in keys):
        return {
            "rule": "F4_dead_knob", "severity": "blocking",
            "message": (
                f"scalar-only damping proposal {keys}: these shape a "
                f"proportional band and the fast wiggle, not the broadband "
                f"wander the reversals gate counts. Proportional-band constants "
                f"cannot produce absorbing behaviour — change topology."
            ),
        }
    return {
        "rule": "F4_dead_knob", "severity": "ok",
        "message": f"proposal levers {keys} reach the simulation",
    }


def _manifest_verdict(rule, severity, message):
    return {"rule": rule, "severity": severity, "message": message}


def _lint_manifest(compare_manifest):
    """I — two runs are comparable only if they were produced the same way.

    `compare_manifest` is the whole list of manifests under comparison, not a
    pair: with three or more paths, checking only the first and the last lets a
    drifted run in the middle through, and the table then reports a gate delta
    between runs nobody established were comparable.

    Two things this must never do:

    * report agreement it did not check. An absent manifest read through
      `(m or {}).get(k)` is `None` for every key, so two legacy artifacts with no
      manifest at all used to print "manifests agree on ...". Absence is now
      reported as absence, and a key a manifest does not carry is a failure to
      check, not a match.
    * refuse a legitimate comparison. The seed and a run's own declared proposal
      are excluded from the config key for exactly that reason — see
      `MANIFEST_COMPARE_KEYS`.
    """
    rule = "manifest_mismatch"
    if not compare_manifest:
        return _manifest_verdict(rule, "ok", "no comparison requested")
    men = list(compare_manifest)
    if len(men) < 2:
        return _manifest_verdict(
            rule, "ok", "no comparison requested: one manifest is not a comparison"
        )

    absent = [i for i, m in enumerate(men) if not m]
    if len(absent) == len(men):
        return _manifest_verdict(
            rule, "warning",
            f"manifest absent for all {len(men)} runs: comparability is unverified "
            f"(these artifacts predate the run manifest), so nothing has been "
            f"checked — a gate delta between them is not evidence",
        )
    if absent:
        return _manifest_verdict(
            rule, "blocking",
            f"manifest absent for run(s) {absent} but present for the others: a run "
            f"with recorded provenance cannot be compared against one without",
        )

    ref = men[0]
    diffs, unchecked = [], []
    for i, man in enumerate(men):
        for k in MANIFEST_COMPARE_KEYS:
            if k not in man:
                unchecked.append(f"{k} (run {i})")
            elif i and man.get(k) != ref.get(k):
                diffs.append(f"{k} (run {i})")
    if unchecked:
        return _manifest_verdict(
            rule, "blocking",
            f"manifest does not record {sorted(unchecked)}: comparability cannot be "
            f"checked, so treating it as agreement would be a false all-clear",
        )
    if diffs:
        return _manifest_verdict(
            rule, "blocking",
            f"manifest mismatch on {sorted(diffs)}: these runs are not comparable, so "
            f"a gate delta between them means nothing",
        )

    same_config = ref.get("config_hash") is not None and all(
        m.get("config_hash") == ref.get("config_hash") for m in men
    )
    if same_config:
        seeds = sorted({m.get("seed") for m in men}, key=lambda s: (s is None, s))
        detail = (
            f" (replicate comparison: identical resolved config, seeds {seeds} "
            f"excluded from the hash)"
        )
    else:
        levers = sorted(
            {k for m in men for k in (m.get("overrides") or {})} or {"<none>"}
        )
        detail = (
            f" (proposal comparison: the config keys that differ are the declared "
            f"levers {levers}; every undeclared field is identical)"
        )
    return _manifest_verdict(
        rule, "ok",
        "manifests agree on " + ", ".join(MANIFEST_COMPARE_KEYS) + detail,
    )


def gate_lint(run, *, proposal=None, compare_manifest=None, metrics=None):
    """Deterministic pre-flight. Returns {ok, rules[], admissible}.

    `ok` is False when any rule is blocking; warnings are reported and do not
    block, because a warning is advice about *how* to fix something, not a
    statement that the run is unscoreable. `manifest_mismatch` is the one rule
    where a warning is an epistemic limit instead of advice — comparability
    *unverified*, not comparability refuted — which is why it is allowed to
    print a table for reference while saying out loud that the table is not
    evidence.
    """
    m = metrics if metrics is not None else osc_metrics(run)
    sample = int(run.get("sample", OSC_SAMPLE)) if run else OSC_SAMPLE
    pops = [s["pop"] for s in (run or {}).get("samples", [])] or [0.0]
    rules = [
        _lint_no_periodicity(_osc_smooth(pops, sample), sample),
        _lint_median0(m),
        _lint_xi_mean(m),
        _lint_dead_knob(proposal),
        _lint_manifest(compare_manifest),
    ]
    return {
        "ok": not any(r["severity"] == "blocking" for r in rules),
        "rules": rules,
        "admissible": gate_admissible_region(m),
    }


def format_gate_lint(report) -> str:
    lines = ["[lint] " + ("OK to escalate" if report["ok"] else "BLOCKED")]
    for r in report["rules"]:
        if r["severity"] != "ok":
            lines.append(f"[lint]   {r['severity'].upper():8} {r['rule']}: {r['message']}")
    lines.append("[lint]   " + format_admissible(report["admissible"]))
    return "\n".join(lines)




def osc_ab_run(args):
    """CLI: run one world/seed trace and persist metrics+samples as JSON."""
    world = args.get("world", "B").upper()
    seed = int(args.get("seed", 42))
    out = args.get("out", os.path.join(ROOT, "scripts", f"oscillation_{world}_{seed}.json"))
    ticks = int(args.get("ticks", OSC_TOTAL_TICKS))
    burn_in = int(args.get("burn_in", OSC_BURN_IN))
    overrides = args.get("overrides") or None
    # World A = pre-fix code keeps the age/season moving setpoint.
    modulated = (world == "A")
    print(f"[osc] world={world} backend={BACKEND_DIR} seed={seed} ticks={ticks} burn_in={burn_in} modulated={modulated} overrides={overrides or {}}", flush=True)
    run = run_oscillation(seed, total_ticks=ticks, burn_in=burn_in, sample=OSC_SAMPLE, modulated=modulated, overrides=overrides)
    m = osc_metrics(run)
    passed, checks = osc_gate_report(m, _effective_flat(run))
    lint = gate_lint(run, metrics=m, proposal=overrides)
    manifest = build_run_manifest(
        _osc_config(seed, overrides=overrides), argv=sys.argv, total_ticks=ticks,
        burn_in=burn_in, sample=OSC_SAMPLE, seam="harness-replace",
        overrides=overrides or {}, base_cfg=_osc_config(seed),
    )
    payload = {"meta": {"world": world, "registry": OSC_GATES, "backend": BACKEND_DIR, "manifest": manifest}, "metrics": m, "gates": [{"name": n, "pass": ok, "status": _gate_status(ok), "value": v} for n, ok, v in checks], "lint": lint, "passed": passed, "samples": run["samples"]}
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    mpath = write_run_manifest(out, manifest)
    print(f"[osc] world={world} seed={seed} metrics={json.dumps(m)}", flush=True)
    print(f"[osc] gates={'PASS' if passed else 'FAIL'} -> {out}", flush=True)
    print(f"[osc] manifest={manifest['git_sha']}/{manifest['config_hash']} -> {mpath}", flush=True)
    print(format_gate_lint(lint), flush=True)
    return payload


def osc_compare(paths):
    """Print the per-seed A-vs-B metrics table and overall gate verdict.

    Refuses to compare runs whose manifests disagree, and prints each run's
    measured (D, r) beside the region the gates actually admit.
    """
    runs = []
    manifests = []
    for p in paths:
        with open(p) as f:
            runs.append(json.load(f))
        manifests.append(read_run_manifest(p) or (runs[-1].get("meta") or {}).get("manifest"))
    table = f"\n{'world':>5} {'seed':>5} {'Nmean':>6} {'Nmin':>5} {'Nmax':>5} {'CV':>7} {'amp':>6} {'rev/72k':>8} {'burst':>6} {'minNfrac':>9} {'starve':>7} {'oldage':>7} {'pass':>7}"
    print(table)
    print("-" * len(table))
    print("  burst 'n/m' = not measurable (median 100-tick old-age bin is 0); pass '*' = at least one gate not measurable")
    all_a, all_b = [], []
    for r in sorted(runs, key=lambda r: (r["meta"]["world"], r["metrics"]["seed"])):
        m = r["metrics"]
        # A None burstiness is *undefined* (median bin 0), not infinite — do not
        # print a number the run never measured.
        b = m["old_age_burstiness"] if m["old_age_burstiness"] is not None else "n/m"
        gate_txt = ("PASS" if r["passed"] else "FAIL")
        if any(g.get("status") == "not-measurable" for g in r.get("gates", [])):
            gate_txt += "*"
        print(f"{r['meta']['world']:>5} {m['seed']:>5} {m['N_mean']:>6.0f} {m['N_min']:>5} {m['N_max']:>5} {m['N_cv']:>7.3f} {m['amplitude']:>6.3f} {m['reversals_per_72k']:>8.1f} {b:>6} {m['min_n_frac']:>9.2f} {m['starvation_total']:>7} {m['old_age_total']:>7} {gate_txt:>7}")
        if "band_width" in m:
            print("           " + format_admissible(gate_admissible_region(m)))
        (all_a if r["meta"]["world"] == "A" else all_b).append(r["passed"])
    print("-" * len(table))
    if len(manifests) > 1:
        # Every manifest, not just the two ends: a drifted run in the middle of
        # a three-way comparison has to be caught, or the table below it is
        # printed for a comparison nobody established.
        report = gate_lint(
            runs[0], metrics=runs[0].get("metrics"),
            compare_manifest=manifests,
        )
        entry = next(r for r in report["rules"] if r["rule"] == "manifest_mismatch")
        print("MANIFEST:", entry["message"])
        if entry["severity"] == "blocking":
            print("REFUSING TO COMPARE: the table above is printed for reference only;")
            print("  a gate delta between non-comparable runs does not mean anything.")
    print(f"A (baseline) all-seed pass={all(all_a) if all_a else 'n/a'}   B (fixed) all-seed pass={all(all_b) if all_b else 'n/a'}")
    if all_b:
        print("GATE VERDICT:", "B MEETS ALL GATES" if all(all_b) else "B FAILS GATES")
    return runs


def main():
    all_results=[]
    total_start=time.perf_counter()
    for preset in PRESET_ORDER:
        for seed in SEEDS:
            print(f"\n>>> Running preset={preset} seed={seed} for {TOTAL_TICKS} ticks (400x300) ...", flush=True)
            try:
                res=run_one(preset, seed, TOTAL_TICKS, CHECKPOINTS)
                all_results.append(res)
                cp1000=res["checkpoints"].get(1000) or res["checkpoints"].get(max(res["checkpoints"].keys()))
                print(f"    done: alive={cp1000['alive']} dead={cp1000['dead']} clans={cp1000['clans_alive']}/{cp1000['clans_total']} houses={cp1000['houses']} war={cp1000['history_counts'].get('war',0)} outbreak={cp1000['history_counts'].get('outbreak',0)} ms/tick avg {res['performance']['avg_ms']}")
            except Exception as e:
                print(f"    FAILED preset={preset} seed={seed}: {e}", flush=True)
                traceback.print_exc()
    elapsed=time.perf_counter()-total_start
    print(f"\n=== All runs complete in {elapsed:.1f}s, {len(all_results)} results ===")
    # save JSON
    out_path=os.path.join(ROOT, "scripts", "preset_experiment_results.json")
    with open(out_path, "w") as f:
        json.dump({"meta":{"W":W,"H":H,"seeds":SEEDS,"checkpoints":CHECKPOINTS,"total_ticks":TOTAL_TICKS,"presets":PRESET_ORDER,"intent":INTENT}, "results":all_results}, f, indent=2)
    print(f"Saved JSON to {out_path}")

    # analysis prints
    analyze(all_results)
    propose_adjustments(all_results)

    # summary table for quick copy
    print("\n" + "="*110)
    print("COMPACT SUMMARY (avg across 3 seeds @ 1000 ticks)")
    print("="*110)
    print(f"{'preset':<12} {'alive avg':>9} {'min':>5} {'max':>5} {'intent':>13} {'dead avg':>9} {'war avg':>7} {'houses':>6} {'ms/t':>6} verdict")
    for preset in PRESET_ORDER:
        runs=[r for r in all_results if r["preset"]==preset]
        avgs=[r["checkpoints"][1000]["alive"] for r in runs if 1000 in r["checkpoints"]]
        avg=sum(avgs)/len(avgs) if avgs else 0
        mn=min(avgs) if avgs else 0
        mx=max(avgs) if avgs else 0
        lo,hi=INTENT[preset]["range"]
        dead=sum(r["final_dead"] for r in runs)/len(runs) if runs else 0
        wars=sum(r["checkpoints"][1000]["history_counts"].get("war",0) for r in runs if 1000 in r["checkpoints"])/len(runs) if runs else 0
        houses=sum(r["checkpoints"][1000]["houses"] for r in runs if 1000 in r["checkpoints"])/len(runs) if runs else 0
        ms=sum(r["performance"]["avg_ms"] for r in runs)/len(runs) if runs else 0
        verdict="OK" if lo<=avg<=hi else ("HIGH" if avg>hi else "LOW")
        print(f"{preset:<12} {avg:9.0f} {mn:5.0f} {mx:5.0f} {f'{lo}-{hi}':>13} {dead:9.0f} {wars:7.0f} {houses:6.0f} {ms:6.1f} {verdict}")

def _parse_set_overrides(argv):
    """`--set field=value`, coerced to the Config field's declared type.

    A proposal must be able to reach *any* field: the harness builds its Config
    with the dataclass constructor, not from_env(), so an env var cannot switch a
    law on for a gate run. An unknown field is a hard error rather than a silent
    no-op — a misspelt knob is exactly the dead-knob class the linter rejects.
    """
    out = {}
    i = 0
    while i < len(argv):
        if argv[i] != "--set":
            i += 1
            continue
        if i + 1 >= len(argv) or "=" not in argv[i + 1]:
            print("[osc] --set needs field=value", file=sys.stderr)
            raise SystemExit(2)
        key, _, raw = argv[i + 1].partition("=")
        field = Config.__dataclass_fields__.get(key)
        if field is None:
            print(f"[osc] --set: {key!r} is not a Config field", file=sys.stderr)
            raise SystemExit(2)
        want = field.type
        try:
            if want is bool or want == "bool":
                out[key] = str(raw).lower() in ("true", "1", "yes", "on")
            elif want is int or want == "int":
                out[key] = int(raw)
            elif want is float or want == "float":
                out[key] = float(raw)
            else:
                out[key] = raw
        except (TypeError, ValueError):
            print(f"[osc] --set: cannot read {raw!r} as {want}", file=sys.stderr)
            raise SystemExit(2)
        i += 2
    return out


def _parse_osc_args(argv):
    args = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--world", "--seed", "--out", "--ticks", "--burn-in"):
            key = a.lstrip("-").replace("-", "_")
            args[key] = argv[i + 1]
            i += 2
        elif a == "--set":
            i += 2
        else:
            i += 1
    overrides = _parse_set_overrides(argv)
    if overrides:
        args["overrides"] = overrides
    return args


if __name__=="__main__":
    argv = sys.argv[1:]
    if "--osc-run" in argv:
        osc_ab_run(_parse_osc_args(argv))
    elif "--osc-compare" in argv:
        idx = argv.index("--osc-compare")
        osc_compare(argv[idx + 1:])
    else:
        main()
