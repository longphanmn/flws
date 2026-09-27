"""Task 7 — tool 6: ledger_append, the predicted signed gate delta.

These tests are the anti-whack-a-mole mechanism. Each one removes a way the ledger
could accept a card that later reads as a successful campaign.
"""
import json

import pytest

from deepagents_harness.ledger import Ledger, LedgerError

PRED = {"gate": 3, "direction": "decrease", "min_delta": 5.0}


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(str(tmp_path / "ledger" / "cards.jsonl"))


def test_a_card_needs_a_hypothesis(ledger):
    with pytest.raises(LedgerError):
        ledger.open_card("  ", PRED)


def test_a_hypothesis_with_no_prediction_is_rejected(ledger):
    with pytest.raises(LedgerError) as exc:
        ledger.open_card("G2 granary buffering decouples N from the season", None)
    assert "falsifiable" in str(exc.value)


def test_a_prediction_with_no_gate_is_rejected(ledger):
    with pytest.raises(LedgerError):
        ledger.open_card("h", {"direction": "decrease", "min_delta": 5.0})


def test_a_prediction_with_no_direction_is_rejected(ledger):
    with pytest.raises(LedgerError):
        ledger.open_card("h", {"gate": 3, "min_delta": 5.0})


def test_an_unsigned_direction_is_rejected(ledger):
    with pytest.raises(LedgerError) as exc:
        ledger.open_card("h", {"gate": 3, "direction": "better", "min_delta": 5.0})
    assert "unsigned" in str(exc.value)


def test_a_zero_min_delta_is_rejected_as_unfalsifiable(ledger):
    with pytest.raises(LedgerError) as exc:
        ledger.open_card("h", {"gate": 3, "direction": "decrease", "min_delta": 0})
    assert "not a prediction" in str(exc.value)


def test_a_prediction_about_the_wrong_metric_for_its_gate_is_rejected(ledger):
    with pytest.raises(LedgerError) as exc:
        ledger.open_card("h", {"gate": 3, "metric": "N_cv", "direction": "decrease",
                               "min_delta": 1.0})
    assert "reversals_per_72k" in str(exc.value)


def test_opening_a_card_returns_an_id_and_writes_one_json_line(ledger):
    cid = ledger.open_card("G2: buffer the season in a larder", PRED)
    assert cid.startswith("card-0001-")
    lines = [json.loads(x) for x in open(ledger.path) if x.strip()]
    assert len(lines) == 1
    assert lines[0]["event"] == "card_opened"
    assert lines[0]["prediction"]["direction"] == "decrease"
    assert lines[0]["prediction"]["min_delta"] == 5.0


def test_card_ids_are_unique_and_a_repeated_hypothesis_is_refused(ledger):
    """§6 L307-309: a falsified card is archived, not retried.

    This test previously asserted the opposite -- that two identical hypotheses get
    two distinct cards. Re-proposing a falsified hypothesis under a fresh id is the
    whack-a-mole the ledger exists to stop, so `open_card` now refuses it.
    """
    a = ledger.open_card("same", PRED)
    with pytest.raises(LedgerError):
        ledger.open_card("same", PRED)
    assert len(ledger.cards()) == 1
    assert ledger.cards()[0]["card_id"] == a


def test_a_different_prediction_for_the_same_hypothesis_is_still_refused(ledger):
    """Retrying with a tweaked threshold is the same hypothesis, not a new one."""
    ledger.open_card("same", PRED)
    with pytest.raises(LedgerError):
        ledger.open_card("same", {"gate": 3, "direction": "decrease",
                                  "min_delta": 0.5})


def test_a_genuinely_different_hypothesis_gets_its_own_card(ledger):
    a = ledger.open_card("G2 larder", PRED)
    b = ledger.open_card("G2 beds as binding capacity",
                         {"gate": 5, "direction": "increase", "min_delta": 0.02})
    assert a != b
    assert len(ledger.cards()) == 2


def test_closing_a_card_appends_and_never_rewrites_the_opening_line(ledger):
    cid = ledger.open_card("G2", PRED)
    opened_line = open(ledger.path).read()
    ledger.close_card(cid, {"note": "ran T0"}, before={"reversals_per_72k": 100.0},
                      after={"reversals_per_72k": 40.0})
    text = open(ledger.path).read()
    assert text.startswith(opened_line)
    assert len([x for x in text.splitlines() if x.strip()]) == 2


def test_a_prediction_met_in_direction_and_magnitude_is_confirmed(ledger):
    cid = ledger.open_card("G2", PRED)
    ev = ledger.close_card(cid, {}, before={"reversals_per_72k": 100.0},
                          after={"reversals_per_72k": 40.0})
    assert ev["status"] == "confirmed"
    assert ev["measured_delta"] == -60.0
    assert ledger.card(cid)["status"] == "confirmed"


def test_a_prediction_moved_the_wrong_way_is_falsified(ledger):
    cid = ledger.open_card("G2", PRED)
    ev = ledger.close_card(cid, {}, before={"reversals_per_72k": 100.0},
                          after={"reversals_per_72k": 160.0})
    assert ev["status"] == "falsified"
    assert ev["measured_delta"] == 60.0


def test_a_prediction_that_moved_too_little_is_falsified(ledger):
    cid = ledger.open_card("G2", PRED)
    ev = ledger.close_card(cid, {}, before={"reversals_per_72k": 100.0},
                          after={"reversals_per_72k": 99.0})
    assert ev["status"] == "falsified"


def test_a_prediction_met_by_exactly_zero_movement_is_falsified(ledger):
    cid = ledger.open_card("G2", PRED)
    ev = ledger.close_card(cid, {}, before={"reversals_per_72k": 100.0},
                          after={"reversals_per_72k": 100.0})
    assert ev["status"] == "falsified"
    assert ev["measured_delta"] == 0.0


def test_a_falsified_card_cannot_be_retried(ledger):
    cid = ledger.open_card("G2", PRED)
    ledger.close_card(cid, {}, before={"reversals_per_72k": 100.0},
                      after={"reversals_per_72k": 160.0})
    with pytest.raises(LedgerError) as exc:
        ledger.close_card(cid, {}, before={"reversals_per_72k": 160.0},
                          after={"reversals_per_72k": 40.0})
    assert "archived" in str(exc.value)


def test_a_gate_that_improves_by_rising_has_an_increasing_prediction(ledger):
    cid = ledger.open_card("raise min N fraction", {"gate": 5, "direction": "increase",
                                                    "min_delta": 0.02})
    ev = ledger.close_card(cid, {}, before={"min_n_frac": 0.90},
                          after={"min_n_frac": 0.95})
    assert ev["status"] == "confirmed"


def test_a_missing_metric_makes_the_card_unscoreable_rather_than_guessed(ledger):
    cid = ledger.open_card("G2", PRED)
    with pytest.raises(LedgerError) as exc:
        ledger.close_card(cid, {}, before={"N_cv": 0.1}, after={"N_cv": 0.2})
    assert "cannot be scored" in str(exc.value)


def test_the_oneshot_ledger_append_signature_returns_a_card_and_a_verdict(ledger):
    out = ledger.ledger_append(
        "G2: larder buffering", 3, {"note": "T0"},
        before={"reversals_per_72k": 100.0}, after={"reversals_per_72k": 40.0},
    )
    assert out["status"] == "confirmed"
    assert out["card_id"].startswith("card-0001-")
    assert len(ledger.cards()) == 1


def test_the_oneshot_signature_still_refuses_an_unfalsifiable_prediction(ledger):
    with pytest.raises(LedgerError):
        ledger.ledger_append("G2", 99, {}, before={"N_cv": 1}, after={"N_cv": 0})


def test_every_card_in_the_ledger_shows_its_predicted_signed_delta(ledger):
    """The §12 Step 3 acceptance check, as a test."""
    a = ledger.open_card("G2 larder", PRED)
    ledger.close_card(a, {}, before={"reversals_per_72k": 100.0},
                      after={"reversals_per_72k": 40.0})
    b = ledger.open_card("G2 granary", {"gate": 5, "direction": "increase",
                                        "min_delta": 0.02})
    ledger.close_card(b, {}, before={"min_n_frac": 0.9}, after={"min_n_frac": 0.8})

    cards = ledger.cards()
    assert len(cards) == 2
    for c in cards:
        assert c["prediction"]["direction"] in ("increase", "decrease")
        assert c["prediction"]["min_delta"] > 0
        assert c["status"] in ("confirmed", "falsified")
    assert [c["status"] for c in cards] == ["confirmed", "falsified"]


def test_the_ledger_is_readable_as_one_json_object_per_line(ledger):
    a = ledger.open_card("G2", PRED)
    ledger.close_card(a, {}, before={"reversals_per_72k": 10.0},
                      after={"reversals_per_72k": 1.0})
    for line in open(ledger.path):
        if line.strip():
            assert isinstance(json.loads(line), dict)


def test_cards_ignores_events_that_are_not_cards(ledger):
    """`cards()` folds the log by `card_id`, so any non-card event on it -- the
    campaign's deliberate `budget_raised` record, for one -- used to raise KeyError and
    take the campaign down at the moment it opened its first card. Found live: writing
    the campaign-2 budget change to ledger_campaign.jsonl made `Ledger.cards()` raise,
    so `--candidate` died before spending a single tick."""
    cid = ledger.open_card("G1 envelope pins N", PRED)
    ledger._append({"event": "budget_raised", "campaign": "CAMPAIGN-2",
                    "after": {"max_t1_candidates": 6}})
    assert [c["card_id"] for c in ledger.cards()] == [cid]
    assert ledger.card(cid)["status"] == "open"
    # the non-card record is still on the log, unchanged: append-only means it survives
    # the fold ignoring it
    assert [e["event"] for e in ledger.events()] == ["card_opened", "budget_raised"]
