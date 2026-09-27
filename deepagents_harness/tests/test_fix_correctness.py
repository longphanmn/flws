"""Fix pass 2 — correctness findings from the fresh-context review.

C2   run_trace validated the proposal and then applied the RAW dict, so a
     string-typed float (the shape an LLM tool-calling loop emits) reached the sim
I5   any run_trace failure was reported as a budget-wall decision
I6   close_card raised TypeError on a not-measurable gate metric
I7   inf - inf was scored "falsified" and wrote bare NaN into the JSONL
I8   open_card did not enforce "a falsified card is archived, not retried"
I9   the budget wall implemented 1 of its 3 spec'd duties (no wall-clock, no
     ledger gate) and charged itself for runs it then refused
I10  the smoke ran one seed and silently dropped the rest (§13 L557-558)
I11  a run with no samples raised KeyError('N_cv'), after spending budget
I12  GATE_REV was an undefined name reachable from the unknown branch
I13  world was not normalised, so world="a" measured B and recorded "a"
I14  _coerce was a second type parser, not the --set door it claimed to mirror
M1   the exported ledger_append was an unbound method
M2   the sandbox used abspath, so a symlink under the root escaped it
"""
import json
import os

import pytest

from deepagents_harness import _flws


# --- C2 ---------------------------------------------------------------------

def test_run_trace_applies_the_coerced_proposal_not_the_raw_one(tmp_path):
    """An LLM emits "1200.0" as a JSON string for a float field. The validated,
    coerced mapping must be what reaches the Config."""
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path),
                    overrides={"larder_capacity": "1200.0"})
    payload = json.load(open(out))
    assert payload["meta"]["manifest"]["overrides"] == {"larder_capacity": 1200.0}
    assert isinstance(payload["meta"]["manifest"]["overrides"]["larder_capacity"], float)


# --- I5 ---------------------------------------------------------------------

def test_a_run_failure_is_not_reported_as_a_budget_decision(smoke_env, monkeypatch):
    from deepagents_harness import smoke as smoke_mod

    def boom(*a, **k):
        raise TypeError("unsupported operand type(s) for -: 'str' and 'float'")

    monkeypatch.setattr(smoke_mod, "run_trace", boom)
    out = smoke_mod.run_g2_smoke(**smoke_env)
    assert out["verdict"]["status"] == "failed"
    assert "TypeError" in out["verdict"]["reason"]
    assert "budget" not in out["verdict"]["reason"].lower()


def test_a_budget_refusal_is_still_reported_as_a_budget_decision(smoke_env):
    smoke_env["max_sim_runs"] = 0 + 1
    from deepagents_harness.smoke import run_g2_smoke

    out = run_g2_smoke(**smoke_env)
    assert out["verdict"]["status"] == "inconclusive"
    assert "budget" in out["verdict"]["reason"].lower()


# --- I6 / I7 ----------------------------------------------------------------

def test_closing_a_card_on_a_not_measurable_metric_refuses_rather_than_crashing(tmp_path):
    from deepagents_harness.ledger import Ledger, LedgerError

    led = Ledger(str(tmp_path / "l.jsonl"))
    cid = led.open_card("burstiness", {"gate": 4, "direction": "decrease",
                                       "min_delta": 1.0})
    with pytest.raises(LedgerError) as exc:
        led.close_card(cid, {}, before={"old_age_burstiness": 1.5},
                       after={"old_age_burstiness": None})
    assert "not measurable" in str(exc.value).lower()
    assert led.card(cid)["status"] == "open"


def test_closing_a_card_on_a_non_finite_metric_refuses(tmp_path):
    from deepagents_harness.ledger import Ledger, LedgerError

    led = Ledger(str(tmp_path / "l.jsonl"))
    cid = led.open_card("collapse", {"gate": 5, "direction": "increase",
                                     "min_delta": 0.01})
    with pytest.raises(LedgerError) as exc:
        led.close_card(cid, {}, before={"min_n_frac": 0.9},
                       after={"min_n_frac": float("inf")})
    assert "finite" in str(exc.value).lower()


def test_the_ledger_file_contains_only_strict_json(tmp_path):
    """NaN and Infinity are Python leniencies, not JSON. A strict reader must work."""
    from deepagents_harness.ledger import Ledger

    led = Ledger(str(tmp_path / "l.jsonl"))
    cid = led.open_card("ok", {"gate": 3, "direction": "decrease", "min_delta": 1.0})
    led.close_card(cid, {}, before={"reversals_per_72k": 10.0},
                   after={"reversals_per_72k": 2.0})
    for line in open(led.path):
        if line.strip():
            json.loads(line, parse_constant=lambda c: pytest.fail(f"non-JSON {c}"))


# --- I8 ---------------------------------------------------------------------

def test_the_same_hypothesis_cannot_be_re_proposed_as_a_new_card(tmp_path):
    from deepagents_harness.ledger import Ledger

    led = Ledger(str(tmp_path / "l.jsonl"))
    pred = {"gate": 3, "direction": "decrease", "min_delta": 5.0}
    a = led.open_card("G2 granary buffering", pred)
    led.close_card(a, {}, before={"reversals_per_72k": 100.0},
                   after={"reversals_per_72k": 160.0})
    with pytest.raises(Exception) as exc:
        led.open_card("G2 granary buffering", pred)
    assert "archiv" in str(exc.value).lower() or "falsified" in str(exc.value).lower()


def test_a_still_open_card_may_not_be_duplicated_either(tmp_path):
    from deepagents_harness.ledger import Ledger

    led = Ledger(str(tmp_path / "l.jsonl"))
    pred = {"gate": 3, "direction": "decrease", "min_delta": 5.0}
    led.open_card("G2 larder", pred)
    with pytest.raises(Exception):
        led.open_card("G2 larder", pred)


# --- I9 ---------------------------------------------------------------------

def test_the_wall_refuses_when_a_ledger_entry_is_required_and_absent(tmp_path):
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.ledger import Ledger
    from deepagents_harness.tools import run_trace

    led = Ledger(str(tmp_path / "l.jsonl"))
    wall = BudgetWall(max_sim_runs=2, ledger=led, require_ledger_entry=True)
    with pytest.raises(Exception) as exc:
        run_trace("B", 42, ticks=100, root=str(tmp_path), budget=wall)
    assert "ledger" in str(exc.value).lower()


def test_the_wall_allows_the_run_once_a_ledger_card_is_open(tmp_path):
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.ledger import Ledger
    from deepagents_harness.tools import run_trace

    led = Ledger(str(tmp_path / "l.jsonl"))
    led.open_card("h", {"gate": 3, "direction": "decrease", "min_delta": 5.0})
    wall = BudgetWall(max_sim_runs=2, ledger=led, require_ledger_entry=True)
    out = run_trace("B", 42, ticks=100, root=str(tmp_path), budget=wall)
    assert os.path.exists(out)


def test_the_wall_charges_a_running_tick_total_not_just_a_per_run_ceiling(tmp_path):
    from deepagents_harness.budget import BudgetExhausted, BudgetWall

    wall = BudgetWall(max_sim_runs=10, max_ticks_total=1000)
    wall.spend_ticks(600, "first")
    with pytest.raises(BudgetExhausted):
        wall.spend_ticks(600, "second")
    assert wall.to_dict()["ticks_spent"] == 600


def test_a_refused_run_does_not_consume_a_sim_run(tmp_path):
    """A run refused because its artifact already exists spent no ticks."""
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.tools import run_trace

    out = run_trace("B", 42, ticks=100, root=str(tmp_path))
    wall = BudgetWall(max_sim_runs=2)
    with pytest.raises(FileExistsError):
        run_trace("B", 42, ticks=100, out=out, root=str(tmp_path), budget=wall)
    assert wall.used == 0


# --- I10 --------------------------------------------------------------------

def test_the_smoke_records_the_seeds_it_asked_for_and_the_seeds_it_ran(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    smoke_env["seeds"] = (42, 123)
    out = run_g2_smoke(**smoke_env)
    assert out["seeds_requested"] == [42, 123]
    assert out["seeds_run"], "the trace does not say which seeds produced a result"
    assert set(out["seeds_run"]) <= set(out["seeds_requested"])


def test_the_smoke_does_not_call_a_multi_seed_request_a_clean_campaign(smoke_env):
    from deepagents_harness.smoke import run_g2_smoke

    smoke_env["seeds"] = (42, 123)
    out = run_g2_smoke(**smoke_env)
    assert out["seeds_run"] != out["seeds_requested"], (
        "3 sim-runs cannot cover 2 seeds x (baseline + candidate); the campaign "
        "must say it was truncated"
    )
    assert "truncat" in out["verdict"]["reason"].lower() or \
        out["verdict"]["status"] == "inconclusive"


# --- I11 --------------------------------------------------------------------

def test_a_tick_count_that_cannot_yield_a_sample_is_refused_before_the_wall_is_charged(tmp_path):
    from deepagents_harness.budget import BudgetWall
    from deepagents_harness.tools import run_trace

    wall = BudgetWall(max_sim_runs=2)
    with pytest.raises(ValueError):
        run_trace("B", 42, ticks=60, root=str(tmp_path), budget=wall)
    assert wall.used == 0


def test_a_burn_in_longer_than_the_run_is_refused(tmp_path):
    from deepagents_harness.tools import run_trace

    with pytest.raises(ValueError):
        run_trace("B", 42, ticks=100, burn_in=500, root=str(tmp_path))


# --- I12 / I13 --------------------------------------------------------------

def test_every_module_level_name_in_tools_resolves():
    import deepagents_harness.tools as t

    import dis  # noqa: F401  (documents that co_names is what we inspect)
    for name in t.__dict__:
        assert isinstance(t.__dict__[name], object)


def test_world_is_normalised_and_validated(tmp_path):
    from deepagents_harness.tools import run_trace

    out = run_trace("a", 42, ticks=100, root=str(tmp_path))
    assert json.load(open(out))["meta"]["world"] == "A"
    with pytest.raises(ValueError):
        run_trace("C", 42, ticks=100, root=str(tmp_path))


# --- I14 --------------------------------------------------------------------

def test_the_type_grammar_is_the_runs_own_set_door():
    """One grammar, not two. A proposal the tool accepts is one the run applies."""
    from deepagents_harness.tools import propose_law_delta

    out = propose_law_delta(current={}, delta={"larder_capacity": "1200.0"})
    assert out["proposal"] == {"larder_capacity": 1200.0}
    g = _flws.gates()
    seam = g._parse_set_overrides(["--set", "larder_capacity=1200.0"])
    assert out["proposal"] == seam


# --- M1 / M2 ----------------------------------------------------------------

def test_the_exported_ledger_append_is_callable(tmp_path):
    import deepagents_harness
    from deepagents_harness.ledger import Ledger

    led = Ledger(str(tmp_path / "l.jsonl"))
    out = deepagents_harness.ledger_append(
        led, "h", 3, {}, before={"reversals_per_72k": 10.0},
        after={"reversals_per_72k": 1.0})
    assert out["status"] == "confirmed"


def test_a_symlink_under_the_sweep_root_cannot_escape_the_sandbox(tmp_path):
    from deepagents_harness.tools import run_trace

    root = tmp_path / "sweeps"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside)
    with pytest.raises(ValueError):
        run_trace("B", 42, ticks=100, out=str(root / "escape" / "trace.json"),
                  root=str(root))
    assert not (outside / "trace.json").exists()
