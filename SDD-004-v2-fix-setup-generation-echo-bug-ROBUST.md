# SDD-004 v2: Fix /setup Generation Echo Bug (Robust)

## Status: Draft → Ready for Review

---

## 1. Problem Statement (Recap from v1)

When a user runs `/setup <description>`, the bot returns a campaign preview where:
- **Premise** = literal copy-paste or thin paraphrase of user's input
- **Hook** = generic placeholder
- **Location** = "un lugar olvidado" when no keyword matches
- **NPCs** = generic fantasy NPCs with zero connection to the premise

**v1 fixed the symptoms but left structural weaknesses in the validator, prompt design, and fallback quality.**

---

## 2. v1 Weaknesses Identified

| # | Weakness | Impact |
|---|---|---|
| W1 | `_is_echo()` uses simple word-set overlap → false positives on short inputs | Rejects valid premises |
| W2 | Second-chance AI prompt lacks anti-copy guardrails → MORE prone to echo | Wastes tokens, worse output |
| W3 | Fallback premise is generic filler text | Users still get low-quality fallback |
| W4 | Procedural NPCs use raw input words as names | "Demonio" as an NPC name |
| W5 | No few-shot examples in LLM prompt | LLM doesn't learn what "original" means |
| W6 | No happy-path tests with mocked LLM responses | Can't verify echo detection works |
| W7 | `max_tokens=2048` hardcoded, no fallback if model rejects | Silent failure → fallback path |

---

## 3. Design Decisions

### Decision 1: Hybrid Echo Validator (n-gram + word overlap + input-length-aware threshold)

**Rationale:** Word overlap alone fails on short inputs (2-word descriptions = 100% overlap on any mention). N-gram overlap detects copied phrases. Input-length-aware threshold prevents false positives.

**Rule:**
- For inputs ≤ 5 unique words: threshold = 0.80 (must be almost exact copy)
- For inputs 6-15 unique words: threshold = 0.65
- For inputs > 15 unique words: threshold = 0.55
- **Additional rule:** If ANY sequence of 4+ consecutive words from the description appears in the premise → always echo (regardless of overall overlap)

### Decision 2: Remove Second-Chance AI Call

**Rationale:** If the first prompt (with guardrails + examples) fails, a weaker prompt won't succeed. Two API calls = 2x cost, 2x latency, worse quality. Go straight to high-quality template fallback.

### Decision 3: Few-Shot Examples in Main Prompt

**Rationale:** LLMs learn from examples better than from instructions. Show one BAD example (echo) and one GOOD example (original) so the model internalizes the difference.

### Decision 4: Fallback Premise Uses Templates by Setting + Threat

**Rationale:** Generic filler is worse than a well-written template that references the actual threat and setting. Pre-write 6 premise templates per setting type, parameterized with threat/location.

### Decision 5: Procedural NPCs Use Setting + Threat, Not Input Words

**Rationale:** Using "Demonio" as a name is lazy. Instead, derive NPC archetypes from the detected threat/setting and generate names from curated name pools.

---

## 4. Detailed Changes

### 4.1 Replace `_is_echo()` with `_is_echo_v2()`

```python
def _is_echo_v2(description: str, premise: str) -> tuple[bool, str]:
    """
    Hybrid echo detection.
    
    Returns (is_echo: bool, reason: str)
    """
    import re
    
    desc_clean = re.findall(r'\b\w+\b', description.lower())
    premise_clean = re.findall(r'\b\w+\b', premise.lower())
    
    if not desc_clean or not premise_clean:
        return False, "empty"
    
    desc_set = set(desc_clean)
    premise_set = set(premise_clean)
    overlap = len(desc_set & premise_set) / len(desc_set)
    
    # Input-length-aware threshold
    unique_count = len(desc_set)
    if unique_count <= 5:
        threshold = 0.80
    elif unique_count <= 15:
        threshold = 0.65
    else:
        threshold = 0.55
    
    if overlap >= threshold:
        return True, f"word_overlap:{overlap:.2f}>={threshold}"
    
    # N-gram check: detect 4+ consecutive copied words
    for i in range(len(desc_clean) - 3):
        ngram = " ".join(desc_clean[i:i+4])
        if ngram in " ".join(premise_clean):
            return True, f"ngram_copy:{ngram}"
    
    return False, f"word_overlap:{overlap:.2f}<{threshold}"
```

**Test cases:**
- `("fantasía oscura", "En un reino de fantasía oscura...")` → `(False, ...)` — was `(True, ...)` in v1
- `("quiero una historia de SAO con demonios", "quiero una historia de SAO con demonios y ninjas")` → `(True, "ngram_copy:quiero una historia de")`

### 4.2 Rewrite Main Prompt with Few-Shot Examples

Replace the current prompt with:

```
Eres un DM creativo de D&D 5e con 20 años de experiencia. Generás campañas ORIGINALES.

Regla de oro: NUNCA copies, repitas ni parafraseés la idea del DM. En su lugar, CREÁ contenido nuevo inspirado en ella.

---

EJEMPLO DE MALA RESPUESTA (echo — NUNCA hagas esto):
IDEA DEL DM: "quiero una historia de piratas en el mar"
❌ premise: "Los personajes son piratas que navegan el mar buscando aventuras..."
→ Esto repite las palabras del DM. Es echo.

EJEMPLO DE BUENA RESPUESTA (original):
IDEA DEL DM: "quiero una historia de piratas en el mar"
✅ premise: "En el Archipiélago de los Mil Ahogados, los últimos corsarios libres luchan contra la Flota de Hierro que quiere extinguir toda bandera negra."
→ Toma la idea (piratas, mar) y CREA algo nuevo con nombres propios y conflicto específico.

---

AHORA ES TU TURNO. IDEA DEL DM:
{description}

Generá una campaña COMPLETA en español. Cada campo debe ser original, creativo, y específico.

[premise, hook, location, threat, factions, npcs, classes, equipment, story_arc — same fields as v1]

Respondé ÚNICAMENTE en JSON válido. No escribas nada más que el JSON.
```

**Rationale:** The examples create a strong prior. The LLM now has a concrete reference for what "original" means.

### 4.3 Remove Second-Chance AI Layer

Delete the entire `Layer 3` block (lines ~370-446 in current code). If Layer 1 fails or produces echo → go directly to Layer 4 (template fallback).

**Rationale:** Empirically, if a model fails with a strong prompt, a weaker prompt won't succeed. The second call adds cost and latency with negative expected value.

### 4.4 Rewrite Template Fallback Premise

Replace the current generic premise with **parameterized templates**:

```python
_PREMISE_TEMPLATES = {
    "fantasy": {
        "dark": [
            "En {location}, el {threat} ha extinguido toda esperanza. Los sobrevivientes se refugian en las sombras, sabiendo que cada amanecer podría ser el último.",
            "Las tierras de {location} yacen bajo el yugo de {threat}. Aquellos que resisten no son héroes: son cadáveres que aún no han caído.",
        ],
        "epic": [
            "Una profecía antigua despertó en {location}: cuando {threat} amenace con consumir el mundo, unos pocos elegidos tendrán el poder de detenerlo.",
            "El destino de {location} pende de un hilo. {threat} se fortalece con cada día que pasa, y solo quienes se atrevan a desafiarlo podrán forjar una nueva era.",
        ],
        "serious": [
            "En {location}, el orden se desmorona bajo la presión de {threat}. Los que aún creen en la justicia deben elegir entre la ley y la supervivencia.",
            "Una conspiración silenciosa une a {threat} con las élites de {location}. Descubrir la verdad significa arriesgar todo lo que se ama.",
        ],
        "comedic": [
            "¡En {location}, nadie espera que {threat} sea TAN incompetente! Entre bufones y calamidades, un grupo de inadaptados podría salvar el día... por accidente.",
        ],
    },
    "scifi": {
        "dark": [
            "La estación {location} es un ataúd flotante. {threat} controla los sistemas de soporte vital, y cada corridor podría ser una trampa mortal.",
        ],
        "epic": [
            "En los confines de {location}, {threat} desafía los límites de la humanidad. La próxima frontera no es el espacio: es la supervivencia.",
        ],
        "serious": [
            "Los datos no mienten: {threat} ha comprometido cada sistema en {location}. Alguien debe entrar en la Zona Roja y desconectarlo antes de que sea tarde.",
        ],
    },
    "horror": {
        "dark": [
            "En {location}, las paredes susurran. {threat} no es un enemigo que puedas ver: es la casa misma, despertando de un sueño milenario.",
            "Nadie que entre a {location} sale igual. {threat} deja marcas invisibles, y las pesadillas son solo el comienzo.",
        ],
    },
}
```

**Selection logic:**
```python
def _build_fallback_premise(setting: str, tone: str, location: str, threat: str) -> str:
    templates = _PREMISE_TEMPLATES.get(setting, _PREMISE_TEMPLATES["fantasy"])
    tone_templates = templates.get(tone, templates.get("serious", list(templates.values())[0]))
    template = random.choice(tone_templates)
    return template.format(location=location, threat=threat or "una fuerza desconocida")
```

### 4.5 Rewrite `_generate_procedural_npcs()`

**Current (v1):** Extracts words from input, uses them as NPC names.

**New (v2):** Use threat/setting to select name pools and archetypes.

```python
_NPC_NAME_POOLS = {
    "demonio": {"first": ["Vex", "Mordrake", "Sariel", "Baal", "Lilith"], "last": ["el Ocaso", "de las Cenizas", "el Hambriento", "la Sombra"]},
    "zombie": {"first": ["Voss", "Mordrake", "Sera", "Kain", "Elías"], "last": ["el Infectado", "de la Cuarentena", "el Último", "Sin Nombre"]},
    "ninja": {"first": ["Kage", "Hattori", "Sombra", "Rin", "Jin"], "last": ["de Hielo", "del Clan Oscuro", "el Silencioso", "Rojo"]},
    "pirata": {"first": ["Barracuda", "Morgan", "Sparrow", "Calico", "Anne"], "last": ["el Rojo", "de las Sombras", "la Feroz", "Sin Bandera"]},
    "default": {"first": ["Elias", "Mira", "Vorn", "Sera", "Aldric"], "last": ["", "el Viejo", "la Sabia", "el Rápido"]},
}

_NPC_ARCHETYPES = {
    "demonio": [
        ("Sacerdote caído", "La carne es temporal. La oscuridad, eterna."),
        ("Exorcista con las manos quemadas", "He visto lo que hay detrás de los ojos poseídos."),
        ("Ermitaño que aún reza", "Dios no abandona... pero a veces tarda."),
    ],
    "zombie": [
        ("Alquimista que estudia la plaga", "No son muertos... son la siguiente evolución."),
        ("Comandante de cuarentena", "Disparad a la cabeza. No preguntéis."),
        ("Superviviente inmune", "No me muerden. No sé por qué."),
    ],
    "ninja": [
        ("Espía del clan oculto", "He visto tu muerte. Fue silenciosa."),
        ("Viejo sensei traidor", "La lealtad es una herramienta. Como la katana."),
        ("Asesino de élite", "Mi precio es alto. Mi silencio, más."),
    ],
    "default": [
        ("Mercenario cansado", "Pago por día. Sangre extra cuesta más."),
        ("Erudito paranoico", "Sé demasiado. Por eso me escondo."),
        ("Mensajero sin rostro", "Llevo noticias. No siempre buenas."),
    ],
}

def _generate_procedural_npcs_v2(threat: str, setting: str, count: int = 3) -> list[dict]:
    """Generate NPCs from threat/setting archetypes, never from raw input words."""
    # Select archetype pool
    archetypes = _NPC_ARCHETYPES.get(threat.lower(), _NPC_ARCHETYPES.get(setting.lower(), _NPC_ARCHETYPES["default"]))
    name_pool = _NPC_NAME_POOLS.get(threat.lower(), _NPC_NAME_POOLS.get(setting.lower(), _NPC_NAME_POOLS["default"]))
    
    npcs = []
    used_names = set()
    for i in range(min(count, len(archetypes))):
        archetype = archetypes[i % len(archetypes)]
        # Generate unique name
        for _ in range(20):
            first = random.choice(name_pool["first"])
            last = random.choice(name_pool["last"])
            name = f"{first} {last}".strip()
            if name not in used_names:
                used_names.add(name)
                break
        else:
            name = f"Desconocido {i+1}"
        
        npcs.append({
            "name": name,
            "role": archetype[0],
            "dialogue": archetype[1],
        })
    return npcs
```

### 4.6 Add Happy-Path Tests with Mocked LLM Responses

```python
def test_ai_path_with_echo_detected_and_rejected():
    """F7: if LLM echoes input, validator rejects and fallback triggers."""
    fake_echo_response = mock.Mock()
    fake_echo_response.text = json.dumps({
        "premise": "quiero una historia de SAO con un rey demonio",
        "hook": "test hook",
        "starting_location": "test",
        "starting_location_desc": "test",
        "main_threat": "test",
        "factions": {},
        "npcs": [],
        "classes": [],
        "starting_equipment": [],
    })
    
    with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.text.return_value = fake_echo_response
        
        result = generate_setup_with_ai("quiero una historia de SAO con un rey demonio")
        # Should have fallen back to template (not returned the echo)
        assert "quiero" not in result["premise"].lower()
        assert result["lore"]["starting_location"] != ""

def test_ai_path_with_original_content_accepted():
    """F1: if LLM generates original content, validator accepts."""
    fake_original_response = mock.Mock()
    fake_original_response.text = json.dumps({
        "premise": "En Aincrad, los cazadores de mazmorras enfrentan horrores digitales que desafían la línea entre realidad y código.",
        "hook": "Un mensajero aparece muerto con un mensaje cifrado en su brazalete.",
        "starting_location": "Piso 47: El Jardín de Cristal",
        "starting_location_desc": "Un bosque de árboles de cristal quebrado. Cada paso produce un eco metálico.",
        "main_threat": "El Administrador ha perdido el control del sistema.",
        "factions": {"Cazadores": "RISING", "Administración": "DOMINANT"},
        "npcs": [{"name": "Klein", "role": "Líder de cazadores", "dialogue": "No bajes al piso 50. Nadie vuelve de allí."}],
        "classes": ["Espadachín Negro", "Curandera de Campo", "Ingeniero de Mazmorras"],
        "starting_equipment": [{"name": "Brazalete de Estado", "description": "Muestra tu HP en tiempo real.", "is_consumable": False}],
    })
    
    with mock.patch("dm.provider_client.MiniMaxProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.text.return_value = fake_original_response
        
        result = generate_setup_with_ai("quiero una historia de SAO con un rey demonio")
        # Should return the AI-generated content (not fallback)
        assert "Aincrad" in result["premise"]
        assert result["lore"]["starting_location"] == "Piso 47: El Jardín de Cristal"
```

### 4.7 Make `max_tokens` Configurable with Auto-Fallback

```python
# In config or constants
MAX_TOKENS_PRIMARY = 2048
MAX_TOKENS_FALLBACK = 1500  # If 2048 is rejected by model

# In generate_setup_with_ai:
try:
    response = provider.text(prompt, system=..., max_tokens=MAX_TOKENS_PRIMARY, temperature=0.85)
except Exception as e:
    if "max_tokens" in str(e).lower() or "token" in str(e).lower():
        # Model might not support 2048 output, try 1500
        response = provider.text(prompt, system=..., max_tokens=MAX_TOKENS_FALLBACK, temperature=0.85)
    else:
        raise
```

---

## 5. Testing Strategy

### Unit Tests (all existing + new)

| Test | Description |
|---|---|
| `test_is_echo_v2_short_input` | Input ≤5 words, valid premise with 2 words in common → NOT echo |
| `test_is_echo_v2_long_input` | Input >15 words, 60% overlap → IS echo |
| `test_is_echo_v2_ngram_detected` | 4-word sequence copied → IS echo regardless of overall overlap |
| `test_ai_path_echo_rejected` | Mock LLM returning echo → triggers fallback |
| `test_ai_path_original_accepted` | Mock LLM returning original → returns AI content |
| `test_fallback_premise_uses_template` | Fallback premise uses setting+tone template, not generic text |
| `test_procedural_npcs_v2_no_input_words` | NPC names come from curated pools, not raw description |
| `test_procedural_npcs_v2_unique_names` | No duplicate names in generated NPC list |
| `test_fallback_detects_threat_and_builds_premise` | Threat "zombie" → premise references zombies specifically |

### Integration Test

Run `/setup quiero una historia de SAO con un rey demonio, zombies y ninjas, seria y oscura` against the real MiniMax API and verify:
1. Premise does not contain "quiero una historia"
2. Premise contains specific names/places (not generic)
3. Location is not "un lugar olvidado"
4. NPCs are related to SAO/demonios/zombies/ninjas
5. No 4+ word sequence from input appears in premise

---

## 6. Files Modified

| File | Changes |
|---|---|
| `dm/world_builder.py` | Replace `_is_echo()` → `_is_echo_v2()`, rewrite prompt with examples, remove second-chance AI, add `_PREMISE_TEMPLATES`, rewrite `_generate_procedural_npcs()` → `_generate_procedural_npcs_v2()`, add `_NPC_NAME_POOLS` + `_NPC_ARCHETYPES`, add `MAX_TOKENS_PRIMARY/FALLBACK` |
| `tests/test_world_builder_echo.py` | Add tests for `_is_echo_v2`, happy-path AI mock tests, template premise tests, procedural NPC v2 tests |

---

## 7. Migration Notes

- v1 functions `_is_echo()` and `_generate_procedural_npcs()` will be **replaced** (not kept alongside) to avoid confusion
- The second-chance AI layer will be **removed entirely** (code deletion, not deprecation)
- No breaking changes to the public API of `generate_setup_with_ai()`

---

## 8. Acceptance Criteria (F1–F7 from v1, unchanged)

- [ ] **F1:** `/setup` with AI available produces premise that is NOT a copy-paste of the user's description
- [ ] **F2:** Location is never the hardcoded string `"un lugar olvidado"` when keywords are present in the description
- [ ] **F3:** Hook references the main threat and the starting location by name
- [ ] **F4:** NPCs are related to the setting (e.g., SAO → VR-themed NPCs, demonio → cultist NPCs)
- [ ] **F5:** Tone detection works (dark/epic/comedic/serious keywords in description)
- [ ] **F6:** Fallback path (AI unavailable) produces original premise — does NOT concatenate raw `description` string
- [ ] **F7:** Echo validator does not reject valid original content (e.g., "fantasía oscura" mentioned naturally in premise)

---

*SPEC v2 addresses all 7 weaknesses of v1 (W1–W7) while maintaining the same acceptance criteria.*
