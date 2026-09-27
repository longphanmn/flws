"""Task 2 — tool 1: read_metrics.

§6 L273: ``read_metrics(path)`` -> ``{metrics, gates}`` only; strips ``samples``;
token cap 4 KB. §6 L261 and L552-553 make the reason explicit: the samples array is
~500 KB and the agent must never see it, and the verdict is copied from
``osc_gate_report`` rather than authored.

The tool also re-derives the verdict from the metrics instead of trusting the
artifact's stored ``passed``. An artifact is a file; a hand-edited ``passed: true``
is exactly the "summarise a FAIL as a PASS" failure mode §13 L561-562 forbids, and
re-deriving is the only thing that catches it.
"""
import json

import pytest

from deepagents_harness import _flws


def _synthetic_run(seed=42, pops=None, sample=100, n=30):
    pops = pops or [200 + (i % 3) for i in range(n)]
    return {
        "preset": "theocracy",
        "seed": seed,
        "modulated": False,
        "K": 380.0,
        "M": 600.0,
        "total_ticks": n * sample,
        "burn_in": 0,
        "sample": sample,
        "elapsed_s": 12.0,
        "ms_per_tick": 40.0,
        "samples": [
            {
                "tick": (i + 1) * sample,
                "pop": pops[i],
                "food": 400,
                "xi": 0.1,
                "age_mult": 1.0,
                "season_mult": 1.0,
                "deaths": {"old_age": 2, "starvation": 0},
            }
            for i in range(n)
        ],
    }


@pytest.fixture()
def artifact(tmp_path):
    """An artifact shaped exactly like osc_ab_run writes it, via the real code."""
    g = _flws.gates()
    run = _synthetic_run()
    m = g.osc_metrics(run)
    passed, checks = g.osc_gate_report(m, flat=True)
    path = str(tmp_path / "run.json")
    with open(path, "w") as f:
        json.dump(
            {
                "meta": {"world": "B", "manifest": None},
                "metrics": m,
                "gates": [
                    {"name": n, "pass": ok, "status": g._gate_status(ok), "value": v}
                    for n, ok, v in checks
                ],
                "passed": passed,
                "samples": run["samples"],
            },
            f,
        )
    return path


def test_returns_metrics_and_gates(artifact):
    from deepagents_harness.tools import read_metrics

    out = read_metrics(artifact)
    assert out["metrics"]["seed"] == 42
    assert len(out["gates"]) == 5


def test_strips_the_samples_array_entirely(artifact):
    from deepagents_harness.tools import read_metrics

    out = read_metrics(artifact)
    # Assert on keys, not on a substring of the whole blob: pytest derives
    # tmp_path from the test name, so the path itself contains the word.
    assert "samples" not in out
    assert "samples" not in out["metrics"]
    assert set(out) == {
        "path", "metrics", "gates", "passed", "stored_passed", "verdict_present",
        "verdict_consistent", "admissible", "bytes", "within_cap",
    }
    assert "pop" not in json.dumps(out["metrics"])


def test_stays_under_the_4kb_cap_even_though_the_artifact_is_much_bigger(artifact):
    import os

    from deepagents_harness.tools import METRICS_TOKEN_CAP_BYTES, read_metrics

    out = read_metrics(artifact)
    assert os.path.getsize(artifact) > METRICS_TOKEN_CAP_BYTES
    assert out["bytes"] <= METRICS_TOKEN_CAP_BYTES
    assert out["within_cap"] is True


def test_refuses_rather_than_truncating_when_the_cap_is_exceeded(monkeypatch, artifact):
    from deepagents_harness import tools

    monkeypatch.setattr(tools, "METRICS_TOKEN_CAP_BYTES", 64)
    with pytest.raises(ValueError) as exc:
        tools.read_metrics(artifact)
    # A truncated metric dict is a number the run never measured.
    assert "cap" in str(exc.value).lower()


def test_verdict_is_re_derived_not_taken_from_the_artifact(artifact):
    from deepagents_harness.tools import read_metrics

    with open(artifact) as f:
        payload = json.load(f)
    payload["passed"] = True
    payload["metrics"]["N_cv"] = 0.9  # a real FAIL
    with open(artifact, "w") as f:
        json.dump(payload, f)

    out = read_metrics(artifact)
    assert out["passed"] is False
    assert out["stored_passed"] is True
    assert out["verdict_consistent"] is False


def test_reports_a_tri_state_gate_status_so_not_measurable_is_not_a_number(artifact):
    from deepagents_harness.tools import read_metrics

    out = read_metrics(artifact)
    statuses = {g["status"] for g in out["gates"]}
    assert statuses <= {"pass", "fail", "not-measurable"}


def test_raises_on_a_missing_artifact(tmp_path):
    from deepagents_harness.tools import read_metrics

    with pytest.raises(FileNotFoundError):
        read_metrics(str(tmp_path / "nope.json"))
