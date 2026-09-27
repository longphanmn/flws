"""The G2 smoke: one hypothesis, one budget-walled campaign, one honest verdict.

G2 (brainstorm §6 L377) is the seasonal-decoupling topology: decouple N from the
seasonal food target with season-sized larder/granary buffering, or make
beds/territory the binding capacity. §12 Step 3 points the harness here because it is
the one topology T0 alone cannot validate.

The loop this runs is the whole point of the harness:

    1. open a card carrying a predicted SIGNED gate delta -- before any tick
    2. refuse a proposal that is not a runnable candidate -- before paying for it
    3. run the baseline and the candidate per seed: sequential, OMP=1, wall-bounded
    4. compare them with the deterministic verifier
    5. close the card confirmed or falsified from the measured signed delta

Three things this module refuses to do, each of which a first draft did:

* **Score a gate the run could not exercise.** The first delivery closed `falsified`
  on gate 3 while the same run's lint reported gates 1-4 unreachable: xi_mean=0.0
  means the density controller never engaged (F6), and a 1000-tick trace gives 10
  samples, so reversals_per_72k sits at its floor of 0.0 in both runs and cannot
  move. The delta was real arithmetic on a pinned number. §6 L296 already lists
  reversals under T0's "it cannot" column.
* **Call a single-seed result a campaign.** §13 L557-558 forbids a topology search on
  one seed, and §6 L296 makes T0 three seeds. Seeds the wall could not reach are
  reported as truncation.
* **Call a crash a budget decision.** Only ``BudgetExhausted`` is a budget outcome;
  anything else is a failure and is labelled one.
"""
import time

from .agent import endpoint_status
from .budget import BudgetExhausted, BudgetWall
from .ledger import Ledger
from .tools import compare, gate_lint, propose_law_delta, read_metrics, run_trace

# G2's season-sized buffering. These are topology levers, not proportional-band
# scalars, so they survive the F4 dead-knob/scalar rule; §13 L547-549 forbids the
# scalar route to this gate.
G2_LEVERS = {"larder_capacity": 1200.0, "granary_capacity": 1600.0}

# Gate 3 is the one G2 is predicted to move: decoupling N from the season is
# predicted to *reduce* reversals/72k, because a seasonal knock-off is what drives
# the smoothed series back and forth. Signed, with a floor, so a run that barely
# moves falsifies the card instead of confirming it.
G2_PREDICTION = {
    "gate": 3,
    "direction": "decrease",
    "min_delta": 5.0,
    "rationale": (
        "season-sized larder/granary buffering removes the seasonal supply wave "
        "that knocks N off the band, so the 300-tick smoothed series should stop "
        "reversing (brainstorm §6 L377, F2)"
    ),
}

G2_HYPOTHESIS = (
    "G2: season-sized larder + granary buffering decouples N from the seasonal "
    "food target, so the reversals gate falls"
)


def run_g2_smoke(*, ledger_path, root, ticks=1000, burn_in=0, seeds=(42,),
                 max_sim_runs=3, credentials=None, prediction=None, levers=None):
    """Run the G2 campaign once and return a trace of everything it did."""
    ledger = Ledger(ledger_path)
    budget = BudgetWall(max_sim_runs=max_sim_runs, ledger=ledger,
                        require_ledger_entry=True)
    levers = dict(levers or G2_LEVERS)
    ctx = {
        "ledger": ledger, "budget": budget, "credentials": credentials,
        "levers": levers, "steps": [], "seeds_run": [], "seed_results": [],
        "baseline_path": None, "candidate_path": None, "verdict": None,
        "stop": None, "verdict_status": None, "unreachable_gates": [],
    }

    def step(name, **kw):
        rec = {"step": name, "ts": time.time()}
        rec.update(kw)
        ctx["steps"].append(rec)
        return rec

    def finish():
        card = ledger.card(ctx["card_id"])
        return {
            "hypothesis": G2_HYPOTHESIS,
            "card_id": ctx["card_id"],
            # The ledger holds the *validated* prediction, including the metric the
            # gate is measured by; this is the single source of truth for it.
            "prediction": card["prediction"],
            "g2_levers": levers,
            "steps": ctx["steps"],
            "verdict": _verdict(ctx, card),
            "seed_results": ctx["seed_results"],
            "budget": budget.to_dict(),
            "endpoint": endpoint_status(credentials),
            "baseline_path": ctx["baseline_path"],
            "candidate_path": ctx["candidate_path"],
            "ledger_path": ledger.path,
            "card_status": card["status"],
            "seeds_requested": [int(s) for s in seeds],
            "seeds_run": list(ctx["seeds_run"]),
        }

    def fail(exc):
        """Record how the campaign stopped, without mislabelling why."""
        if isinstance(exc, BudgetExhausted):
            ctx["verdict_status"] = "inconclusive"
            reason = f"the budget wall stopped the campaign: {exc}"
        else:
            # A crash, a disk error, a TypeError from a bad proposal: none of these
            # are budget decisions, and reporting them as one hides the bug behind
            # a plausible-sounding explanation.
            ctx["verdict_status"] = "failed"
            reason = f"the run failed: {type(exc).__name__}: {exc}"
        ctx["stop"] = reason
        step("run_refused", error=f"{type(exc).__name__}: {exc}",
             budget_refusal=isinstance(exc, BudgetExhausted))
        return finish()

    # 1. The prediction is on the record before any tick is spent. The wall is
    #    configured to require exactly this, so an escalation without a card is
    #    refused by the budget rather than merely advised against.
    ctx["card_id"] = ledger.open_card(
        G2_HYPOTHESIS, dict(prediction or G2_PREDICTION), topology="G2")
    step("card_opened", card_id=ctx["card_id"],
         prediction=ledger.card(ctx["card_id"])["prediction"],
         hypothesis=G2_HYPOTHESIS)

    wanted = [int(s) for s in seeds]
    if len(wanted) > 1 and budget.remaining < 2 * len(wanted):
        step("campaign_truncated", seeds_requested=wanted,
             runs_needed=2 * len(wanted), budget_runs=budget.max_sim_runs,
             note=(f"{budget.max_sim_runs} sim-run(s) cannot cover {len(wanted)} "
                   f"seeds x (baseline + candidate) = {2 * len(wanted)}; a "
                   f"single-seed result does not decide a gate (§13 L557-558)"))

    for seed in wanted:
        if budget.remaining < 1:
            step("seeds_not_run",
                 seeds=[s for s in wanted if s not in ctx["seeds_run"]],
                 note="the budget wall ran out before these seeds were reached")
            break
        ctx["baseline_path"] = None
        ctx["candidate_path"] = None

        # 2. Baseline: the preset as served, no proposal.
        try:
            ctx["baseline_path"] = run_trace(
                "B", seed, ticks, burn_in, budget=budget, root=root,
                reason=f"G2 baseline seed {seed}")
        except Exception as exc:
            return fail(exc)
        step("baseline_run", path=ctx["baseline_path"], seed=seed)

        # 3a. The pre-spend gate is on the PROPOSAL, not on the baseline's physics.
        #     `propose_law_delta` is the check §12 Step 3 asks for: "a
        #     deliberately-broken proposal is rejected without spending a single
        #     tick". It refuses a key that is not a Config field (a silent no-op)
        #     and a scalar-only damping nudge.
        try:
            proposal = propose_law_delta(current={}, delta=levers)["proposal"]
        except Exception as exc:
            return fail(exc)
        step("proposal_check", ok=True, proposal=proposal,
             is_topology_change=bool(set(proposal) - {"larder_capacity",
                                                      "granary_capacity"}))

        # 3b. Lint the *artifact*. (The read_metrics envelope has no `samples` and
        #     no nested metrics; feeding that to the linter made F5/F6 read keys
        #     that were not there and D_in_region come out true for a dict with no
        #     N_mean.) Advisory for BLOCKING -- at the T0 rung the full suite is
        #     explicitly not expected to be scorable, and blocking on the
        #     baseline's short-run metrics would forbid every cheap rung -- but
        #     authoritative for SCORING, in step 5b.
        lint = gate_lint(ctx["baseline_path"], proposal=proposal)
        step("baseline_lint", advisory=True, ok=lint["ok"],
             unreachable_gates=lint["unreachable_gates"],
             at_risk_gates=lint["at_risk_gates"],
             unknown_gates=lint["unknown_gates"],
             metrics_seen=bool(lint["metrics"].get("N_mean") is not None
                               or lint["metrics"].get("N_cv") is not None),
             admissible=lint["admissible"],
             note=("advisory for blocking: these describe what the baseline "
                   "measurement can score, not what the proposal can move"))

        # 4. The candidate: same seed, same budget, same tick count.
        try:
            ctx["candidate_path"] = run_trace(
                "B", seed, ticks, burn_in, budget=budget, root=root, overrides=levers,
                reason=f"G2 candidate seed {seed}")
        except Exception as exc:
            return fail(exc)
        step("candidate_run", path=ctx["candidate_path"], seed=seed, levers=levers)
        ctx["seeds_run"].append(seed)

        # 5. The deterministic verdict -- and only if the manifests permit a delta.
        table = compare([ctx["baseline_path"], ctx["candidate_path"]])
        step("compare", comparable=table["comparable"], note=table["note"], seed=seed)

        if not table["delta_readable"]:
            ctx["stop"] = ("the two runs are not comparable, so no signed delta may "
                           "be read: " + table["note"])
            return finish()

        # 5b. Do not score a card on a gate this rung cannot exercise.
        prediction = ledger.card(ctx["card_id"])["prediction"]
        unreachable = sorted(set(lint["unreachable_gates"])
                             | set(lint["unknown_gates"]))
        ctx["unreachable_gates"] = unreachable
        if prediction["gate"] in unreachable:
            ctx["stop"] = (
                f"gate {prediction['gate']} ({prediction['metric']}) is structurally "
                f"unreachable at this rung: {unreachable}. xi_mean="
                f"{read_metrics(ctx['baseline_path'])['metrics'].get('xi_mean')} means "
                f"the density controller never engaged (F6), and {ticks} ticks is too "
                f"few to measure it. The card stays OPEN: an unscoreable gate is not "
                f"a falsified hypothesis."
            )
            return finish()

        before = read_metrics(ctx["baseline_path"])["metrics"]
        after = read_metrics(ctx["candidate_path"])["metrics"]
        try:
            closed = ledger.close_card(
                ctx["card_id"],
                {"ticks": ticks, "seed": seed, "levers": levers,
                 "baseline": ctx["baseline_path"],
                 "candidate": ctx["candidate_path"]},
                before=before, after=after,
            )
        except Exception as exc:
            return fail(exc)
        step("card_closed", card_id=ctx["card_id"], status=closed["status"],
             measured_delta=closed["measured_delta"], seed=seed)
        ctx["verdict"] = closed
        ctx["seed_results"].append({"seed": seed, "status": closed["status"],
                                    "measured_delta": closed["measured_delta"]})

    if not ctx["stop"]:
        if ctx["seeds_run"] != wanted:
            ctx["stop"] = (
                f"the campaign was truncated by the budget wall: covered "
                f"{ctx['seeds_run']} of {wanted} seeds. A single-seed result does "
                f"not decide a gate (§13 L557-558)."
            )
        else:
            ctx["stop"] = "the campaign covered no seed"
    return finish()


def _verdict(ctx, card):
    """Report what happened. An unrun, unscoreable or failed card is not a result."""
    metric = card["prediction"]["metric"]
    base = {
        "metric": metric,
        "unreachable_gates": ctx["unreachable_gates"],
        "comparable": None,
        "delta_readable": False,
        "rule": "none",
    }
    if ctx["verdict"] is not None:
        return dict(base, status=ctx["verdict"]["status"],
                    measured_delta=ctx["verdict"]["measured_delta"],
                    comparable=True, delta_readable=True, rule="deterministic",
                    reason="signed gate delta measured by the deterministic verifier")
    return dict(base, status=ctx["verdict_status"] or "inconclusive",
                measured_delta=None,
                reason=ctx["stop"] or "the campaign did not reach a comparison")
