"""
Tests for world_builder.py — campaign world generation.
"""
from dm.world_builder import NPC_TEMPLATES, build_world, create_campaign, generate_npcs
from state.templates import SETTINGS as TEMPLATES


class TestGenerateNpcs:
    def test_generate_npcs_returns_dict(self):
        npcs = generate_npcs(count=3)
        assert isinstance(npcs, dict)
        assert len(npcs) == 3

    def test_generate_npcs_keys_are_valid_ids(self):
        npcs = generate_npcs(count=3)
        for npc_id in npcs:
            assert " " not in npc_id  # spaces replaced with underscores

    def test_generate_npcs_has_required_fields(self):
        npcs = generate_npcs(count=2)
        required = ["name", "role", "status", "location", "disposition",
                    "race", "disposition_value", "relationship_to_party",
                    "memory", "goals", "mood", "appearance", "secret"]
        for npc_id, npc in npcs.items():
            for field in required:
                assert field in npc, f"{npc_id} missing {field}"
            assert npc["status"] == "ALIVE"

    def test_generate_npcs_count_respects_max(self):
        all_npcs = generate_npcs(count=5)
        assert len(all_npcs) == 5
        few_npcs = generate_npcs(count=2)
        assert len(few_npcs) == 2


class TestBuildWorld:
    def test_build_world_fantasy(self):
        state = build_world("fantasy")
        assert state["campaign"]["setting"] == "fantasy"
        assert state["campaign"]["name"] == TEMPLATES["fantasy"]["name"]
        assert state["campaign"]["current_location"] == TEMPLATES["fantasy"]["starting_location"]
        assert len(state["npcs"]) == 3
        assert "world" in state
        assert "main_threat" in state["world"]
        assert len(state["history"]) == 1

    def test_build_world_scifi(self):
        state = build_world("scifi")
        assert state["campaign"]["setting"] == "scifi"
        assert state["campaign"]["name"] == TEMPLATES["scifi"]["name"]

    def test_build_world_horror(self):
        state = build_world("horror")
        assert state["campaign"]["setting"] == "horror"
        assert state["campaign"]["name"] == TEMPLATES["horror"]["name"]

    def test_build_world_unknown_falls_back_to_fantasy(self):
        state = build_world("unknown_setting")
        assert state["campaign"]["setting"] == "fantasy"

    def test_build_world_creates_location(self):
        state = build_world("fantasy")
        loc = state["campaign"]["current_location"]
        assert loc in state["world"]["locations"]
        assert "description" in state["world"]["locations"][loc]
        assert state["world"]["locations"][loc]["visited"] is True

    def test_build_world_npcs_linked_to_location(self):
        """NPCs in the starting location are linked via world['locations'][loc]['npcs']."""
        state = build_world("fantasy")
        loc = state["campaign"]["current_location"]
        location_npcs = state["world"]["locations"].get(loc, {}).get("npcs", [])
        assert len(location_npcs) >= 1, f"No NPCs linked to {loc}"

    def test_build_world_has_npc_memory(self):
        """NPCs from template have a memory field."""
        state = build_world("fantasy")
        for npc_id, npc in state["npcs"].items():
            assert "memory" in npc, f"{npc_id} missing memory field"

    def test_build_world_has_timeline(self):
        """World state includes timeline for continuity."""
        state = build_world("fantasy")
        assert "timeline" in state.get("world", {})

    def test_build_world_has_settings(self):
        """Campaign settings are initialized in the state."""
        state = build_world("fantasy")
        assert "settings" in state


class TestCreateCampaign:
    def test_create_campaign_returns_id_and_state(self):
        result = create_campaign("fantasy")
        assert "campaign_id" in result
        assert "state" in result
        assert result["campaign_id"].startswith("campaign_")

    def test_create_campaign_saves_state(self):
        from state.state_manager import load_state
        result = create_campaign("fantasy")
        cid = result["campaign_id"]
        loaded = load_state(cid)
        assert loaded is not None
        assert loaded["campaign"]["id"] == cid

    def test_create_campaign_generates_uuid(self):
        r1 = create_campaign("fantasy")
        r2 = create_campaign("fantasy")
        assert r1["campaign_id"] != r2["campaign_id"]


class TestSettings:
    def test_new_templates_have_required_fields(self):
        """New templates have required fields."""
        required = ["name", "description", "starting_location", "npcs", "quests"]
        for setting_name, setting in TEMPLATES.items():
            for field in required:
                assert field in setting, f"{setting_name} missing {field}"

    def test_npc_templates_have_required_fields(self):
        required = ["name", "role", "disposition", "location",
                    "race", "secret", "goals"]
        for tmpl in NPC_TEMPLATES:
            for field in required:
                assert field in tmpl, f"{tmpl['name']} missing {field}"
