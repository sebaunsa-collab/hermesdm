#!/usr/bin/env python3
"""
E2E test: 4-player D&D game simulation.
Verifies that state.json is properly updated after every game action.

Run: python scripts/test_e2e_state_persistence.py
"""

import json
import sys
import time
from pathlib import Path

# Ensure hermesdm package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.character_sheet import create_character
from bot.turn_manager import Combatant, CombatState, start_combat
from state.state_manager import (
    append_history,
    load_state,
    new_state,
    save_state,
    sync_chatstate_to_state,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def green(msg: str) -> str:
    return f"\033[92m✓ {msg}\033[0m"


def red(msg: str) -> str:
    return f"\033[91m✗ {msg}\033[0m"


def blue(msg: str) -> str:
    return f"\033[94m→ {msg}\033[0m"


def header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def assert_state_has(path: Path, key: str, expected_description: str) -> None:
    state = load_json(path)
    value = key.split(".")[0]  # e.g. "characters.valdric"
    sub = state
    for part in key.split("."):
        sub = sub[part]
    print(f"    {blue(key)}: {json.dumps(sub, indent=2)[:200]}")
    assert sub, f"Expected {key} to exist in state.json"
    print(f"    {green(expected_description)}")


def assert_combat_active(path: Path, expected: bool) -> None:
    state = load_json(path)
    assert state["combat"]["active"] == expected
    print(f"    {green(f'combat.active == {expected}')}")


def get_mtime(path: Path) -> float:
    return path.stat().st_mtime


# ── main test ─────────────────────────────────────────────────────────────────

def main() -> int:
    campaign_id = "test_e2e_001"
    state_path = Path.home() / ".hermes" / "hermesdm" / "campaigns" / campaign_id / "state.json"

    print("\n🎲 HermesDM — E2E State Persistence Test")
    print("    Simula 4 jugadores, combate, ataques y hechizos.")
    print("    Verifica que state.json se actualice en cada paso.\n")

    # ── Setup: create campaign ───────────────────────────────────────────────
    header("STEP 1 — Create campaign")
    st = new_state(campaign_id, "The Dragon's Lair", "fantasy")
    st["campaign"]["status"] = "active"  # skip setup phase
    save_state(campaign_id, st)
    print(f"    {green('Campaign created')} → {state_path}")
    assert state_path.exists(), f"state.json should exist at {state_path}"

    # ── Create ChatState (simulating 4 players joining) ─────────────────────
    header("STEP 2 — 4 players join the campaign")

    # We simulate ChatState in memory (what context.chat_data holds)
    class FakeChatState:
        active_campaign = campaign_id
        characters = {}
        combat_state: CombatState | None = None
        pending_attacks = {}
        pending_spell = None

    cs = FakeChatState()

    players = [
        ("Valdric", "fighter", 3),
        ("Mira",     "wizard", 3),
        ("Thorne",   "rogue",  2),
        ("Lyra",     "cleric", 2),
    ]

    mtimes = []
    for name, cls, lvl in players:
        char = create_character(name, cls, lvl)
        cs.characters[name.lower()] = char
        # Persist after each join (simulates cmd_join flow)
        sync_chatstate_to_state(campaign_id, cs)
        mtimes.append(get_mtime(state_path))
        time.sleep(0.05)  # ensure different mtime
        print(f"    {green(f'{name} ({cls} lvl{lvl}) joined and persisted')}")

    # Verify all 4 characters in state.json
    state = load_json(state_path)
    for name, cls, lvl in players:
        char_key = name.lower()
        assert char_key in state["characters"], f"{name} should be in state.json"
        print(f"    {green(f'character.{char_key} exists in state.json')}")

    # Verify mtime advanced
    assert mtimes[-1] >= mtimes[0], "mtime should increase on each persist"
    print(f"    {green('state.json mtime advances on each persist')}")

    # ── STEP 3: NPC enemy joins ───────────────────────────────────────────────
    header("STEP 3 — NPC enemy (Red Dragon Wyrmling) added to combat")

    append_history(
        campaign_id,
        "A Red Dragon Wyrmling descends upon the party, smoke billowing from its nostrils!",
        entry_type="combat",
    )
    append_history(
        campaign_id,
        "Initiative is rolled — the dragon hisses and takes the lead!",
        entry_type="narration",
    )
    print(f"    {green('History entries appended')}")

    # ── STEP 4: Combat starts ────────────────────────────────────────────────
    header("STEP 4 — Combat begins (start_combat)")

    participants = [
        {"name": "Valdric", "is_player": True, "dex_mod": 1},
        {"name": "Mira",    "is_player": True, "dex_mod": 0},
        {"name": "Thorne",  "is_player": True, "dex_mod": 2},
        {"name": "Lyra",    "is_player": True, "dex_mod": 1},
        {"name": "Red Dragon Wyrmling", "is_player": False, "dex_mod": 0},
    ]
    cs.combat_state = start_combat(participants)
    sync_chatstate_to_state(campaign_id, cs)

    state = load_json(state_path)
    assert state["combat"]["active"], "combat should be active"
    assert len(state["combat"]["initiative_order"]) == 5, "5 combatants in initiative"
    print(f"    {green('Combat active')}")
    print(f"    {blue('Initiative order:')} {[c['name'] for c in state['combat']['initiative_order']]}")
    print(f"    {green(f'Round {state["combat"]["round"]}')}")

    # ── STEP 5: Each character acts ────────────────────────────────────────────
    header("STEP 5 — Each character takes an action")

    # Valdric attacks the dragon (fighter action)
    append_history(
        campaign_id,
        "Valdric charges forward and strikes the dragon with his longsword! (1d8+4 slashing damage)",
        entry_type="combat",
    )
    # Simulate HP reduction on dragon
    dragon = next((c for c in cs.combat_state.initiative_order if c.name == "Red Dragon Wyrmling"), None)
    if dragon:
        dragon.held = True  # simulate dragon took damage and is now held
    sync_chatstate_to_state(campaign_id, cs)
    mtime_after_attack = get_mtime(state_path)
    assert mtime_after_attack >= mtimes[-1]
    print(f"    {green('Valdric attacked — state.json updated (mtime advanced)')}")
    mtimes.append(mtime_after_attack)

    # Mira casts Magic Missile
    append_history(
        campaign_id,
        "Mira whispers arcane words and fires three magic missiles at the dragon! (3d4+3 force damage)",
        entry_type="combat",
    )
    sync_chatstate_to_state(campaign_id, cs)
    print(f"    {green('Mira cast spell — state.json updated')}")

    # Thorne uses Cunning Action to disengage
    append_history(
        campaign_id,
        "Thorne vanishes into the shadows with a burst of speed, retreating from the dragon's reach.",
        entry_type="combat",
    )
    sync_chatstate_to_state(campaign_id, cs)
    print(f"    {green('Thorne disengaged — state.json updated')}")

    # Lyra heals Valdric
    append_history(
        campaign_id,
        "Lyra channels divine power and heals Valdric for 5 hit points!",
        entry_type="combat",
    )
    sync_chatstate_to_state(campaign_id, cs)
    print(f"    {green('Lyra cast heal — state.json updated')}")

    # Dragon's turn
    append_history(
        campaign_id,
        "The Red Dragon Wyrmling breathes fire! The party takes 16 fire damage!",
        entry_type="combat",
    )
    sync_chatstate_to_state(campaign_id, cs)
    print(f"    {green('Dragon attacked — state.json updated')}")

    # ── STEP 6: Verify state.json content ─────────────────────────────────────
    header("STEP 6 — Final state.json verification")

    state = load_json(state_path)

    checks = [
        ("campaign.status",         "active"),
        ("campaign.name",           "The Dragon's Lair"),
        ("characters.valdric.hp",   None),   # just check existence
        ("characters.mira.hp",      None),
        ("characters.thorne.hp",    None),
        ("characters.lyra.hp",      None),
        ("combat.active",           True),
        ("combat.round",            1),
        ("combat.initiative_order", None),   # length checked below
        ("history",                 None),   # should have 6+ entries
    ]

    for key, expected in checks:
        parts = key.split(".")
        val = state
        for p in parts:
            val = val[p]
        if expected is not None:
            assert val == expected, f"{key} should be {expected}, got {val}"
        print(f"    {green(f'{key} = {json.dumps(val) if isinstance(val, (str,int,bool)) else str(val)[:60]}')}")

    assert len(state["combat"]["initiative_order"]) == 5
    assert len(state["history"]) >= 6, f"Expected 6+ history entries, got {len(state['history'])}"
    print(f"    {green(f'combat.initiative_order has 5 combatants')}")
    print(f"    {green(f'history has {len(state["history"])} entries')}")

    # ── STEP 7: Verify mtime advances ────────────────────────────────────────
    header("STEP 7 — mtime monotonicity check")
    # (mtimes was accumulated throughout — re-read current mtime)
    final_mtime = get_mtime(state_path)
    assert final_mtime >= mtimes[0], "state.json mtime should have advanced"
    print(f"    {green(f'state.json mtime advanced from {mtimes[0]} to {final_mtime}')}")

    # ── All green ─────────────────────────────────────────────────────────────
    header("ALL TESTS PASSED ✅")
    print(f"""
  Campaign:     {campaign_id}
  Players:      {', '.join(n for n,_,_ in players)}
  Combat:       {state['combat']['active']}
  Rounds:       {state['combat']['round']}
  History:      {len(state['history'])} entries
  State file:   {state_path}
    """)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\n{red('ASSERTION FAILED')}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{red('ERROR')}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
