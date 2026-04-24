# SDD-004: Fix /setup Generation Echo Bug

## Status: Draft → Ready for Review

---

## 1. Problem Statement

### 1.1 User-Reported Bug

When a user runs `/setup <description>`, the bot returns a campaign preview where:

- **Premise** = literal copy-paste of the user's input (e.g. `"quiero una historia de SAO con un rey demonio..."`)
- **Hook** = generic placeholder text unrelated to the premise
- **Location** = `"un lugar olvidado"` (hardcoded default)
- **NPCs** = random templates with no thematic connection (e.g. Captain Vorn in a SAO campaign)
- **Tone** = `"serious"` (default, ignoring user intent)

**Expected behavior:** The AI (or fallback) should generate **original** campaign content inspired by the user's prompt, not echo it back.

### 1.2 Reproduction Steps

```
User: /setup quiero una historia de SAO con un rey demonio, zombies y ninjas, seria y oscura, un gremio de ladrones, con las siguientes clases: Corsario, Navegante, Contrabandista, Bucanero, Oficial de Marina
Bot:  🎲 Generando con AI...
Bot:  [Preview where premise ≈ user's raw text]
```

### 1.3 Evidence

```
Premise: quiero una historia de SAO con un rey demonio, zombies y ninjas, seria y oscura, un gremio de ladrones...
Hook: La amenaza se cierne sobre un lugar olvidado...
Tone: serious
```

---

## 2. Root Cause Analysis

Two independent root causes produce the same broken UX.

### 2.1 Root Cause A — AI Path: Insufficient Prompt Engineering + Token Budget

**Location:** `dm/world_builder.py::generate_setup_with_ai()` (lines 220–268)

**Failure modes:**

1. **Prompt framing invites repetition.** The prompt wraps the user's description in quotes and presents it as the primary context. The LLM interprets this as a paraphrasing task rather than a creative generation task:
   ```python
   prompt = f'''... El DM quiere una campaña con esta descripción:
   "{description}" ...'''
   ```

2. **`max_tokens=800` is too low.** The requested JSON contains 9 fields with nested arrays and objects. At ~100–150 tokens per field, the response needs ~1200–1500 tokens. With only 800 tokens, the LLM truncates or resorts to cheap shortcuts (copying the user's text to save tokens).

3. **No anti-copy guardrail.** The prompt lacks an explicit instruction such as *"Do NOT repeat the user's description verbatim. Create original content inspired by it."*

4. **No semantic detection of copy-paste.** Even if the LLM copies 80% of the input, the code blindly accepts and parses it.

### 2.2 Root Cause B — Fallback Path: Literal Concatenation

**Location:** `dm/world_builder.py::generate_setup_with_ai()` except block (lines 318–409)

**Failure modes:**

1. **Premise = user's description + template prefix.** The fallback explicitly concatenates the raw user text:
   ```python
   premise = f"Los personajes son aventureros comprometidos con una misión peligrosa: {description.strip('.')}. Un conflicto de poder y traición los enfrentará a enemigos inesperados."
   ```

2. **Hook = generic regex soup.** The hook is built from regex-extracted fragments (`threat`, `location`, `roles`) with hardcoded sentence templates. If no keyword matches, all fragments are empty and the hook becomes nonsensical.

3. **Location = keyword fallback.** Location detection uses a trivial `if/elif/else` with 6 Spanish keywords. If none match → `"un lugar olvidado"`.

4. **NPCs = static keyword lookup.** `_generate_themed_npcs()` maps a handful of keywords to fixed NPC lists. "SAO", "demonio", "zombie", "ninja" have **zero matches** → falls back to random generic NPCs.

5. **Tone = default `"serious"`.** The fallback ignores the user's requested tone entirely unless it happens to match `"oscuro"`/`"dark"` or `"épico"`/`"heroico"`.

### 2.3 Decision Matrix: When Each Root Cause Triggers

| Condition | Path Triggered | Why |
|-----------|---------------|-----|
| `MINIMAX_API_KEY` unset | Fallback (B) | `api_key` empty → immediate `ValueError` |
| API timeout / 5xx | Fallback (B) | Exception caught → except block |
| LLM returns non-JSON | Fallback (B) | `json.loads()` raises → except block |
| LLM returns JSON but copies input | AI path (A) | Parsed as "valid" but content is garbage |
| LLM returns truncated JSON | Fallback (B) | `json.loads()` raises → except block |

---

## 3. Proposed Solution

### 3.1 High-Level Strategy

Apply three layers of defense:

1. **Layer 1 — Prevent:** Fix the AI prompt and token budget so the LLM generates original content.
2. **Layer 2 — Detect:** Add a post-generation validator that detects copy-paste and regenerates.
3. **Layer 3 — Recover:** If all AI paths fail, use an LLM-powered fallback (not regex templates) to generate original content from the description.

### 3.2 Detailed Changes

#### 3.2.1 AI Path Hardening (`generate_setup_with_ai`, AI success branch)

**Change 3.2.1.1 — Rewrite the prompt with anti-copy guardrails**

Replace the current prompt template with:

```python
PROMPT_TEMPLATE = """Eres un DM creativo de D&D 5e con 20 años de experiencia.

El DM te da esta IDEA para una campaña. NO copies ni repitas esta idea. En su lugar, CREÁ contenido original e inspirado en ella.

IDEA DEL DM:
{description}

---

Generá una campaña COMPLETA en español. Cada campo debe ser original, creativo, y específico. Nada de textos genéricos.

1. **premise** (2-3 oraciones): ¿Quiénes son los PJ y qué los une? Usá vocabulario específico del setting. NO menciones "aventureros genéricos".
2. **hook** (2 oraciones): ¿Qué evento disruptivo arranca la aventura? Debe ser concreto y urgente.
3. **starting_location** (nombre propio): Un lugar específico con nombre propio. NO uses "un lugar olvidado".
4. **starting_location_desc** (2-3 oraciones): Descripción sensorial y atmosférica del lugar.
5. **main_threat** (1 oración): La amenaza central con nombre propio si aplica.
6. **factions** (2-3): Nombre + estado (DOMINANT/RISING/HIDDEN/CORRUPT/etc). Deben estar en conflicto.
7. **npcs** (2-3): Nombre propio, rol específico, y una línea de diálogo que revele personalidad. Deben estar relacionados con el setting.
8. **classes** (3-5): Nombres de clases temáticas que encajen en el setting. NO uses "Guerrero/Mago/Pícaro" a menos que sea fantasy genérico.
9. **starting_equipment** (3-5): Objetos con nombre y descripción corta.
10. **story_arc**: Milestones según pacing_level={pacing_level}.

Respondé ÚNICAMENTE en JSON válido con este formato:
{{ ... }}
"""
```

**Change 3.2.1.2 — Increase `max_tokens` to 1500**

```python
response = provider.text(
    prompt,
    system="Eres un DM creativo de D&D 5e. Generás campañas originales. Nunca repetís el input del usuario. Respondés solo en JSON válido.",
    max_tokens=1500,
    temperature=0.85,
)
```

**Change 3.2.1.3 — Add copy-paste detection validator**

After parsing the JSON, run:

```python
def _is_echo(description: str, premise: str, threshold: float = 0.60) -> bool:
    """Detect if the LLM echoed the user's description."""
    import re
    desc_words = set(re.findall(r'\b\w+\b', description.lower()))
    premise_words = set(re.findall(r'\b\w+\b', premise.lower()))
    if not desc_words:
        return False
    overlap = len(desc_words & premise_words) / len(desc_words)
    return overlap > threshold
```

If `_is_echo()` returns `True`, raise an exception to trigger the fallback path.

#### 3.2.2 Fallback Path Rewrite (`generate_setup_with_ai`, except block)

**Change 3.2.2.1 — Never concatenate raw description into premise**

Delete:
```python
premise = f"Los personajes son aventureros comprometidos con una misión peligrosa: {description.strip('.')}. ..."
```

Replace with an **LLM-powered mini-generation** using the same provider (or any available provider). This is a second-chance AI call with a simpler prompt:

```python
# Fallback: try a simpler, single-shot generation
fallback_prompt = f"""Crea una campaña de D&D 5e basada en esta idea: {description}

Responde en JSON:
{{
  "premise": "...",
  "hook": "...",
  "starting_location": "...",
  "starting_location_desc": "...",
  "main_threat": "...",
  "factions": {{"...": "..."}},
  "npcs": [{{"name": "...", "role": "...", "dialogue": "..."}}],
  "classes": ["..."],
  "starting_equipment": [{{"name": "...", "description": "...", "is_consumable": false}}]
}}

Reglas:
- NO repitas la idea del usuario.
- Todo contenido debe ser original y específico.
"""
```

If this second AI call also fails, then and only then use template-based fallback.

**Change 3.2.2.2 — Improve template fallback if ALL AI fails**

If even the second AI call fails, keep the template fallback but make it **non-literal**:

- **Premise:** Extract 3–5 key nouns from `description` (using simple regex), then build: `"En un mundo donde {noun1} y {noun2} coexisten, un grupo de {role} debe enfrentar {noun3} antes de que {noun4} consuma todo."`
- **Location:** Use the first proper noun from description, or `"las Tierras de {random_name}"` instead of `"un lugar olvidado"`.
- **Hook:** Must reference the `main_threat` and `location`.
- **NPCs:** Use `_generate_themed_npcs()` but if no keyword matches, generate procedurally: `"{Adjective} {Name}"` + role derived from setting.

#### 3.2.3 NPC Generation Improvements

**Change 3.2.3.1 — Expand `_generate_themed_npcs()` keyword map**

Add keywords for common requests:

```python
"demonio": [
    {"name": "Vex, el Ocaso", "role": "Sacerdote caído del rey demonio", "dialogue": "La carne es temporal. La oscuridad, eterna."},
    ...
],
"zombie": [
    {"name": "Doctor Mordrake", "role": "Alquimista que estudia la plaga", "dialogue": "No son muertos... son la siguiente evolución."},
    ...
],
"ninja": [
    {"name": "Sombra de Hielo", "role": "Espía del clan oculto", "dialogue": "He visto tu muerte. Fue silenciosa."},
    ...
],
"SAO": [
    {"name": "Kirito (NPC)", "role": "Espadachín negro legendario", "dialogue": "No importa en qué mundo estés... nunca dejes de luchar."},
    ...
],
```

**Change 3.2.3.2 — Procedural NPC generation for unmatched keywords**

If no keyword matches, generate NPCs procedurally from description nouns:

```python
def _generate_procedural_npcs(description: str, count: int = 3) -> list[dict]:
    """Generate NPCs from description keywords when no themed template matches."""
    import re, random
    nouns = re.findall(r'\b[A-Z][a-z]+\b', description)  # capitalized words
    roles = ["mercenario", "sacerdote", "mercader", "espía", "eremita", "noble", "artista"]
    personalities = ["cínico", "apasionado", "paranoico", "noble", "sarcástico", "misterioso"]
    npcs = []
    for i in range(min(count, len(nouns) if nouns else 3)):
        name = nouns[i] if i < len(nouns) else f"Desconocido {i+1}"
        role = random.choice(roles)
        personality = random.choice(personalities)
        npcs.append({
            "name": name,
            "role": f"{personality.capitalize()} {role}",
            "dialogue": f"Algo sobre {name.lower()} no es lo que parece..."
        })
    return npcs
```

---

## 4. Acceptance Criteria

### 4.1 Functional Requirements

| ID | Requirement | Test |
|----|-------------|------|
| F1 | Premise must NOT contain >60% word overlap with user's raw description | Unit test with SAO description |
| F2 | Location must NOT be `"un lugar olvidado"` unless AI explicitly chooses it | Unit test with unmatched keywords |
| F3 | Hook must reference the `main_threat` and `starting_location` specifically | Unit test: assert `main_threat in hook` |
| F4 | NPCs must have names and roles related to the setting (not generic Captain Vorn in SAO) | Unit test: SAO → NPCs reference swords/VR/levels |
| F5 | Tone must match user request (e.g. `"oscura"` → dark tone, not `"serious"`) | Unit test with tone keywords |
| F6 | Fallback path must NOT concatenate raw description into premise | Unit test: mock AI failure, check premise |
| F7 | If AI returns echoed content, validator must detect and trigger fallback | Unit test: mock LLM returning user's text |

### 4.2 Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NF1 | Setup generation must complete in <10s (including retry) |
| NF2 | Fallback must work offline (no API key) with acceptable quality |
| NF3 | No breaking changes to existing `/setup` command interface |

---

## 5. Testing Plan

### 5.1 Unit Tests

```python
# tests/test_world_builder.py

def test_generate_setup_with_ai_no_echo():
    """F1: premise should not be a copy of description."""
    desc = "quiero una historia de SAO con un rey demonio, zombies y ninjas"
    result = generate_setup_with_ai(desc)
    overlap = _compute_word_overlap(desc, result["premise"])
    assert overlap < 0.60, f"Echo detected: overlap={overlap}"

def test_generate_setup_with_ai_location_not_generic():
    """F2: location must not be the hardcoded fallback."""
    desc = "aventura en un puerto pirata llamado Puerto Tormenta"
    result = generate_setup_with_ai(desc)
    assert result["lore"]["starting_location"] != "un lugar olvidado"

def test_generate_setup_fallback_no_concatenation():
    """F6: fallback must not paste description into premise."""
    with mock.patch("dm.world_builder.MiniMaxProvider") as MockProvider:
        MockProvider.side_effect = Exception("API down")
        result = generate_setup_with_ai("SAO con demonios")
        assert "SAO" not in result["premise"].lower() or result["premise"].count(" ") > 10
        assert "quiero" not in result["premise"].lower()

def test_echo_validator():
    """F7: validator detects copy-paste."""
    desc = "zombies y ninjas en un mundo de SAO"
    premise = "zombies y ninjas en un mundo de SAO con un rey demonio"
    assert _is_echo(desc, premise, threshold=0.60) is True
    premise = "En Aincrad, los cazadores de mazmorras enfrentan horrores digitales."
    assert _is_echo(desc, premise, threshold=0.60) is False
```

### 5.2 Integration Tests

```python
# tests/test_setup_flow_integration.py

@pytest.mark.asyncio
async def test_full_setup_flow_no_echo():
    """End-to-end: /setup → preview → no echo in premise."""
    update = MockUpdate(message=MockMessage(text="/setup SAO con rey demonio"))
    context = MockContext()
    await cmd_setup(update, context)
    
    # Inspect the preview message sent
    preview = context.bot.sent_messages[0]["text"]
    assert "quiero" not in preview.lower()
    assert "SAO" in preview  # OK if it's original content referencing SAO
```

---

## 6. Implementation Checklist

- [ ] **Step 1:** Rewrite AI prompt template with anti-copy guardrails
- [ ] **Step 2:** Increase `max_tokens` from 800 → 1500
- [ ] **Step 3:** Implement `_is_echo()` validator
- [ ] **Step 4:** Add validator call after JSON parse in AI path
- [ ] **Step 5:** Rewrite fallback premise (no concatenation)
- [ ] **Step 6:** Add second-chance AI call in fallback with simplified prompt
- [ ] **Step 7:** Improve template fallback (procedural location/NPCs)
- [ ] **Step 8:** Expand `_generate_themed_npcs()` keyword map (demonio, zombie, ninja, SAO, etc.)
- [ ] **Step 9:** Implement `_generate_procedural_npcs()` for unmatched keywords
- [ ] **Step 10:** Write unit tests (F1–F7)
- [ ] **Step 11:** Run integration tests
- [ ] **Step 12:** Update CHANGELOG

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `max_tokens=1500` increases API cost | Medium | Low | Only affects setup (1x per campaign). Cache response. |
| Second-chance AI call doubles latency | Medium | Medium | Add 5s timeout. If exceeded, skip to template fallback. |
| `_is_echo()` false positive rejects good output | Low | Medium | Threshold = 0.60 (generous). Can tune to 0.70 if needed. |
| Procedural NPCs feel generic | Medium | Low | Improve noun extraction or add more keyword templates. |

---

## 8. Future Work (Out of Scope)

- **Semantic keyword matching:** Use embeddings to match description themes to NPC templates instead of substring search.
- **Interactive setup refinement:** After preview, let the user say `"más oscuro"` or `"cambialo a cyberpunk"` and regenerate only changed fields.
- **Multi-provider LLM fallback:** If MiniMax fails, try Pollinations/GLM/OpenAI before template fallback.

---

## 9. References

- `dm/world_builder.py` — `generate_setup_with_ai()` (lines 190–409)
- `dm/world_builder.py` — `_generate_themed_npcs()` (lines 461–600+)
- `dm/provider_client.py` — `MiniMaxProvider.text()` (lines 93–135)
- `bot/telegram_handler.py` — `cmd_setup()` (lines 493–618)
