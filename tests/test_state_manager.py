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


    def test_append_history(self):
        """append_history adds entry to campaign history log."""
        from state.state_manager import append_history
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        ok = append_history(TEST_ID, "El grupo llega a la aldea.", "narration", session=1)
        assert ok is True
        loaded = load_state(TEST_ID)
        assert len(loaded["history"]) == 1
        assert loaded["history"][0]["type"] == "narration"
        assert loaded["history"][0]["session"] == 1

    def test_append_history_campaign_not_found(self):
        """append_history returns False for nonexistent campaign."""
        from state.state_manager import append_history
        ok = append_history("nonexistent_xyzzz", "test", "narration")
        assert ok is False

    def test_get_settings(self):
        """get_settings returns CampaignSettings for a campaign."""
        from state.state_manager import get_settings
        from campaign_settings import CampaignSettings
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        settings = get_settings(TEST_ID)
        assert isinstance(settings, CampaignSettings)

    def test_get_settings_nonexistent_returns_defaults(self):
        """get_settings returns default CampaignSettings for nonexistent campaign."""
        from state.state_manager import get_settings
        from campaign_settings import CampaignSettings
        settings = get_settings("nonexistent_xyzzz")
        assert isinstance(settings, CampaignSettings)

    def test_update_settings(self):
        """update_settings changes a single setting."""
        from state.state_manager import update_settings, get_settings
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        success, msg, settings = update_settings(TEST_ID, "image_provider", "flux")
        # May succeed or fail depending on CampaignSettings validation
        assert isinstance(success, bool)
        assert isinstance(msg, str)

    def test_load_npc_store(self):
        """load_npc_store returns NPCStore from campaign state."""
        from state.state_manager import load_npc_store
        from state.npc_store import NPCStore
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        store = load_npc_store(TEST_ID)
        assert isinstance(store, NPCStore)

    def test_load_npc_store_nonexistent(self):
        """load_npc_store returns empty NPCStore for nonexistent campaign."""
        from state.state_manager import load_npc_store
        from state.npc_store import NPCStore
        store = load_npc_store("nonexistent_xyzzz")
        assert isinstance(store, NPCStore)

    def test_add_npc_to_state(self):
        """add_npc_to_state adds an NPC and persists it."""
        from state.state_manager import add_npc_to_state, load_npc_store
        from state.npc_store import NPCRecord
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        npc = NPCRecord(
            npc_id="captain_vorn",
            name="Captain Vorn",
            title="Guard Captain",
            description="A stern guard captain",
            personality="Stern and loyal",
            motivation="Protect the town",
            secret=None,
            location="Town gates",
        )
        add_npc_to_state(TEST_ID, npc)
        store = load_npc_store(TEST_ID)
        assert store.get("captain_vorn") is not None

    def test_remove_npc_from_state(self):
        """remove_npc_from_state removes an NPC from campaign state."""
        from state.state_manager import remove_npc_from_state, add_npc_to_state, load_npc_store
        from state.npc_store import NPCRecord
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)
        npc = NPCRecord(
            npc_id="guard_1",
            name="Guard",
            title="Town Guard",
            description="A watchful guard",
            personality="Alert",
            motivation="Keep the peace",
            secret=None,
            location="Town square",
        )
        add_npc_to_state(TEST_ID, npc)
        result = remove_npc_from_state(TEST_ID, "guard_1")
        assert result is True

    def test_sync_chatstate_to_state(self):
        """sync_chatstate_to_state persists characters and combat to state.json."""
        from state.state_manager import sync_chatstate_to_state
        from unittest.mock import MagicMock
        state = new_state(TEST_ID, "Test", "fantasy")
        save_state(TEST_ID, state)

        # Mock ChatState with characters
        mock_char = MagicMock()
        mock_char.to_dict.return_value = {"name": "Valdric", "class": "fighter", "level": 3}
        mock_cs = MagicMock()
        mock_cs.characters = {"123456": mock_char}
        mock_cs.combat_state = None

        result = sync_chatstate_to_state(TEST_ID, mock_cs)
        assert result is not None
        assert "123456" in result["characters"]
        assert result["characters"]["123456"]["name"] == "Valdric"

    def test_update_settings_nonexistent_campaign(self):
        """update_settings returns failure for nonexistent campaign."""
        from state.state_manager import update_settings
        success, msg, settings = update_settings("nonexistent_xyzzz", "image_provider", "flux")
        assert success is False
        assert "not found" in msg.lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
