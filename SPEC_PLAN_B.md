# SPEC: HermesDM — Plan B (Integración Simple via Skill)

## Status: PENDIENTE APROBACIÓN (Sherman dice sí → se implementa)

---

## 1. Definición del Componente

**¿Qué es HermesDM?**

Es una **skill** de Hermes Agent — un conjunto de handlers de Telegram + lógica de juego (dados, combate, personajes, narrativa) que se activa cuando el chat_id corresponde al grupo de D&D.

**No es:**
- Un agent separado (no necesita subprocess con LLM propio)
- Un mode (no hay toggle, solo contexto de chat)

**Es:**
- Una skill — handlers + módulos Python que viven en `/home/hermes/hermesdm/bot/`
- Los comandos existen o no según el `chat_id` de origen

---

## 2. Arquitectura

```
Telegram
    │
    ├── Chat 1:1 Sherman (chat_id: 7267426377)
    │       └── @Hermeciano_bot
    │           ├── /ask, /model, /skills... → handlers core de Hermes Agent
    │           └── /newgame, /j, /roll... → IGNORED (unknown command)
    │
    └── Grupo D&D (chat_id: -1003916745496)
            └── @Hermesciano_bot
                ├── /newgame, /j, /roll, /me... → HermesDM handlers
                ├── texto libre → _echo_handler ("usá /j")
                └── #comentario → IGNORED (OOC)

    Los módulos de juego (dice_engine, combat_engine, etc.) se importan via
    execute_code o como módulos locales. El LLM solo interviene para
    generar narrativa (NarrativeGenerator).
```

**Sesiones completamente aisladas por chat_id** — el gateway routingea automáticamente.

---

## 3. Handlers del Grupo

Ubicación: `bot/telegram_handler.py`

### 3.1 Handlers D&D

| Comando | Función | Estado |
|---------|---------|--------|
| `/newgame` | `cmd_newgame` | Ya existe |
| `/join` | `cmd_join` | Ya existe |
| `/roll <XdY+Z>` | `cmd_roll` | Ya existe |
| `/j <acción>` | `_j_action_handler` | Mover de `adapters/mode_b/action_router.py` |
| `/me <acción>` | `cmd_me` | Ya existe |
| `/attack <target>` | `cmd_attack` | Ya existe |
| `/cast <spell> <target>` | `cmd_cast` | Ya existe |
| `/skill <skill_name>` | `cmd_skill` | Ya existe |
| `/status` | `cmd_status` | Ya existe |
| `/hp` | `cmd_hp` | Ya existe |
| `/inventory` | `cmd_inventory` | Ya existe |
| `/talk <npc>` | `cmd_talk` | Ya existe |
| `/map` | `cmd_map` | Ya existe |
| `/quests` | `cmd_quests` | Ya existe |
| `/recap` | `cmd_recap` | Ya existe |
| `/save` | `cmd_save` | Ya existe |
| `/campaign` | `cmd_campaign` | Ya existe |
| `/help` | `cmd_help` | Ya existe (adaptar para grupo) |

### 3.2 Echo Fallback

Handler que atrapa todo texto que no matcheó con los anteriores:

```python
async def _echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""

    # OOC comments — ignore silently
    if text.startswith("#"):
        return

    cs: ChatState = context.chat_data.get("_hermes_state", ChatState())

    if cs.active_campaign:
        await update.message.reply_text(
            "🎲 Usá /j antes de tu acción.\n"
            "Ejemplo: /j ataco al dragón\n"
            "Para acciones sin dado: /me <acción>"
        )
        return

    await update.message.reply_text(
        "No entendí eso. Escribí /help para ver los comandos disponibles."
    )
```

### 3.3 Filtro de Chat

Todos los handlers D&D incluyen un guard al inicio:

```python
ALLOWED_GROUP_ID = -1003916745496

async def cmd_j(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        return  # No responde en chats que no son el grupo
    # ... resto del handler
```

Alternativamente, registrar los handlers SOLO para el grupo usando `filters.Chat(ALLOWED_GROUP_ID)`:

```python
app.add_handler(
    CommandHandler("j", cmd_j, filters.Chat(ALLOWED_GROUP_ID))
)
```

---

## 4. Módulos de Juego a Usar

```python
import sys
sys.path.insert(0, '/home/hermes/hermesdm')

from bot.dice_engine import roll
from bot.combat_engine import resolve_attack, resolve_spell, apply_damage
from bot.turn_manager import start_combat, next_turn, combat_summary
from bot.character_sheet import create_character, Character
from adapters.mode_b.action_router import ActionRouter, SceneType
from state.state_manager import load_state, save_state
from dm.world_builder import create_campaign
from dm.narrative_generator import NarrativeGenerator
```

---

## 5. Flujo del Comando /j (核心 del gameplay)

```
Jugador en grupo → "/j ataco al dragón con mi espada"

    1. _j_action_handler recibe el mensaje
           └── Verifica chat_id = grupo D&D
           └── Verifica campaña activa
           └── Busca personaje del jugador

    2. ActionRouter.route(intent, action_text)
           ├── _parse: "ataco" → attack intent, target="dragón"
           ├── _resolve_attack:
           │     roll("1d20") → 17
           │     attack_bonus = str_mod + prof = +5
           │     total = 22 vs AC 16 → HIT
           │     roll("1d8") → 6 damage
           ├── _classify: attack → COMBAT
           └── _build_context + _generate_narrative

    3. Respuesta al grupo:
           🎲 Valdric ataca al dragón con su espada
           ⚔️ ¡Impacto! D20: 17+5=22 vs AC 16 — 6 damage al dragón

           "El acero corta el aire cuando Valdric embiste al dragón.
            La criatura ruge de dolor mientras la sangre mancha el piso
            de la caverna."
```

---

## 6. Chat State (estado por grupo)

```python
@dataclass
class ChatState:
    active_campaign: str | None = None
    characters: dict[str, Character] = field(default_factory=dict)
    combat: CombatState | None = None
    world_state: dict | None = None
```

El `ChatState` se guarda en `context.chat_data` de python-telegram-bot. Persistencia en `~/.hermes/hermesdm/campaigns/{campaign_id}/`.

---

## 7. Integración con Hermes Agent (Gateway)

El gateway de Hermes Agent (`gateway/run.py`) tiene `ChatData` por sesión. Cuando `@Hermesciano_bot` recibe un mensaje del grupo:

1. Gateway detecta `chat_id = -1003916745496`
2. Busca/crea sesión `group:-1003916745496`
3. El message handler del grupo (`bot/telegram_handler.py`) procesa
4. Los handlers D&D generan respuesta y `await update.message.reply_text(...)`
5. Gateway envía la respuesta al grupo

**No se usa `execute_code` para los módulos** — se importan directamente como cualquier módulo Python. El REPL del gateway no está involucrado.

---

## 8. Archivos a Modificar

| Archivo | Cambio |
|---------|--------|
| `bot/telegram_handler.py` | Agregar filtro `filters.Chat` a todos los handlers D&D, adaptar `_echo_handler`, mover `_j_action_handler` de `adapters/mode_b/` |
| `adapters/mode_b/action_router.py` | Mover lógica relevante a `bot/telegram_handler.py` o mantener como import |
| `~/.hermes/config.yaml` | Agregar `allowed_chat_ids: [-1003916745496]` si no está |

---

## 9. Tests

```bash
cd /home/hermes/hermesdm
pytest tests/ -q  # debe mantener ≥266 tests passing

# Test específico del filtro de grupo
python3 -c "
from bot.telegram_handler import cmd_j, ChatState
from unittest.mock import AsyncMock, MagicMock
import asyncio

# Simular mensaje del grupo
msg = MagicMock()
msg.text = '/j ataco al dragon'
msg.reply_text = AsyncMock()
update = MagicMock()
update.message = msg
update.effective_chat.id = -1003916745496
update.effective_user.first_name = 'Valdric'
ctx = MagicMock()
ctx.args = ['ataco', 'al', 'dragon']
ctx.chat_data = {'_hermes_state': ChatState()}
ctx.chat_data['_hermes_state'].active_campaign = 'test-campaign'

asyncio.run(cmd_j(update, ctx))
print('OK — handler respondió')
"
```

---

## 10. Secuencia de Implementación

```
[s1] Agregar @Hermesciano_bot al grupo de testing
[s2] Verificar allowed_chat_ids en config.yaml
[s3] Agregar filtro filters.Chat a todos los handlers D&D
[s4] Mover/adaptar _j_action_handler
[s5] Actualizar _echo_handler con mensaje "usá /j"
[s6] Correr tests: pytest -q
[s7] Test manual en grupo real
```

---

## 11. Criterios de Éxito

- [ ] `@Hermesciano_bot` recibe mensajes del grupo D&D
- [ ] `/newgame` en el grupo inicia campaña (ignora en 1:1)
- [ ] `/j ataco al dragon` procesa y responde en el grupo
- [ ] `texto libre` en el grupo responde "usá /j"
- [ ] `#comentario` en el grupo se ignora silenciosamente
- [ ] `/newgame` en 1:1 dice "Unknown command"
- [ ] Sherman 1:1 funciona normalmente durante la partida
- [ ] Suite de tests pasa (≥266)
