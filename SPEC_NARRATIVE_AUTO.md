# SPEC — Narrativa Automática para HermesDM
## Modo B: El DM narra sin que le pidan

```
═══════════════════════════════════════════════════════════════════════════════
STATUS: SPEC v1.0 — Para aprobación de Sherman
═══════════════════════════════════════════════════════════════════════════════
```

---

## 1. CONTEXTO

**Problema actual:**
- El bot procesa comandos (`/j Ataco al dragón`) y resuelve mecánicamente (tira dado, aplica daño)
- Devuelve el resultado numérico pero NO narra la escena
- El jugador recibe "18 de daño" pero no sabe qué pasó narrativamente

**Lo que queremos:**
- Cada vez que un jugador envía `/j <acción>`, HermesDM responde con:
  1. Narración del DM (2-4 oraciones, en español, estilo cinematográfico)
  2. Resultado mecánico inline (damage, DC check)
  3. (Opcional) Imagen si la escena es dramática

**Flujo completo:**

```
Jugador → "/j Ataco al dragón con mi espada"
                    │
                    ▼
          ┌─────────────────────┐
          │  1. RESOLVE ACTION  │
          │  - Parse intent     │
          │  - Roll dice        │
          │  - Apply to state   │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  2. BUILD CONTEXT    │
          │  - SceneType         │
          │  - World state       │
          │  - Player info      │
          │  - Tone setting      │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  3. GENERATE NARRATIVE│
          │  - LLM call (minimax) │
          │  - 2-4 sentences     │
          │  - Never a question  │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  4. SEND TO GROUP   │
          │  - Broadcast result │
          │  - Inline mechanic  │
          │  - Maybe image       │
          └─────────────────────┘
```

---

## 2. ARQUITECTURA

### 2.1 Mapa de archivos (cambios)

```
hermesdm/
├── bot/
│   ├── telegram_handler.py     # MODIFICAR: agregar MessageHandler para /j
│   └── game_commands.py       # MODIFICAR: hook post-resolve → narrative
│
├── dm/
│   ├── narrative_generator.py  # EXISTE — enhance con LLM mode
│   ├── scene_classifier.py    # EXISTE — determina scene_type + drama
│   ├── image_prompt_builder.py # EXISTE — genera prompt para imagen
│   └── providers/             # EXISTE — LLM client (minimax)
│
├── state/
│   └── state_manager.py        # EXISTE — get/update world state
│
└── adapters/
    └── mode_b/
        └── action_router.py   # NUEVO: rutea /j → resolve → narrate → broadcast
```

### 2.2 Diagrama de flujo de datos

```
User message "/j Ataco al dragón"
         │
         ▼
action_router.py
  ├── parse_action(message) → {type, target, params}
  ├── resolve_action(state, action) → {result, state_delta}
  ├── classify_scene(state, action_type) → SceneType
  ├── build_narrative_context(state, action, result) → dict
  ├── narrative_generator.generate_scene(ctx) → {narrative, triggered_image}
  ├── image_generator.generate(prompt) → image_url (if triggered)
  └── broadcast_to_group(narrative, result, image?)
```

---

## 3. COMPONENTES

### 3.1 `action_router.py` (NUEVO)

Recibe `/j <acción>` y orquesta el flujo completo.

```python
class ActionRouter:
    def route(self, update: Update, action_text: str) -> ActionResult:
        """
        Returns: ActionResult(narrative, mechanic_inline, image_url, new_state)
        """
        # 1. Parse intent → ActionIntent {type, target, params}
        intent = self._parse(action_text)
        
        # 2. Resolve with game engine → ActionResolution {hit, damage, narrative_snippet}
        resolution = self._resolve(intent, self._state)
        
        # 3. Classify scene → SceneType
        scene_type = self._classify(intent, resolution)
        
        # 4. Build context for narrative
        ctx = self._build_context(intent, resolution, scene_type)
        
        # 5. Generate narrative (LLM or template)
        narrative_result = self._narrate(ctx)
        
        # 6. Check if we should generate image
        image_url = None
        if narrative_result.triggered_image:
            prompt = image_prompt_builder.build(narrative_result.narrative, scene_type)
            image_url = image_generator.generate(prompt)
        
        return ActionResult(
            narrative=narrative_result.narrative,
            mechanic=narrative_result.mechanic_inline,
            image_url=image_url,
        )
```

### 3.2 `narrative_generator.py` (MEJORAR)

**YA EXISTE** con templates. Solo hay que:

1. Agregar `_generate_with_llm()` que llame a MiniMax
2. Hacer que `generate_scene()` acepte un `GameState` real y llene los slots del template con datos reales
3. Devolver también `mechanic_inline` (el resultado numérico embebido en la narración)

```python
def generate_scene(self, state, scene_type, context, language=Language.ES) -> dict:
    """
    Returns:
        narrative: str (2-4 sentences, ends with situation, no question)
        triggered_image: bool
        mechanic_inline: str (e.g. "💥 22 damage" or "DC 15: 18 ✅")
    """
    # Si hay LLM client → _generate_with_llm
    # Si no → _generate_with_template (mejorado)
    
    # El mechanic_inline SIEMPRE viene del resolve, no del LLM
    mechanic_inline = context.get("mechanic_inline", "")
    
    return {
        "narrative": narrative,
        "triggered_image": triggered_image,
        "mechanic_inline": mechanic_inline,
    }
```

### 3.3 `scene_classifier.py` (MEJORAR)

**YA EXISTE.** Solo hay que garantizar que `should_trigger_image()` funcione correctamente.

```python
class SceneClassifier:
    DRAMATIC_THRESHOLD = 0.7  # score > 0.7 → genera imagen
    
    def classify(self, action_type: str, resolution: dict) -> SceneType:
        """Mapea intent + resultado → SceneType."""
        pass
    
    def drama_score(self, scene_type: SceneType, resolution: dict) -> float:
        """
        0.0 → 1.0. Decide si la escena merece imagen.
        - COMBAT + kill → 0.95
        - COMBAT + nat_20 → 0.90
        - COMBAT + hit → 0.6
        - EXPLORATION + discovery → 0.7
        - DIALOGUE → 0.2
        """
        pass
    
    def should_trigger_image(self, scene_type, resolution) -> bool:
        return self.drama_score(scene_type, resolution) > self.DRAMATIC_THRESHOLD
```

### 3.4 Image Pipeline (YA EXISTE)

```
image_prompt_builder.py → image_generator.py → Pollinations/MiniMax
```

**Ya existe.** Solo hay que wirearlo en `action_router.py`.

---

## 4. PROMPT DE LLM (narrativa)

### System Prompt para el generador de叙事

```markdown
Eres el Narrador de un juego de D&D 5e. Tu trabajo es describir escenas
de forma cinematográfica, en español, sin preguntas.

REGLAS:
1. 2-4 oraciones máximo
2. Siempre termina con una situación abierta (nunca con "?")
3. Incluye detalles sensoriales concretos (sonidos, luces, olores)
4. El resultado de la acción YA está determinado — solo narralo
5. No inventes resultados ni contradigas lo que ya pasó
6. Estilo: cinematográfico, no infantil, no excesivamente épico

CONTEXTO QUE RECIBES:
- World state: ubicación actual, NPCs presentes, condiciones del entorno
- Acción del jugador: qué intentó hacer
- Resultado mecánico: si acertó, daño, DC, etc.
- Tipo de escena: COMBAT / EXPLORATION / DIALOGUE / STORY_BEAT / REST

EJEMPLO — Combat hit:
Jugador: "Ataco al dragón con mi espada"
Resultado: hit, 22 damage, nat_20=false
Ubicación: Throne Room del castillo, 3 NPC observando

NARRACIÓN ESPERADA:
"El acero de tu espada atraviesa las escamas del dragón con un chirrido
metálico. El impacto hace temblar el trono de hueso. El dragón ruge
y retrocede un paso, sangrando sobre las ruinas del salón."

EJEMPLO — Skill check success:
Jugador: "Uso sigilo para pasar desapercibido"
Resultado: DC 15, roll 18, success
Ubicación: Pasillo oscuro, guardias cerca

NARRACIÓN ESPERADA:
"Te deslizas entre las sombras como humo entre las columnas. Los pasos
de los guardias pasan cerca, pero sus linternas no encuentran más que
oscuridad. El camino adelante está despejado."

EJEMPLO — Combat miss:
Jugador: "Apunto a la cabeza del orco"
Resultado: miss, nat_1=false
Ubicación: Cueva subterránea, humedad extrema

NARRACIÓN ESPERADA:
"El hacha pasa silbando junto a tu oído. El orco sonríe con dientes
rotos y contraataca con un golpe bajo que rozas apenas con el escudo."
```

### Fallback: Template Mode (sin LLM)

Si no hay API key configurada, usar templates del `narrative_generator.py`
pero **mejorados** — que cojan datos reales del state:

```python
def _generate_with_template(self, scene_type: SceneType, ctx: dict) -> str:
    """Template mode mejorado que usa datos reales del state."""
    template = random.choice(_NARRATIVE_TEMPLATES[Language.ES][scene_type])
    
    # Llenar con datos reales del context
    filled = template
    for key, value in ctx.items():
        filled = filled.replace(f"{{{key}}}", str(value))
    
    return filled
```

---

## 5. FLUJO TELEGRAM (wire-in)

### 5.1 Hook en `telegram_handler.py`

```python
# Agregar MessageHandler para /j prefix
async def _handle_j_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa /j <acción> del Modo B async."""
    text = update.message.text.strip()
    
    # Extraer después del prefijo /j
    if not text.startswith("/j"):
        return
    
    action_text = text[2:].strip()  #去掉 "/j "
    if not action_text:
        await update.message.reply_text("Usá `/j <tu acción>` para jugar.")
        return
    
    # Obtener campaign state para este chat
    chat_id = update.effective_chat.id
    campaign_id = _get_chat_campaign(chat_id)
    state = load_state(campaign_id)
    
    # Router
    router = ActionRouter(state, llm_client=_get_llm_client())
    result = router.route(update, action_text)
    
    # Enviar narración al GRUPO (broadcast)
    msg = f"{result.narrative}\n\n{result.mechanic}"
    await update.message.reply_text(msg)
    
    # Si hay imagen → enviar después
    if result.image_url:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=result.image_url,
            caption="🎨 *Escena*",
            parse_mode="Markdown",
        )
    
    # Actualizar state
    save_state(campaign_id, router.get_updated_state())
```

### 5.2 Registro del handler

```python
# En register_game_handlers() o en __main__ del bot:
app.add_handler(
    MessageHandler(
        filters.TEXT & filters.Prefix("/j "),
        _handle_j_action,
    )
)
```

---

## 6. CASOS DE ESCENA

| Tipo de acción | SceneType | Ejemplo | Drama score |
|----------------|-----------|---------|-------------|
| Ataque/hit | COMBAT | "/j ataco al orco" | 0.6 |
| Ataque/crit | COMBAT | nat_20 | 0.9 |
| Ataque/kill | COMBAT | HP llega a 0 | 0.95 |
| Ataque/miss | COMBAT | falla | 0.3 |
| Skill check/success | EXPLORATION | sigilo, percepción | 0.5 |
| Skill check/fail | EXPLORATION | falla cerradura | 0.2 |
| Diálogo | DIALOGUE | "/j le digo al npc que..." | 0.2 |
| Descubrimiento | STORY_BEAT | encuentras el tesoro | 0.8 |
| Descanso | REST | "/j descansamos" | 0.1 |
| Muerte | STORY_BEAT | personaje muere | 1.0 |

---

## 7. CRITERIOS DE ACEPTACIÓN

```
═══════════════════════════════════════
N1: El DM narra después de cada /j
═══════════════════════════════════════
  [ ] "/j Ataco al dragón" → narración de 2-4 oraciones al grupo
  [ ] La narración incluye el resultado específico (daño exacto)
  [ ] La narración NUNCA contradice el resultado mecánico
  [ ] La narración NUNCA hace una pregunta al final

═══════════════════════════════════════
N2: Templates con datos reales
═══════════════════════════════════════
  [ ] El template usa location, npcs, conditions REALES del state
  [ ] No hardcodear "el dragón" — usar el nombre real del enemigo
  [ ] No hardcodear "el pasillo" — usar la ubicación real

═══════════════════════════════════════
N3: LLM mode como upgrade
═══════════════════════════════════════
  [ ] Si hay MINIMAX_API_KEY → usa LLM para generar narración
  [ ] Si NO hay key → usa template mode
  [ ] El switch es transparente para el usuario
  [ ] El LLM respeta el world state (no inventa)

═══════════════════════════════════════
N4: Imagen automática en escenas dramáticas
═══════════════════════════════════════
  [ ] Críticos (nat_20) → disparan imagen (score 0.9+)
  [ ] Kills → disparan imagen (score 0.95+)
  [ ] Descubrimientos importantes → pueden disparar imagen (score 0.7+)
  [ ] Fallos triviales → NO disparan imagen (score < 0.3)
  [ ] Configuración "free on/off" es respetada

═══════════════════════════════════════
N5: Performance
═══════════════════════════════════════
  [ ] Narración template < 100ms
  [ ] Narración LLM < 5s
  [ ] Imagen Pollinations < 5s
  [ ] Imagen MiniMax < 90s (async, no bloquea)

═══════════════════════════════════════
N6: Idioma
═══════════════════════════════════════
  [ ] Todo en español (narración + mecánica)
  [ ] LosDC, HP, daño → usar notación internacional pero texto en español
  [ ] Emoji de ayuda para separar mecánica de narración
```

---

## 8. PLAN DE IMPLEMENTACIÓN (pasos concretos)

```
PASO 1 — action_router.py nuevo
  → Crear router que tome action_text y devuelva ActionResult
  → Solo con templates (sin LLM) para probar primero
  → Test: invocar router desde ipython con state mock

PASO 2 — Wire en telegram_handler.py
  → Agregar MessageHandler para /j
  → Conectar router → broadcast al grupo
  → Test: enviar "/j ataco al dragón" en grupo de test

PASO 3 — Mejoras en narrative_generator.py
  → Agregar method _generate_with_llm() con MiniMax
  → Mejorar fill_template para usar datos reales del state
  → Test: con/sin API key produce resultados distintos

PASO 4 — Image auto-trigger
  → Conectar scene_classifier.should_trigger_image() → image_generator
  → Configuración free on/off respetada
  → Test: crítica dispara imagen vs fail no la dispara

PASO 5 — End-to-end test
  → Secuencia: "/j ataco" → narración → dado → resultado → imagen
  → Verificar que el state se actualiza correctamente
```

---

## 9. CONFIGURACIÓN

```python
# state_manager o campaign_settings
CAMPAIGN_DEFAULTS = {
    "narrative": {
        "mode": "llm",        # "llm" | "template"
        "tone": "cinematic",   # "cinematic" | "humor" | "dark" | "epic"
        "image_auto": True,
        "image_provider": "pollinations",  # "pollinations" | "minimax"
    }
}

# /configuracion narrativa llm on/off
# /configuracion imagen_auto on/off
```

---

## 10. COSTOS Y RIESGOS

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| LLM inventa resultados | Media | Alto | El mechanic_inline viene DEL ENGINE, no del LLM. LLM solo narra |
| LLM cost alto | Baja | Medio | Template mode como fallback; caching de narraciones |
| Imagen tarda 90s | Baja | Bajo | Async, se envía cuando está lista |
| Race condition /j simultáneos | Baja | Medio | Timestamp ordering, no es crítico en async |
| State se desync | Baja | Alto | Tests con state real, validación post-save |
