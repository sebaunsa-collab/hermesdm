# SPEC — Sistema Extendido de Acciones (/j)

## 1. Objetivo

Extender el sistema actual de acciones (`ActionRouter` + `j_action_handler`) para cubrir las 20 acciones comunes de D&D 5e, con keyword matching inteligente, resolución mecánica correcta, y estados persistentes (help/disengage/dodge) que duran hasta el siguiente turno del personaje.

---

## 2. Contexto

- **Estado actual:** `ActionRouter` maneja attack/skill/cast/dialogue/rest/explore con keywords simples y resolución de dados. El `j_action_handler` broadcast el resultado al grupo.
- **Problema:** Faltan 14 acciones (disengage, dash, hide, help, dodge, ready, shove, investigate, persuade/deceive, intimidate, medicine, knowledge, survival, sleight of hand, acrobatics/athletics, animal handling, use object).
- **Beneficio esperado:** Sistema completo tipo D&D 5e donde los jugadores pueden hacer cualquier acción standard con mecánica correcta.

---

## 3. Requisitos

### R1: Extender keywords del ActionRouter (must-have)

Agregar keywords para las 14 acciones nuevas:

| Acción | Keywords en español | Keywords en inglés |
|--------|-------------------|-------------------|
| Disengage | "desenganchar", "desengage", "escabullirse", "evadir" | "disengage" |
| Dash | "correr", "dash", "esprintar", "desbordar" | "dash" |
| Hide | "esconderse", "ocultarme", "hide", "escondeme" | "hide" |
| Help | "ayudar", "help", "asistir", "apoyar" | "help" |
| Dodge | "esquivar", "dodge", "evadir", "defender" | "dodge" |
| Ready | "preparar", "ready", "esperar", "si cuando" | "ready" |
| Use Object | "usar", "objeto", "poción", "pocion", "herramienta" | "use", "potion", "tool" |
| Shove | "empujar", "derribar", "shove", "tirar al suelo" | "shove", "prone" |
| Investigate | "investigar", "buscar", "investigar", "escrutar" | "investigate", "search" |
| Persuade | "persuadir", "convencer", "diplomacia", "persuade" | "persuade", "convince" |
| Deceive | "engañar", "mentir", "engaño", "deceive" | "deceive", "lie" |
| Intimidate | "intimidar", "amenazar", "asustar" | "intimidate", "threaten" |
| Medicine | "medicina", "sanar", "estabilizar", "primeros aux" | "medicine", "heal", "stabilize" |
| History | "historia", "recordar", "historia" | "history" |
| Arcana | "arcano", "magia", "arcanos" | "arcana" |
| Religion | "religión", "dios", "religión" | "religion" |
| Survival | "supervivencia", "rastrear", "orientarme", "cazar" | "survival", "track", "hunt" |
| Sleight of Hand | "juego de manos", "robar", "prestidigitación" | "sleight", "pickpocket" |
| Athletics | "atletismo", "saltar", "escalar", "nadar" | "athletics", "jump", "climb" |
| Acrobatics | "acrobacias", "equilibrio", "voltereta" | "acrobatics", "flip" |
| Animal Handling | "animales", "montar", "cabalgar", "calmar bestia" | "animal", "mount", "calm" |

**Prioridad de match:** attack > cast > shove > hide > disengage > dodge > help > dash > ready > intimidate > persuade > deceive > skill (persuasion/arcana/history/religion/survival/sleight/athletics/acrobatics/animal/investigate/medicine/use object)

### R2: Resolution mecánica de cada acción (must-have)

| Acción | Resolution |
|--------|-----------|
| Attack | d20 + STR/DEX mod + prof vs AC 14 (o del NPC) |
| Cast | d20 + INT mod + prof vs spell save DC |
| Disengage | Sin tirada. Marca `char.has_disengaged = True` hasta sig turno |
| Dash | Sin tirada. Marca `char.has_dashed = True` hasta sig turno |
| Hide | Stealth check (DEX) vs passive perception del enemigo |
| Help | Sin tirada. Marca `char.is_helping = True` hasta sig turno (otorga ventaja al aliado en su próximo ataque) |
| Dodge | Sin tirada. Marca `char.is_dodging = True` hasta sig turno (enemigos tienen desventaja vs este char) |
| Ready | Sin tirada. Guarda `pending_ready = {"action": "...", "trigger": "..."}` hasta trigger o fin del turno |
| Use Object | Sin tirada. Consume 1 uso del objeto si aplica |
| Shove | Athletics check (STR) vs enemy's Athletics or Acrobatics (DC 15 por defecto) — puede knock prone o push 5ft |
| Investigate | Investigation check (INT) vs DC 15 |
| Persuade | Persuasion check (CHA) vs DC 12 (social) |
| Deceive | Deception check (CHA) vs DC 12 (social) |
| Intimidate | Intimidation check (CHA) vs DC 14 (social) |
| Medicine | Medicine check (WIS) vs DC 15 — estabiliza o restaura 1d4 HP |
| History | History check (INT) vs DC 12 — recordar información |
| Arcana | Arcana check (INT) vs DC 12 — recordar sobre magia |
| Religion | Religion check (INT) vs DC 12 — recordar sobre dioses |
| Survival | Survival check (WIS) vs DC 13 — rastrear o navegar |
| Sleight of Hand | Sleight of Hand check (DEX) vs DC 14 — robar o usar manos |
| Athletics | Athletics check (STR) vs DC 12 — saltar, escalar, nadar |
| Acrobatics | Acrobatics check (DEX) vs DC 12 — equilibrio, evadir |
| Animal Handling | Animal Handling check (WIS) vs DC 13 — calmar o dirigir animales |

### R3: Estados persistentes en Character (must-have)

Agregar a la clase `Character`:

```python
class Character:
    # ... existing fields ...

    # Acciones que duran hasta el siguiente turno del personaje
    has_disengaged: bool = False
    has_dashed: bool = False
    is_helping: bool = False
    helping_target: str | None = None  # nombre del aliado que recibe help
    is_dodging: bool = False
    is_hiding: bool = False

    # Ready action
    pending_ready: dict | None = None  # {"action": "...", "trigger": "..."}

    # Inventory tracking
    object_uses: dict | None = None  # {"potion": 2, "torch": 5}
```

Los flags `is_dodging`, `has_disengaged`, `is_helping` se resetean cuando el personaje recibe su próximo turno (en `_advance_turn_with_countdown` o equivalente).

### R4: Narrative spec para cada acción (must-have)

Formato del mensaje broadcast al grupo:

**Acciones con tirada:**
```
🎲 *{nombre_personaje} {verbo_de_accion}*
{descripcion_de_accion}
──────────────────────
🎯 {mecánica_inline}
──────────────────────
📖 {narrativa_generada}
```

**Acciones sin tirada (disengage, dash):**
```
🟡 *{nombre_personaje} {accion}*
{descripcion_de_accion}
──────────────────────
{narrativa_generada}
```

**Acciones de ayuda/influencia (persuade, intimidate):**
```
🎭 *{nombre_personaje} {accion}*
"{dialogo_o_descripcion}"
──────────────────────
🎯 {mecánica_inline}
──────────────────────
📖 {narrativa_generada}
```

### R5: AI interpretation fallback (should-have)

Cuando el texto de `/j` no matchea ninguna keyword con certeza:

```
/act intento atravesar el agua helada sin hacer ruido usando las rocas como cobertura
```

El sistema no encuentra keywords claras → usa MiniMax para:
1. Clasificar la acción → mappear a un action_type del sistema
2. Determinar la habilidad (STR/DEX/INT/WIS/CHA)
3. Definir DC apropiado
4. Generar narrativa descriptiva

Prompt:
```
Clasificá esta acción de D&D 5e:
"{action_text}"

Devolvelo en JSON:
{
  "action_type": "attack|skill|cast|disengage|dash|hide|help|dodge|ready|shove|persuade|deceive|intimidate|investigate|medicine|knowledge|survival|sleight|athletics|acrobatics|animal|use_object|explore",
  "ability": "str|dex|int|wis|cha",
  "dc": 10-20,
  "description": "descripción corta de la acción",
  "narrative_hint": "pista para la generación narrativa"
}
```

### R6: Reset de estados persistentes (must-have)

En `_advance_turn_with_countdown`, cuando avanza al siguiente turno del personaje:
- Reset `has_disengaged = False`
- Reset `has_dashed = False`
- Reset `is_helping = False`
- Reset `helping_target = None`
- Reset `is_dodging = False`
- Reset `is_hiding = False`
- Clear `pending_ready` si no se activó

### R7: Ready action trigger system (should-have)

Cuando un personaje hace `/act preparar acción` (ready):
1. Se guarda `char.pending_ready = {"action": "...", "trigger": "..."}`
2. Se marca el turno como "ready action pending"
3. Cuando OTRO personaje actúa, se checkea si su acción matchea el trigger
4. Si matchea → se resuelve la ready action primero
5. Si no se activa antes del próximo turno del personaje → se pierde

---

## 4. Arquitectura

### Archivos a modificar

1. **`bot/dice_engine.py` o `bot/character.py`** — agregar campos de estado persistente al Character
2. **`adapters/mode_b/action_router.py`** — extender `_parse()` con 20 keywords y `_resolve()` con 20 resolution methods
3. **`adapters/mode_b/action_router.py`** — nuevo `_resolve_social()`, `_resolve_physical()`, `_resolve_knowledge()`
4. **`bot/telegram_handler.py`** — reset estados persistentes en `_advance_turn_with_countdown()`
5. **`adapters/mode_b/action_router.py`** — `_interpret_with_ai()` para fallback de acciones no clasificadas

### Flujo de datos

```
/act <acción libre>
  → j_action_handler (valida, busca personaje)
    → ActionRouter.route(action_text)
      → _parse() [keywords → action_type + params]
        → _resolve() [d20 + mods vs DC → success/damage/effect]
          → _classify() [SceneType]
            → _build_context()
              → _generate_narrative() [NarrativeGenerator o template]
      → ActionResult(narrative, mechanic_inline, image_url)
    → broadcast al grupo
```

---

## 5. Edge cases

| Situación | Comportamiento |
|-----------|----------------|
| Player hace /act hide dos veces seguidas | Segunda vez pide "Ya te estás escondiendo" |
| Player hace /act dodge cuando YA está dodging | "Ya estás en modo dodge. Necesitás actuar para salir." |
| Player hace /act dash pero no tiene disengage y se mueve | Puede provoke opportunity attack — se le avisa |
| Player hace /act help y luego /act attack en el mismo turno | El help se consumió pero el flag persiste hasta el turno del aliado |
| Ready action no se activa en 1 round | Se pierde, se avisa al jugador |
| Action no matchea ninguna keyword | AI fallback para clasificar, o mensaje "No entendí esa acción. Usá /help para ver las acciones disponibles." |
| /act durante countdown de combate | Resuelve acción normally |
| /act durante exploración (sin combate activo) | Funciona, scene_type = EXPLORATION |

---

## 6. Out of scope

- Movimiento en grid/tactical map (eso es feature separate)
- Acciones bonus (BA) y reactions (son separate de las 20 standard)
- Legendary actions / lair actions
- Spell slots y resource management (para spells)
- HP tracking automático por daño del sistema (ya existe)

---

## 7. Verificación

- [ ] `/act esconderse detrás del barril` → stealth check + narrativa
- [ ] `/act corro hacia la puerta` → dash flag + sin tirada
- [ ] `/act help a Valdric` → help flag en personaje
- [ ] `/act dodge` → dodge flag en personaje
- [ ] Al avanzar turno del personaje → flags se resetean
- [ ] `/act intimidar al guardia` → intimidation check vs DC 14
- [ ] `/act me preparo para atacar si el dragón mueve las alas` → ready action guardada
- [ ] `/act uso poción` → consume potion si tiene
- [ ] `/act investigo la habitación` → investigation check vs DC 15
- [ ] Acción ambigua → AI classification fallback
