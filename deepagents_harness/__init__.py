"""deepagents harness for the flws oscillation gate suite.

Brainstorm §6: the agent's job is to reach a falsifiable hypothesis cheaply and to
refuse to spend simulation time on a candidate that is structurally impossible. It is
not to decide whether a run passed -- the Verifier is a plain function
(``osc_gate_report``) and nothing in this package lets a model write one.

The seven tools (§6 L271-L279) are thin wrappers over the Phase 0-2 gate code in
``scripts/preset_experiment.py``; the seam that loads it is :mod:`deepagents_harness._flws`.
Nothing here re-derives a gate, touches ``law_state_v1``, or writes outside
``scripts/sweeps/``.

The harness lives at the repo root, outside ``backend/``, so the simulation package
and its test suite are untouched by it.
"""
from .budget import BudgetExhausted, BudgetWall
from .ledger import Ledger, LedgerError
from .tools import (
    METRICS_TOKEN_CAP_BYTES,
    compare,
    default_out_path,
    gate_lint,
    propose_law_delta,
    read_metrics,
    read_run_manifest,
    run_trace,
)

__version__ = "0.1.0"

# §6 L278 names `ledger_append(hypothesis, expected_gate, result) -> card id`. It is a
# method of Ledger because a card is always appended to a specific ledger file, and
# an agent handed a bare function could name any path it liked.
ledger_append = Ledger.ledger_append

__all__ = [
    "METRICS_TOKEN_CAP_BYTES",
    "BudgetExhausted",
    "BudgetWall",
    "Ledger",
    "LedgerError",
    "compare",
    "default_out_path",
    "gate_lint",
    "ledger_append",
    "propose_law_delta",
    "read_metrics",
    "read_run_manifest",
    "run_trace",
    "__version__",
]
