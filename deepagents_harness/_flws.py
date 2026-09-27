"""The import seam onto the flws Phase 0-2 gate code.

Every tool in this harness wraps a function that already exists in
``scripts/preset_experiment.py``: the gate metrics, the gate report, the gate linter
and the run manifest. Nothing here re-derives a gate, because a second
implementation of a gate is a second opinion about the same number, and the whole
point of the harness is that the LLM never renders a verdict -- it can only ask the
deterministic code for one.

Importing the gate module pulls in ``app.simulation``, so it is imported once and
cached. The module is a script rather than a package, hence the file-location load.
"""
import importlib.util
import os
import sys

# deepagents_harness/ lives at the repo root, deliberately outside backend/ so the
# simulation package and its test suite are untouched by the harness.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
BACKEND_DIR = os.environ.get("FLWS_BACKEND", os.path.join(REPO_ROOT, "backend"))
SWEEPS_DIR = os.path.join(SCRIPTS_DIR, "sweeps")

_GATE_MODULE = None


def gates():
    """Import and cache scripts/preset_experiment.py, the only source of gate truth."""
    global _GATE_MODULE
    if _GATE_MODULE is not None:
        return _GATE_MODULE

    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, BACKEND_DIR)

    path = os.path.join(SCRIPTS_DIR, "preset_experiment.py")
    spec = importlib.util.spec_from_file_location("flws_preset_experiment", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load the flws gate harness at {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _GATE_MODULE = mod
    return mod
