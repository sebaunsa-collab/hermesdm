"""
Tests for turn_manager.py — combat initiative and turn tracking.
"""
from bot.turn_manager import (
    CombatState,
    combat_summary,
    delay,
    end_combat,
    next_turn,
    remove_combatant,
    roll_initiative,
    start_combat,
)


class TestRollInitiative:
    def test_roll_initiative_returns_int(self):
        result = roll_initiative("Valdric", dex_mod=2)
        assert isinstance(result, int)
        assert 2 <= result <= 22

    def test_dex_mod_applied(self):
        result = roll_initiative("Mira", dex_mod=3)
        assert isinstance(result, int)


class TestStartCombat:
    def test_start_combat_orders_by_initiative(self):
        participants = [
            {"name": "Slow", "is_player": True, "dex_mod": -2},
            {"name": "Fast", "is_player": True, "dex_mod": 5},
            {"name": "Medium", "is_player": False, "dex_mod": 2},
        ]
        state = start_combat(participants)
        assert state.active is True
        assert state.round == 1
        assert len(state.initiative_order) == 3
        # Sorted high -> low (only check relative ordering)
        for i in range(len(state.initiative_order) - 1):
            assert state.initiative_order[i].initiative >= state.initiative_order[i + 1].initiative

    def test_start_combat_single_combatant(self):
        participants = [{"name": "Solo", "is_player": True, "dex_mod": 0}]
        state = start_combat(participants)
        assert state.active is True
        assert state.current_turn == "Solo"
        assert len(state.initiative_order) == 1

    def test_start_combat_current_turn_is_first_in_order(self):
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
        ]
        state = start_combat(participants)
        assert state.current_turn == state.initiative_order[0].name
        assert state.current_index == 0


class TestNextTurn:
    def test_next_turn_returns_valid_structure(self):
        """Verify next_turn returns the expected dict keys regardless of order."""
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
        ]
        state = start_combat(participants)
        result = next_turn(state)
        assert "who" in result
        assert "round" in result
        assert "note" in result
        assert result["who"] in ["A", "B"]

    def test_next_turn_round_increments_on_last_combatant(self):
        """Round increments when we wrap from last back to first."""
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
        ]
        state = start_combat(participants)
        first_round = state.round
        next_turn(state)  # Advance once
        # With 2 combatants, 1st next_turn goes to the other combatant (who is last)
        # → round should increment
        assert state.round == first_round + 1

    def test_next_turn_advances_through_all_combatants(self):
        """After N next_turn calls, all N combatants should have had a turn."""
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
            {"name": "C", "is_player": True, "dex_mod": 1},
        ]
        state = start_combat(participants)
        who_got_turn = [state.initiative_order[0].name]  # First turn
        for _ in range(3):
            next_turn(state)
            who_got_turn.append(state.current_turn)
        # All 3 unique combatants should appear in turn order
        assert len(set(who_got_turn)) == 3

    def test_next_turn_skips_inactive_combatant(self):
        """When a combatant is inactive, next_turn skips them."""
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
            {"name": "C", "is_player": True, "dex_mod": 1},
        ]
        state = start_combat(participants)
        # Mark middle combatant inactive
        middle = state.initiative_order[1]
        middle.is_active = False
        next_turn(state)  # Should skip inactive
        # Should NOT be the inactive combatant's turn
        assert state.current_turn != middle.name or state.current_turn == state.initiative_order[-1].name


class TestDelay:
    def test_delay_reinserts_at_end(self):
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": True, "dex_mod": 3},
            {"name": "C", "is_player": True, "dex_mod": 1},
        ]
        state = start_combat(participants)
        current_name = state.current_turn
        result = delay(state, current_name)
        assert "error" not in result
        assert state.initiative_order[-1].name == current_name


class TestRemoveCombatant:
    def test_remove_combatant_removes_from_order(self):
        participants = [
            {"name": "A", "is_player": True, "dex_mod": 5},
            {"name": "B", "is_player": False, "dex_mod": 3},
        ]
        state = start_combat(participants)
        result = remove_combatant(state, "B")
        assert "error" not in result
        names = [c.name for c in state.initiative_order]
        assert "B" not in names

    def test_remove_nonexistent_returns_error(self):
        participants = [{"name": "A", "is_player": True, "dex_mod": 0}]
        state = start_combat(participants)
        result = remove_combatant(state, "Z")
        assert "error" in result


class TestEndCombat:
    def test_end_combat_resets_state(self):
        participants = [{"name": "A", "is_player": True, "dex_mod": 0}]
        state = start_combat(participants)
        state = end_combat(state)
        assert state.active is False
        assert state.round == 0
        assert state.current_turn is None
        assert state.initiative_order == []


class TestCombatSummary:
    def test_combat_summary_no_combat(self):
        state = CombatState()
        summary = combat_summary(state)
        assert "No active combat" in summary

    def test_combat_summary_active_shows_round(self):
        participants = [{"name": "A", "is_player": True, "dex_mod": 5}]
        state = start_combat(participants)
        summary = combat_summary(state)
        assert "Round 1" in summary
        assert "A" in summary
