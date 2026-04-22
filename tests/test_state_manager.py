"""
test_state_manager.py
Run: pytest tests/test_state_manager.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.state_manager import (
    apply_world_change,
    campaign_exists,
    list_campaigns,
    load_state,
    new_state,
    save_state,
)

TEST_ID = "test_phase1_001"


class TestStateManager:
    def setup_method(self):
        # Clean up before each test
        import shutil

        from state.state_manager import CAMPAIGNS_DIR
        test_dir = CAMPAIGNS_DIR / TEST_ID
        if test_dir.exists():
            shutil.rmtree(test_dir)

    def test_new_state(self):
        state = new_state(TEST_ID, "Test Campaign", "fantasy")
        assert state["campaign"]["id"] == TEST_ID
        assert state["campaign"]["name"] == "Test Campaign"
        assert state["campaign"]["setting"] == "fantasy"
        assert not state["combat"]["active"]
        assert state["npcs"] == {}

    def test_save_and_load(self):
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        loaded = load_state(TEST_ID)
        assert loaded is not None
        assert loaded["campaign"]["id"] == TEST_ID
        assert loaded["campaign"]["name"] == "Test"

    def test_load_nonexistent(self):
        result = load_state("nonexistent_id_xyz")
        assert result is None

    def test_campaign_exists(self):
        assert not campaign_exists(TEST_ID)
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        assert campaign_exists(TEST_ID)

    def test_apply_world_change(self):
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        apply_world_change(TEST_ID, "world.main_threat", "Dragon attack")
        updated = load_state(TEST_ID)
        assert updated["world"]["main_threat"] == "Dragon attack"

    def test_list_campaigns(self):
        campaigns = list_campaigns()
        assert isinstance(campaigns, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
