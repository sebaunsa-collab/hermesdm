# SDD-005 v1: Fix Gameplay — Action → Narrative Integration

## Status: Draft → Ready for Review

---

## 1. Problem Statement

After `/setup` → `/join` → `/begin`, the bot broadcasts an opening scene. When a player then runs `/j <acción>`, the response is broken in **7 distinct ways** that make the game unplayable:

### Symptoms observed by user
> "cuando el bot narra la primer escenario, yo ejecuto una accion y me manda este mensaje: `> HermesDM_bot: 🎭 ¡LA AVENTURA COMIENZA! El un lugar olvidado te recibe con las sombras se aferran a cada superficie. shug`"

**Translation:** The opening scene says `"El un lugar olvidado te recibe..."` (grammatically broken — `"El"` + `"un"` = wrong article + wrong noun). Then the player's action produces a truncated/empty response ending with `"shug"` (likely the player's name or a cut-off message).

---

## 2. Root Cause Analysis (verified against actual code)

### Bug 1 — Location never persisted to state (CRITICAL)
**File:** `bot/telegram_handler.py:1014-1043` (`cmd_begin`)

`cmd_begin` builds a `ctx` dict with `"location": lore.get("starting_location", ...)` and passes it to `NarrativeGenerator.generate_scene()`. **But it never writes `starting_location` into `state["campaign"]["current_location"]`**.

Later, `ActionRouter._build_context()` (l.1016-1024) reads:
```python
location = camp.get("current_location", {}).get("name", "el dungeon")
```
Since `current_location` is `None`, it falls back to `"el dungeon"`. But `NarrativeGenerator._build_context()` reads `campaign.get("current_location")` and gets `None`, so it falls back to `"an unknown place"` (English!). The template then produces `"El un lugar olvidado te recibe..."` because `"un lugar olvidado"` comes from the old `world_builder.py` fallback.

### Bug 2 — Player's action text never reaches NarrativeGenerator (CRITICAL)
**File:** `adapters/mode_b/action_router.py:1010-1076` (`_build_context`)

`_build_context()` receives `intent` and `resolution`, but **never the original `action_text`**. The context dict has no key like `"player_action"`, `"player_intent"`, or `"action_description"` that contains what the player actually typed.

The NarrativeGenerator templates have placeholders like:
- `{action_description}` — hardcoded to `"se mueve con cautela por el terreno"`
- `{dialogue_excerpt}` — never filled
- `{attack_description}` — generic `"{char_name} ataca a {target}"`

**Result:** The narrative has zero connection to what the player actually said. `/j le pregunto al tabernero por el dragón` produces the same text as `/j ataco al goblin`.

### Bug 3 — No dialogue resolver (CRITICAL)
**File:** `adapters/mode_b/action_router.py`

`ActionRouter` has `_resolve_attack`, `_resolve_hide`, `_resolve_shove`, `_resolve_medicine`... but **NO `_resolve_dialogue`**. When `_parse()` detects dialogue keywords (`"digo"`, `"hablo"`, `"pregunto"`), it sets `action_type="dialogue"`. Then `_resolve()` calls `getattr(self, "_resolve_dialogue", self._resolve_generic)` which falls through to `_resolve_generic()` — a d20 vs DC 12 as if talking were a physical skill check.

**Result:** `/j hablo con el tabernero` → "🎲 dialogue: 9 (+2+2) vs DC 12 — ❌" (talking fails a DC check).

### Bug 4 — NPC name resolution broken (HIGH)
**File:** `adapters/mode_b/action_router.py:1025-1027`

```python
npcs = self.state.get("npcs", {})
if npcs:
    npc_name = list(npcs.keys())[0] if npcs else "Un guerrero"
```

This gets the **dict key** (e.g., `"knight_01"`), not the NPC's actual name (`"Sir Aldric"`). The template then says `"knight_01 te evalúa con cautela"`.

### Bug 5 — `_interpret_with_ai()` hardcoded broken URL (HIGH)
**File:** `adapters/mode_b/action_router.py:986-987`

```python
"https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId=YOUR_GROUP_ID"
```

`YOUR_GROUP_ID` is a placeholder. This call always fails, so ambiguous actions (classified as `"explore"`) get no AI interpretation and fall through to generic resolution.

### Bug 6 — NarrativeGenerator fallbacks are English (MEDIUM)
**File:** `dm/narrative_generator.py:304-365` (`_build_context`)

All fallback values are in English:
- `"shadows cling to every surface"` → gets prepended with `"El"` in Spanish template
- `"a metallic aroma fills the air"`
- `"The party is ready"`

**Result:** Mixed Spanish/English output: `"El shadows cling to every surface te recibe..."` (if the template were working, which it isn't because of Bug 1).

### Bug 7 — NarrativeGenerator doesn't read setup lore (MEDIUM)
**File:** `dm/narrative_generator.py:304-365`

`_build_context()` reads `state.get("campaign", {})` and `state.get("npcs", {})`, but **never reads `state.get("setup", {})` or `state.get("setup", {}).get("lore", {})`**. The rich lore data (premise, hook, main_threat, factions, starting_location_desc) generated during `/setup` is completely ignored by the narrative engine.

**Result:** Even if location were persisted, the narrative would still use generic `"dungeon"` descriptions instead of the campaign-specific setting.

---

## 3. Design Decisions

### Decision 1: Persist location + setup lore to state on `/begin`
**Rationale:** The narrative generator needs campaign-specific data. `/begin` is the single point where setup transitions to active game state. Writing setup-derived values into `state["campaign"]` makes them available to all subsequent handlers.

**What gets written:**
```python
state["campaign"]["current_location"] = setup["lore"]["starting_location"]
state["campaign"]["current_location_desc"] = setup["lore"]["starting_location_desc"]
state["campaign"]["main_threat"] = setup["lore"]["main_threat"]
state["campaign"]["premise"] = setup["premise"]
state["campaign"]["hook"] = setup["hook"]
state["campaign"]["tone"] = setup["tone"]
```

### Decision 2: Thread `action_text` through the entire pipeline
**Rationale:** The narrative MUST know what the player did. Currently the pipeline is:
```
/j <text> → _parse(text) → _resolve(intent) → _classify(intent, resolution) → _build_context(intent, resolution) → _generate_narrative(scene_type, ctx)
```

The text is lost after `_parse()`. We need:
```
/j <text> → _parse(text) → _resolve(intent) → _classify(intent, resolution) → _build_context(intent, resolution, action_text) → _generate_narrative(scene_type, ctx)
```

And `_build_context` must populate `ctx["player_action"] = action_text`.

### Decision 3: Add `_resolve_dialogue()` with NPC lookup
**Rationale:** Dialogue is not a skill check. It's a social interaction that needs to:
1. Identify the target NPC from `intent.target`
2. Look up the NPC in `state["npcs"]`
3. Generate a thematic response based on the NPC's role + disposition + campaign lore
4. Return a `mechanic_inline` that describes the interaction, not a dice roll

**No dice roll for dialogue** — the "resolution" is narrative, not mechanical.

### Decision 4: Fix `_interpret_with_ai()` or remove it
**Rationale:** A hardcoded broken URL is worse than no feature. Two options:
- **Option A:** Fix the URL to use the real MiniMax endpoint + proper GroupId from env
- **Option B:** Remove the feature entirely and rely on keyword parsing

**Decision: Option B (remove).** The keyword parser already covers 25+ action types. Adding an AI call for edge cases adds latency, cost, and another point of failure. If a player types something truly unparseable, the fallback should be `"explore"` with a generic narrative, not a broken API call.

### Decision 5: NarrativeGenerator reads setup lore + translated fallbacks
**Rationale:** The generator should produce Spanish text with campaign-specific details. All fallback values must be in Spanish, and the generator should attempt to read `state["setup"]["lore"]` before falling back to generic values.

### Decision 6: Fix NPC name resolution
**Rationale:** Using dict keys as names is a bug. `_build_context()` should read `npcs[npc_id]["name"]`.

---

## 4. Detailed Changes

### 4.1 Fix `cmd_begin` — persist location + lore

**File:** `bot/telegram_handler.py` (around line 1038)

**Current code:**
```python
state["adventure_started"] = True
# Transfer story_arc from setup to state if present
setup_arc = setup.get("story_arc")
if setup_arc and state.get("story_arc") is None:
    state["story_arc"] = setup_arc
```

**New code:**
```python
state["adventure_started"] = True

# Persist campaign metadata from setup so all handlers can read it
state["campaign"]["current_location"] = lore.get("starting_location", "Ubicación desconocida")
state["campaign"]["current_location_desc"] = lore.get("starting_location_desc", "")
state["campaign"]["main_threat"] = lore.get("main_threat", "")
state["campaign"]["premise"] = setup.get("premise", "")
state["campaign"]["hook"] = setup.get("hook", "")
state["campaign"]["tone"] = setup.get("tone", "serious")
state["campaign"]["setting_type"] = setup.get("setting_type", "fantasy")

# Transfer story_arc from setup to state if present
setup_arc = setup.get("story_arc")
if setup_arc and state.get("story_arc") is None:
    state["story_arc"] = setup_arc
```

**Test verification:** After `cmd_begin`, `load_state(campaign_id)["campaign"]["current_location"]` must equal `setup["lore"]["starting_location"]`.

---

### 4.2 Thread `action_text` through ActionRouter

**File:** `adapters/mode_b/action_router.py`

**4.2.1 — Update `route()` signature**
```python
def route(self, update: Update, action_text: str, ...) -> ActionResult:
```
Already receives `action_text`. Pass it to `_build_context`.

**Current:**
```python
ctx = self._build_context(intent, resolution, scene_type)
```

**New:**
```python
ctx = self._build_context(intent, resolution, scene_type, action_text)
```

**4.2.2 — Update `_build_context()` signature**
```python
def _build_context(self, intent: ActionIntent, resolution: ActionResolution, scene_type: SceneType, action_text: str) -> dict:
```

**4.2.3 — Populate `player_action` in context**
Add to the `ctx` dict:
```python
"player_action": action_text,
"player_action_type": intent.action_type,
```

---

### 4.3 Add `_resolve_dialogue()`

**File:** `adapters/mode_b/action_router.py`

**New method:**
```python
def _resolve_dialogue(self, intent: ActionIntent) -> ActionResolution:
    """
    Resuelve una acción de diálogo.
    No tira dados — la resolución es narrativa.
    Busca el NPC objetivo en el estado para generar contexto.
    """
    target = intent.target or "el PNJ"
    
    # Buscar NPC en el estado para contexto narrativo
    npc_data = None
    if self.state and "npcs" in self.state:
        npcs = self.state["npcs"]
        # Buscar por nombre (case-insensitive)
        target_lower = target.lower()
        for npc_id, npc in npcs.items():
            npc_name = npc.get("name", npc_id).lower()
            if target_lower in npc_name or npc_name in target_lower:
                npc_data = npc
                break
    
    if npc_data:
        npc_name = npc_data.get("name", target)
        npc_role = npc_data.get("role", "")
        disposition = npc_data.get("disposition", "NEUTRAL")
        
        # Determinar reacción base según disposición
        if disposition == "HOSTILE":
            reaction = f"{npc_name} te mira con hostilidad."
        elif disposition == "FRIENDLY":
            reaction = f"{npc_name} te saluda con una sonrisa."
        else:
            reaction = f"{npc_name} te observa con cautela."
        
        mechanic = f"🗣️ Diálogo con {npc_name} ({npc_role}). {reaction}"
    else:
        mechanic = f"🗣️ Intentas hablar con {target}. No hay nadie con ese nombre cerca."
    
    return ActionResolution(
        success=True,  # Diálogo no falla mecánicamente
        hit=None,
        damage=None,
        roll=None,
        dc=None,
        mechanic_inline=mechanic,
        attack_roll=0,
    )
```

---

### 4.4 Remove `_interpret_with_ai()`

**File:** `adapters/mode_b/action_router.py`

**Current:** Lines 959-1008. Delete entirely.

**In `route()`, update the call site:**
```python
# REMOVE this block:
# if intent.action_type == "explore":
#     ai_intent = self._interpret_with_ai(action_text)
#     if ai_intent:
#         intent = ai_intent
```

**Result:** If `_parse()` returns `"explore"`, it stays as `"explore"`. The generic narrative handles it.

---

### 4.5 Fix `_build_context()` — NPC names + lore-aware fallbacks

**File:** `adapters/mode_b/action_router.py:1010-1104`

**4.5.1 — Fix NPC name resolution**
```python
# CURRENT (broken):
npcs = self.state.get("npcs", {})
if npcs:
    npc_name = list(npcs.keys())[0] if npcs else "Un guerrero"

# NEW:
npcs = self.state.get("npcs", {})
npc_name = "Un guerrero"
npc_data = None
if npcs:
    first_npc_id = list(npcs.keys())[0]
    first_npc = npcs[first_npc_id]
    npc_name = first_npc.get("name", first_npc_id)
    npc_data = first_npc
```

**4.5.2 — Read campaign lore from state**
```python
campaign = self.state.get("campaign", {}) if self.state else {}
location = campaign.get("current_location", "el dungeon")
location_desc = campaign.get("current_location_desc", "")
main_threat = campaign.get("main_threat", "")
premise = campaign.get("premise", "")
hook = campaign.get("hook", "")
tone = campaign.get("tone", "serious")
```

**4.5.3 — Use location_desc if available**
```python
# If we have a location description from setup, use it as sensory detail
if location_desc:
    sensory_detail = location_desc
else:
    sensory_detail = "las sombras se aferran a cada superficie"
```

---

### 4.6 Fix NarrativeGenerator fallbacks to Spanish

**File:** `dm/narrative_generator.py:304-365`

**Translate ALL fallback values to Spanish:**

| Current (English) | New (Spanish) |
|---|---|
| `"shadows cling to every surface"` | `"las sombras se aferran a cada superficie"` |
| `"a cold fog swirls between ancient stones"` | `"una fría niebla se arremolina entre piedras antiguas"` |
| `"A distant growl echoes"` | `"Un gruñido distante resuena"` |
| `"hidden by vegetation and forgetfulness"` | `"oculto por la vegetación y el olvido"` |
| `"The party is ready"` | `"El grupo está listo"` |
| `"observes attentively"` | `"te observa con recelo"` |
| `"charged with unspoken tension"` | `"cargado de tensión no dicha"` |
| `"A voice emerges"` | `"Una voz emerge"` |
| `"You weigh their words carefully."` | `"Sopesás sus palabras con cuidado."` |
| `"battlefield"` | `"campo de batalla"` |
| `"Positioning becomes critical."` | `"El posicionamiento se vuelve crítico."` |
| `"everything you believed was built on lies"` | `"todo en lo que creías estaba construido sobre mentiras"` |
| `"The weight of it settles on the group"` | `"El peso de ello se asienta sobre el grupo"` |
| `"a campfire crackles nearby"` | `"una hoguera crepita cerca"` |
| `"Provisions and rest"` | `"Provisiones y descanso"` |
| `"Fatigue weighs heavily"` | `"La fatiga pesa mucho"` |
| `"The night passes slowly"` | `"La noche transcurre lentamente"` |
| `"Training or preparation is possible"` | `"Entrenamiento o preparación es posible"` |

**Also fix the location fallback:**
```python
# CURRENT:
location = campaign.get("current_location") or "an unknown place"

# NEW:
location = campaign.get("current_location") or "un lugar desconocido"
```

---

### 4.7 NarrativeGenerator reads setup lore

**File:** `dm/narrative_generator.py:304-365` (`_build_context`)

**Add setup lore reading:**
```python
setup = state.get("setup", {})
lore = setup.get("lore", {}) if setup else {}

# Override fallbacks with setup lore if available
if lore.get("starting_location_desc"):
    context["sensory_detail"] = lore["starting_location_desc"]
if lore.get("main_threat"):
    context["ambient_threat"] = f"La presencia de {lore['main_threat']} se siente cerca"
if setup.get("premise"):
    context["revelation"] = setup["premise"]
```

---

### 4.8 Add `player_action` to template context

**File:** `dm/narrative_generator.py:304-365`

In `_build_context()`, after applying overrides:
```python
# Add player's action to context if provided in overrides
if "player_action" in overrides:
    context["player_action"] = overrides["player_action"]
    context["action_description"] = overrides["player_action"]
```

---

### 4.9 Fix template for EXPLORATION to use `player_action`

**File:** `dm/narrative_generator.py:40-51`

**Current templates:**
```python
"El {location} se extiende ante ti, {sensory_detail}. "
"{character_present} {action_description}. "
"El camino adelante está {obstacle}",
```

**New templates (using player_action when available):**
```python
"El {location} se extiende ante ti, {sensory_detail}. "
"{character_present} {action_description}. "
"El camino adelante está {obstacle}",
"Te encuentras en {location}, donde {environmental_detail}. "
"{npc_or_character_present} {reaction_description}. "
"{ambient_threat} mientras considerás tu siguiente movimiento",
"El {location} te recibe con {sensory_detail}. "
"{character_present} {action_description}. "
"Algo en este lugar se siente {emotional_tone}",
```

These are already good. The fix is that `action_description` will now be filled with the player's actual action text instead of the hardcoded `"se mueve con cautela por el terreno"`.

---

## 5. Files Modified

| File | Changes |
|---|---|
| `bot/telegram_handler.py` | `cmd_begin`: persist `current_location`, `current_location_desc`, `main_threat`, `premise`, `hook`, `tone`, `setting_type` to `state["campaign"]` |
| `adapters/mode_b/action_router.py` | `route()`: pass `action_text` to `_build_context`; `_build_context()`: add `action_text` param, fix NPC name resolution, read campaign lore; Add `_resolve_dialogue()`; Remove `_interpret_with_ai()` |
| `dm/narrative_generator.py` | `_build_context()`: translate ALL fallback values to Spanish, read `setup["lore"]` for overrides, accept `player_action` in overrides, fix location fallback |

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Test: `test_cmd_begin_persists_location()`**
```python
def test_cmd_begin_persists_location():
    """F1: cmd_begin must write starting_location to state['campaign']['current_location']."""
    # Mock state with setup lore
    state = {
        "campaign": {"status": "active"},
        "setup": {
            "lore": {
                "starting_location": "Piso 47: El Jardín de Cristal",
                "starting_location_desc": "Un bosque de cristales quebrados.",
                "main_threat": "El Administrador",
            },
            "premise": "En Aincrad...",
            "hook": "Un mensajero aparece muerto...",
            "tone": "dark",
        },
        "characters": {"shug": {...}},
    }
    # Call cmd_begin logic
    # Assert state["campaign"]["current_location"] == "Piso 47: El Jardín de Cristal"
    # Assert state["campaign"]["main_threat"] == "El Administrador"
```

**Test: `test_action_router_build_context_has_player_action()`**
```python
def test_action_router_build_context_has_player_action():
    """F2: _build_context must include the original action_text."""
    router = ActionRouter(state=mock_state, character=mock_char)
    intent = ActionIntent(action_type="dialogue", target="tabernero")
    resolution = ActionResolution(success=True, mechanic_inline="test")
    ctx = router._build_context(intent, resolution, SceneType.DIALOGUE, "le pregunto al tabernero por el dragón")
    assert ctx["player_action"] == "le pregunto al tabernero por el dragón"
```

**Test: `test_resolve_dialogue_finds_npc()`**
```python
def test_resolve_dialogue_finds_npc():
    """F3: _resolve_dialogue must find NPC by name and use their role/disposition."""
    state = {"npcs": {"bartender_01": {"name": "Gromm", "role": "Tabernero", "disposition": "FRIENDLY"}}}
    router = ActionRouter(state=state, character=mock_char)
    intent = ActionIntent(action_type="dialogue", target="gromm")
    result = router._resolve_dialogue(intent)
    assert "Gromm" in result.mechanic_inline
    assert "Tabernero" in result.mechanic_inline
    assert result.success is True
    assert result.roll is None  # No dice roll
```

**Test: `test_resolve_dialogue_no_dice_roll()`**
```python
def test_resolve_dialogue_no_dice_roll():
    """F3b: Dialogue must not trigger a dice roll."""
    router = ActionRouter(state={}, character=mock_char)
    intent = ActionIntent(action_type="dialogue", target="desconocido")
    result = router._resolve_dialogue(intent)
    assert result.roll is None
    assert result.dc is None
```

**Test: `test_npc_name_resolution_uses_name_field()`**
```python
def test_npc_name_resolution_uses_name_field():
    """F4: _build_context must use npc['name'], not the dict key."""
    state = {"npcs": {"knight_01": {"name": "Sir Aldric", "role": "Caballero"}}}
    router = ActionRouter(state=state, character=mock_char)
    intent = ActionIntent(action_type="attack", target="goblin")
    resolution = ActionResolution(success=True, mechanic_inline="test")
    ctx = router._build_context(intent, resolution, SceneType.COMBAT, "ataco al goblin")
    assert "Sir Aldric" in ctx["npc_present"]
    assert "knight_01" not in ctx["npc_present"]
```

**Test: `test_narrative_generator_fallbacks_spanish()`**
```python
def test_narrative_generator_fallbacks_spanish():
    """F5: _build_context fallback values must be in Spanish."""
    ng = NarrativeGenerator()
    ctx = ng._build_context({"campaign": {}, "characters": {}, "npcs": {}}, {})
    assert "shadows" not in ctx["sensory_detail"].lower()
    assert "The party" not in ctx["character_present"]
```

**Test: `test_narrative_generator_reads_setup_lore()`**
```python
def test_narrative_generator_reads_setup_lore():
    """F6: _build_context must read setup['lore'] for sensory details."""
    ng = NarrativeGenerator()
    state = {
        "campaign": {},
        "setup": {
            "lore": {"starting_location_desc": "Cristales rotos por doquier."}
        },
    }
    ctx = ng._build_context(state, {})
    assert ctx["sensory_detail"] == "Cristales rotos por doquier."
```

### 6.2 Integration Test

**Test: `/j` action produces coherent narrative**

Setup:
1. Create campaign with setup lore
2. Run `/begin`
3. Run `/j le pregunto al tabernero si vio al dragón`

Assertions:
- Response does NOT contain `"El un lugar olvidado"`
- Response contains `"tabernero"` or `"dragón"` (the action was understood)
- Response does NOT contain a dice roll result for dialogue
- Response is in Spanish (no English words)

---

## 7. Acceptance Criteria

- [ ] **F1:** After `/begin`, `state["campaign"]["current_location"]` equals `setup["lore"]["starting_location"]`
- [ ] **F2:** `ActionRouter._build_context()` includes `"player_action"` key with the original `/j` text
- [ ] **F3:** `/j <dialogue>` triggers `_resolve_dialogue()`, not `_resolve_generic()` — no dice roll
- [ ] **F4:** NPC names in narrative come from `npc["name"]` not the dict key
- [ ] **F5:** All NarrativeGenerator fallback values are in Spanish
- [ ] **F6:** NarrativeGenerator reads `setup["lore"]` for location descriptions and threats
- [ ] **F7:** `_interpret_with_ai()` is removed (no hardcoded broken URL)
- [ ] **F8:** After `/begin`, the opening scene uses the actual starting location name (not `"un lugar olvidado"`)
- [ ] **F9:** After `/j <action>`, the narrative references the player's actual action text

---

## 8. Out of Scope

These are real problems but NOT fixed by this SPEC (to keep scope manageable):

| Problem | Why out of scope |
|---|---|
| Dialogue doesn't use LLM to generate actual NPC responses | Would require LLM integration + context window management. Templates suffice for now. |
| `/j` actions don't update HP, inventory, or quest state | Requires full game state machine. Not part of this integration fix. |
| Combat actions (`/j ataco`) don't actually reduce enemy HP | Requires enemy state in `state["npcs"]` with HP tracking. Separate SPEC. |
| NarrativeGenerator LLM mode is never used (no `llm_client` passed) | Requires MiniMax API setup + token management. Separate SPEC. |
| Scene images are never auto-generated | Requires image provider integration in `_handle_player_action`. Separate SPEC. |
| No save/load of action history for narrative continuity | `append_history` exists but isn't read by NarrativeGenerator. Separate SPEC. |

---

## 9. Migration Notes

- **Breaking change:** `_build_context()` signature changes from `(intent, resolution, scene_type)` to `(intent, resolution, scene_type, action_text)`. Any code calling `_build_context` directly (tests, other modules) must be updated.
- **Breaking change:** `_interpret_with_ai()` is deleted. If any test mocks it, those tests must be removed.
- **Backward compatible:** Adding fields to `state["campaign"]` doesn't break old state files — code already uses `.get()` with defaults.

---

## 10. Estimated Complexity

| Metric | Value |
|---|---|
| Files touched | 3 |
| New methods | 1 (`_resolve_dialogue`) |
| Deleted methods | 1 (`_interpret_with_ai`) |
| Lines changed | ~150 |
| Tests to write | 8 |
| Risk | Medium (changes core action pipeline) |
| Estimated time | **M** (Medium — 2-3 hours of focused work) |

---

*SPEC SDD-005 v1 addresses the 7 bugs that make HermesDM unplayable after `/begin`. It does NOT add new features — it fixes the integration between existing components.*
