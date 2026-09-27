"""The budget wall.

§6 L263: the Budgeter holds "a hard wall-clock + tick budget; refuses to escalate
without a ledger entry". The reason this is code and not a prompt instruction is
arithmetic (§6 L292-L304): one T2 iteration is ~2 h of a 4-core box, a 34-hypothesis
campaign is 8.2 h, and tokens are ~3 orders of magnitude cheaper than CPU. An engine
that optimises decisions per sim-hour is the entire economic content of the proposal,
so "no" has to be a mechanism rather than a hope.

A refusal raises. It never returns a truncated result: a caller that cannot tell it
was cut off will go on to report a partial run as if it were a whole one.
"""
import time


class BudgetExhausted(RuntimeError):
    """Raised when a run would exceed the wall. The message is the whole point."""


class BudgetWall:
    """A hard cap on simulation runs, ticks, and wall-clock.

    §6 L263 names three duties: "hard wall-clock + tick budget; refuses to escalate
    without a ledger entry". All three are here, because the third is the one that
    does the work -- a card with a falsifiable prediction is what makes a run
    spendable, and without the gate the wall is only a counter.
    """

    def __init__(self, max_sim_runs, *, max_ticks=None, max_ticks_total=None,
                 deadline_s=None, ledger=None, require_ledger_entry=False):
        if not isinstance(max_sim_runs, int) or max_sim_runs < 1:
            raise ValueError(f"max_sim_runs must be a positive int, got {max_sim_runs!r}")
        self.max_sim_runs = max_sim_runs
        self.max_ticks = max_ticks
        self.max_ticks_total = max_ticks_total
        self.deadline_s = deadline_s
        self.ledger = ledger
        self.require_ledger_entry = require_ledger_entry
        self.ticks_spent = 0
        self.spends = []
        self._t0 = time.monotonic()

    @property
    def used(self):
        return len(self.spends)

    @property
    def remaining(self):
        return max(0, self.max_sim_runs - self.used)

    @property
    def elapsed_s(self):
        return round(time.monotonic() - self._t0, 3)

    def has_open_card(self):
        if self.ledger is None:
            return False
        return any(c["status"] == "open" for c in self.ledger.cards())

    def _check_deadline(self, reason):
        if self.deadline_s is not None and self.elapsed_s > self.deadline_s:
            raise BudgetExhausted(
                f"budget wall: {self.elapsed_s}s elapsed exceeds the "
                f"{self.deadline_s}s wall-clock ceiling for {reason!r}"
            )

    def _check_ledger(self, reason):
        if not self.require_ledger_entry:
            return
        if self.ledger is None:
            raise BudgetExhausted(
                f"budget wall: this wall requires a ledger entry before spending "
                f"simulation time, and no ledger is attached ({reason!r})"
            )
        if not self.has_open_card():
            raise BudgetExhausted(
                f"budget wall: refusing {reason!r} because the ledger has no open "
                f"card. A run with no falsifiable prediction on the record is how "
                f"the campaign becomes whack-a-mole; open a card first."
            )

    def spend(self, reason="unspecified"):
        """Consume one run's worth of budget, or refuse.

        Checked *before* the work, so a refused run costs no ticks and leaves no
        partial artifact behind.
        """
        if self.remaining <= 0:
            raise BudgetExhausted(
                f"budget wall: {self.max_sim_runs} sim-run(s) already spent, refusing "
                f"{reason!r}. Escalating without a ledger entry is not allowed; "
                f"archive the falsified card or raise the wall deliberately."
            )
        self._check_deadline(reason)
        self._check_ledger(reason)
        self.spends.append({"index": self.used, "reason": reason})

    def spend_ticks(self, ticks, reason="unspecified"):
        """Charge a run against the per-run ceiling and the running tick total."""
        if self.max_ticks is not None and ticks > self.max_ticks:
            raise BudgetExhausted(
                f"budget wall: {ticks} ticks exceeds the {self.max_ticks}-tick "
                f"per-run ceiling for {reason!r}"
            )
        if (self.max_ticks_total is not None
                and self.ticks_spent + ticks > self.max_ticks_total):
            raise BudgetExhausted(
                f"budget wall: {self.ticks_spent}+{ticks} ticks exceeds the "
                f"{self.max_ticks_total}-tick campaign ceiling for {reason!r}"
            )
        self.spend(reason)
        self.ticks_spent += ticks

    def to_dict(self):
        return {
            "max_sim_runs": self.max_sim_runs,
            "spent": self.used,
            "remaining": self.remaining,
            "max_ticks": self.max_ticks,
            "max_ticks_total": self.max_ticks_total,
            "ticks_spent": self.ticks_spent,
            "deadline_s": self.deadline_s,
            "elapsed_s": self.elapsed_s,
            "require_ledger_entry": self.require_ledger_entry,
            "spends": list(self.spends),
        }
