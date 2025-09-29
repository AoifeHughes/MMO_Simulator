import pytest
from src.ai.personality import Personality
from src.ai.character_class import CharacterClass, CHARACTER_CLASSES, get_character_class
from src.ai.goal import ExploreGoal, GatherResourceGoal, AttackEnemyGoal, RestGoal
from src.ai.decision_maker import DecisionMaker
from src.entities.agent import Agent, create_random_agent, create_agent_with_archetype
from src.entities.stats import Stats
from src.core.world import World


class TestPersonality:
    def test_personality_creation(self):
        personality = Personality(
            curiosity=0.8,
            bravery=0.6,
            sociability=0.4,
            greed=0.3,
            patience=0.7
        )

        assert personality.curiosity == 0.8
        assert personality.bravery == 0.6
        assert personality.sociability == 0.4

    def test_personality_bounds(self):
        # Test that values are clamped to 0-1
        personality = Personality(
            curiosity=1.5,  # Should be clamped to 1.0
            bravery=-0.5,   # Should be clamped to 0.0
            greed=0.5
        )

        assert personality.curiosity == 1.0
        assert personality.bravery == 0.0
        assert personality.greed == 0.5

    def test_random_personality(self):
        personality = Personality.randomize(seed=42)

        # Values should be between 0 and 1
        assert 0.0 <= personality.curiosity <= 1.0
        assert 0.0 <= personality.bravery <= 1.0
        assert 0.0 <= personality.sociability <= 1.0

        # Should be deterministic with same seed
        personality2 = Personality.randomize(seed=42)
        assert personality.curiosity == personality2.curiosity

    def test_personality_archetypes(self):
        explorer = Personality.create_archetype("explorer")
        warrior = Personality.create_archetype("warrior")
        trader = Personality.create_archetype("trader")

        # Explorers should be more curious
        assert explorer.curiosity > 0.7
        assert explorer.curiosity > warrior.curiosity

        # Warriors should be more brave and aggressive
        assert warrior.bravery > 0.8
        assert warrior.aggression > 0.6

        # Traders should be more sociable
        assert trader.sociability > 0.8
        assert trader.greed > 0.6

    def test_dominant_traits(self):
        personality = Personality(
            curiosity=0.9,
            bravery=0.4,
            greed=0.7,
            patience=0.2
        )

        dominant = personality.get_dominant_traits(threshold=0.6)
        assert "curious" in dominant
        assert "greedy" in dominant
        assert "brave" not in dominant

    def test_personality_similarity(self):
        personality1 = Personality(
            curiosity=0.8, bravery=0.6, sociability=0.7, greed=0.3,
            patience=0.8, aggression=0.2, industriousness=0.9, caution=0.3
        )
        personality2 = Personality(
            curiosity=0.8, bravery=0.6, sociability=0.7, greed=0.3,
            patience=0.8, aggression=0.2, industriousness=0.9, caution=0.3
        )
        personality3 = Personality(
            curiosity=0.1, bravery=0.1, sociability=0.1, greed=0.9,
            patience=0.1, aggression=0.9, industriousness=0.1, caution=0.9
        )

        # Identical personalities should have high similarity
        assert personality1.similarity_to(personality2) > 0.95

        # Different personalities should have low similarity
        assert personality1.similarity_to(personality3) < 0.5

    def test_action_modifiers(self):
        explorer = Personality.create_archetype("explorer")
        warrior = Personality.create_archetype("warrior")

        # Explorer should have higher explore modifier
        assert explorer.get_action_modifier("explore") > warrior.get_action_modifier("explore")

        # Warrior should have higher combat modifier
        assert warrior.get_action_modifier("combat") > explorer.get_action_modifier("combat")

    def test_serialization(self):
        personality = Personality(curiosity=0.8, bravery=0.6)
        data = personality.to_dict()
        restored = Personality.from_dict(data)

        assert restored.curiosity == personality.curiosity
        assert restored.bravery == personality.bravery


class TestCharacterClass:
    def test_warrior_creation(self):
        warrior = CharacterClass.create_warrior()

        assert warrior.name == "Warrior"
        assert "combat" in warrior.skill_affinities
        assert warrior.skill_affinities["combat"] > 1.0
        assert "combat" in warrior.preferred_actions

    def test_skill_modifiers(self):
        warrior = CharacterClass.create_warrior()
        mage = CharacterClass.create_mage()

        # Warrior should get bonus to combat skills
        assert warrior.get_skill_modifier("combat") > 1.0

        # Mage should get bonus to magic skills
        assert mage.get_skill_modifier("magic") > 1.0
        assert mage.get_skill_modifier("magic") > warrior.get_skill_modifier("magic")

    def test_action_preferences(self):
        hunter = CharacterClass.create_hunter()
        trader = CharacterClass.create_trader()

        # Hunter should prefer hunting actions
        assert hunter.get_action_preference("hunt") > 1.0

        # Trader should prefer trading actions
        assert trader.get_action_preference("trade") > 1.0

    def test_starting_equipment(self):
        warrior = CharacterClass.create_warrior()
        equipment = warrior.get_starting_equipment()

        assert len(equipment) > 0

        # Should have some kind of weapon
        weapon_found = any(item.item_type == "weapon" for item in equipment)
        assert weapon_found

    def test_character_class_registry(self):
        # Test that all classes are accessible
        for class_name in CHARACTER_CLASSES:
            char_class = get_character_class(class_name)
            assert char_class is not None
            assert char_class.name is not None

    def test_stat_bonuses(self):
        warrior = CharacterClass.create_warrior()
        mage = CharacterClass.create_mage()

        # Warrior should have health bonus
        assert warrior.get_stat_bonus("max_health") > 0

        # Mage should have magic bonus
        assert mage.get_stat_bonus("max_magic") > 0

    def test_serialization(self):
        warrior = CharacterClass.create_warrior()
        data = warrior.to_dict()
        restored = CharacterClass.from_dict(data)

        assert restored.name == warrior.name
        assert restored.skill_affinities == warrior.skill_affinities


class TestGoals:
    def test_explore_goal(self):
        goal = ExploreGoal()

        assert goal.name == "Explore"
        assert goal.priority >= 1

        # Mock agent and world for testing
        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        world = World(10, 10, seed=42)

        assert goal.is_valid(agent, world)

    def test_gather_resource_goal(self):
        goal = GatherResourceGoal("wood", target_quantity=5)

        assert goal.resource_type == "wood"
        assert goal.target_quantity == 5

        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        world = World(10, 10, seed=42)

        # Goal should be valid if wood exists in world
        is_valid = goal.is_valid(agent, world)
        # Can't assert true/false due to random world generation

    def test_attack_enemy_goal(self):
        goal = AttackEnemyGoal(target_id=123)

        assert goal.target_id == 123

        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        world = World(10, 10, seed=42)

        # Should be invalid if target doesn't exist
        assert not goal.is_valid(agent, world)

    def test_rest_goal(self):
        goal = RestGoal()

        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        agent.stats = Stats(stamina=10, max_stamina=100, health=30, max_health=100)  # Low stamina and health
        world = World(10, 10, seed=42)

        # Should be valid when agent needs rest
        assert goal.is_valid(agent, world)

        # Should have high utility when tired and injured
        utility = goal.get_utility(agent, world)
        assert utility > 0.5


class TestDecisionMaker:
    def test_decision_maker_creation(self):
        dm = DecisionMaker()
        assert dm.goal_history == {}
        assert dm.decision_cooldown > 0

    def test_goal_evaluation(self):
        dm = DecisionMaker()

        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        agent.personality = Personality.create_archetype("explorer")
        world = World(10, 10, seed=42)

        explore_goal = ExploreGoal()
        rest_goal = RestGoal()

        goal_utilities = dm.evaluate_all_goals(agent, world, [explore_goal, rest_goal])

        assert len(goal_utilities) > 0

        # Should return tuples of (goal, utility)
        for goal, utility in goal_utilities:
            assert isinstance(utility, float)
            assert 0.0 <= utility <= 1.0

    def test_goal_selection(self):
        dm = DecisionMaker()

        from ..unit.test_entities import MockEntity
        agent = MockEntity((5, 5))
        agent.personality = Personality.create_archetype("explorer")
        world = World(10, 10, seed=42)
        world.current_tick = 10  # Set tick to bypass cooldown

        selected_goal = dm.select_goal(agent, world, [])

        assert selected_goal is not None


class TestAgent:
    def test_agent_creation(self):
        personality = Personality.create_archetype("warrior")
        char_class = CharacterClass.create_warrior()
        agent = Agent((5, 5), "Test Agent", personality, char_class)

        assert agent.name == "Test Agent"
        assert agent.position == (5, 5)
        assert agent.personality == personality
        assert agent.character_class == char_class

    def test_agent_class_bonuses(self):
        warrior_class = CharacterClass.create_warrior()
        agent = Agent((0, 0), "Warrior", character_class=warrior_class)

        # Should have applied warrior stat bonuses
        base_stats = Stats()
        assert agent.stats.max_health > base_stats.max_health

    def test_agent_starting_equipment(self):
        agent = Agent((0, 0), "Test Agent")

        # Should have some starting equipment
        assert len(agent.inventory.get_all_items()) > 0

    def test_agent_skills(self):
        agent = Agent((0, 0), "Test Agent")

        # Should start with empty skills
        assert agent.skills == {}

        # Should be able to gain skills
        agent.skills["combat"] = 5
        assert agent.get_skill_level("combat") == 5

    def test_agent_relationships(self):
        agent = Agent((0, 0), "Test Agent")

        # Should start with no relationships
        assert len(agent.relationships) == 0

        # Should be able to add relationships
        agent.add_relationship(123, 0.5)
        assert agent.get_relationship(123) == 0.5

        # Should clamp relationship values
        agent.add_relationship(123, 1.0)  # Should clamp to 1.0
        assert agent.get_relationship(123) == 1.0

    def test_agent_perception(self):
        world = World(10, 10, seed=42)
        agent = Agent((5, 5), "Test Agent")
        world.add_entity(agent)

        # Initially should know no entities
        assert len(agent.known_entities) == 0

        agent.perceive(world)

        # Should update perception (though might not see anything in empty world)

    def test_agent_update_cycle(self):
        world = World(10, 10, seed=42)
        agent = Agent((5, 5), "Test Agent")
        world.add_entity(agent)

        # Should start with no goals
        assert len(agent.current_goals) == 0

        # Update should work without errors
        agent.update(world)

        # Should have made some decision (might have added goals)

    def test_random_agent_creation(self):
        agent = create_random_agent((3, 3))

        assert agent.position == (3, 3)
        assert agent.personality is not None
        assert agent.character_class is not None
        assert agent.name is not None

    def test_archetype_agent_creation(self):
        explorer = create_agent_with_archetype((0, 0), "explorer")
        warrior = create_agent_with_archetype((1, 1), "warrior")

        # Explorer should have explorer personality
        assert explorer.personality.curiosity > 0.7

        # Warrior should have warrior personality
        assert warrior.personality.bravery > 0.7

    def test_agent_summary(self):
        agent = create_random_agent((2, 2), "Test Agent")
        summary = agent.get_agent_summary()

        assert "id" in summary
        assert "name" in summary
        assert "personality" in summary
        assert "character_class" in summary
        assert summary["position"] == (2, 2)

    def test_agent_memory_system(self):
        world = World(10, 10, seed=42)
        agent1 = Agent((5, 5), "Agent1")
        agent2 = Agent((6, 6), "Agent2")

        world.add_entity(agent1)
        world.add_entity(agent2)

        # Agent1 should perceive Agent2 when close
        agent1.perceive(world)

        if agent1.distance_to(agent2) <= agent1.vision_range:
            assert agent2.id in agent1.known_entities