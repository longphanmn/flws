"""Task 7 — tool 6: the append-only ledger with predicted signed gate deltas.

§6 L278: ``ledger_append(hypothesis, expected_gate, result)`` -> card id; append-only;
a hypothesis without a falsifiable prediction is rejected. §6 L307-309 gives the
reason: the failure mode this exists to stop is tuning whack-a-mole, and the only
defence that works is a *signed* prediction written down before the ticks are spent.
"Stability will improve" cannot be falsified, so it is not a prediction; "gate 3
reversals/72k falls by at least 5" can be, and a run that does not do it closes the
card as falsified.

Two properties do the work:

* **Two-phase.** A card is opened with its prediction *before* the run and closed
  with the measured delta after. A one-shot "hypothesis + result" call is available
  for the §6 signature, but the two-phase form is the one the smoke uses, because a
  prediction recorded after seeing the result is a rationalisation, not a forecast.
* **Append-only.** Closing a card appends an event; it never rewrites the opening
  line. A ledger that can be edited is a ledger that can be made to say the campaign
  worked.
"""
import hashlib
import json
import math
import os
import time

VALID_DIRECTIONS = ("increase", "decrease")

# gate -> the metric a signed prediction is made about. A prediction has to name a
# number, or "the gate improves" is not falsifiable.
GATE_METRICS = {
    1: "N_cv",
    2: "amplitude",
    3: "reversals_per_72k",
    4: "old_age_burstiness",
    5: "min_n_frac",
}

# Lower-is-better for every gate except 5: a population that sits too low relative
# to its carrying capacity is the failure, so gate 5 improves by rising.
GATE_LOWER_IS_BETTER = {1: True, 2: True, 3: True, 4: True, 5: False}


class LedgerError(ValueError):
    """A card that cannot be falsified is not a card."""


class Ledger:
    """An append-only JSONL ledger of hypothesis cards."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            open(path, "a").close()

    # -- reading ------------------------------------------------------------
    def events(self):
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def cards(self):
        """Fold the event log into one record per card, in opening order.

        Events without a `card_id` are skipped, not rejected: the log is the campaign's
        append-only record and also carries non-card entries (the deliberate
        `budget_raised` write). Folding by `card_id` unconditionally made the whole
        campaign die with a KeyError at the moment it opened its first card, which is
        how this was found.
        """
        out = {}
        for ev in self.events():
            cid = ev.get("card_id")
            if not cid:
                continue
            rec = out.setdefault(cid, {"card_id": cid, "status": "open", "events": []})
            rec["events"].append(ev)
            if ev["event"] == "card_opened":
                rec["hypothesis"] = ev["hypothesis"]
                rec["prediction"] = ev["prediction"]
            elif ev["event"] == "card_closed":
                rec["status"] = ev["status"]
                rec["result"] = ev.get("result")
                rec["measured_delta"] = ev.get("measured_delta")
        return [out[k] for k in sorted(out)]

    def card(self, card_id):
        for c in self.cards():
            if c["card_id"] == card_id:
                return c
        raise KeyError(card_id)

    # -- writing ------------------------------------------------------------
    def _append(self, ev):
        with open(self.path, "a") as f:
            # allow_nan=False: NaN/Infinity are Python leniencies, not JSON, and a
            # strict reader of "one JSON object per line" would choke on them.
            f.write(json.dumps(ev, sort_keys=True, allow_nan=False) + "\n")
        return ev

    def open_card(self, hypothesis, prediction, *, topology=None):
        """Record a hypothesis and its signed prediction *before* any tick runs."""
        if not hypothesis or not str(hypothesis).strip():
            raise LedgerError("a card needs a hypothesis")
        pred = _validate_prediction(prediction)
        # §6 L307-309: "cards whose prediction is not met are archived, not
        # retried". Enforced here rather than only at close time, because a
        # falsified hypothesis re-proposed as a fresh card is the whack-a-mole this
        # ledger exists to stop, and nothing else in the harness would notice.
        for existing in self.cards():
            if existing["hypothesis"] == hypothesis:
                raise LedgerError(
                    f"hypothesis already on the ledger as {existing['card_id']} "
                    f"(status {existing['status']}): a falsified card is archived, "
                    f"not retried. Propose a different topology, or a different "
                    f"falsifiable prediction for the same one."
                )
        cid = _card_id(hypothesis, pred, self._n_opened())
        self._append({
            "event": "card_opened",
            "card_id": cid,
            "ts": time.time(),
            "hypothesis": hypothesis,
            "prediction": pred,
            "topology": topology,
        })
        return cid

    def _n_opened(self):
        return sum(1 for e in self.events() if e["event"] == "card_opened")

    def close_card(self, card_id, result, *, before=None, after=None):
        """Append the verdict for a card, computed from the measured signed delta."""
        rec = self.card(card_id)
        if rec["status"] != "open":
            raise LedgerError(
                f"{card_id} is already {rec['status']}: a falsified card is "
                f"archived, not retried (§6 L307-309)"
            )
        pred = rec["prediction"]
        measured, delta = _measure(pred, before, after)
        status = "confirmed" if _met(pred, delta) else "falsified"
        return self._append({
            "event": "card_closed",
            "card_id": card_id,
            "ts": time.time(),
            "status": status,
            "result": result,
            "measured": measured,
            "measured_delta": delta,
            "prediction": pred,
        })

    def ledger_append(self, hypothesis, expected_gate, result, **kw):
        """The §6 L278 one-shot signature: hypothesis + expected gate + result.

        Kept for the documented tool surface. It still refuses a hypothesis with no
        falsifiable prediction, and it still appends a single event rather than
        rewriting one.
        """
        prediction = kw.pop("prediction", None) or _prediction_from_gate(expected_gate)
        before, after = kw.pop("before", None), kw.pop("after", None)
        if before is None or after is None:
            raise LedgerError(
                "ledger_append needs before/after metric values to evaluate a signed "
                "prediction; open_card + close_card is the two-phase form the smoke uses"
            )
        cid = self.open_card(hypothesis, prediction, topology=kw.pop("topology", None))
        ev = self.close_card(cid, result, before=before, after=after)
        return {"card_id": cid, "status": ev["status"], "measured_delta": ev["measured_delta"]}


def _validate_prediction(prediction):
    if not isinstance(prediction, dict):
        raise LedgerError(
            "a card needs a prediction dict: {gate, direction, min_delta}. "
            "A hypothesis with no falsifiable prediction is rejected (§6 L278)."
        )
    missing = [k for k in ("gate", "direction", "min_delta") if k not in prediction]
    if missing:
        raise LedgerError(f"prediction is missing {missing}")
    gate = prediction["gate"]
    if gate not in GATE_METRICS:
        raise LedgerError(
            f"prediction gate {gate!r} is not one of the five gates {sorted(GATE_METRICS)}"
        )
    direction = prediction["direction"]
    if direction not in VALID_DIRECTIONS:
        raise LedgerError(
            f"prediction direction {direction!r} must be one of {VALID_DIRECTIONS}: "
            f"an unsigned prediction cannot be falsified"
        )
    min_delta = prediction["min_delta"]
    if not isinstance(min_delta, (int, float)) or isinstance(min_delta, bool):
        raise LedgerError("prediction min_delta must be a number")
    if min_delta <= 0:
        raise LedgerError(
            f"prediction min_delta {min_delta!r} must be > 0: a prediction that any "
            f"result satisfies is not a prediction"
        )
    out = {"gate": gate, "metric": prediction.get("metric") or GATE_METRICS[gate],
           "direction": direction, "min_delta": float(min_delta),
           "rationale": prediction.get("rationale", "")}
    if out["metric"] != GATE_METRICS[gate]:
        raise LedgerError(
            f"gate {gate} is measured by {GATE_METRICS[gate]!r}, not {out['metric']!r}"
        )
    return out


def _prediction_from_gate(gate):
    """The default signed prediction for a gate, from the gate's own direction."""
    if gate not in GATE_METRICS:
        raise LedgerError(f"unknown gate {gate!r}")
    return {
        "gate": gate,
        "direction": "decrease" if GATE_LOWER_IS_BETTER[gate] else "increase",
        "min_delta": 0.0 + 1e-9,
    }


def _measure(pred, before, after):
    metric = pred["metric"]
    for label, src in (("before", before), ("after", after)):
        if not isinstance(src, dict) or metric not in src:
            raise LedgerError(
                f"{label} metrics have no {metric!r}, so the signed delta cannot be "
                f"computed and the prediction cannot be scored"
            )
        val = src[metric]
        # `None` is F5: the metric is undefined on this run (median old-age bin 0).
        # inf is a collapsed world. Neither is a measurement, and subtracting them
        # either raises TypeError or yields NaN -- which then reads as "falsified",
        # i.e. an undefined value reported as one that refuted the prediction.
        if val is None:
            raise LedgerError(
                f"gate {pred['gate']} ({metric}) is not measurable on this run "
                f"({label}={val!r}); the prediction cannot be scored, and an "
                f"unmeasurable gate is not a falsified hypothesis"
            )
        if isinstance(val, float) and not math.isfinite(val):
            raise LedgerError(
                f"{label} {metric}={val!r} is not finite (the world collapsed or the "
                f"metric is undefined); the prediction cannot be scored"
            )
    return {metric: after[metric]}, round(after[metric] - before[metric], 12)


def _met(pred, delta):
    if delta == 0:
        return False
    sign = "increase" if delta > 0 else "decrease"
    return sign == pred["direction"] and abs(delta) >= pred["min_delta"]


def _card_id(hypothesis, pred, n):
    blob = json.dumps([hypothesis, pred], sort_keys=True, default=repr)
    return f"card-{n + 1:04d}-{hashlib.sha256(blob.encode()).hexdigest()[:8]}"
