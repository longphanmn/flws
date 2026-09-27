"""The seven harness tools (brainstorm §6, L271-L279).

Every tool is a thin, deterministic wrapper over code that already exists in
``scripts/preset_experiment.py``. The harness never re-derives a gate, never
authors a verdict, and never writes law state: the Verifier is a plain function and
the orchestrator is physically unable to write one (§6 L289-L290).

| tool | §6 line | what it wraps |
|---|---|---|
| ``read_metrics`` | L273 | ``osc_metrics`` / ``osc_gate_report`` |
| ``gate_lint`` | L274 | ``gate_lint`` |
| ``propose_law_delta`` | L275 | ``_parse_set_overrides`` / ``Config`` fields |
| ``run_trace`` | L276 | ``run_oscillation`` + manifest |
| ``compare`` | L277 | pure gate table over artifacts |
| ``ledger_append`` | L278 | the JSONL ledger |
| ``read_run_manifest`` | L279 | ``read_run_manifest`` |
"""
import json
import os
import uuid

from . import _flws

# §6 L273: "token cap 4 KB". read_metrics is the only tool that touches a run
# artifact, and the artifact carries a samples array the agent must never see.
METRICS_TOKEN_CAP_BYTES = 4096

# The metric keys osc_gate_report reads. A metrics dict missing any of them cannot
# be scored, and a tool that scores it anyway is inventing a verdict.
_GATE_METRIC_KEYS = ("N_cv", "amplitude", "reversals_per_72k", "old_age_burstiness",
                     "min_n_frac")

_LAW_STATE_NOTE = (
    "the gate path builds Config in-process and never opens the SQLite "
    "law_state_v1, so there is no law state to hash (F7/C4); the Phase 1 manifest "
    "schema has no such field and this tool does not invent one"
)


def _load_artifact(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path) as f:
        return json.load(f)


# Which gates a linter rule makes unreachable, at risk, or unknown. Keyed by the
# Phase 1 rule names so the mapping stays attached to the rules it interprets.
#
# A *blocking* rule means no constant fixes this: spending sim time on the candidate
# optimizes against nothing (§6 L281-283). A *warning* means the gate is scoreable
# but is measuring something other than what it claims. *unknown* means the check
# could not be run and must not be reported as a pass.
_RULE_GATES = {
    "F5_median0_burstiness": {"unreachable": [4], "why": "burstiness is undefined (median old-age bin is 0)"},
    "F6_xi_mean_zero": {
        "unreachable": [1, 2, 3],
        "why": "the density controller never engaged, so the run has not tested it",
    },
    "F3_no_periodicity": {
        "at_risk": [3],
        "why": "broadband wander: the reversals gate counts noise, not a limit cycle",
    },
    "F4_dead_knob": {
        "unreachable": [],
        "why": "the proposal is a no-op or a forbidden scalar-only nudge, so no gate can move",
    },
    "manifest_mismatch": {
        "unreachable": [],
        "why": "comparability is unverified, so no gate delta may be read from this comparison",
    },
}


def _as_run(source, pops, sample, metrics=None):
    """Accept an artifact path, a run dict, or a metrics dict.

    ``run_oscillation`` returns a run dict whose metrics have not been derived yet,
    so a caller holding both passes ``metrics`` explicitly rather than having them
    read out of a key the run does not have.
    """
    if isinstance(source, str):
        payload = _load_artifact(source)
        run = {"sample": (payload.get("meta") or {}).get("sample") or sample}
        run["samples"] = payload.get("samples") or []
        if run["sample"] in (None, sample):
            run["sample"] = sample
        return run, payload.get("metrics") or {}
    if isinstance(source, dict) and "samples" in source:
        return source, (metrics if metrics is not None else source.get("metrics") or {})
    return {"sample": sample,
            "samples": [{"pop": p} for p in pops] if pops is not None else []}, \
        (metrics if metrics is not None else source)


def gate_lint(source, *, proposal=None, compare_manifest=None, pops=None, sample=100,
              metrics=None):
    """Tool 2 (§6 L274). The gates this candidate structurally cannot reach.

    A mapping over the Phase 1 linter's five rules onto the five gates
    ``osc_gate_report`` emits, not a second linter. Three outcomes, kept distinct
    because collapsing them is how a linter lies:

    * ``unreachable_gates`` — a blocking rule fired; no constant fixes this.
    * ``at_risk_gates`` — a warning fired; scoreable, but measuring something else.
    * ``unknown_gates`` — the check could not be run, so it is not a pass.

    ``ok`` is False when a gate is unreachable *or* unknown. A run whose samples
    were never supplied does not get to pass the periodicity check: the Phase 1
    rule reads an empty series as flat, and "flat" is a claim about data.
    """
    g = _flws.gates()
    run, metrics = _as_run(source, pops, sample, metrics=metrics)
    if not metrics:
        raise ValueError("gate_lint needs metrics: pass an artifact path or a metrics dict")

    if not run.get("samples"):
        # No series to check: mark F3 unknown instead of passing the empty case
        # through, where a zero spread reads as "no reversals to explain". This is
        # keyed on the samples being absent for ANY source -- an artifact path
        # included. Keying it on the argument's type left the path form reporting
        # "ok" for a check that never ran.
        report = g.gate_lint(run, proposal=proposal, compare_manifest=compare_manifest,
                             metrics=metrics)
        rules = []
        for r in report["rules"]:
            if r["rule"] == "F3_no_periodicity":
                r = dict(r)
                r["severity"] = "unknown"
                r["message"] = (
                    "no samples supplied, so the periodicity check did not run; "
                    "an unrun check is not a passing check"
                )
            rules.append(r)
        report = dict(report, rules=rules)
    else:
        report = g.gate_lint(run, proposal=proposal, compare_manifest=compare_manifest,
                             metrics=metrics)

    unreachable, at_risk, unknown = [], [], []
    for r in report["rules"]:
        spec = _RULE_GATES.get(r["rule"])
        if spec is None:  # pragma: no cover - a new Phase 1 rule the map lacks
            continue
        sev = r["severity"]
        if sev == "blocking":
            unreachable.extend(spec.get("unreachable", []))
        elif sev == "warning":
            at_risk.extend(spec.get("at_risk", []))
        elif sev == "unknown":
            unknown.extend(spec.get("at_risk") or spec.get("unreachable") or [])

    return {
        # A blocking rule with no gate of its own (F4 dead knob, manifest mismatch)
        # still blocks: `ok` may not be decided by the gate lists alone, or a dead
        # proposal reads as "no unreachable gate, go ahead and spend the ticks".
        "ok": bool(report["ok"]) and not unknown,
        "unreachable_gates": sorted(set(unreachable)),
        "at_risk_gates": sorted(set(at_risk)),
        "unknown_gates": sorted(set(unknown)),
        "rules": report["rules"],
        "admissible": report["admissible"],
        "metrics": metrics,
    }


def propose_law_delta(current, delta, *, allow_scalar_damping=False):
    """Tool 3 (§6 L275). Validated ``dataclasses.replace`` kwargs, or a refusal.

    This is the agent's whole write scope. A key that is not a ``Config`` field is
    rejected rather than passed through: such a key is a silent no-op, which is
    exactly the F4 dead-knob class that Phase 0.3 discovered in this repo's own
    knobs, and a no-op proposal costs a full campaign to discover.

    Type coercion mirrors the Phase 0-2 ``--set`` door exactly, so a proposal the
    tool accepts is a proposal the run will actually apply -- two different type
    parsers would let the tool bless something the run then ignores.

    Values are absolute. ``current`` is used only to report what changed; nothing
    here reads or writes law state, and the returned mapping is safe to hand to
    ``dataclasses.replace`` on a Config the harness built itself.
    """
    g = _flws.gates()
    Config = g.Config
    if not isinstance(delta, dict) or not delta:
        raise ValueError("propose_law_delta needs a non-empty field -> value mapping")

    # Reuse the run's own type grammar via the same coercion the --set door applies,
    # then take the proposal through the linter's dead-knob rule rather than
    # restating it.
    proposal = {}
    for key, raw in delta.items():
        field = Config.__dataclass_fields__.get(key)
        if field is None:
            raise ValueError(
                f"{key!r} is not a Config field, so the simulation cannot read it: "
                f"this proposal would be a silent no-op (dead knob)"
            )
        proposal[key] = _coerce(field, raw, key)

    lint = g.gate_lint({"samples": [], "sample": 100}, proposal=proposal,
                       metrics={"old_age_bins_median": 1, "old_age_burstiness": 1.0,
                                "xi_mean": 0.1})
    f4 = next((r for r in lint["rules"] if r["rule"] == "F4_dead_knob"), None)
    if f4 is not None and f4["severity"] == "blocking" and not allow_scalar_damping:
        raise ValueError(f4["message"])

    changed = {
        k: {"from": current.get(k), "to": v}
        for k, v in proposal.items()
        if k in current and current.get(k) != v
    }
    return {
        "proposal": proposal,
        "fields": sorted(proposal),
        "changed": changed,
        "is_topology_change": bool(
            set(proposal) & {"population_envelope_enabled", "pop_env_lo_frac",
                             "pop_env_hi_frac", "pop_env_lo_birth_boost"}
        ),
    }


def _coerce(field, raw, key):
    """Coerce one value to the Config field's declared type, or refuse.

    Delegates to the run's own ``--set`` door rather than re-deriving the grammar.
    Two type parsers is how a proposal ends up blessed by the tool and ignored by
    the run: the old private version read ``2`` as True for a bool field where the
    door reads it as False.
    """
    g = _flws.gates()
    literal = raw if isinstance(raw, str) else repr(raw)
    try:
        parsed = g._parse_set_overrides(["--set", f"{key}={literal}"])
    except SystemExit as exc:  # the door's own refusal path
        raise ValueError(
            f"cannot read {raw!r} for {key} as {field.type}"
        ) from exc
    return parsed.get(key, raw)


def default_out_path(world, seed, *, root=None, run_id=None):
    """Where a trace goes when the caller does not say: ``<sweeps>/<run_id>/``.

    ``run_id`` is unique per call even when the caller does not supply one. The
    first G2 smoke derived it from world+seed alone, so a baseline and a candidate
    run of the same seed resolved to the same file, the candidate overwrote the
    baseline, and the campaign reported a signed delta of 0.0 -- a run compared with
    itself. A default that can collide is not a default.
    """
    sweep_root = os.path.abspath(root or _flws.SWEEPS_DIR)
    if run_id is None:
        run_id = f"{world}_{seed}_{uuid.uuid4().hex[:8]}"
    return os.path.join(sweep_root, run_id, f"{world}_{seed}.json")


def _sandboxed_out_path(out, root):
    """Resolve `out` and refuse anything outside the sweep root.

    The historical ``scripts/oscillation_*.json`` datasets and ``/tmp/opencode/t0``
    are the evidence base every earlier phase was measured against. A trace landing
    on one of them does not merely lose a run, it destroys the record the gates are
    read against, so the check is on the resolved path rather than on the string the
    caller passed.
    """
    # realpath, not abspath: abspath does not follow symlinks, so a link planted
    # under the sweep root resolved to a path outside it and passed the check.
    sweep_root = os.path.realpath(root or _flws.SWEEPS_DIR)
    resolved = os.path.realpath(out)
    if os.path.commonpath([resolved, sweep_root]) != sweep_root:
        raise ValueError(
            f"run_trace writes only inside the sweep root {sweep_root}; "
            f"{resolved} is outside it"
        )
    if os.path.basename(resolved).startswith("oscillation_"):
        raise ValueError(
            f"refusing to write {os.path.basename(resolved)}: the historical "
            f"oscillation_*.json datasets are read-only evidence"
        )
    return resolved


def run_trace(world="B", seed=42, ticks=1000, burn_in=0, out=None, overrides=None,
              *, budget=None, root=None, run_id=None, reason=None, overwrite=False):
    """Tool 4 (§6 L276). One trace -> artifact path. Writes only to the sweep dir.

    OMP is pinned to 1 before the sim is constructed (§13 L550-551: the C kernel
    hardcodes num_threads(4), so 3-way parallelism on a 4-core box is ~2x slower than
    sequential; sequential is the correct setting). The manifest records the thread
    count, the tick budget, the git sha, the resolved config hash, the declared
    proposal, and the baseline the proposal was applied on top of -- so this run is
    comparable to its own baseline and not to an unrelated artifact that happens to
    share its filename.

    An existing artifact is never overwritten unless ``overwrite=True`` is passed
    explicitly. A gate artifact is evidence: silently replacing one destroys the
    measurement a comparison may already be quoting, and the replacement is
    indistinguishable from a fresh run in every downstream read.
    """
    g = _flws.gates()
    # `world` selects the physics (A = moving setpoint, B = flat) and is compared
    # case-sensitively by run_oscillation and by osc_compare's bucketing, so an
    # unnormalised "a" would measure world B and record itself as world A.
    world = str(world).strip().upper()
    if world not in ("A", "B"):
        raise ValueError(f"world must be 'A' or 'B', got {world!r}")

    # A run that cannot yield a sample interval cannot produce metrics: osc_metrics
    # returns {"error": "no samples"} and osc_gate_report then indexes N_cv out of
    # it. Refuse up front rather than spend a run to raise KeyError.
    if ticks < g.OSC_SAMPLE:
        raise ValueError(
            f"ticks={ticks} cannot yield a single {g.OSC_SAMPLE}-tick sample "
            f"interval, so the run would produce no metrics"
        )
    if burn_in >= ticks:
        raise ValueError(f"burn_in={burn_in} must be less than ticks={ticks}")

    proposal = None
    if overrides:
        # Validate AND KEEP the coerced mapping. Passing the raw dict to the run
        # meant a string-typed float -- the shape an LLM tool-calling loop emits --
        # reached dataclasses.replace and crashed the sim after the budget was spent.
        proposal = propose_law_delta(current={}, delta=overrides)["proposal"]

    out = out or default_out_path(world, seed, root=root, run_id=run_id)
    out = _sandboxed_out_path(out, root)

    if os.path.exists(out) and not overwrite:
        raise FileExistsError(
            f"{out} already exists: a gate artifact is evidence and is not "
            f"overwritten implicitly. Pass overwrite=True if you mean to replace it."
        )

    # Pin threads first: the value is read when the native core initialises.
    os.environ["OMP_NUM_THREADS"] = "1"
    # Consult the wall before creating anything. A refused run must leave the tree
    # exactly as it found it -- not even an empty run_id directory, which would read
    # as "a run happened here" to the next person auditing the sweep dir.
    if budget is not None:
        budget.spend_ticks(
            ticks, reason or f"{world} seed {seed} {ticks} ticks"
        )
    os.makedirs(os.path.dirname(out), exist_ok=True)

    run = g.run_oscillation(seed, total_ticks=ticks, burn_in=burn_in,
                            sample=g.OSC_SAMPLE, modulated=(world == "A"),
                            overrides=proposal or None)
    m = g.osc_metrics(run)
    passed, checks = g.osc_gate_report(m, g._effective_flat(run))
    lint = gate_lint(run, proposal=proposal, metrics=m)
    manifest = g.build_run_manifest(
        g._osc_config(seed, overrides=proposal), argv=["run_trace"],
        total_ticks=ticks, burn_in=burn_in, sample=g.OSC_SAMPLE,
        seam="harness-replace", overrides=proposal or {},
        base_cfg=g._osc_config(seed),
    )
    payload = {
        "meta": {"world": world, "registry": g.OSC_GATES, "manifest": manifest},
        "metrics": m,
        "gates": [{"name": n, "pass": ok, "status": g._gate_status(ok), "value": v}
                  for n, ok, v in checks],
        "lint": lint,
        "passed": passed,
        "samples": run["samples"],
    }
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    g.write_run_manifest(out, manifest)
    return out


def compare(paths):
    """Tool 5 (§6 L277). A gate table over artifacts. A pure function.

    The table is built from the deterministic per-run verdict, and the one thing
    this tool does decide is whether the table may be *read*: manifest equality is
    a precondition for a gate delta meaning anything (§6 L310), and a drifted run
    anywhere in the list makes the whole set unreadable — Phase 1 issue 3 was
    exactly this, comparing only the ends and letting a drifted middle through.

    When the set is not comparable the table is still returned, labelled, because
    the Phase 1 behaviour of printing it "for reference" is useful; what it must
    not do is let the numbers be quoted as a verdict.
    """
    if not paths:
        raise ValueError("compare needs at least one artifact path")
    g = _flws.gates()

    rows = []
    manifests = []
    for p in paths:
        payload = _load_artifact(p)
        man = g.read_run_manifest(p) or (payload.get("meta") or {}).get("manifest")
        manifests.append(man)
        metrics = payload.get("metrics") or {}
        # Re-derive rather than quote: an artifact is a file, and a hand-edited
        # `passed: true` is the §13 L561 failure mode. `compare` is the table the
        # agent reads, so it is the last place a tampered verdict may be quoted.
        # A partial metrics dict cannot be re-derived, and guessing would be the
        # same defect one level up -- so `passed` stays None.
        if metrics and all(k in metrics for k in _GATE_METRIC_KEYS):
            derived, _checks = g.osc_gate_report(metrics, flat=True)
        else:
            derived = None
        stored = payload.get("passed")
        stored_gates = payload.get("gates")
        rows.append(
            {
                "path": p,
                "seed": metrics.get("seed"),
                "N_mean": metrics.get("N_mean"),
                "N_cv": metrics.get("N_cv"),
                "amplitude": metrics.get("amplitude"),
                "reversals_per_72k": metrics.get("reversals_per_72k"),
                "old_age_burstiness": metrics.get("old_age_burstiness"),
                "min_n_frac": metrics.get("min_n_frac"),
                "declared_levers": dict((man or {}).get("overrides") or {}),
                # None, not []: an absent gate list is not a list of zero failures.
                "gates": stored_gates,
                "gates_present": stored_gates is not None,
                "passed": derived,
                "stored_passed": stored,
                "verdict_present": stored is not None,
                "verdict_consistent": (
                    None if stored is None or derived is None
                    else (False if not isinstance(stored, bool)
                          else bool(stored) == bool(derived))
                ),
            }
        )

    # The whole list goes to the linter, not (first, last).
    lint = g.gate_lint(rows[0] and {"samples": [], "sample": 100},
                       compare_manifest=manifests, metrics=rows[0] or {})
    rule = next(r for r in lint["rules"] if r["rule"] == "manifest_mismatch")
    severity = rule["severity"]
    # `comparable` is true only when two or more *distinct* runs were checked and
    # their manifests agreed. A single path is not a comparison, and a path compared
    # with itself is the run-against-itself bug the clobber guard exists to prevent
    # -- both used to report `comparable: true` with a note asserting the delta was
    # evidence.
    distinct = len(set(os.path.abspath(p) for p in paths))
    if len(paths) < 2 or distinct < 2:
        reason = ("no comparison was performed: "
                  + ("one manifest is not a comparison" if len(paths) < 2
                     else "a run cannot be compared with itself"))
        return {
            "paths": list(paths),
            "rows": rows,
            "manifest_rule": rule,
            "manifest_severity": severity,
            "comparable": False,
            "delta_readable": False,
            "note": reason + "; no gate delta may be read",
        }
    # A warning here means comparability is *unverified*, and unverified is not
    # comparable: reporting True for a set nobody checked is the false all-clear
    # Phase 1 issue 5 was about, one level up.
    ok = severity == "ok"
    if ok:
        note = "manifests agree: a gate delta between these runs is evidence"
    elif severity == "warning":
        note = (
            "comparability unverified: the table is printed for reference only, "
            "and a gate delta between unverified runs does not mean anything"
        )
    else:
        note = (
            "manifests disagree: the table is printed for reference only, and a "
            "gate delta between non-comparable runs does not mean anything"
        )
    return {
        "paths": list(paths),
        "rows": rows,
        "manifest_rule": rule,
        "manifest_severity": severity,
        "comparable": ok,
        "delta_readable": ok,
        "note": note,
    }


def read_metrics(path):
    """Tool 1 (§6 L273). ``{metrics, gates}`` only, samples stripped, 4 KB cap.

    The samples array is ~500 KB and is the one input the agent must never read
    (§6 L261, §13 L552-553), so it is dropped here rather than filtered later. The
    cap *refuses* instead of truncating: a metric dict cut in half is a number the
    run never measured, which is the same class of error as reporting a FAIL as a
    PASS.

    The verdict is re-derived with ``osc_gate_report`` rather than read from the
    artifact's stored ``passed``. An artifact is a file, and a hand-edited
    ``passed: true`` is precisely the failure §13 L561-562 forbids; re-deriving is
    the only thing that catches it, so a disagreement is reported rather than
    resolved in the artifact's favour.
    """
    g = _flws.gates()
    payload = _load_artifact(path)
    metrics = payload.get("metrics")
    if not metrics:
        raise ValueError(f"{path}: no metrics; this is not a gate artifact")
    passed, checks = g.osc_gate_report(metrics, flat=True)
    stored = payload.get("passed")
    out = {
        "path": path,
        "metrics": metrics,
        "gates": [
            {"name": n, "pass": ok, "status": g._gate_status(ok), "value": v}
            for n, ok, v in checks
        ],
        "passed": bool(passed),
        "stored_passed": stored,
        # Absence is not agreement. An artifact with no stored verdict has had no
        # check performed, and `verdict_consistent: True` for it would be exactly
        # the false all-clear this tool exists to prevent. A present-but-malformed
        # verdict is a different failure and reports False.
        "verdict_present": stored is not None,
        "verdict_consistent": (
            None if stored is None
            else (False if not isinstance(stored, bool)
                  else bool(stored) == bool(passed))
        ),
        "admissible": g.gate_admissible_region(metrics),
    }
    blob = json.dumps(out, sort_keys=True, default=repr).encode()
    if len(blob) > METRICS_TOKEN_CAP_BYTES:
        raise ValueError(
            f"{path}: metrics+gates is {len(blob)} B, over the "
            f"{METRICS_TOKEN_CAP_BYTES} B cap; refusing to truncate a measurement"
        )
    out["bytes"] = len(blob)
    out["within_cap"] = True
    return out


def read_run_manifest(path):
    """Tool 7 (§6 L279). Provenance for one gate artifact.

    Four of the five fields §6 asks for are in the manifest schema. The two that
    are not are reported as what they are rather than filled in:

    * ``ms_per_tick`` is recorded per run by ``osc_metrics``, not by the manifest,
      so it is read from the artifact's own metrics.
    * ``law_state_hash`` is ``None`` with a note. The gate path never opens
      ``law_state_v1``; a hash here would be a fabricated provenance claim about
      the one thing this harness must not touch.
    """
    g = _flws.gates()
    payload = _load_artifact(path)
    manifest = g.read_run_manifest(path)
    if manifest is None:
        # A legacy artifact with no manifest sidecar. Report the absence: reading
        # it through `(m or {}).get(k)` is how Phase 1 printed "manifests agree"
        # for two artifacts that had none at all (agy issue 5).
        manifest = None
    metrics = payload.get("metrics") or {}
    embedded = (payload.get("meta") or {}).get("manifest")
    present = manifest is not None or embedded is not None
    m = manifest if manifest is not None else (embedded or {})
    return {
        "path": path,
        "manifest_present": present,
        "manifest_version": m.get("manifest_version"),
        "git_sha": m.get("git_sha"),
        "config_hash": m.get("config_hash"),
        "base_config_hash": m.get("base_config_hash"),
        "tick_budget": m.get("tick_budget"),
        "omp_num_threads": m.get("omp_num_threads"),
        "seam": m.get("seam"),
        "seed": m.get("seed"),
        "overrides": m.get("overrides"),
        "ms_per_tick": metrics.get("ms_per_tick"),
        "law_state_hash": None,
        "law_state_note": _LAW_STATE_NOTE,
        # Named for what was checked. This is manifest *presence*: whether this run
        # is comparable to another is `compare`'s question, and a key called
        # `comparable` here claimed a check this function never made.
        "has_provenance": bool(present),
    }
