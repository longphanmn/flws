"""Task 0 — the import seam onto the Phase 0-2 gate code.

The harness must not re-implement a gate. Every tool wraps a function that already
exists in scripts/preset_experiment.py, so this seam is the single place that knows
where the flws gate code lives, and it is cached so the module is imported once
(importing it pulls in app.simulation, which is not free).
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_gates_module_is_importable():
    from deepagents_harness import _flws

    mod = _flws.gates()
    assert mod is not None


def test_seam_exposes_every_phase_0_2_gate_function_the_tools_wrap():
    from deepagents_harness import _flws

    mod = _flws.gates()
    for name in (
        "osc_metrics",
        "osc_gate_report",
        "gate_lint",
        "build_run_manifest",
        "read_run_manifest",
        "write_run_manifest",
        "manifest_path_for",
        "gate_admissible_region",
        "run_oscillation",
        "_osc_config",
        "_parse_set_overrides",
    ):
        assert hasattr(mod, name), f"gate seam is missing {name}"


def test_seam_resolves_the_scripts_directory_relative_to_the_repo():
    from deepagents_harness import _flws

    assert _flws.SCRIPTS_DIR == os.path.join(REPO_ROOT, "scripts")
    assert _flws.SWEEPS_DIR == os.path.join(REPO_ROOT, "scripts", "sweeps")


def test_seam_imports_the_gate_module_exactly_once():
    from deepagents_harness import _flws

    assert _flws.gates() is _flws.gates()


def test_seam_puts_the_backend_on_sys_path_so_app_imports_resolve():
    from deepagents_harness import _flws

    _flws.gates()
    backend = os.path.join(REPO_ROOT, "backend")
    assert backend in sys.path
