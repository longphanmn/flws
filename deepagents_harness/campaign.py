"""Campaign driver — the flws population-gate fix ladder (card 1872343720142046811).

Spec: ``/root/flws_deepagents_campaign.md``. This module is the *executor* for that
brief; it adds no gate logic of its own. Every number it reports comes from
``osc_gate_report`` via the harness tools, and every signed prediction is scored by
``ledger.close_card`` from those same metrics. The campaign never authors a verdict.

Ladder
------
    linter (0 ticks) -> T0 (3000 ticks, burn-in 1500) -> T1 (18000 ticks, burn-in 4000)
                    -> at most ONE full run_gate (120k A/B)

Three things this module is built to make impossible, each of which a naive driver
gets wrong:

* **A candidate cannot spend a tick before its signed prediction is on the ledger.**
  The budget wall is attached to the ledger with ``require_ledger_entry=True``, and the
  wall is charged in *this* process before the worker subprocess exists — so a refused
  run costs no ticks and leaves no artifact, which is the property
  ``tools.run_trace`` gets by charging before it creates anything.
* **The physics a candidate runs under is provable.** Three of the four topologies have
  no ``Config`` lever, and the brief forbids editing ``backend/``. Each is materialized
  as a byte-copy of ``backend/`` under ``/tmp/opencode/campaign/trees/<name>/`` and
  selected through the existing ``FLWS_BACKEND`` seam, one subprocess per run. Every
  patched file's sha256 and the unified diff are recorded on the card, because
  ``MANIFEST_COMPARE_KEYS`` does *not* include the backend tree identity: ``compare()``
  saying "manifests agree" across two trees is not evidence that the physics matched.
* **An unscoreable gate is never scored.** ``gate_lint`` decides which gates a run can
  reach (F5 median-0 burstiness, F6 xi_mean==0). A card whose gate is unreachable or
  unknown at the rung in hand stays OPEN and escalates; it is not closed "falsified",
  because an undefined metric is not a measurement that refuted anything.

Reads samples never. ``read_metrics`` strips them and the driver only ever calls that.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)  # invoked as a file path, so the package is not importable yet
CAMPAIGN_DIR = "/tmp/opencode/campaign"
TREES_DIR = os.path.join(CAMPAIGN_DIR, "trees")
LOG_DIR = os.path.join(CAMPAIGN_DIR, "log")
REPORT_PATH = os.path.join(CAMPAIGN_DIR, "campaign_report.json")
LEDGER_PATH = os.path.join(REPO, "scripts", "deepagents", "ledger_campaign.jsonl")
SRC_BACKEND = os.path.join(REPO, "backend")
SEEDS = (42, 123, 999)
PY = "/root/deepagents-venv/bin/python"

# Rungs. T0 falsifies (can this candidate move its gate at all, and did the mechanism
# even engage?); T1 is where a signed prediction is scored. burn_in 4000 keeps the
# founding transient out of the reversal count and leaves the season edge at tick 14400
# inside the scored window -- without that, G2 has nothing to decouple from.
RUNGS = {
    "T0": {"ticks": 3000, "burn_in": 1500},
    "T1": {"ticks": 18000, "burn_in": 4000},
}

# The raised budget, stated in the ledger as the brief requires.
#
# CAMPAIGN-2 (this revision). Campaign-1 closed at 4 T1 candidates / 21 cards with a
# 12 h wall. The raise is deliberate and its arithmetic is in the ledger entry
# `budget_raised_campaign2`:
#
#   * 5 T1 candidates: C1 (G1 ablation) + C5 (G2 seasonal) + <=3 tuned C3 variants.
#     Per candidate the driver spends 3 x T0 (3000 ticks) + 3 x T1 (18000 ticks).
#   * measured throughput, campaign-1 (ms/tick, OMP_NUM_THREADS=1, sequential):
#     T0 121-172 s/run, T1 741-1250 s/run -> 5 candidates x 3 x (150 + 1050) s
#     = 5 x 3600 s = 5.0 h of simulation, plus ~0.2 h of tree copies and cards.
#   * one full run_gate (120k A/B) would be 6 runs x 120000 ticks x ~55 ms/tick
#     = 11.0 h on top. It is authorised but NOT spent unless the pre-registered
#     3-of-3-seeds criterion is met, and campaign-1's evidence (best 1 of 3) says
#     it will not be. The wall is 14 h so that the conditional run_gate would FIT if
#     the criterion were ever met -- the criterion, not the clock, is the gate, and a
#     wall that made the run impossible would be deciding by arithmetic.
#   * max_sim_runs 120 covers 6 control runs + 5 x 6 candidate runs (36) with room
#     for a re-measured cell; the wall refuses before that, which is the point.
BUDGET = {
    "max_t1_candidates": 6,
    "max_full_run_gate": 1,
    "max_sim_runs": 120,
    "deadline_s": 60 * 60 * 14,
    "note": (
        "CAMPAIGN-2 raise: 5 T1 candidates (C1, C5, <=3 C3 variants) at 18000 ticks x 3 "
        "seeds, sequential, OMP_NUM_THREADS=1 = ~5.0 h of simulation at the measured "
        "42-68 ms/tick, plus at most ONE full 120k run_gate (6 runs = ~11.0 h) which is "
        "authorised but spent only on the pre-registered 3-of-3-seeds criterion. The "
        "14 h wall is set so the conditional run_gate would fit; the criterion, not the "
        "clock, decides."
    ),
}

GATE_RESOLUTION = {  # osc_metrics rounding: a no-mechanism prediction is floored here
    1: 0.0001,  # N_cv, round(...,4)
    2: 0.0001,  # amplitude, round(...,4)
    3: 0.01,    # reversals_per_72k, round(...,2)
    4: 0.01,    # old_age_burstiness, round(...,2)
    5: 0.001,   # min_n_frac, round(...,3)
}


# --------------------------------------------------------------------------- trees
# Each patch is (relative path under backend/, old, new, expected_count). The driver
# asserts the count before writing: a patch that matches nothing, or matches somewhere
# unexpected, is a silent no-op -- the F4 dead-knob class, in source form.
# G4 with a parameterised elder-onset fraction. The onset is the hazard's SHAPE knob,
# and the only one G4 owns: lambda = 1 / (lifespan - onset) is chosen so the mean age at
# death stays exactly `lifespan`, so moving the onset does NOT change the turnover rate --
# it changes how much of the lifespan the same number of deaths is spread over. That is
# a shape, not a constant tuned for a better number.
def _g4_patches(onset_frac):
    marker = "    OLD_HAZARD_ONSET_FRAC = 0.75\n"
    out, hits = [], 0
    for _rel, _old, _new, _expect in _G4_BODY:
        if marker in _new:
            hits += 1
            _new = _new.replace(marker, f"    OLD_HAZARD_ONSET_FRAC = {onset_frac}\n")
        out.append((_rel, _old, _new, _expect))
    assert hits == 1, f"G4 body carried the onset marker {hits} time(s), expected 1"
    return out


_G4_BODY = [

    (
        "app/simulation/creature_update.py",
        "class CreatureUpdateMixin:\n    def _update_creature(",
        "class CreatureUpdateMixin:\n"
        "    # G4 hazard-uniformised senescence: the fraction of lifespan at which the\n"
        "    # stochastic old-age hazard starts. 0.75 is the existing elder-stage onset,\n"
        "    # so the hazard replaces the threshold without moving the age of onset.\n"
        "    OLD_HAZARD_ONSET_FRAC = 0.75\n\n"
        "    def _update_creature(",
        1,
    ),
    (
        "app/simulation/creature_update.py",
        "                elif c.age >= c.lifespan:\n"
        "                    self._kill(c, \"old_age\")\n"
        "                # Asleep means STILL:",
        "                elif self._senescence_due(c):\n"
        "                    self._kill(c, \"old_age\")\n"
        "                # Asleep means STILL:",
        1,
    ),
    (
        "app/simulation/creature_update.py",
        "            elif c.age >= c.lifespan:\n"
        "                self._kill(c, \"old_age\")\n"
        "            return\n",
        "            elif self._senescence_due(c):\n"
        "                self._kill(c, \"old_age\")\n"
        "            return\n",
        1,
    ),
    (
        "app/simulation/creature_update.py",
        "        if c.age >= c.lifespan:\n"
        "            self._kill(c, \"old_age\")\n"
        "\n"
        "    def _creature_tick_timers(",
        "        if self._senescence_due(c):\n"
        "            self._kill(c, \"old_age\")\n"
        "\n"
        "    def _senescence_due(self, c) -> bool:\n"
        "        \"\"\"G4 hazard-uniformised senescence. True when the hazard fires.\n"
        "\n"
        "        `age >= lifespan` is a threshold, i.e. a delta function of age: every\n"
        "        creature of a cohort crosses it in the same few ticks, so old-age deaths\n"
        "        arrive in lumps and the 100-tick old-age bin ratio (gate 4) measures the\n"
        "        lumpiness of the cohort rather than the mortality of the population.\n"
        "\n"
        "        A memoryless (constant) hazard above the elder onset has age-at-death\n"
        "        exponential with mean `onset + 1/lambda`. Taking\n"
        "        `lambda = 1 / (lifespan - onset)` makes that mean exactly `lifespan`, so\n"
        "        the turnover rate is unchanged and only the *shape* of the death stream\n"
        "        moves: uniform over the old-age window instead of concentrated at its end.\n"
        "        \"\"\"\n"
        "        onset = self.OLD_HAZARD_ONSET_FRAC * c.lifespan\n"
        "        span = c.lifespan - onset\n"
        "        if span <= 0.0 or c.age < onset:\n"
        "            return False\n"
        "        return self.rng.random() < 1.0 / span\n"
        "\n"
        "    def _creature_tick_timers(",
        1,
    ),

]

PATCHES = {
    # G4: hazard-uniformised ageing. The old-age kill was `age >= lifespan`, a delta
    # function of age, so a cohort born together died together (measured 100-tick
    # old-age bins max/median 28-31 against a gate of <3). A memoryless hazard above
    # the elder onset, lambda = 1/(lifespan - onset), has the SAME mean age at death
    # and spreads the same deaths over the whole old-age window.
    "G4": _g4_patches(0.75),
    # G4_EARLY: the same hazard started at 0.60 of lifespan instead of 0.75. Mean age
    # at death is unchanged (lambda is re-derived), so the turnover rate is unchanged;
    # the death stream is spread over 0.60-1.00 of lifespan instead of 0.75-1.00, i.e.
    # 2.3x the window for the same deaths. C3v2's hypothesis: a longer, flatter death
    # stream removes the cohort-locked steps in the 300-tick-smoothed dN/dt that gate 3
    # counts, and buys margin on gate 4 at the same time.
    "G4_EARLY": _g4_patches(0.60),
    # PD: derivative braking. The onset of xi is already immediate; the *release* is an
    # asymmetric exponential with tau=300, which is the textbook delay-induced limit
    # cycle: the brake stays on for 300 ticks after the population has already turned
    # over, drives it back down, and the smoothed series reverses. tau is untouched --
    # this removes the lag, it does not retune the band.
    "PD": [
        (
            "app/density_damping.py",
            "        elif tick != self._last_decay_tick:\n"
            "            # Exponential release toward the target instead of snapping to 0.\n"
            "            # Prevents the birth brake from switching fully off the instant N\n"
            "            # dips below the onset edge (the textbook delay-induced limit cycle).\n"
            "            xi = target + (self.last_xi - target) * math.exp(-1.0 / max(1.0, tau))\n"
            "            if (xi - target) < 0.005:\n"
            "                xi = target\n"
            "            self._last_decay_tick = tick",
            "        elif tick != self._last_decay_tick:\n"
            "            # PD damping: the release lag is only paid on the way UP. When the\n"
            "            # population is not growing (dN/dt <= 0) the brake is already fighting\n"
            "            # the wrong direction, so xi is released to the target at once. When it\n"
            "            # IS growing, the exponential slew is kept, so a rising population is\n"
            "            # still met with a gradually strengthening brake. tau is unchanged.\n"
            "            if N <= self.last_N:\n"
            "                xi = target\n"
            "            else:\n"
            "                xi = target + (self.last_xi - target) * math.exp(-1.0 / max(1.0, tau))\n"
            "                if (xi - target) < 0.005:\n"
            "                    xi = target\n"
            "            self._last_decay_tick = tick",
            1,
        ),
    ],
    # G1T -- the envelope's CEILING reshaped from a veto into a reflecting taper.
    #
    # `_repro_room` returns 0.0 outright the moment n >= hi. That is a step
    # discontinuity in the birth channel sitting exactly where the population is
    # pinned: inside the band N oscillates around K, and every time it touches hi the
    # birth rate snaps to zero, N falls, births resume, N rises. That is a
    # bang-bang relaxation oscillator, and gate 3 counts the sign reversals of the
    # 300-tick-smoothed dN/dt that it produces. C3 measured 5.14/72k on seed 42 (one
    # reversal, the gate allows one) and 20.57/72k on seed 999 (four), with the band
    # and the hazard identical between the two -- so the reversals are the ceiling's
    # switching, not the band's width.
    #
    # The fix is the same shape the LOWER edge already has and the same one the cosine
    # fertility room already uses: no step, room falls continuously to 0 AT hi. The
    # taper occupies the top half of the band, so the birth channel is C1 (the
    # half-band above lo) smooth and continuous everywhere. Reflecting, not
    # approaching-and-leaving. One mechanism, one place, no new state.
    "G1T": [
        (
            "app/simulation/lifecycle.py",
            "            # The upper edge is a veto, not a taper: above K*pop_env_hi_frac\n"
            "            # there are no births at all, so the ceiling reflects instead of\n"
            "            # being approached and left again.\n"
            "            if _env_hi is not None and n >= _env_hi:\n"
            "                return 0.0\n",
            "            # G1T the upper edge is a REFLECTING TAPER, not a veto: room falls\n"
            "            # continuously from 1 at the mid-band to 0 at hi, over the top half\n"
            "            # of the band. A veto is a step discontinuity in the birth channel at\n"
            "            # exactly the population the band pins, so every contact with hi is a\n"
            "            # bang-bang cycle and a sign reversal in the smoothed dN/dt (gate 3).\n"
            "            if _env_hi is not None and n >= _env_hi:\n"
            "                return 0.0\n"
            "            if _env_hi is not None and _env_lo is not None and n > _env_lo:\n"
            "                _mid = 0.5 * (_env_lo + _env_hi)\n"
            "                if n >= _mid:\n"
            "                    _t = (float(n) - _mid) / max(1e-9, _env_hi - _mid)\n"
            "                    return 0.5 * (1.0 + math.cos(math.pi * min(1.0, _t)))\n",
            1,
        ),
    ],
    # G2b: plant-growth decoupling. Plant growth was divided by (1 + resource_strain_mult
    # * xi), so a crowded population also starved the land: the food channel and the
    # density controller were the same signal, and the season's supply wave was
    # amplified exactly when N was high. Dropping the xi term at the coupling site
    # leaves the seasonal food target and the xi birth brake as separate channels.
    "G2": [
        (
            "app/simulation/ecology.py",
            "        if _xi_g:\n"
            "            _growth_eff /= (1.0 + float(getattr(cfg, \"resource_strain_mult\", 1.2)) * _xi_g)\n",
            "        # G2 plant-growth decoupling: no xi throttle on plant growth. The food\n"
            "        # channel and the density controller are separate signals.\n",
            1,
        ),
    ],
}

CANDIDATES = {
    # C1 -- G1 hard envelope (opencode brainstorm 8.2). Already implemented in the
    # serving code behind an inert law flag, so this candidate is pure Config and
    # touches no physics. Prior T1 evidence (/tmp/opencode/t0/T1_inside_band.log,
    # 6000 ticks, 3 seeds): CV 0.0, reversals 0, minNfrac 1.042 PASS, burstiness
    # 28.0/None/31.0 FAIL -- i.e. it buys gates 1,2,3,5 and spends gate 4.
    "C1_G1_env": {
        "topology": "G1",
        "patches": [],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.96,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 hard envelope (birth veto above K*1.04, birth boost below K*0.96)",
        "mechanism_gates": {1: 0.10, 2: 0.25, 3: 50.0, 4: -5.0, 5: 0.20},
    },
    # C2 -- G4 hazard-uniformised ageing. Targets the one gate C1 leaves failing, and
    # the only gate whose metric is a *shape* statistic rather than a level.
    "C2_G4_hazard": {
        "topology": "G4",
        "patches": ["G4"],
        "overrides": {},
        "label": "G4 memoryless old-age hazard (lambda = 1/(lifespan-0.75*lifespan))",
        "mechanism_gates": {4: None},  # min_delta anchored to the measured baseline
    },
    # C3 -- the composition. The only candidate that can be expected to pass all five
    # gates, and therefore the only one worth the single full run_gate.
    "C3_G1xG4": {
        "topology": "G1+G4",
        "patches": ["G4"],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.96,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 envelope + G4 hazard-uniformised ageing",
        "mechanism_gates": {1: 0.10, 2: 0.25, 3: 50.0, 4: 0.0, 5: 0.20},
    },
    # C4 -- PD damping. The only topology that can move gate 3 in the UN-enveloped
    # world, which is the world the shipped preset actually runs.
    "C4_PD_damp": {
        "topology": "PD",
        "patches": ["PD"],
        "overrides": {},
        "label": "PD damping (xi released at once when dN/dt <= 0; tau unchanged)",
        "mechanism_gates": {3: None},
    },
    # C5 -- G2 seasonal/food decoupling. Lowest prior (the 1000-tick smoke moved
    # N_mean 218.1 -> 219.7, i.e. nothing), kept because it is the one topology T0
    # cannot validate and the brief names it.
    #
    # CAMPAIGN-2 promotes it to the second slot and gives it a MECHANISM on gates 1, 2
    # and 5, which is the point of running it: it is the standing gate-5/seasonal gap.
    # Plant growth was divided by (1 + resource_strain_mult * xi), so a crowded
    # population also starved the land -- the food channel and the density controller
    # were the same signal, and the season's supply wave was amplified exactly when N
    # was high. Removing the xi term at the coupling site leaves two separate channels,
    # and the larder/granary capacities buffer the season's step. The predicted move is
    # a SMALL one, and the floors are deliberately small: the 1000-tick prior measured
    # +0.7% on N_mean, so a floor of 0.02 on CV is what the evidence supports. A large
    # floor here would be a prediction I do not believe dressed up as a strong one.
    # Gate 3 is a control expectation: decoupling the food channel has no mechanism on
    # the reversals of the population series, and the F3 lint reads the control's 185
    # as broadband wander rather than anything the food target sets the period of.
    "C5_G2_food": {
        "topology": "G2",
        "patches": ["G2"],
        "overrides": {"larder_capacity": 1200.0, "granary_capacity": 1600.0},
        "label": "G2 larder+granary buffering and no xi throttle on plant growth",
        "mechanism_gates": {1: 0.02, 2: 0.05, 3: None, 4: None, 5: 0.05},
    },
    # C6 -- the composition the ledger first pointed at. C2 (G4) and C4 (PD) were each
    # measured at T1 and their falsifications are on DISJOINT gates: G4 confirmed gate 4
    # (-5.04) and falsified 1/2/5; PD confirmed 1/2/3/5 and falsified gate 4 (+2.0). No
    # envelope, so this is two mechanisms aimed at two gate sets rather than one clamp plus
    # a patch. NOT RUN: see C7 for why its parents' own numbers bound its gate-3 outcome an
    # order of magnitude from the limit. The honest caveat, written before it would run:
    # the two patches each shift the whole RNG stream, so their effects are NOT additive,
    # and that is exactly what such a run would have to measure.
    "C6_G4xPD": {
        "topology": "G4+PD",
        "patches": ["G4", "PD"],
        "overrides": {},
        "label": "G4 hazard-uniformised ageing + PD damping (no envelope)",
        "mechanism_gates": {1: None, 2: None, 3: None, 4: None, 5: None},
    },
    # C7 -- the 4th and final T1 slot, chosen against C6 on the parents' own numbers.
    # C6 (G4+PD, no envelope) is the obvious composition of the two complementary
    # mechanisms, and it is still the wrong one to spend a slot on: its parents measured
    # gate 3 at 162.85 (C2) and 152.57 (C4) against a limit of 8, so C6's gate-3 outcome
    # is already bounded an order of magnitude away by measurement, and the F3 lint reads
    # that series as broadband wander, which needs a structural clamp. C3 (G1xG4) is the
    # only candidate that has PASSED all five gates on a seed, and the gates it still
    # misses are the ones PD owns: gate 3 on seed 999 (20.57 vs 8) and the seed-123
    # collapse (minNfrac 0.495 vs >0.5), where PD alone moved minNfrac 0.158 -> 0.300.
    # So the last slot goes to the three-mechanism composition, and every floor below is
    # the move that REACHES its gate on the seed-mean.
    "C7_G1xG4xPD": {
        "topology": "G1+G4+PD",
        "patches": ["G4", "PD"],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.96,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 envelope + G4 hazard ageing + PD damping",
        "mechanism_gates": {1: 0.1209, 2: 0.3738, 3: 177.143, 4: 6.165, 5: 0.25},
    },
    # ============================ CAMPAIGN-2 ==================================
    # Every candidate below changes exactly ONE thing relative to C3, and every card's
    # floor below was written before the candidate's first tick. The controlling
    # measurement is C3 at T1: seed 42 passes all five gates (CV 0.0002, amp 0.0025,
    # rev 5.14, burst 2.80, minNf 1.039); seed 999 fails gate 3 alone (rev 20.57 vs a
    # limit of 8.0); seed 123 collapses (N_min 0.495K, minNf 0.495 vs a floor of 0.5,
    # CV 0.2469, amp 0.6995, rev 97.71, xi 0.0663 -- famine, not crowding).
    # Two blockers, two different mechanisms, three variants between them.
    #
    # C3v1 -- the CEILING is the reversals generator. `_repro_room` returned 0.0 the
    # moment N >= hi, a step discontinuity in the birth channel sitting exactly where
    # the band pins the population, so every contact with hi is a bang-bang cycle and a
    # sign reversal in the 300-tick-smoothed dN/dt that gate 3 counts. C3's seeds 42
    # and 999 differ ONLY in the RNG stream (identical band, identical hazard) and
    # score 1 reversal and 4 reversals respectively: the gate permits exactly 1
    # (72000/14000 = 5.14 per reversal, limit 8.0). G1T replaces the veto with a
    # cosine taper to zero AT hi, the shape the lower edge and the ordinary fertility
    # room already use. No new state, one place, no constant tuned.
    "C3v1_G1xG4t": {
        "topology": "G1+G4+G1T",
        "patches": ["G4", "G1T"],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.96,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 envelope + G4 hazard ageing + G1T reflecting-taper ceiling",
        # gate 3 is the target: <= 25.14/72k against the control's 185.14, i.e. about
        # half of C3's own 41.14. Gate 4 is the declared risk: letting births persist
        # nearer the ceiling can partially restore the cohort flush G4 de-lumps.
        "mechanism_gates": {1: 0.04, 2: 0.10, 3: 160.0, 4: -0.5, 5: None},
    },
    # C3v2 -- the HAZARD's shape, the only knob G4 owns. lambda = 1/(lifespan-onset)
    # keeps the mean age at death at exactly `lifespan`, so the turnover rate is
    # unchanged; moving the onset from 0.75 to 0.60 of lifespan spreads the same
    # deaths over 2.3x the window (0.40-1.00 instead of 0.25-1.00 of lifespan). The
    # hypothesis is that the cohort-locked steps in the smoothed dN/dt that gate 3
    # counts ARE those death steps, so flattening them removes reversals; and that the
    # same flattening buys margin under gate 4's 3.0 limit. The declared cost is gate
    # 5: the same deaths now happen earlier in life, so the mid-life population -- and
    # therefore the trough -- sits slightly lower.
    "C3v2_G1xG4haz": {
        "topology": "G1+G4(hazard onset 0.60)",
        "patches": ["G4_EARLY"],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.96,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 envelope + G4 hazard ageing started at 0.60 of lifespan",
        "mechanism_gates": {1: 0.03, 2: 0.08, 3: 160.0, 4: 1.0, 5: -0.02},
    },
    # C3v3 -- the only variant that can reach seed 123. `envelope_lower_boost` has
    # jurisdiction only down to `reach = lo - (hi - lo)`, so C3's 0.96/1.04 band has
    # NO jurisdiction below 0.88K -- and seed 123's trough is 0.495K. The lower edge
    # structurally cannot touch that basin at C3's bounds; it is not a matter of
    # strength. Dropping lo to 0.72 while leaving hi at 1.04 widens the band to 0.32K,
    # which pushes reach down to 0.40K -- below the trough -- and puts a 0.35x
    # birth-room lift at exactly 0.495K. Above 0.72K the law is inert, so the pinned
    # band on seeds 42/999 and G4's death-stream shape are untouched. The declared
    # cost is gate 3: a birth gain that is active across 0.40-0.72K is a new gain the
    # collapse basin traverses repeatedly.
    "C3v3_G1xG4deep": {
        "topology": "G1(deep)+G4",
        "patches": ["G4"],
        "overrides": {
            "population_envelope_enabled": True,
            "pop_env_lo_frac": 0.72,
            "pop_env_hi_frac": 1.04,
            "pop_env_lo_birth_boost": 0.5,
        },
        "label": "G1 envelope with lo=0.72 (reach 0.40K, over the collapse basin) + G4",
        "mechanism_gates": {1: 0.04, 2: 0.12, 3: -5.0, 4: None, 5: 0.10},
    },
}

# Candidate order for the ladder, and the reason it is this order.
#
# CAMPAIGN-2 (`/root/flws_deepagents_campaign2.md`) replaced campaign-1's order. The
# order is re-derived from campaign-1's MEASUREMENTS, not from the brief's listing:
#
#   C1 G1    -- the ablation campaign-1 never ran at a scored rung. Its number is the
#               control every other candidate is read against, and it is the only
#               candidate that pins N outright, so it is also the only clean measurement
#               of what the band ALONE costs (Phase 2, 6000 ticks: CV 0.0, rev 0.0,
#               minNf 1.042 PASS, burstiness 28.0/None/31.0 FAIL). Campaign-1 read that
#               at 6000 ticks and never at 18000, so C1's own row is part of the gap.
#   C5 G2    -- the seasonal/food decoupling. The standing gap: gate 5 has only ever
#               been read as a LEVEL, never decomposed against the season, and seed
#               123's gate-5 failure is famine (starvation 508 vs old_age 99,
#               xi 0.0596) rather than crowding, so no density-shaped law reaches it.
#               C5 is the only topology in the families the brief allows that acts on
#               the food channel at all.
#   C3v1     -- the ceiling's bang-bang contact (seed 999's gate 3).
#   C3v2     -- the death stream's shape (seed 999's gate 3, and gate 4's margin).
#   C3v3     -- the lower edge's jurisdiction (seed 123's collapse; the only variant
#               that can reach it at all).
#
# Campaign-1's C2/C4/C3/C7 are exempt: each was measured at T1 and its cards are closed
# on the ledger with its artifacts in the report. Re-running any of them would spend a T1
# slot to re-measure a number that is already on the record. C3 in particular is the
# BASELINE the three variants change one thing from, and C2/C4 are the measured
# calibration for the G4 and PD families.
LADDER = ["C1_G1_env", "C5_G2_food", "C3v1_G1xG4t", "C3v2_G1xG4haz", "C3v3_G1xG4deep"]
LADDER_EXEMPT = {
    "C6_G4xPD": (
        "not run: C2 and C4 measured gate 3 at 162.85 and 152.57 against a limit of 8, so "
        "C6's gate-3 outcome is bounded an order of magnitude away by its parents' own cards; "
        "the 4th T1 slot went to C7 (G1xG4xPD) instead"),
    "C2_G4_hazard": (
        "campaign-1, measured at T1: cards 0002-0006 closed (2 confirmed / 3 falsified), "
        "verdict FAIL on 3 of 3 seeds, seed-mean burstiness 4.125 and reversals 162.85. That "
        "burstiness is the G4 mechanism's calibration, so this row is an INPUT to C3v2 rather "
        "than a candidate to re-run"),
    "C4_PD_damp": (
        "campaign-1, measured at T1: cards 0007-0011 closed (4 confirmed / 1 falsified), "
        "verdict FAIL on 3 of 3 seeds, seed-mean reversals 152.57 and min_n_frac 0.791. It is "
        "the measured statement that no damping law reaches gate 3, which is why no variant in "
        "either campaign touches tau or the damping sigmoid"),
    "C3_G1xG4": (
        "campaign-1, measured at T1: cards 0012-0016 closed (4 confirmed / 1 falsified), the "
        "best candidate in either campaign (seed 42 passes all five gates). It is the BASELINE "
        "each C3 variant changes exactly one thing from, so re-running it would measure the same "
        "number twice and spend a T1 slot to do it"),
    "C7_G1xG4xPD": (
        "campaign-1, measured at T1: cards 0017-0021 closed (1 confirmed / 4 falsified), "
        "verdict FAIL on 3 of 3 seeds. It falsified the additivity of PD to the envelope, which "
        "is why no C3 variant in campaign-2 adds PD"),
}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def materialize_tree(patch_names):
    """Copy backend/ and apply the named patches. Returns provenance for the ledger.

    A copy, not a symlink and not a worktree: the candidate must be a *complete*
    backend (the sim imports ~40 modules by relative path) and the repo's backend/
    must come out of this byte-identical. Verified after the copy by hashing every
    file and comparing to the source.
    """
    name = "cand_" + "_".join(patch_names) if patch_names else "cand_repo"
    dest = os.path.join(TREES_DIR, name)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(SRC_BACKEND, dest, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for pn in patch_names:
        for idx, (rel, old, new, expect) in enumerate(PATCHES[pn]):
            p = os.path.join(dest, rel)
            with open(p) as f:
                src = f.read()
            got = src.count(old)
            if got != expect:
                raise SystemExit(
                    f"patch {pn}[{idx}] on {rel}: expected {expect} occurrence(s) of the "
                    f"anchor, found {got}. Anchor starts {old[:70]!r}. Refusing to write "
                    f"a patch that is a silent no-op."
                )
            with open(p, "w") as f:
                f.write(src.replace(old, new))
    # Provenance: every file whose content differs from the serving tree, with the
    # diff, so the card records what physics the run actually had.
    changed = []
    for root, _dirs, files in os.walk(dest):
        for fn in files:
            d = os.path.join(root, fn)
            rel = os.path.relpath(d, dest)
            s = os.path.join(SRC_BACKEND, rel)
            if not os.path.exists(s) or _sha256(d) != _sha256(s):
                changed.append(rel)
    diffs = {}
    for rel in sorted(changed):
        with open(os.path.join(SRC_BACKEND, rel)) as f:
            a = f.readlines()
        with open(os.path.join(dest, rel)) as f:
            b = f.readlines()
        diffs[rel] = {
            "candidate_sha256": _sha256(os.path.join(dest, rel)),
            "served_sha256": _sha256(os.path.join(SRC_BACKEND, rel)),
            "diff": "".join(difflib.unified_diff(a, b, "served/" + rel,
                                                 "candidate/" + rel, n=2)),
        }
    # config.py must be untouched: config_hash equality across trees is then a true
    # statement about the Config, and the ONLY difference is the declared topology.
    cfg_same = _sha256(os.path.join(dest, "app/config.py")) == _sha256(
        os.path.join(SRC_BACKEND, "app/config.py"))
    if not cfg_same:
        raise SystemExit("candidate tree modified app/config.py; refusing to run")
    return {"tree": name, "path": dest, "changed": sorted(changed), "diffs": diffs,
            "config_py_identical": True, "served_backend_sha256_config": _sha256(
                os.path.join(SRC_BACKEND, "app/config.py"))}


# --------------------------------------------------------------------------- worker
def worker(spec_path):
    """One trace, in a process whose FLWS_BACKEND is the candidate's tree.

    A subprocess per run is not ceremony: `_flws.BACKEND_DIR` is read at import time
    and the gate module caches it, so two physics variants cannot share a process.
    """
    with open(spec_path) as f:
        spec = json.load(f)
    os.environ["FLWS_BACKEND"] = spec["backend"]
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, REPO)
    from deepagents_harness import tools as T  # noqa: E402  (after the env seam)

    out = T.run_trace(
        world=spec["world"], seed=spec["seed"], ticks=spec["ticks"],
        burn_in=spec["burn_in"], out=spec["out"], overrides=spec["overrides"] or None,
        run_id=None, reason=spec["reason"], overwrite=spec.get("overwrite", False),
    )
    print(json.dumps({"ok": True, "path": out, "backend": spec["backend"],
                      "ms_per_tick": T.read_metrics(out)["metrics"].get("ms_per_tick")}))
    return 0


# --------------------------------------------------------------------------- ladder
class Campaign:
    def __init__(self, *, lock=True):
        import atexit
        import fcntl

        from deepagents_harness.budget import BudgetWall
        from deepagents_harness.ledger import GATE_METRICS, Ledger

        os.makedirs(CAMPAIGN_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        # One writer at a time. Found the hard way: a --restate run fixed C3's gate-4
        # card entry and saved the report, and the still-running ladder then saved ITS
        # in-memory copy over the top and reverted the fix -- silently, because the
        # report is a plain JSON file and last-writer-wins. The append-only ledger
        # survived (the card was still open and closable), but the campaign's own memory
        # did not. flock is advisory and tied to the fd, so a killed holder releases it
        # and there is no stale lock to clean up by hand.
        self._lock_fh = None
        if lock:
            self._lock_fh = open(os.path.join(CAMPAIGN_DIR, ".campaign.lock"), "w")
            try:
                fcntl.flock(self._lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                holder = self._lock_fh.name
                try:
                    with open(holder) as f:
                        pid = f.read().strip()
                except OSError:
                    pid = "unknown"
                raise SystemExit(
                    f"another campaign process holds {holder} (pid {pid}). One writer at a "
                    f"time: two processes over one report file revert each other's saves."
                )
            self._lock_fh.write(str(os.getpid()))
            self._lock_fh.flush()
            atexit.register(self._release)

        self.ledger = Ledger(LEDGER_PATH)
        self.budget = BudgetWall(max_sim_runs=BUDGET["max_sim_runs"],
                                 deadline_s=BUDGET["deadline_s"], ledger=self.ledger,
                                 require_ledger_entry=True)
        self.report = {"budget_declared": BUDGET, "rungs": RUNGS, "seeds": list(SEEDS),
                       "ladder": [], "trees": {}, "cards": {}, "notes": []}
        if os.path.exists(REPORT_PATH):
            with open(REPORT_PATH) as f:
                prev = json.load(f)
            # Merge the WHOLE previous report over the defaults. Cherry-picking the keys
            # this class happens to use looked harmless and was not: a second process
            # started with a report missing `control`, `cand` and `linter`, and its first
            # save() deleted them — the campaign's own memory of its results, gone,
            # because a resume path forgot to carry it. A cache that loses fields on
            # resume is worse than no cache, so the resume is now total, and
            # `--rebuild` can re-derive every metric section from the artifacts anyway.
            self.report.update(prev)
            # ...except the budget: the wall in force is the MODULE's BUDGET, not
            # whatever the last process wrote down. Merging the previous report over the
            # defaults put campaign-1's wall (4 T1 candidates, 96 runs, 12 h) back into
            # `budget_declared` while the wall actually refusing runs was campaign-2's
            # (6, 120, 14 h) -- and the report is the artifact of record, so a stale
            # budget in it is a false statement about what governed the runs.
            self.report["budget_declared"] = BUDGET
            self.report.setdefault("notes", [])
            self.budget.spends = prev.get("budget_spends", [])
            self.budget.ticks_spent = prev.get("ticks_spent", 0)

    # -- plumbing ---------------------------------------------------------
    def _release(self):
        import fcntl
        if self._lock_fh is not None:
            try:
                fcntl.flock(self._lock_fh, fcntl.LOCK_UN)
            finally:
                self._lock_fh.close()
                self._lock_fh = None

    def save(self):
        with open(REPORT_PATH, "w") as f:
            json.dump(self.report, f, indent=2, default=repr)
        self.report["budget_spends"] = self.budget.spends
        self.report["ticks_spent"] = self.budget.ticks_spent

    def artifact(self, cand, rung, seed, attempt=0):
        rid = f"camp_{rung}_{cand or 'BASE'}_s{seed}" + (f"_a{attempt}" if attempt else "")
        return os.path.join(REPO, "scripts", "sweeps", rid, f"B_{seed}.json")

    def run_one(self, cand_key, rung, seed, *, tree_path, label):
        """Charge the wall, then spawn the worker. Returns the artifact path."""
        from deepagents_harness import tools as T

        r = RUNGS[rung]
        out = self.artifact(cand_key, rung, seed)
        attempt = 0
        while os.path.exists(out):
            attempt += 1
            out = self.artifact(cand_key, rung, seed, attempt)
        spec = {
            "world": "B", "seed": seed, "ticks": r["ticks"], "burn_in": r["burn_in"],
            "out": out, "overrides": CANDIDATES[cand_key]["overrides"] if cand_key else {},
            "backend": tree_path, "reason": f"campaign {label} {rung} seed {seed}",
        }
        # The wall is charged here, before the subprocess exists: a refusal costs no
        # ticks and leaves no artifact behind.
        self.budget.spend_ticks(r["ticks"], spec["reason"])
        spec_path = os.path.join(CAMPAIGN_DIR, f"spec_{cand_key or 'BASE'}_{rung}_{seed}"
                                           f"{'_a' + str(attempt) if attempt else ''}.json")
        with open(spec_path, "w") as f:
            json.dump(spec, f)
        log = os.path.join(LOG_DIR, f"{cand_key or 'BASE'}_{rung}_{seed}"
                                   f"{'_a' + str(attempt) if attempt else ''}.log")
        t0 = time.time()
        with open(log, "w") as lf:
            proc = subprocess.run([PY, os.path.abspath(__file__), "--worker", spec_path],
                                  stdout=lf, stderr=subprocess.STDOUT, cwd=REPO)
        if proc.returncode != 0:
            self.report["notes"].append(
                f"WORKER FAILED {label} {rung} seed {seed} rc={proc.returncode}; see {log}")
            self.save()
            return None
        m = T.read_metrics(out)
        return {"path": out, "metrics": m["metrics"], "gates": m["gates"],
                "passed": m["passed"], "wall_s": round(time.time() - t0, 1),
                "lint": T.gate_lint(out, proposal=spec["overrides"] or None)}

    # -- rung 0: the linter, no ticks -------------------------------------
    def rung_linter(self):
        from deepagents_harness import tools as T

        out = {}
        for key, spec in CANDIDATES.items():
            entry = {"label": spec["label"], "topology": spec["topology"]}
            # F4: is the proposal a runnable candidate, or a dead knob / scalar nudge?
            try:
                p = T.propose_law_delta(current={}, delta=spec["overrides"] or
                                       {"_no_proposal_": 0}) if spec["overrides"] else {
                    "proposal": {}, "fields": [], "changed": {},
                    "is_topology_change": bool(spec["patches"])}
                entry["proposal_check"] = {"ok": True, "proposal": p["proposal"],
                                           "is_topology_change": p["is_topology_change"]}
            except Exception as exc:
                entry["proposal_check"] = {"ok": False,
                                           "error": f"{type(exc).__name__}: {exc}"}
            # A deliberately broken proposal must be refused without spending a tick.
            try:
                T.propose_law_delta(current={}, delta={"larder_capcity": 1200.0})
                entry["dead_knob_refused"] = False
            except Exception as exc:
                entry["dead_knob_refused"] = True
                entry["dead_knob_error"] = f"{type(exc).__name__}"
            prov = self.tree_for(key)
            entry["tree"] = {"name": prov["tree"], "changed": prov["changed"],
                             "config_py_identical": prov["config_py_identical"],
                             "file_sha256": {k: v["candidate_sha256"]
                                             for k, v in prov["diffs"].items()}}
            out[key] = entry
        self.report["linter"] = out
        self.report["trees"] = {k: v for k, v in self.report["trees"].items()}
        self.save()
        return out

    def tree_for(self, cand_key):
        name = "_".join(CANDIDATES[cand_key]["patches"]) or "repo"
        if name not in self.report["trees"]:
            self.report["trees"][name] = materialize_tree(
                CANDIDATES[cand_key]["patches"])
        return self.report["trees"][name]

    # -- the control, which is a measurement and not a hypothesis ---------
    # The wall refuses any spend without an open card, and that refusal is correct for
    # a *candidate*. The control is the reference every candidate is scored against, so
    # it gets a card of its own with a prediction that is falsifiable and about the
    # control: the brief's ground truth is that the served preset chatters 171-194
    # reversals/72k at 120k ticks, and a 3000-tick trace has 15 samples, i.e. one
    # reversal is worth 48/72k. So the horizon, not the law, is what makes gate 3
    # scoreable -- stated here, before either rung runs, and scored T0 -> T1.
    CONTROL_HYPOTHESIS = (
        "CONTROL (served preset B, no overrides, served backend): the reversals gate is "
        "a function of the scoring horizon, not of the law -- reversals_per_72k rises "
        "from its 3000-tick floor to above the gate limit of 8 by 18000 ticks"
    )
    CONTROL_PREDICTION = {
        "gate": 3,
        "direction": "increase",
        "min_delta": 8.0,
        "rationale": (
            "3000 ticks is 15 samples: one sign flip is worth 72000/1500 = 48 per 72k, "
            "so gate 3 is pinned near 0 and uninformative. Ground truth (brief) is "
            "171-194 reversals/72k at 120k on this preset. If 18000 ticks does not lift "
            "the count above the gate limit, the horizon -- not the density controller "
            "-- is what the reversals gate is reading, and no 18k rung can score it."
        ),
    }

    def open_control_card(self):
        for c in self.ledger.cards():
            if c["hypothesis"] == self.CONTROL_HYPOTHESIS and c["status"] == "open":
                self.report["control_card"] = c["card_id"]
                return c["card_id"]
        cid = self.ledger.open_card(self.CONTROL_HYPOTHESIS,
                                    dict(self.CONTROL_PREDICTION), topology="control")
        self.report["control_card"] = cid
        self.save()
        return cid

    def close_control_card(self, before, after):
        cid = self.report.get("control_card")
        if not cid:
            return None
        rec = self.ledger.card(cid)
        if rec["status"] != "open":
            return rec
        ev = self.ledger.close_card(cid, {"t0": self.report.get("control_t0_path"),
                                          "t1": self.report.get("control_t1_path")},
                                    before=before, after=after)
        self.report["control_verdict"] = {k: ev[k] for k in
                                          ("status", "measured", "measured_delta")}
        self.save()
        return ev

    # -- one candidate, both rungs, cards opened before the first tick ----
    def do_candidate(self, cand_key, rungs=("T0", "T1")):
        """T0 to falsify, T1 to score. Cards are opened before the first tick either way.

        The T0 rung is not a cheaper T1: it asks a different question (did the mechanism
        engage at all -- F6 xi_mean, F5 measurable burstiness -- and did any gate move),
        and a T0 run that shows the mechanism never engaged is a falsification of the
        *mechanism*, not of the signed prediction, which is stated for T1.
        """
        ctl = self.report.get("control", {}).get("T1", {}).get("seed_means")
        if ctl is None:
            raise SystemExit("refusing to open candidate cards before the T1 control exists")
        prior = {c["card_id"] for c in self.report["cards"].get(cand_key, [])
                 if c.get("card_id")}
        if prior:
            cards = self.report["cards"][cand_key]
            print(f"[{cand_key}] cards already on the ledger: "
                  f"{sorted(prior)} (not re-opened)", flush=True)
        else:
            cards = self.open_cards(cand_key, ctl)
        opened = [c for c in cards if c.get("status") == "open"]
        print(f"[{cand_key}] cards open before any further tick: "
              f"{[c['card_id'] for c in opened]}", flush=True)
        out = {}
        for rung in rungs:
            out[rung] = self.do_rung(cand_key, rung)
            if rung == "T1" and len(out[rung]["rows"]) == len(SEEDS):
                agg = _agg_metrics(out[rung]["rows"])
                self.report.setdefault("cand", {}).setdefault(cand_key, {})["T1"] = {
                    "seed_means": {k: v[0] for k, v in agg.items()},
                    "n_seeds": {k: v[1] for k, v in agg.items()},
                    "per_seed": {str(r["seed"]): r["metrics"] for r in out[rung]["rows"]},
                    "per_seed_gates": {str(r["seed"]): r["gates"] for r in out[rung]["rows"]},
                    "per_seed_pass": {str(r["seed"]): r["passed"] for r in out[rung]["rows"]},
                    "paths": [r["path"] for r in out[rung]["rows"]],
                    "lint": [{"seed": r["seed"], "ok": r["lint"]["ok"],
                              "unreachable": r["lint"]["unreachable_gates"],
                              "at_risk": r["lint"]["at_risk_gates"],
                              "unknown": r["lint"]["unknown_gates"],
                              "rules": [(x["rule"], x["severity"]) for x in r["lint"]["rules"]]}
                             for r in out[rung]["rows"]],
                }
                self.close_cards(cand_key, ctl, {k: v[0] for k, v in agg.items()},
                                 {"rung": "T1", "ticks": RUNGS["T1"]["ticks"],
                                  "burn_in": RUNGS["T1"]["burn_in"], "seeds": list(SEEDS),
                                  "control_t1": ctl,
                                  "control_t1_n_seeds": self.report["control"]["T1"]["n_seeds"],
                                  "candidate_t1": {k: v[0] for k, v in agg.items()},
                                  "candidate_t1_n_seeds": {k: v[1] for k, v in agg.items()},
                                  "artifacts": [r["path"] for r in out[rung]["rows"]],
                                  "backend_tree": self.tree_for(cand_key)["tree"],
                                  "tree_file_sha256": {k: v["candidate_sha256"] for k, v
                                                       in self.tree_for(cand_key)["diffs"].items()},
                                  "tree_diff": {k: v["diff"] for k, v
                                                in self.tree_for(cand_key)["diffs"].items()},
                                  "config_overrides": CANDIDATES[cand_key]["overrides"],
                                  "verdicts": {str(r["seed"]): [
                                      {"name": g["name"], "status": g["status"],
                                       "value": g["value"]} for g in r["gates"]]
                                      for r in out[rung]["rows"]}})
        return out

    # -- the signed prediction, opened before the candidate's first tick ---
    def open_cards(self, cand_key, baseline_metrics):
        """One card per gate, min_delta anchored to the MEASURED control.

        Anchoring to the measured baseline is what makes the floor mean something: a
        "decrease by 5" against a baseline of 0.0 is unsatisfiable, and one against a
        baseline of 194 is trivial. The cards are opened after the control run and
        before any candidate tick, so the prediction still precedes the evidence it
        is scored against.
        """
        from deepagents_harness.ledger import GATE_METRICS, LedgerError

        spec = CANDIDATES[cand_key]
        prov = self.tree_for(cand_key)
        opened = []
        for gate in (1, 2, 3, 4, 5):
            metric = GATE_METRICS[gate]
            base_val = (baseline_metrics or {}).get(metric)
            mech = spec["mechanism_gates"].get(gate)
            if base_val is None:
                # F5/F6: the control cannot score this gate, so no signed delta can be
                # computed against it. The card is not opened; the gate is reported as
                # unmeasurable on this rung rather than guessed at.
                opened.append({"gate": gate, "status": "not_opened",
                               "why": f"baseline {metric} is None (not measurable)"})
                continue
            if mech is None:
                direction = "increase" if gate == 5 else "decrease"
                min_delta = GATE_RESOLUTION[gate]
                why = ("control expectation: this topology has no mechanism on this "
                       "gate; min_delta is the metric's reporting resolution, so a "
                       "confirmed card means 'gate unmoved in the expected direction' "
                       "and a falsified one means 'gate moved against it'")
            elif mech < 0:
                direction = "increase"  # lower is better, so a negative floor is a cost
                min_delta = -mech
                why = ("predicted COST: this topology is expected to make this gate "
                       "worse, and the card is falsified if the gate does not get worse")
            else:
                direction = "decrease" if gate != 5 else "increase"
                min_delta = mech
                why = ("mechanism gate: predicted signed move from the topology, floor "
                       "set from the measured control")
            hyp = (f"{cand_key} [{spec['topology']}] {spec['label']} -> gate {gate} "
                   f"({metric}) {direction} by >= {min_delta} at rung T1 "
                   f"({RUNGS['T1']['ticks']} ticks, burn-in {RUNGS['T1']['burn_in']}, "
                   f"seeds {list(SEEDS)}); backend tree {prov['tree']}")
            try:
                cid = self.ledger.open_card(hyp, {"gate": gate, "direction": direction,
                                                  "min_delta": min_delta,
                                                  "rationale": why}, topology=spec["topology"])
            except LedgerError as exc:
                opened.append({"gate": gate, "status": "ledger_refused",
                               "why": f"{exc}"})
                continue
            opened.append({"gate": gate, "status": "open", "card_id": cid,
                           "prediction": self.ledger.card(cid)["prediction"]})
        self.report["cards"][cand_key] = opened
        self.save()
        return opened

    def close_cards(self, cand_key, before, after, result_extra):
        """Score every open card from the measured signed delta. Never authored."""
        closed = []
        for rec in self.report["cards"].get(cand_key, []):
            if rec.get("status") != "open":
                closed.append(rec)
                continue
            cid = rec["card_id"]
            try:
                ev = self.ledger.close_card(cid, result_extra, before=before, after=after)
                rec.update(status=ev["status"], measured=ev["measured"],
                           measured_delta=ev["measured_delta"])
            except Exception as exc:
                rec.update(status="unscorable", why=f"{type(exc).__name__}: {exc}")
            closed.append(rec)
        self.save()
        return closed

    # -- one rung of one candidate ----------------------------------------
    def do_rung(self, cand_key, rung):
        from deepagents_harness import tools as T

        label = cand_key or "BASELINE"
        if cand_key is None:
            self.open_control_card()
        tree = SRC_BACKEND if cand_key is None else self.tree_for(cand_key)["path"]
        rows = []
        # Resume: a row already measured in this campaign is reused, never re-run. The
        # alternative -- a fresh attempt directory for the same (cand, rung, seed) --
        # would leave two artifacts per cell and no way to tell which one a card was
        # scored against.
        done = {(e["rung"], e["cand"], r["seed"]): r for e in self.report["ladder"]
                for r in e["rows"]}
        for seed in SEEDS:
            prior = done.get((rung, cand_key, seed))
            if prior and os.path.exists(prior["path"]):
                rows.append(prior)
                print(f"[{label} {rung} seed {seed}] reused {prior['path']}", flush=True)
                continue
            res = self.run_one(cand_key, rung, seed, tree_path=tree, label=label)
            if res is None:
                break
            rows.append({"seed": seed, **res})
            print(f"[{label} {rung} seed {seed}] {res['wall_s']}s "
                  f"cv={res['metrics']['N_cv']} amp={res['metrics']['amplitude']} "
                  f"rev={res['metrics']['reversals_per_72k']} "
                  f"burst={res['metrics']['old_age_burstiness']} "
                  f"minNf={res['metrics']['min_n_frac']} xi={res['metrics']['xi_mean']} "
                  f"pass={res['passed']}", flush=True)
            self.save()
        entry = {"rung": rung, "cand": cand_key, "label": label, "rows": rows}
        if cand_key is None and len(rows) == len(SEEDS):
            # The control's per-rung metrics: T0 is the `before` of the control card and
            # T1 the `after`, and T1 is also the anchor every candidate's min_delta is
            # measured against. A metric that is None on some seeds (F5: burstiness is
            # undefined when the median 100-tick old-age bin is 0) is averaged over the
            # seeds that HAVE it, and the count is carried with it: a mean over 1 of 3
            # seeds reported as if it were a mean over 3 is how a gate gets a verdict it
            # did not earn.
            agg = _agg_metrics(rows)
            entry["seed_means"] = {k: v[0] for k, v in agg.items()}
            self.report.setdefault("control", {})[rung] = {
                "seed_means": {k: v[0] for k, v in agg.items()},
                "n_seeds": {k: v[1] for k, v in agg.items()},
                "per_seed": {str(r["seed"]): r["metrics"] for r in rows}}
            if rung == "T0":
                self.report["control_t0_path"] = rows[0]["path"]
            if rung == "T1":
                self.report["control_t1_path"] = rows[0]["path"]
        if len(rows) == 2:  # baseline vs candidate
            base, cand = rows[0], rows[1]
            if base["seed"] == cand["seed"]:
                table = T.compare([base["path"], cand["path"]])
                entry["compare"] = {"comparable": table["comparable"],
                                    "delta_readable": table["delta_readable"],
                                    "note": table["note"]}
        self.report["ladder"].append(entry)
        self.save()
        return entry


    # -- re-stating a floor the ledger refused -----------------------------
    def restate_refused(self, cand_key, gate, min_delta, why):
        from deepagents_harness.ledger import GATE_METRICS

        """Re-open ONE refused card with a floor that is actually falsifiable.

        `Ledger._validate_prediction` rejects `min_delta <= 0` — "a prediction that any
        result satisfies is not a prediction" — which is correct, and it caught a real
        authoring error: C3's gate-4 floor was written as 0.0 meaning "any decrease
        counts". The floor that was actually meant is the one that reaches the gate:
        control 9.165 minus the 3.0 limit.

        Guarded twice over. The candidate must have no T1 row yet (the prediction has to
        precede the ticks it is scored against), and a refused entry may be restated only
        once, so a floor cannot be re-stated until it stops being falsifiable.
        """
        spent = [r for e in self.report["ladder"]
                 if e["cand"] == cand_key and e["rung"] == "T1" for r in e["rows"]]
        if spent:
            raise SystemExit(
                f"refusing to re-state a floor for {cand_key}: {len(spent)} T1 row(s) are "
                f"already measured. A prediction written after the evidence is a "
                f"rationalisation, not a forecast."
            )
        recs = self.report["cards"].get(cand_key, [])
        target = [r for r in recs if r["gate"] == gate and r["status"] == "ledger_refused"]
        if not target:
            raise SystemExit(f"{cand_key} gate {gate}: no refused card to re-state")
        if any(r["gate"] == gate and r["status"] == "open" for r in recs):
            raise SystemExit(f"{cand_key} gate {gate} already has an open card")
        spec = CANDIDATES[cand_key]
        prov = self.tree_for(cand_key)
        direction = "increase" if gate == 5 else "decrease"
        hyp = (f"{cand_key} [{spec['topology']}] {spec['label']} -> gate {gate} "
               f"({GATE_METRICS[gate]}) {direction} by >= {min_delta} at rung T1 "
               f"({RUNGS['T1']['ticks']} ticks, burn-in {RUNGS['T1']['burn_in']}, "
               f"seeds {list(SEEDS)}); backend tree {prov['tree']}")
        cid = self.ledger.open_card(hyp, {"gate": gate, "direction": direction,
                                          "min_delta": min_delta, "rationale": why},
                                    topology=spec["topology"])
        target[0].update(status="open", card_id=cid,
                         prediction=self.ledger.card(cid)["prediction"],
                         restated_from_ledger_refusal=True,
                         restated_why="the 0.0 floor was refused by "
                                      "Ledger._validate_prediction before any T1 tick was "
                                      "spent; restated as the move that reaches the gate")
        self.save()
        return cid

    # -- adopting a card that outlived the process that opened it ----------
    def adopt_open_card(self, cand_key, card_id):
        """Attach an already-open ledger card to this candidate and close it.

        Needed because a `--restate` run in a *second* process wrote a fix that the
        still-running ladder then reverted with its own save (fixed: the campaign now
        holds an exclusive lock, one writer at a time). The append-only ledger kept the
        card, so nothing was lost -- but the report's card list no longer mentioned it,
        and an open card is a promise the campaign has to keep.

        The check that matters is TIMING, and it is checked against the filesystem rather
        than asserted: every T1 artifact for this candidate must be NEWER than the card's
        own `ts` on the ledger. A card opened after its evidence cannot be adopted, which
        is the whole reason the prediction has to precede the run.
        """
        rec = self.ledger.card(card_id)
        if rec["status"] != "open":
            raise SystemExit(f"{card_id} is {rec['status']}, not open")
        opened_ts = next(e["ts"] for e in rec["events"] if e["event"] == "card_opened")
        rows = [r for e in self.report["ladder"]
                if e["cand"] == cand_key and e["rung"] == "T1" for r in e["rows"]]
        for r in rows:
            mt = os.path.getmtime(r["path"])
            if mt < opened_ts:
                raise SystemExit(
                    f"refusing to adopt {card_id}: T1 artifact {r['path']} was written "
                    f"{mt - opened_ts:.0f}s BEFORE the card was opened. A prediction "
                    f"recorded after the evidence is a rationalisation, not a forecast."
                )
        gate = rec["prediction"]["gate"]
        recs = self.report["cards"].setdefault(cand_key, [])
        entry = next((r for r in recs if r["gate"] == gate), None)
        if entry is None:
            recs.append({"gate": gate, "status": "open", "card_id": card_id,
                         "adopted": True,
                         "adopted_note": "opened by an earlier campaign process; adopted "
                                         "and closed by this one"})
            entry = recs[-1]
        entry.update(status="open", card_id=card_id,
                     prediction=rec["prediction"], adopted=True,
                     adopted_after_clobber=True)
        self.save()
        return card_id

    # -- the whole ladder, one process ------------------------------------
    def run_ladder(self, cands):
        """Control first (it anchors every prediction), then the candidates in order.

        One process for the whole ladder on purpose: the wall's state, the open cards and
        the report are the campaign's memory, and a fresh process per candidate would
        mean re-deriving them. Every step is resumable, so a killed ladder is restarted
        with the same command and spends nothing twice.
        """
        self.rung_linter()
        self.do_rung(None, "T0")
        self.do_rung(None, "T1")
        t0 = self.report.get("control", {}).get("T0", {}).get("seed_means")
        t1 = self.report.get("control", {}).get("T1", {}).get("seed_means")
        if t0 and t1:
            print("[control] " + json.dumps(self.close_control_card(t0, t1),
                                            default=repr), flush=True)
        for key in cands:
            print(f"\n===== CANDIDATE {key} =====", flush=True)
            try:
                self.do_candidate(key)
            except SystemExit as exc:
                # A driver refusal is a RESULT, not a crash. `Campaign.__init__`,
                # `materialize_tree` and the budget wall all refuse with SystemExit,
                # which is a BaseException and so slips past `except Exception`: one
                # refused candidate used to end the process with a non-zero code after
                # the report was written and the other candidates measured -- a
                # complete campaign's results on disk and a failed exit status for the
                # wrapper, which is the worst of both. Only SystemExit is absorbed;
                # KeyboardInterrupt/SIGTERM still propagate.
                self.report["notes"].append(
                    f"CANDIDATE {key} REFUSED (SystemExit): {exc}")
                print(f"[{key}] REFUSED (SystemExit): {exc}", flush=True)
            except Exception as exc:
                self.report["notes"].append(f"CANDIDATE {key} FAILED: "
                                            f"{type(exc).__name__}: {exc}")
                print(f"[{key}] FAILED {type(exc).__name__}: {exc}", flush=True)
            self.write_summary(key)
            self.save()
            print(f"STATUS {key}: {self.one_line(key)}", flush=True)
        self.write_summary("ALL")
        return 0

    def one_line(self, key):
        c = self.report.get("cand", {}).get(key, {}).get("T1")
        if not c:
            return "no T1 result"
        gates = []
        for g, m in (("CV", "N_cv"), ("amp", "amplitude"), ("rev", "reversals_per_72k"),
                     ("burst", "old_age_burstiness"), ("minNf", "min_n_frac")):
            v = c["seed_means"].get(m)
            gates.append(f"{g}={v}({c['n_seeds'].get(m)})")
        cards = self.report["cards"].get(key, [])
        st = {}
        for rec in cards:
            st[rec.get("status")] = st.get(rec.get("status"), 0) + 1
        return (f"T1 seed-means {' '.join(gates)} | pass/seed {c['per_seed_pass']} | "
                f"cards {st}")

    # -- rebuild the derived sections from the artifacts -------------------
    def rebuild(self):
        """Re-derive every metric section from the artifacts on disk. No ticks.

        The artifacts are the record; the report is a cache over them. This walks the
        ladder, re-reads each artifact through `read_metrics` (which strips samples and
        RE-DERIVES the verdict with `osc_gate_report` rather than quoting the stored one),
        and recomputes the control and candidate aggregates. A hand-edited `passed: true`
        in an artifact therefore cannot survive a rebuild.
        """
        from deepagents_harness import tools as T
        for entry in self.report["ladder"]:
            for row in entry["rows"]:
                m = T.read_metrics(row["path"])
                row["metrics"] = m["metrics"]
                row["gates"] = m["gates"]
                row["passed"] = m["passed"]
                if not m["verdict_consistent"] and m["verdict_present"]:
                    self.report["notes"].append(
                        f"stored verdict disagrees with the re-derived one at "
                        f"{row['path']}: stored={m['stored_passed']} derived={m['passed']}")
        for entry in self.report["ladder"]:
            rows, rung, cand = entry["rows"], entry["rung"], entry["cand"]
            if not rows:
                continue
            agg = _agg_metrics(rows)
            means = {k: v[0] for k, v in agg.items()}
            ns = {k: v[1] for k, v in agg.items()}
            if cand is None:
                self.report.setdefault("control", {})[rung] = {
                    "seed_means": means, "n_seeds": ns,
                    "per_seed": {str(r["seed"]): r["metrics"] for r in rows}}
            elif rung == "T1":
                self.report.setdefault("cand", {}).setdefault(cand, {})["T1"] = {
                    "seed_means": means, "n_seeds": ns,
                    "per_seed": {str(r["seed"]): r["metrics"] for r in rows},
                    "per_seed_gates": {str(r["seed"]): r["gates"] for r in rows},
                    "per_seed_pass": {str(r["seed"]): r["passed"] for r in rows},
                    "paths": [r["path"] for r in rows]}
        self.save()
        return self.report

    def write_summary(self, key):
        out = {"candidate": key,
               "label": (CANDIDATES[key]["label"] if key in CANDIDATES else "campaign"),
               "cards": self.report["cards"].get(key, []),
               "t1": self.report.get("cand", {}).get(key, {}).get("T1"),
               "notes": self.report["notes"]}
        p = os.path.join(CAMPAIGN_DIR, f"summary_{key}.json")
        with open(p, "w") as f:
            json.dump(out, f, indent=2, default=repr)
        return p


def _agg_metrics(rows):
    """Seed-mean of every gate metric, with the number of seeds that contributed.

    Returns {key: (mean_or_None, n_seeds_used)}. None for a key no seed measured: a
    metric that does not exist on any seed has no signed delta to score.
    """
    keys = ("N_cv", "amplitude", "reversals_per_72k", "old_age_burstiness",
            "min_n_frac", "xi_mean", "N_mean", "old_age_total", "starvation_total",
            "old_age_bins_median", "old_age_bins_max", "band_width")
    out = {}
    for k in keys:
        vals = [r["metrics"].get(k) for r in rows]
        vals = [v for v in vals if v is not None]
        out[k] = (round(sum(vals) / len(vals), 6) if vals else None, len(vals))
    return out


def _print_table(report):
    for entry in report["ladder"]:
        for r in entry["rows"]:
            m = r["metrics"]
            gates = " ".join(
                f"{g['name'].split('(')[0].split('<')[0].split('>')[0].strip()}="
                f"{g['status'][:4]}" for g in r["gates"])
            print(f"{entry['label']:12} {entry['rung']} s{r['seed']:<4} "
                  f"N={m['N_mean']:<7} CV={m['N_cv']:<7} amp={m['amplitude']:<7} "
                  f"rev={m['reversals_per_72k']:<8} burst={m['old_age_burstiness']} "
                  f"minNf={m['min_n_frac']:<6} xi={m['xi_mean']:<7} "
                  f"pass={r['passed']} | {gates}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker")
    ap.add_argument("--rung", choices=list(RUNGS))
    ap.add_argument("--cand", default=None)
    ap.add_argument("--candidate", action="store_true",
                    help="run T0 then T1 for --cand, opening its cards first")
    ap.add_argument("--close-control", action="store_true",
                    help="score the control card from the T0 and T1 control metrics")
    ap.add_argument("--ladder", action="store_true", help="rung 0: the gate linter")
    ap.add_argument("--run-ladder", action="store_true",
                    help="control T0+T1, then every candidate in ladder order")
    ap.add_argument("--cands", default=None,
                    help="comma-separated candidate keys for --run-ladder")
    ap.add_argument("--rebuild", action="store_true",
                    help="re-derive the report's metric sections from the artifacts")
    ap.add_argument("--adopt", default=None,
                    help="CAND:CARD_ID -- adopt an open ledger card into the report")
    ap.add_argument("--restate", default=None,
                    help="CAND:gate:min_delta:why -- re-state a ledger-refused floor")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.worker:
        return worker(a.worker)
    camp = Campaign()
    if a.show:
        _print_table(camp.report)
        return 0
    if a.ladder:
        camp.rung_linter()
        print(json.dumps(camp.report["linter"], indent=2, default=repr)[:6000])
        return 0
    if a.rebuild:
        camp.rebuild()
        camp.rung_linter()
        print(json.dumps({"control": sorted(camp.report.get("control", {})),
                          "cand": sorted(camp.report.get("cand", {})),
                          "ladder": len(camp.report["ladder"]),
                          "notes": camp.report["notes"]}, indent=1))
        return 0
    if a.adopt:
        cand, cid = a.adopt.split(":", 1)
        print(camp.adopt_open_card(cand, cid))
        ctl = camp.report["control"]["T1"]["seed_means"]
        c3 = camp.report["cand"][cand]["T1"]
        agg = c3["seed_means"]
        closed = camp.close_cards(cand, ctl, agg, {
            "rung": "T1", "ticks": RUNGS["T1"]["ticks"], "burn_in": RUNGS["T1"]["burn_in"],
            "seeds": list(SEEDS), "control_t1": ctl,
            "control_t1_n_seeds": camp.report["control"]["T1"]["n_seeds"],
            "candidate_t1": agg, "candidate_t1_n_seeds": c3["n_seeds"],
            "artifacts": c3["paths"],
            "backend_tree": camp.tree_for(cand)["tree"],
            "tree_file_sha256": {k: v["candidate_sha256"] for k, v
                                 in camp.tree_for(cand)["diffs"].items()},
            "config_overrides": CANDIDATES[cand]["overrides"],
            "adopted_note": "card opened by an earlier campaign process whose report save "
                            "was reverted by a concurrent writer; closed here from the "
                            "same measured metrics",
            "verdicts": c3["per_seed_gates"]})
        print(json.dumps([c for c in closed], indent=1, default=repr)[:1200])
        return 0
    if a.restate:
        parts = a.restate.split(":", 3)
        if len(parts) != 4:
            raise SystemExit("--restate wants CAND:GATE:MIN_DELTA:WHY")
        print(camp.restate_refused(parts[0], int(parts[1]), float(parts[2]), parts[3]))
        return 0
    if a.close_control:
        t0 = camp.report.get("control", {}).get("T0", {}).get("seed_means")
        t1 = camp.report.get("control", {}).get("T1", {}).get("seed_means")
        print(json.dumps(camp.close_control_card(t0, t1), indent=2, default=repr))
        return 0
    if a.rung:
        camp.do_rung(a.cand, a.rung)
        return 0
    if a.candidate:
        camp.do_candidate(a.cand)
        camp.write_summary(a.cand)
        return 0
    if a.run_ladder:
        cands = [c.strip() for c in (a.cands or ",".join(LADDER)).split(",") if c.strip()]
        for c in cands:
            if c not in CANDIDATES:
                raise SystemExit(f"unknown candidate {c!r}; known: {sorted(CANDIDATES)}")
        return camp.run_ladder(cands)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
