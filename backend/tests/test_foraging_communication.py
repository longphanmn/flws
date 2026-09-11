import math
import pytest

from app.config import Config
from app.entities import Creature, Food, House
from app.simulation import Simulation


def sim_cfg(**kw) -> Config:
    kw.setdefault("signal_speed", 0.0)
    kw.setdefault("anomaly_count", 0)
    kw.setdefault("relief_enabled", False)
    kw.setdefault("safeguard_enabled", False)
    defaults = dict(
        seed=42,
        width=100.0,
        height=100.0,
        num_triangles=0,
        num_squares=0,
        num_pentagons=0,
        num_hexagons=0,
        num_priests=0,
        num_women=0,
        food_count=0,
        num_houses=0,
        weather_enabled=False,
        birth_enabled=False,
        predation_enabled=False,
        war_enabled=False,
        disease_enabled=False,
        communication_enabled=True,
        knowledge_enabled=True,
        perceive_radius=30.0,
        food_giveup_ticks=40,
    )
    defaults.update(kw)
    return Config(**defaults)


def test_hungry_creature_emits_food_call():
    """A hungry creature discovering food emits a food call to its clan."""
    s = Simulation(sim_cfg(food_call_rate=1.0))
    c = s.world.add(Creature(x=50.0, y=50.0, energy=40.0, clan_id=1, age=500))
    s.clans[1] = {"color": [255, 0, 0], "name": "Clan 1"}
    food = s.world.add(Food(x=55.0, y=50.0, growth=1.0))

    s.step()

    # Verify a food signal was emitted
    food_signals = [sg for sg in s.signals if sg["kind"] == "food"]
    assert len(food_signals) >= 1
    assert food_signals[0]["sender"] == c.id
    assert food_signals[0]["clan_id"] == 1
    assert food_signals[0]["food_x"] == food.x
    assert food_signals[0]["food_y"] == food.y


def test_clan_member_hears_food_signal_and_learns_fact():
    """A clan member who hears a food signal saves the fact in c.facts['food'] and targets it when hungry."""
    s = Simulation(sim_cfg())
    c1 = s.world.add(Creature(x=30.0, y=30.0, energy=30.0, clan_id=1, age=500))
    s.clans[1] = {"color": [255, 0, 0], "name": "Clan 1"}

    # Simulate food signal received from clan-mate
    s.signals.append({
        "x": 35.0,
        "y": 30.0,
        "kind": "food",
        "sender": 999,
        "clan_id": 1,
        "born_tick": s.tick,
        "ttl": 15,
        "food_x": 45.0,
        "food_y": 30.0,
    })

    s.step()

    # Verify c1 stored the food fact in memory
    assert "food" in c1.facts
    assert c1.facts["food"]["x"] == 45.0
    assert c1.facts["food"]["y"] == 30.0


def test_eating_food_broadcasts_call_to_clan():
    """When a creature eats food, it sends a food signal to alert clan members."""
    s = Simulation(sim_cfg())
    c = s.world.add(Creature(x=50.0, y=50.0, energy=50.0, clan_id=2, age=500))
    s.clans[2] = {"color": [0, 255, 0], "name": "Clan 2"}
    food = s.world.add(Food(x=50.5, y=50.0, growth=1.0))  # within eat_radius

    s.step()

    assert c.meals >= 1
    food_signals = [sg for sg in s.signals if sg["kind"] == "food" and sg["sender"] == c.id]
    assert len(food_signals) >= 1
    assert food_signals[0]["clan_id"] == 2


def test_wall_collision_does_not_blacklist_food_for_unobstructed_clan_members():
    """If c1 bumps against a wall and gives up on food F, c2 on the open side does not get blacklisted."""
    s = Simulation(sim_cfg(food_giveup_ticks=50))
    house = House(x=50.0, y=50.0, size=10.0, door_width=2.0, door_side="south")
    s.world.add(house)

    # Food F is outside the house to the north
    food = s.world.add(Food(x=50.0, y=42.0, growth=1.0))

    # c1 is south of the north wall, attempting to reach north through the solid wall
    c1 = s.world.add(Creature(x=50.0, y=48.0, energy=40.0, clan_id=1, age=500))

    # c2 is outside the house right next to the food F (unobstructed)
    c2 = s.world.add(Creature(x=50.0, y=40.0, energy=40.0, clan_id=1, age=500))

    # Trigger give-up on c1 for food blocked by house
    s._give_up_on(c1, food, blocking_entity=house)

    # c1 gave up
    assert food.id in c1.give_ups

    # c2 has direct unobstructed access / is close to food, so it must NOT have given up
    assert food.id not in c2.give_ups


def test_hungry_creature_eats_nearby_food_during_dusk():
    """A hungry creature with food right next to it eats it even during dusk rather than retreating empty-handed."""
    s = Simulation(sim_cfg(sleep_enabled=True))
    house = House(x=30.0, y=30.0, size=8.0, door_width=3.0, door_side="west")
    s.world.add(house)

    # Food is right outside
    food = s.world.add(Food(x=42.0, y=30.0, growth=1.0))
    c = s.world.add(Creature(x=41.5, y=30.0, energy=45.0, status="hungry", age=500))

    # Set time of day to dusk
    s.time_of_day = 0.72  # DUSK_TOD is 0.70

    s.step()

    # Creature should have eaten the food rather than abandoning it
    assert c.meals >= 1
    assert food.id not in s.world.entities


def test_hungry_omnivore_does_not_skip_grass():
    """Diet strictness does not cause hungry omnivores to skip grass."""
    s = Simulation(sim_cfg(diet_strictness=0.9))
    c = s.world.add(Creature(x=20.0, y=20.0, energy=40.0, status="hungry", age=500, caste="Commoner"))
    assert not c.is_herbivore and not c.is_predator  # omnivore
    grass = s.world.add(Food(x=20.5, y=20.0, growth=1.0, variant="grass"))

    s.step()

    # Ate the grass despite strictness=0.9 because creature was hungry
    assert c.meals >= 1
    assert grass.id not in s.world.entities
