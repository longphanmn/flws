"""§V Clan founding redesign — mixed-caste settlements.

Every functional house anchors a clan; the founding generation joins the clan
of its nearest house, so castes mix inside settlements. `max_clans` pins how
many spatial clans arise. All founding is deterministic given the seed.
"""

from fastapi.testclient import TestClient

from app.config import Config
from app.entities import House
from app.main import app
from app.simulation import Simulation


def anchors_of(s: Simulation) -> dict[int, House]:
    """House claims by clan id (each clan at most one anchor)."""
    anchors: dict[int, House] = {}
    for e in s.world.entities.values():
        if isinstance(e, House) and not e.is_ruin and e.clan_id:
            assert e.clan_id not in anchors  # no double-claim
            anchors[e.clan_id] = e
    return anchors


def houses_of(s: Simulation) -> list[House]:
    return [e for e in s.world.entities.values() if isinstance(e, House) and not e.is_ruin]


def roster_by_house(s: Simulation) -> dict[int, set[int]]:
    """Reconstruct 'join your nearest house's clan' from scratch."""
    houses = houses_of(s)
    by_house: dict[int, set[int]] = {}
    for c in s.world.creatures():
        home = min(houses, key=lambda h: (s.distance(c.x, c.y, h.x, h.y), h.id))
        by_house.setdefault(home.id, set()).add(c.id)
    return by_house


def test_founding_clans_are_mixed_caste_settlements():
    s = Simulation(Config(seed=77))
    founders = s.world.creatures()
    houses = houses_of(s)
    assert houses

    # -1 default: every non-ruin house founded exactly one clan; all founders enrolled
    assert len(s.clans) == len(houses)
    assert set(anchors_of(s)) == set(s.clans)
    assert all(c.clan_id > 0 for c in founders)

    # membership is spatial: each founder's nearest anchor house is its own
    anchors = anchors_of(s)
    for c in founders:
        home = anchors[c.clan_id]
        nearest_cid = min(
            anchors,
            key=lambda cid: (s.distance(c.x, c.y, anchors[cid].x, anchors[cid].y), cid),
        )
        assert nearest_cid == c.clan_id

    # mixed castes share settlements — no caste-pure world
    castes_by_clan: dict[int, set[str]] = {}
    for c in founders:
        castes_by_clan.setdefault(c.clan_id, set()).add(c.caste)
    assert any(len(v) >= 2 for v in castes_by_clan.values())


def test_anchor_claims_match_nearest_house_not_round_robin():
    """Uncapped founding: clan rosters must exactly match an independent
    reconstruction of 'every founder joins its nearest house's clan', and each
    anchor wall carries its clan crest (territory/totem anchor on that house)."""
    s = Simulation(Config(seed=31))
    houses = houses_of(s)

    expected = roster_by_house(s)  # house id -> founder ids
    actual: dict[int, set[int]] = {}
    for h in houses:
        # ghost settlements (no founder landed here) legitimately found
        # leaderless clans that decay with §L abandonment — skip them
        if h.clan_id and expected.get(h.id):
            actual.setdefault(h.clan_id, set()).update(expected.get(h.id, set()))
    real_roster: dict[int, set[int]] = {}
    for c in s.world.creatures():
        real_roster.setdefault(c.clan_id, set()).add(c.id)
    assert actual == real_roster

    anchors = anchors_of(s)
    assert all(h.clan_color == s.clans[h.clan_id]["color"] for h in anchors.values())


def test_max_clans_pins_spatial_cluster_count():
    s = Simulation(Config(seed=9, max_clans=3))
    founders = s.world.creatures()
    founding_clans = {c.clan_id for c in founders}
    assert founding_clans == {1, 2, 3}  # exactly N clans, ids 1..N
    # every clan settled at a distinct anchor house
    anchors = anchors_of(s)
    assert set(founding_clans) <= set(anchors)


def test_max_clans_one_unites_founders_in_single_clan():
    s = Simulation(Config(seed=11, max_clans=1))
    founders = s.world.creatures()
    assert {c.clan_id for c in founders} == {1}
    leader_id = s.clans[1]["leader_id"]
    assert leader_id in {c.id for c in founders}


def test_kcenter_clusters_are_spatially_contiguous():
    """max_clans=N: clusters must equal the greedy k-centre over the founders
    (first centre nearest the world's heart, then farthest-from-chosen), and
    greedy anchor matching must never take a house from a strictly nearer
    claimant — contiguity without round-robin."""
    seed, n = 5, 3

    def reconstruct(s: Simulation) -> list[set[int]]:
        w = s.world
        founders = sorted(s.world.creatures(), key=lambda c: c.id)
        cx, cy = s.config.width / 2, s.config.height / 2
        centres = [min(founders, key=lambda c: (w.distance(c.x, c.y, cx, cy), c.id))]
        while len(centres) < n:
            rest = [c for c in founders if all(c.id != ct.id for ct in centres)]
            nxt = max(
                rest,
                key=lambda c: (min(w.distance(c.x, c.y, ct.x, ct.y) for ct in centres), -c.id),
            )
            centres.append(nxt)
        groups: list[set[int]] = [set() for _ in centres]
        for c in founders:
            best_i, best_d = 0, float("inf")
            for i, ct in enumerate(centres):
                d = w.distance(c.x, c.y, ct.x, ct.y)
                if d < best_d:
                    best_i, best_d = i, d
            groups[best_i].add(c.id)
        return [g for g in groups if g]

    s = Simulation(Config(seed=seed, max_clans=n))
    actual: list[set[int]] = []
    for cid in sorted({c.clan_id for c in s.world.creatures()}):
        actual.append({c.id for c in s.world.creatures() if c.clan_id == cid})
    assert sorted(actual) == sorted(reconstruct(s))

    # fairness of greedy matching: if a rival's anchor is nearer this clan's
    # centroid than its own, that rival must be at least as close to it
    anchors = anchors_of(s)
    centroids = {
        cid: (
            sum(m.x for m in members) / len(members),
            sum(m.y for m in members) / len(members),
        )
        for cid in anchors
        for members in [[c for c in s.world.creatures() if c.clan_id == cid]]
        if members
    }
    for cid, (ax, ay) in centroids.items():
        d_own = s.distance(ax, ay, anchors[cid].x, anchors[cid].y)
        for other_cid, other in anchors.items():
            if other_cid == cid:
                continue
            d_alt = s.distance(ax, ay, other.x, other.y)
            if d_alt < d_own:
                ox, oy = centroids[other_cid]
                assert s.distance(ox, oy, other.x, other.y) <= d_alt + 1e-6


def test_founding_is_deterministic_given_seed():
    def build(seed: int) -> dict:
        s = Simulation(Config(seed=seed))
        return {
            "members": sorted((c.id, c.clan_id) for c in s.world.creatures()),
            "clans": {
                cid: (info["name"], info["totem"], info["leader_id"])
                for cid, info in s.clans.items()
            },
            "claims": sorted(
                (e.id, e.clan_id)
                for e in s.world.entities.values()
                if isinstance(e, House)
            ),
        }

    assert build(4242) == build(4242)
    assert build(7) != build(8)  # different seeds, different societies


def test_leader_is_founder_nearest_the_settlement_centre():
    """Founder/leader = the founding creature nearest the house centre; a
    founder leads at most one clan (settlements beyond the founder count get
    leader None). Mirrors the id-order walk used at world creation."""
    s = Simulation(Config(seed=21))  # uncapped: one clan per house
    pos = {c.id: (c.x, c.y) for c in s.world.creatures()}
    by_house = roster_by_house(s)
    taken: set[int] = set()
    for h in sorted(houses_of(s), key=lambda hh: hh.id):
        members = by_house.get(h.id, set())
        pool = [mid for mid in members if mid not in taken] or list(members)
        expected = (
            min(pool, key=lambda mid: (s.distance(*pos[mid], h.x, h.y), mid))
            if pool
            else None
        )
        assert s.clans[h.clan_id]["leader_id"] == expected
        if expected is not None:
            taken.add(expected)


def test_clan_can_have_multiple_houses_and_leader_lives_in_main_house():
    """A clan can possess multiple houses across its territory, and the leader resides in the main house."""
    s = Simulation(Config(seed=42, max_clans=1, shelter_enabled=True, house_claim_enabled=True))
    cid = 1
    leader_id = s.clans[cid]["leader_id"]
    leader = s.world.entities[leader_id]

    # Main house was assigned at founding
    main_hid = s.clans[cid]["main_house_id"]
    assert main_hid is not None
    main_house = s.world.entities[main_hid]
    assert isinstance(main_house, House)
    assert main_house.is_main is True
    assert main_house.clan_id == cid

    # Spawn additional houses for the clan
    h2 = s._spawn_settlement_house(clan_id=cid, near=leader)
    assert h2.clan_id == cid
    assert h2.is_main is False

    # Check shelter preference: Leader prioritizes main house
    houses = [h for h in s.world.entities.values() if isinstance(h, House) and not h.is_ruin]
    chosen = s._house_for(leader, houses)
    assert chosen is not None
    assert chosen.id == main_hid

    # Other clan member chooses nearest available clan house
    other_members = [c for c in s.world.creatures() if c.clan_id == cid and c.id != leader_id]
    if other_members:
        om = other_members[0]
        om_chosen = s._house_for(om, houses)
        assert om_chosen is not None
        assert om_chosen.clan_id == cid


def test_clan_extinction_event_emission():
    """When a clan loses all members and functional houses, it emits clan_extinction event."""
    s = Simulation(Config(seed=7, num_houses=0, num_triangles=0, num_squares=0, num_pentagons=0, num_hexagons=0, num_priests=0, num_women=0))
    cid = s._new_clan(None)
    s.clans[cid]["name"] = "Fallen Dynasty"
    s.clans[cid]["born_tick"] = 0
    s.tick = 100
    s._prune_extinct_clans()
    assert cid not in s.clans
    ext_events = [e for e in s.history if e.type == "clan_extinction"]
    assert len(ext_events) >= 1
    ev = ext_events[-1]
    assert ev.payload["clan_id"] == cid
    assert ev.payload["clan_name"] == "Fallen Dynasty"
    assert ev.payload["lifespan_ticks"] == 100


def test_schism_event_payload_richness():
    """Schism events should include parent, new_clan, parent_name, new_name, and member_count."""
    s = Simulation(Config(seed=42, schism_enabled=True, schism_min_pop=2))
    # Pick a clan with members
    cid = next(iter(s.clans))
    parent_name = s.clans[cid]["name"]
    members = [c for c in s.world.creatures() if c.clan_id == cid]
    assert len(members) >= 2
    # Force a schism
    s.tick = 200
    s._update_schism()
    schisms = [e for e in s.history if e.type == "schism"]
    if schisms:
        ev = schisms[-1]
        assert "parent" in ev.payload
        assert "new_clan" in ev.payload
        assert "parent_name" in ev.payload
        assert "new_name" in ev.payload
        assert "member_count" in ev.payload


def test_clan_war_wins_and_losses_persistence():
    """War wins and losses must persist past sim.history eviction and reflect in payloads."""
    from app.main import _clan_details, _clans_payload, RT
    from app.protocol import HistoryEvent
    from app.simulation.constants import _clan_sig

    s = Simulation(Config(seed=42, war_enabled=True))
    cids = list(s.clans.keys())
    assert len(cids) >= 2
    c1, c2 = cids[0], cids[1]

    assert s.clans[c1].get("war_wins", 0) == 0
    assert s.clans[c1].get("war_losses", 0) == 0
    sig_before = _clan_sig(s.clans[c1])

    # Emit a war duel event where c2 wins against c1
    s._emit(
        HistoryEvent(
            type="war",
            tick=s.tick,
            entity_id=1,
            caste="Warrior",
            x=10.0,
            y=10.0,
            payload={"winner": 2, "a": c1, "b": c2},
        )
    )

    assert s._clan_war_losses[c1] == 1
    assert s._clan_war_wins[c2] == 1
    assert s.clans[c1]["war_losses"] == 1
    assert s.clans[c2]["war_wins"] == 1

    # _clan_sig must change so delta_state broadcasts the update
    sig_after = _clan_sig(s.clans[c1])
    assert sig_before != sig_after

    # Evict event from sim.history by flooding with dummy events
    for i in range(250):
        s._emit(
            HistoryEvent(
                type="birth",
                tick=s.tick + i,
                entity_id=100 + i,
                caste="Worker",
                x=0,
                y=0,
                payload={},
            )
        )
    # Confirm war event is evicted from sim.history
    assert not any(e.type == "war" for e in s.history)

    # Payloads must still return the true persistent war counts
    payload = _clans_payload(s)
    clan1_entry = next(c for c in payload["clans"] if c["id"] == c1)
    clan2_entry = next(c for c in payload["clans"] if c["id"] == c2)
    assert clan1_entry["war_losses"] == 1
    assert clan2_entry["war_wins"] == 1

    # _clan_details must also return persistent war counts
    old_sim = RT.sim
    try:
        RT.sim = s
        details1 = _clan_details(c1)
        details2 = _clan_details(c2)
        assert details1["war_losses"] == 1
        assert details2["war_wins"] == 1
    finally:
        RT.sim = old_sim



