"""Tests for SDD-004: Fix /setup generation echo bug.

Covers F1-F7 acceptance criteria.
"""

import pytest
from unittest import mock

from dm.world_builder import (
    _is_echo,
    _generate_procedural_npcs,
    _generate_themed_npcs,
    _generate_themed_classes,
    generate_setup_with_ai,
)


# ── F1: premise must NOT contain >60% word overlap with user's raw description ──

def test_is_echo_detects_copy_paste():
    """F7: validator detects copy-paste."""
    desc = "zombies y ninjas en un mundo de SAO"
    premise = "zombies y ninjas en un mundo de SAO con un rey demonio"
    assert _is_echo(desc, premise, threshold=0.60) is True


def test_is_echo_allows_original_content():
    """F7: validator allows original content referencing the theme."""
    desc = "zombies y ninjas en un mundo de SAO"
    premise = "En Aincrad, los cazadores de mazmorras enfrentan horrores digitales."
    assert _is_echo(desc, premise, threshold=0.60) is False


def test_is_echo_empty_description():
    """Edge case: empty description should not trigger echo."""
    assert _is_echo("", "anything") is False


# ── F6: Fallback path must NOT concatenate raw description into premise ──

def test_fallback_no_concatenation():
    """F6: fallback must not paste description into premise."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("SAO con demonios y zombies")
            premise = result["premise"]
            # Should NOT contain raw user words like "quiero", "historia", "con"
            assert "quiero" not in premise.lower()
            assert "SAO" not in premise.lower() or premise.count(" ") > 10
            # Should be original narrative, not concatenated input
            assert "Los personajes son aventureros comprometidos con una misión peligrosa:" not in premise


def test_fallback_generates_original_premise_from_nouns():
    """F6: fallback builds premise from extracted nouns, not raw text."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("SAO con demonios y zombies")
            premise = result["premise"]
            # Should contain narrative structure
            assert len(premise.split()) >= 15  # At least a few sentences
            assert "demonios" in premise.lower() or "zombies" in premise.lower() or "SAO" in premise


# ── F2: Location must NOT be generic ──

def test_fallback_location_not_generic_when_keywords_match():
    """F2: location must not be the hardcoded fallback when keywords match."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("aventura en un puerto pirata llamado Puerto Tormenta")
            assert result["lore"]["starting_location"] != "un lugar olvidado"


def test_fallback_location_uses_procedural_name_for_unmatched():
    """F2: when no keyword matches, uses procedural name from nouns."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("Xyloph la dimension oscura")
            loc = result["lore"]["starting_location"]
            assert loc != "un lugar olvidado"
            assert "las Tierras de" in loc or "Xyloph" in loc


# ── F3: Hook must reference threat and location ──

def test_fallback_hook_references_threat_and_location():
    """F3: hook references main_threat and starting_location."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("zombies y ninjas en un puerto pirata")
            hook = result["hook"]
            loc = result["lore"]["starting_location"]
            threat = result["lore"]["main_threat"]
            # Hook should mention location
            assert loc.split()[0] in hook or loc.split()[-1] in hook
            # Hook should reference threat concept
            assert "zombie" in hook.lower() or "fuerza" in hook.lower() or "amenaza" in hook.lower()


# ── F4: NPCs related to setting ──

def test_themed_npcs_match_demonio_keyword():
    """F4: demonio keyword returns demon-themed NPCs."""
    npcs = _generate_themed_npcs("fantasy", "quiero una historia con demonios")
    names = [n["name"] for n in npcs]
    assert any("Vex" in n or "Mordrake" in n or "Creyente" in n for n in names)


def test_themed_npcs_match_zombie_keyword():
    """F4: zombie keyword returns zombie-themed NPCs."""
    npcs = _generate_themed_npcs("fantasy", "quiero una historia con zombies")
    names = [n["name"] for n in npcs]
    assert any("Mordrake" in n or "Voss" in n or "Niña" in n for n in names)


def test_themed_npcs_match_ninja_keyword():
    """F4: ninja keyword returns ninja-themed NPCs."""
    npcs = _generate_themed_npcs("fantasy", "quiero una historia con ninjas")
    names = [n["name"] for n in npcs]
    assert any("Sombra" in n or "Kage" in n or "Shinobi" in n for n in names)


def test_themed_npcs_match_sao_keyword():
    """F4: SAO keyword returns VR-themed NPCs."""
    npcs = _generate_themed_npcs("fantasy", "quiero una historia de SAO")
    names = [n["name"] for n in npcs]
    assert any("Kirito" in n or "Asuna" in n or "Kayaba" in n for n in names)


def test_procedural_npcs_from_description():
    """F4: procedural NPCs use description keywords."""
    npcs = _generate_procedural_npcs("Xyloph la dimension oscura con ninjas", count=3)
    names = [n["name"] for n in npcs]
    # Should extract capitalized words or significant nouns
    assert len(npcs) > 0
    assert all(n["role"] for n in npcs)
    assert all(n["dialogue"] for n in npcs)


# ── F5: Tone detection ──

def test_fallback_detects_dark_tone():
    """F5: dark tone keywords detected."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("historia oscura y sombria")
            assert result["tone"] == "dark"


def test_fallback_detects_epic_tone():
    """F5: epic tone keywords detected."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("historia épica y heroica")
            assert result["tone"] == "epic"


def test_fallback_detects_comedic_tone():
    """F5: comedic tone keywords detected."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("historia comica y graciosa")
            assert result["tone"] == "comedic"


# ── Echo validator edge cases ──

def test_is_echo_partial_overlap_below_threshold():
    """F7: partial overlap below 60% is OK."""
    desc = "quiero una historia de piratas en el mar"
    premise = "En el Mar de la Bruma, los corsarios luchan por el dominio de las islas perdidas."
    assert _is_echo(desc, premise, threshold=0.60) is False


def test_is_echo_high_overlap_detected():
    """F7: high overlap above 60% triggers detection."""
    desc = "quiero una historia de piratas en el mar"
    premise = "quiero una historia de piratas en el mar donde los personajes son corsarios"
    assert _is_echo(desc, premise, threshold=0.60) is True


# ── Integration: full fallback flow ──

def test_full_fallback_flow_structure():
    """Integration: fallback produces complete, valid structure."""
    with mock.patch("os.getenv", return_value="fake_key"):
        with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
            MockProvider.side_effect = Exception("API down")
            result = generate_setup_with_ai("SAO con rey demonio, zombies y ninjas", tone="dark")

            assert "premise" in result
            assert "hook" in result
            assert "lore" in result
            assert "factions" in result["lore"]
            assert "main_threat" in result["lore"]
            assert "starting_location" in result["lore"]
            assert "starting_location_desc" in result["lore"]
            assert "npcs" in result["lore"]
            assert "classes" in result
            assert "starting_equipment" in result
            assert "story_arc" in result
            assert "tone" in result

            assert len(result["lore"]["npcs"]) > 0
            assert len(result["classes"]) > 0
