# SDD PROPOSAL: Scene Director — El Cerebro del DM

**Change:** `scene-director`
**Project:** hermesdm
**Status:** PROPOSAL
**Priority:** P0 — Critical
**Date:** 2026-04-29

---

## 1. PROBLEM STATEMENT

HermesDM is NOT a D&D game. It's a prose generator with fantasy theming.
The LLM decides WHAT happens. There's no DM "brain" driving the game forward.
The player can type 10 exploration actions and nothing ever happens — no combat,
no events, no complications, no resource depletion, no death, no victory.

**Root cause:** The LLM is the brain AND the voice. It needs to be ONLY the voice.

## 2. SOLUTION

Build `dm/scene_director.py` — a module that decides WHAT happens in every scene.
The LLM is demoted to narrator — it writes beautiful prose about what the code
ALREADY DECIDED.

### Architecture Inversion

```
ANTES (broken):                  AHORA (game):
Player → LLM decides → prose     Player → SceneDirector decides → LLM narrates
                                         ↑                          ↑
                                    EncounterEngine            only writes
                                    NPCDirector               what it's told
                                    QuestEngine
                                    ResourceManager
                                    CombatFlow
                                         ↓
                                    State updated (HP, flags, quests)
```

## 3. SIX NEW COMPONENTS

### 3.1 SceneDirector (`dm/scene_director.py`)
**Role:** The DM brain. Main entry point for every game turn.

```python
class SceneDirector:
    def decide(player_action, scene_count, state) -> SceneDecision
```

- Forces combat encounters every 3-4 scenes (70% combat, 20% social, 10% event)
- Triggers NPC actions independently
- Detects exploration → checks for traps/secrets based on location danger
- Ensures milestone pressure triggers events (should_inject_event)
- Decides rest validity (can only rest in safe locations)
- Returns SceneDecision with explicit narrative_instruction

### 3.2 EncounterEngine (`dm/encounter_engine.py`)
**Role:** Generates combat and social encounters.

- Selects enemies based on location danger (1-5) + milestone tier (1-3)
- Enemy pool: goblins (tier 1), orcs (tier 2), dragon (tier 3)
- CR-based difficulty: Easy/Medium/Hard/Deadly
- Generates loot: gold, items, consumables
- Social encounters: merchant, quest-giver, informant, traitor

### 3.3 NPCDirector (`dm/npc_director.py`)
**Role:** Gives NPCs independent agency.

- Tracks NPC agendas: what each NPC wants
- NPC act_counter: acts every 3-5 scenes
- Actions: reveal_secret, offer_quest, betray, ambush, help, flee
- Relationship: numeric disposition (-100 to +100) affected by player choices
- NPCs can move between locations independently

### 3.4 QuestEngine (`dm/quest_engine.py`)
**Role:** Proper quest system connected to gameplay.

- Active quests with Objectives[] (kill X, find Y, reach Z, talk to NPC)
- Objective completion detected via world_flags, location changes, NPC states
- Quest chains: prerequisites, sequential objectives
- Rewards: items, gold, XP, new flags, new locations unlocked
- Quest log: active, completed, failed

### 3.5 ResourceManager (`dm/resource_manager.py`)
**Role:** Proper resource tracking with D&D 5e rules.

- HP depletion and recovery
- Spell slots: per level (1st: 2, 2nd: 0, etc. based on class/level)
- Short rest (1 hour): spend hit dice to heal (1dX + CON per die)
- Long rest (8 hours): full HP, recover half hit dice, all spell slots
- Inventory: add/remove/use items with effects
- Death saves: 3 successes before 3 failures → stable or dead
- Unconscious at 0 HP: can't act, death saves each turn

### 3.6 CombatFlow (`dm/combat_flow.py`)
**Role:** Proper D&D 5e combat structure.

- Roll initiative (d20 + DEX) for all combatants
- Turn order: sorted by initiative
- Action economy: 1 action + 1 bonus action + 1 reaction + movement
- Conditions: poisoned, paralyzed, frightened, charmed, stunned, prone, blinded
- Cover: half (+2 AC), three-quarters (+5 AC), full (untargetable)
- Advantage/disadvantage: roll 2d20 take higher/lower
- Victory: all enemies 0 HP or flee
- Defeat: all players 0 HP (unconscious → death saves → TPK)
- Flee: player can attempt to escape (contested Athletics/Acrobatics)

## 4. DATA FLOW (New Game Loop)

```
/j me muevo hacia la torre
         │
         ▼
SceneDirector.decide("me muevo hacia la torre", scene_count=7, state)
         │
         ├─ scene_count=7, 7%4=3 → FORCE ENCOUNTER
         ├─ location_danger=3 (medium), milestone_tier=2
         │
         ├─ EncounterEngine.generate(danger=3, tier=2)
         │   → enemies: [{"name": "Orc Warrior", "hp": 15, "ac": 13, "attacks": [...]}]
         │   → encounter_type: "combat"
         │
         ├─ SceneDecision(
         │     scene_type="combat",
         │     narrative_instruction="2 Orc Warriors emboscan al jugador en el camino a la torre. Saltan desde las rocas con hachas en mano.",
         │     enemies=[...],
         │     location="Bosque Oscuro",
         │   )
         │
         ▼
CombatFlow.run_initiative() → initiative_order = [Orc1(18), Orc2(14), Player(10)]
CombatFlow.run_turn("Orc1") → ataca al jugador: d20(12)+5=17 vs AC 15 → 8 damage
CombatFlow.run_turn("Player") → (player responde con /j ataco al orco)
         │
         ▼
LLM receives:
  "Narrá una escena de COMBAT. 2 Orc Warriors emboscaron al jugador.
   Orc1 atacó: d20(12)+5=17 vs AC 15 → HIT → 8 damage.
   El jugador contraataca: [dice result].
   Ubicación: Bosque Oscuro. Noche cerrada, antorchas distantes.
   Terminá la narración con el jugador teniendo que decidir qué hacer."
         │
         ▼
State updated:
  - Player HP: 22 → 14
  - Orc1 HP: 15 → 8
  - world_flags["forest_ambush_triggered"] = true
  - scene_count: 7 → 8
```

## 5. SceneDecision Dataclass

```python
@dataclass
class SceneDecision:
    scene_type: str  # "combat", "social", "exploration", "rest", "travel", "event"
    narrative_instruction: str  # WHAT the LLM must narrate (specific instruction)
    enemies: list = field(default_factory=list)
    active_npc: dict | None = None
    location: str = ""
    mechanical_setup: dict = field(default_factory=dict)
    world_changes: dict = field(default_factory=dict)
    quest_updates: list = field(default_factory=list)
    is_encounter: bool = False
```

## 6. FILES

### New (6 files)
| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `dm/scene_director.py` | ~300 | DM brain — scene type decisions |
| `dm/encounter_engine.py` | ~250 | Combat/social encounter generation |
| `dm/npc_director.py` | ~200 | NPC independent agency |
| `dm/quest_engine.py` | ~200 | Quest tracking and completion |
| `dm/resource_manager.py` | ~200 | HP, spells, rests, death saves |
| `dm/combat_flow.py` | ~250 | Initiative, turns, action economy |

### Modified (6 files)
| File | Changes |
|------|---------|
| `adapters/mode_b/action_router.py` | Wire SceneDirector; receive SceneDecision |
| `bot/telegram_handler.py` | New game loop: SceneDirector → CombatFlow → LLM |
| `dm/narrative_generator.py` | Accept structured SceneDecision; remove free invention |
| `dm/pacing_engine.py` | Coordinate encounter forcing with SceneDirector |
| `state/state_manager.py` | Add spell slots, death saves, rest tracking |
| `bot/character_sheet.py` | Add spell_slots, death_saves, hit_dice fields |

### New Tests (6 files)
| File | Tests (est.) |
|------|-------------|
| `tests/test_scene_director.py` | 20+ |
| `tests/test_encounter_engine.py` | 15+ |
| `tests/test_npc_director.py` | 15+ |
| `tests/test_quest_engine.py` | 15+ |
| `tests/test_resource_manager.py` | 15+ |
| `tests/test_combat_flow.py` | 15+ |

## 7. SUCCESS CRITERIA

| # | Criterion | Measurement |
|---|-----------|------------|
| 1 | Combat forced every ≤5 scenes | scene_count % 4 check |
| 2 | NPCs act independently | NPCDirector act_counter |
| 3 | Proper D&D 5e combat flow | Initiative → turns → action economy |
| 4 | HP depletes meaningfully | ResourceManager tracks between encounters |
| 5 | Death is possible | Death saves at 0 HP |
| 6 | Quests have objectives, can complete | QuestEngine objective detection |
| 7 | Story has structure: hook → rising action → climax | Milestone enforcement |
| 8 | LLM only narrates decisions, never invents | SceneDirector.narrative_instruction |
| 9 | Rests work (short=hit dice, long=full) | ResourceManager rest mechanics |
| 10 | Every scene advances plot | should_inject_event + encounter forcing |
| 11 | 0 regression tests | Full test suite passes |

## 8. RISKS

| Risk | Mitigation |
|------|------------|
| LLM ignores narrative_instruction | Few-shot examples showing only-narrate behavior |
| Combat too frequent or too rare | scene_count % 4 tunable via config |
| Existing campaigns break | Backward compat: missing fields default reasonably |
| Performance (6 new modules) | Each module is stateless, pure functions |
| Complexity explosion | Strict separation: each module does ONE thing |

## 9. PHASES

| Phase | Components | Effort | Depends on |
|-------|-----------|--------|------------|
| 1 | SceneDirector + SceneDecision dataclass | 2 days | None |
| 2 | EncounterEngine + CombatFlow | 3 days | Phase 1 |
| 3 | NPCDirector + QuestEngine | 2 days | Phase 1 |
| 4 | ResourceManager + rest/death mechanics | 2 days | Phase 2 |
| 5 | Wire everything into game loop | 2 days | Phases 1-4 |
| 6 | Integration testing + smoke test | 1 day | Phase 5 |
| **Total** | | **12 days** | |
