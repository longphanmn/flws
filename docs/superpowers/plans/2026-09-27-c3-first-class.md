# C3 first-class promotion (envelope x staggered old-age hazard)

> **For the executor:** TDD. Steps are checkbox-tracked. No git commit/push.
> Never print secrets. `OMP_NUM_THREADS=1`, sims sequential, max 2 concurrent.

**Goal:** Move the campaign's best-known fix C3 (population envelope lower-boundary
birth boost G1 x hazard-uniformised senescence G4) into `backend/app/simulation`
as first-class, config-driven code, with failing tests written first.

**Architecture:** G1 already landed in `backend/app/density_damping.py`
(`population_envelope`, `envelope_lower_boost`) and `lifecycle.py::_repro_room`.
The only missing physics is G4: replace the deterministic `c.age >= c.lifespan`
elder death with a memoryless hazard above the elder onset, rate `1/span` so the
mean age at death is unchanged. Make every C3 knob a real `Config` field, parsed
from `FLATWORLD_*` env, pinned in the `theocracy` preset, steerable/persistable
via `GodLaws`/`LAW_FIELDS`, and backfilled absent-only in `_restore_law_state`.
Master enable flags default inert (False), preserving the determinism contract;
the parameter defaults are the verified C3 values.

**Tech stack:** Python 3.14, pytest, dataclasses, pydantic (GodLaws).

**Spec:** `/tmp/flws_impl_c3.md`; campaign evidence `/root/flws_deepagents_FINAL.md`,
`/tmp/opencode/campaign/c2_comment_04_C3v2_G1xG4haz.txt`,
`c2_comment_05_C3v3_and_close.txt`; variant code
`/tmp/opencode/campaign/trees/cand_G4/app/simulation/creature_update.py`.

## Global constraints
- NO git commit / push. Leave campaign/harness leftovers untouched.
- Full backend suite must end `0 failed` (`cd backend && PYTHONPATH=/root/pylibs python3 -m pytest -q`).
- Suite baseline: 661 passed / 14 skipped (verify before claiming).
- Verdicts only from `osc_gate_report`, never authored. No threshold edits.

## File structure
- Modify `backend/app/config.py` — 2 hazard `Config` fields + env parsers.
- Modify `backend/app/simulation/creature_update.py` — `_senescence_due` + 3 call sites.
- Modify `backend/app/protocol.py` — 6 C3 `GodLaws` fields.
- Modify `backend/app/main.py` — 6 keys in `PRESETS["theocracy"]` + backfill list.
- Create `backend/tests/test_old_age_hazard.py` — hazard physics + plumbing.

## Review focus
- Disabled law must consume zero RNG (golden lock).
- Hazard must not fire before `onset_frac * lifespan`.
- Mean age at death under hazard must equal the threshold lifespan.
- Degenerate `lifespan <= 0` must fall back to the threshold, not immortalise.

---

### Task 1: RED — hazard physics tests
- [ ] Create `backend/tests/test_old_age_hazard.py` with stub-based tests for
      disabled threshold semantics, no-fire-before-onset, mean-age-at-death,
      staggering, and onset scaling.
- [ ] Run: `pytest tests/test_old_age_hazard.py -q` → FAIL (`AttributeError: _senescence_due`).

### Task 2: GREEN — implement `_senescence_due`
- [ ] Add the method; replace the 3 `c.age >= c.lifespan` sites.
- [ ] Run the file → hazard physics tests PASS.

### Task 3: RED/GREEN — config plumbing
- [ ] Add failing plumbing tests (fields, env, preset, GodLaws, backfill).
- [ ] Implement config/protocol/main wiring until green.
- [ ] Run new file → all PASS.

### Task 4: Verify
- [ ] Full backend suite → 0 failed.
- [ ] 3-seed T1 ladder (42/123/999, 18000 ticks, burn-in 4000, world B,
      C3 knobs on) via `scripts/preset_experiment.py --osc-run`; table from
      the artifact's `osc_gate_report` gates.
- [ ] `git status --porcelain`; Planka comments; final report.
