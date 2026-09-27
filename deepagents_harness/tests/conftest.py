"""Make the repo-root harness package importable when pytest runs from anywhere."""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest  # noqa: E402  (after the sys.path bootstrap, on purpose)


@pytest.fixture()
def smoke_env(tmp_path):
    """A G2 campaign in a throwaway tree: tiny ticks, so the tests stay quick."""
    return {
        "ledger_path": str(tmp_path / "ledger" / "cards.jsonl"),
        "root": str(tmp_path / "sweeps"),
        "ticks": 100,
        "seeds": (42,),
        "max_sim_runs": 3,
    }
