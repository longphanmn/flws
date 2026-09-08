import pytest
from app.config import Config
from app.entities import Creature, Food, House
from app.simulation import Simulation


def test_creature_evolution_initialization():
    cfg = Config(seed=42)
    sim = Simulation(cfg)

    # All creatures have personality, skills, tools initialized
    creatures = list(sim.world.creatures())
    assert len(creatures) > 0
    for c in creatures:
        assert c.personality in ("brave", "cautious", "altruistic", "greedy", "explorer", "builder")
        assert isinstance(c.skills, dict)
        assert "farming" in c.skills
        assert "combat" in c.skills
        assert "foraging" in c.skills
        assert "healing" in c.skills
        if c.caste == "Soldier":
            assert c.equipped_item == "spear"
        elif c.caste == "Priest":
            assert c.equipped_item == "herb_poultice"


def test_basket_harvest_and_larder_deposit():
    cfg = Config(seed=42, shelter_enabled=True, house_claim_enabled=True, diet_strictness=0.0)
    sim = Simulation(cfg)
    c = Creature(
        shape="polygon",
        sides=4,
        x=20.0,
        y=20.0,
        energy=80.0,
        equipped_item="basket",
        food_basket=0,
        clan_id=1,
        personality="greedy",
    )
    sim._init_creature_evolution(c)
    c.equipped_item = "basket"
    c.food_basket = 0
    sim.world.add(c)

    food = Food(x=20.0, y=20.0, growth=1.0, variant="berry")
    sim.world.add(food)
    sim.world.rebuild_index()

    # Step simulation to eat/harvest
    houses = [h for h in sim.world.entities.values() if isinstance(h, House)]
    sim._update_creature(c, houses)

    # High energy creature stores food in basket
    assert c.food_basket == 1
    assert c.skills["farming"] >= 0.8
    assert c.emote == "craft"


def test_priest_heals_clanmates():
    cfg = Config(seed=42)
    sim = Simulation(cfg)

    priest = Creature(
        shape="polygon",
        sides=24,
        caste="Priest",
        x=10.0,
        y=10.0,
        clan_id=1,
    )
    sim._init_creature_evolution(priest)
    priest.caste = "Priest"
    priest.equipped_item = "herb_poultice"
    sim.world.add(priest)

    patient = Creature(
        shape="polygon",
        sides=4,
        caste="Artisan",
        x=11.0,
        y=10.0,
        clan_id=1,
        health=40.0,
        infected=True,
    )
    sim._init_creature_evolution(patient)
    patient.health = 40.0
    patient.infected = True
    sim.world.add(patient)
    sim.world.rebuild_index()

    houses = []
    # Trigger tick where priest acts
    sim.tick = (8 - (priest.id % 8)) % 8
    sim._update_creature(priest, houses)

    # §AT-4 H-1: base round is 15 HP, scaling with the priest's healing skill
    assert patient.health >= 55.0
    assert not patient.infected
    assert priest.skills["healing"] >= 1.5
    assert priest.emote == "heal"
    assert patient.emote == "cheer"


def test_skill_milestone_and_title_unlock():
    cfg = Config(seed=42)
    sim = Simulation(cfg)

    c = Creature(shape="polygon", sides=3, caste="Soldier", x=5.0, y=5.0)
    sim._init_creature_evolution(c)
    assert c.title is None

    # Give combat XP
    c.skills["combat"] = 15.0
    sim._update_creature_skills_and_titles(c)
    assert c.title == "the Slayer"

    # Master level
    c.skills["combat"] = 35.0
    sim._update_creature_skills_and_titles(c)
    assert c.title == "the Fearless Champion"
    assert c.emote == "cheer"


def test_infant_metabolic_energy_decay():
    cfg = Config(seed=42, shelter_enabled=False)
    sim = Simulation(cfg)

    # Infant creature
    infant = Creature(shape="polygon", sides=4, x=10.0, y=10.0, energy=80.0, age=10, lifespan=1000, generation=1)
    assert infant.stage == "infant"

    # Adult creature
    adult = Creature(shape="polygon", sides=4, x=30.0, y=30.0, energy=80.0, age=500, lifespan=1000, generation=1)
    assert adult.stage == "adult"

    sim._update_creature(infant, [])
    sim._update_creature(adult, [])

    infant_loss = 80.0 - infant.energy
    adult_loss = 80.0 - adult.energy

    # Infant decay is ~45% of adult decay
    assert infant_loss < adult_loss
    assert pytest.approx(infant_loss / adult_loss, 0.05) == 0.45


def test_combat_energy_drain():
    cfg = Config(seed=42, attack_radius=5.0, attack_damage=10.0, war_enabled=True)
    sim = Simulation(cfg)

    # Create 2 creatures from enemy clans
    c1 = Creature(shape="polygon", sides=3, caste="Soldier", x=10.0, y=10.0, clan_id=1, energy=80.0, health=100.0)
    c2 = Creature(shape="polygon", sides=3, caste="Soldier", x=10.5, y=10.0, clan_id=2, energy=80.0, health=100.0)
    sim.world.add(c1)
    sim.world.add(c2)
    sim.world.rebuild_index()

    # Mark clans at war (rivalry threshold is -75)
    sim.relations[(1, 2)] = -80

    sim._update_war()

    # Combatants expend energy
    winner = c2 if c1.id < c2.id else c1
    loser = c1 if c1.id < c2.id else c2
    assert winner.energy < 80.0
    assert loser.energy < 80.0


def test_creature_carries_and_consumes_food_reserve():
    cfg = Config(seed=42, shelter_enabled=False)
    sim = Simulation(cfg)

    # Creature far from any food with low energy and 2 food in basket
    c = Creature(shape="polygon", sides=4, x=10.0, y=10.0, energy=30.0, equipped_item="basket", food_basket=2)
    sim.world.add(c)
    sim.world.rebuild_index()

    # Step creature update
    sim._update_creature(c, [])

    # Autonomously consumed 1 food from reserve, replenished energy
    assert c.food_basket == 1
    assert c.energy > 30.0
    assert c.emote == "craft"


def test_heritable_irregularity_and_drift():
    cfg = Config(seed=42, birth_rate=1.0, mutation_rate=0.0, mutation_heritability=0.75, sex_ratio=1.0, adult_age=0.0)
    sim = Simulation(cfg)
    sim.world.entities.clear()
    father = sim.world.add(Creature(shape="polygon", sides=4, x=25.0, y=25.0, energy=80.0, irregularity=0.60, age=100, lifespan=1000))
    mother = sim.world.add(Creature(shape="line", sides=2, x=25.5, y=25.0, energy=80.0, irregularity=0.0, age=100, lifespan=1000))
    sim.step()

    children = [c for c in sim.world.creatures() if c.generation == 1]
    assert len(children) == 1
    child = children[0]
    # Heritable: parent 0.60 * 0.75 = 0.45 (+- drift)
    assert 0.30 <= child.irregularity <= 0.60


def test_daughter_inherits_irregularity():
    cfg = Config(seed=42, birth_rate=1.0, mutation_rate=0.0, mutation_heritability=0.80, sex_ratio=0.0, adult_age=0.0)
    sim = Simulation(cfg)
    sim.world.entities.clear()
    father = sim.world.add(Creature(shape="polygon", sides=4, x=25.0, y=25.0, energy=80.0, irregularity=0.0, age=100, lifespan=1000))
    mother = sim.world.add(Creature(shape="line", sides=2, x=25.5, y=25.0, energy=80.0, irregularity=0.50, age=100, lifespan=1000))
    sim.step()

    children = [c for c in sim.world.creatures() if c.generation == 1]
    assert len(children) == 1
    daughter = children[0]
    assert daughter.shape == "line"
    assert 0.25 <= daughter.irregularity <= 0.55


def test_soa_preserves_genomes_and_morph_on_population_change():
    from app.agent_soa import AgentSoA, HAS_NUMPY
    cfg = Config(seed=42, width=100.0, height=100.0)
    sim = Simulation(cfg)
    sim.world.entities.clear()

    c1 = Creature(shape="polygon", sides=4, x=10.0, y=10.0, energy=80.0)
    c2 = Creature(shape="line", sides=2, x=12.0, y=10.0, energy=80.0)
    sim.world.add(c1)
    sim.world.add(c2)
    sim._cached_creatures = [c1, c2]

    # Force SoA initialization
    sim._soa = AgentSoA(capacity=20)
    sim._soa.add_agent(c1.id, c1.x, c1.y, morph_radii=[1.5, 0.8, 1.2, 0.9] + [1.0]*20)
    sim._soa.add_agent(c2.id, c2.x, c2.y)
    sim._soa_id_map = {c1.id: 0, c2.id: 1}

    # Set distinct genome values
    if HAS_NUMPY:
        sim._soa.genomes[0, :5] = [1.1, 2.2, 3.3, 4.4, 5.5]
        sim._soa.genomes[1, :5] = [-1.1, -2.2, -3.3, -4.4, -5.5]
    else:
        for i, v in enumerate([1.1, 2.2, 3.3, 4.4, 5.5]):
            sim._soa.genomes[0][i] = v
            sim._soa.genomes[1][i] = -v

    # Add child born to world
    c3 = Creature(shape="polygon", sides=5, x=11.0, y=10.0, mother_id=c2.id, father_id=c1.id, generation=1)
    sim.world.add(c3)

    # Step simulation to trigger SoA sync
    sim.step()

    assert sim._soa.N == 3
    idx1 = sim._soa_id_map[c1.id]
    if HAS_NUMPY:
        assert list(sim._soa.genomes[idx1, :5]) == pytest.approx([1.1, 2.2, 3.3, 4.4, 5.5])
        assert sim._soa.morph_radii[idx1, 0] == pytest.approx(1.5)
    else:
        assert sim._soa.genomes[idx1][:5] == pytest.approx([1.1, 2.2, 3.3, 4.4, 5.5])
        assert sim._soa.morph_radii[idx1][0] == pytest.approx(1.5)


def test_multi_generation_mutation_frequency():
    from app.analytics import attach_to_sim
    cfg = Config(
        seed=123,
        width=100.0,
        height=100.0,
        birth_rate=0.2,
        mutation_rate=0.15,
        mutation_heritability=0.75,
        trait_mutation_rate=0.08,
        sex_ratio=0.5,
        adult_age=5.0,
        reproduction_cooldown=5,
        carrying_capacity=50,
        max_population=80,
    )
    sim = Simulation(cfg)
    sim.world.entities.clear()

    # Seed initial population of 10 creatures
    for i in range(5):
        sim.world.add(Creature(shape="polygon", sides=4, x=20.0 + i * 2, y=20.0, energy=90.0, age=10, lifespan=5000))
        sim.world.add(Creature(shape="line", sides=2, x=20.0 + i * 2, y=21.0, energy=90.0, age=10, lifespan=5000))

    # Add food
    for i in range(20):
        sim.world.add(Food(x=20.0 + (i % 5) * 4, y=20.0 + (i // 5) * 4, growth=1.0))

    eng = attach_to_sim(sim)

    # Run for 250 ticks to ensure 2nd generation is reached reliably
    for _ in range(250):
        sim.step()
        eng.on_tick(sim)

    summary = eng.summary(sim)
    gen_data = summary["generational"]
    # With heritable mutations and active breeding, mutation frequency should be well above 1%
    assert gen_data["max_generation"] >= 2
    assert gen_data["mutation_freq"] > 0.05


def test_polar_morph_caste_template_defaults():
    from app.agent_soa import AgentSoA
    soa = AgentSoA(capacity=10)

    # Soldier
    idx_soldier = soa.add_agent(1, 10.0, 10.0, caste="Soldier", sides=3)
    assert soa.morph_k[idx_soldier] == 3
    assert soa.morph_radii[idx_soldier, 0] == pytest.approx(1.5)

    # Woman
    idx_woman = soa.add_agent(2, 12.0, 10.0, caste="Woman", sides=2)
    assert soa.morph_k[idx_woman] == 3
    assert soa.morph_radii[idx_woman, 0] == pytest.approx(1.8)

    # Gentleman
    idx_gent = soa.add_agent(3, 14.0, 10.0, caste="Gentleman", sides=4)
    assert soa.morph_k[idx_gent] == 4
    assert soa.morph_radii[idx_gent, 0] == pytest.approx(1.0)


def test_child_morphology_respects_caste_template():
    import random
    from app.evolution_manager import child_morphology_two_parent, get_template_for_caste

    rng = random.Random(42)
    # Parents are both K=4 squares
    mo_r, mo_phi, mo_k = [1.0] * 4, [0.0, 1.57, 3.14, 4.71], 4
    fa_r, fa_phi, fa_k = [1.0] * 4, [0.0, 1.57, 3.14, 4.71], 4

    # Child is a Soldier (caste template K=3, apex 1.5)
    tr, tphi, tk = get_template_for_caste("Soldier")
    assert tk == 3

    cr, cphi, ck = child_morphology_two_parent(
        mo_r, mo_phi, mo_k, fa_r, fa_phi, fa_k,
        tr, tphi, tk, lam=0.0, config=None, rng=rng,
    )
    # Must not be clamped to 4! Must receive Soldier K=3
    assert ck == 3


def test_healing_legacy_square_morphs():
    from app.simulation.core import Simulation
    from app.config import Config
    from app.entities import Creature
    from app.agent_soa import AgentSoA

    cfg = Config(seed=42)
    sim = Simulation(cfg)
    sim.world.entities.clear()

    # Create soldier with legacy corrupted k=4 square
    soldier = Creature(shape="polygon", sides=3, caste="Soldier", x=10.0, y=10.0)
    sim.world.add(soldier)
    sim._cached_creatures = [soldier]
    sim._soa = AgentSoA(capacity=10)
    sim._soa.add_agent(soldier.id, 10.0, 10.0, morph_k=4, morph_radii=[1.0]*4)
    sim._soa_id_map = {soldier.id: 0}

    assert sim._soa.morph_k[0] == 4

    # Step simulation: healing pass runs
    sim._sync_soa_incremental()

    assert sim._soa.morph_k[0] == 3
    assert sim._soa.morph_radii[0, 0] == pytest.approx(1.5)




