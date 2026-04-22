# HERMESDM — SPEC OFICIAL
## Sistema Unificado de DM Asistido por IA
### Modos B (Async) + D (Sync) — Versión 1.0

```
═══════════════════════════════════════════════════════════════════════════════
STATUS: DRAFT — Pendiente aprobación de Sherman
═══════════════════════════════════════════════════════════════════════════════
```

---

## RESUMEN EJECUTIVO

HermesDM es un sistema que convierte a Hermes Agent en un Dungeon Master de D&D 5e.
Corre enteramente sobre Telegram como interfaz. Tiene dos modalidades de juego
que comparten el mismo motor de juego:

```
HERMESDM
├── MODO B — Async Social D&D
│   └── Party juega cuando puede, desde cualquier lugar, via Telegram Groups
│
└── MODO D — Turn-Based Sync D&D
    └── Party juega en vivo, misma mesa, via Telegram Groups + Cámara
```

**Toda la magia sucede en Telegram.** No hay app separada. No hay AR complejo.
El teléfono de un jugador es la "pantalla del DM" y el canal de comunicación.

---

## CONTEXTO

- **Por qué existe:** Ningún DM de IA actual permite multiplayer real async.
  Los bots de D&D son individuales o requieren software adicional.
  HermesDM resolve esto con Telegram Groups como interfaz natural.
- **Problema actual:** Construimos un bot standalone (hermesdm) pero Hermes
  Agent no es el DM — solo lo codió. No cumple con el goal original.
- **Beneficio esperado:** Hermes Agent ES el DM, usa sus propios recursos
  (API keys, tools, skills) y corre como skill dentro de su propia sesión.

---

## ARQUITECTURA GENERAL

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         HERMES AGENT (EL DM)                            │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────────┐  │
│  │ hermesdm/    │   │ hermesdm/    │   │ hermesdm/                  │  │
│  │ skill/       │   │ dm/          │   │ bot/                       │  │
│  │ SKILL.md     │   │ narrative_    │   │ dice_engine.py            │  │
│  │              │   │ generator.py  │   │ combat_engine.py          │  │
│  │ Entry point  │   │              │   │ character_sheet.py         │  │
│  │ del DM       │   │ DM Brain      │   │ skill_checks.py            │  │
│  │              │   │ (LLM calls)   │   │ turn_manager.py             │  │
│  │              │   │              │   │ state_validator.py          │  │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬─────────────────┘  │
│         │                  │                      │                   │
│         └──────────────────┴──────────────────────┘                   │
│                            │                                           │
│                   ┌────────▼────────┐                                 │
│                   │ hermesdm/       │                                 │
│                   │ game_engine/    │                                 │
│                   │ core.py         │  ← SHARED entre B y D          │
│                   │                 │                                 │
│                   │ - dice          │                                 │
│                   │ - combat        │                                 │
│                   │ - world_state   │                                 │
│                   │ - characters    │                                 │
│                   │ - NPCs          │                                 │
│                   └────────┬────────┘                                 │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐          ┌─────────▼────────┐
     │   MODO B        │          │   MODO D         │
     │ Async Social    │          │ Turn-Based Sync  │
     │                 │          │                  │
     │ - /j prefix     │          │ - Initiative queue│
     │ - DM Privacy    │          │ - Turn timer     │
     │ - Cola acciones │          │ - Round tracking  │
     │ - Sin timer     │          │ - Camera Vision   │
     └────────┬────────┘          └─────────┬────────┘
              │                             │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼────────┐
                    │  TELEGRAM       │
                    │  (Input/Output) │
                    │                 │
                    │ Group: @dragons │
                    │ private: 726742 │
                    └─────────────────┘
```

---

## SHARED CORE — game_engine/core.py (NUEVO)

El motor de juego existe YA en hermesdm/ pero necesita ser refactorizado
en un módulo central que sea importable por ambos modos.

### Estructura de archivos (reorganización)

```
hermesdm/
├── game_engine/              # MOTOR COMPARTIDO (NUEVO)
│   ├── __init__.py
│   ├── core.py               # Clases base: Character, NPC, CombatState, World
│   ├── dice.py               # roll(), advantage/disadvantage, crits
│   ├── combat.py             # attack(), damage(), spells, saving_throws
│   ├── skills.py             # skill_check(), ability_checks
│   ├── world.py              # WorldState, NPC memory, faction tracking
│   └── serializers.py        # to_json(), from_json()
│
├── adapters/                 # MODOS B y D (NUEVO)
│   ├── __init__.py
│   ├── mode_b/
│   │   ├── __init__.py
│   │   ├── action_queue.py   # Cola de acciones async
│   │   ├── group_handler.py  # Filtro /j + routing
│   │   └── privacy.py        # DM al player, broadcast al grupo
│   └── mode_d/
│       ├── __init__.py
│       ├── turn_engine.py    # Initiative queue, round tracking
│       ├── timer.py          # Turn timer con callback
│       └── camera.py         # Vision analysis de la mesa
│
├── skill/                    # INTEGRACIÓN HERMES AGENT (NUEVO)
│   ├── SKILL.md             # Esta skill
│   ├── dm_skill.py          # Funciones expuestas a Hermes
│   └── templates/            # System prompts, scene templates
│
├── bot/                      # EXISTENTE — refactorizar imports
├── dm/                       # EXISTENTE — narrative + image
├── state/                    # EXISTENTE — state_manager + templates
├── data/campaigns/           # EXISTENTE — JSON persistence
└── tests/                    # EXISTENTE — 236 tests
```

### Clases del Core (existentes, solo re-organizar)

```python
# game_engine/core.py
class Character:
    id, name, class_type, level, hp, max_hp, ac
    abilities: {str,dex,con,int,wis,cha}
    skills: list[Skill]
    inventory: list[Item]
    conditions: list[str]
    death_saves: {successes: int, failures: int}
    spells: list[Spell]  # por class

class NPC(Character):
    disposition: str  # friendly/hostile/neutral
    memory: list[str]  # interacciones pasadas
    secret: str  # objetivo oculto

class CombatState:
    active: bool
    initiative_order: list[str]  # [player_id, ...]
    current_turn: int
    current_round: int
    conditions: dict[str, list[str]]  # npc_id → [conditions]

class WorldState:
    campaign_id: str
    campaign_name: str
    setting: str  # fantasy/dungeon/tavern/horror/scifi
    characters: dict[str, Character]
    npcs: dict[str, NPC]
    combat: CombatState | None
    quests: list[Quest]
    timeline: list[WorldEvent]
    factions: dict[str, str]  # faction_id → status
```

---

## MODO B — ASYNC SOCIAL D&D

### Concepto

Party distribuida geográficamente. Cada jugador juega cuando puede.
No necesitan coordinar horario. La partida avanza según las acciones
de cada uno, procesadas en orden de llegada.

### Experiencia del jugador

```
 GRUPO TELEGRAM: "Party Dragón Negro" (5 jugadores)
──────────────────────────────────────────────────────────

 [Chat casual — Hermes ignora]
 Pedro: Che ya viste el final de that show?
 Ana: No spoiler!
 Miguel: Necesito más café

 [Hernán juega desde su casa, 2am]
 Hernán: /j Ataco al dragón con mi espada

 Hermes → GRUPO:
 🐉 ¡El dragón recibe 22 damage! (Golpe crítico)
 HP restante: 85 → 63
 El dragón cae sobre una rodilla pero se recupera.

 Hermes → DM a Hernán (solo él ve):
 ❤️ Hernán: HP 45/52 | Condición: None
 🎒 Inventario: Espada larga +2, Poción de curación x1

 [Al día siguiente, Ana juega]
 Ana: /j Uso sigilo para acercarme al dragón

 Hermes → GRUPO:
 🥷 Ana se mueve entre las sombras...
 DC 15 Stealth: 18 ✅ Éxito

 [Leo no está online, Hernán lo resuelve]
 Hernán: /j Leo atacó al dragón por la izquierda

 Hermes → GRUPO:
 ⚔️ ¡Leo ataca desde la retaguardia! 15 damage
 HP del dragón: 63 → 48

 [Hernán sigue jugando solo]
 Hernán: /j Termino mi turno

 Hermes → GRUPO:
 ⏳ Turno de Hernán terminado.
 🕐 Última acción: hace 2 horas.
```

### Comandos Modo B

| Comando | Quienlo usa | Visible para | Descripción |
|---------|-------------|--------------|-------------|
| `/j <acción>` | Cualquier jugador | Grupo | Acción de juego |
| `/mj <acción>` | DM (Hermes) | Grupo | Narración del DM |
| `/roll <dado>` | Cualquier jugador | Grupo | Tiro de dados |
| `/attack <target> [adv\|dis]` | Jugador | Grupo | Encola ataque — inicia combate automático si no hay |
| `/startcombat [enemigo1] [enemigo2]` | Jugador | Grupo | Inicia combate manualmente con enemigos |
| `/begincombat` | Jugador | Grupo | Alias de /startcombat |
| `/endcombat` | Jugador | Grupo | Termina combate activo + cancela timer |
| `/endturn` | Jugador | Grupo | Pasa al siguiente turno + reinicia timer |
| `/status` | Jugador | Solo él (DM) | Su hoja de personaje |
| `/hp` | Jugador | Solo él (DM) | HP actual |
| `/inventory` | Jugador | Solo él (DM) | Inventario |
| `/talk <npc>` | Jugador | Grupo | Hablar con NPC |
| `/map` | Jugador | Grupo | Describir ubicación |
| `/quests` | Jugador | Grupo | Misiones activas |
| `/recap` | Jugador | Grupo | Resumen de historia |

### Requirements MODO B

```
═══════════════════════════════════════
R1: Prefijo /j para acciones de juego
═══════════════════════════════════════
Descripción:
  Los mensajes que comienzan con "/j " en el grupo son interpretados
  como acciones de juego. Todo lo demás Hermes lo ignora o responde
  como chat normal.

Criterio de aceptación:
  [ ] Mensaje "/j Ataco al dragón" → procesa como acción de combate
  [ ] Mensaje "Che jugamos mañana?" → Hermes NO procesa como acción
  [ ] Mensaje "/j le pego a Juan por la espalda" → permitido (PvP)
  [ ] Mensaje "/j  + espacios" → debe pedir retry (vacío)
  [ ] /j sin argumento → error "Usá /j <tu acción>"

Risks: Ninguno
Priority: MUST HAVE

═══════════════════════════════════════
R2: Privacidad de HP/Status
═══════════════════════════════════════
Descripción:
  HP, inventario y status de cada jugador solo son visibles para
  ese jugador via DM directo, no en el grupo.

Criterio de aceptación:
  [ ] /status → llega solo al jugador (DM Telegram, no grupo)
  [ ] /hp → llega solo al jugador
  [ ] /inventory → llega solo al jugador
  [ ] En grupo NO se filtra accidentalmente HP de otro jugador
  [ ] Hermes detecta player_id del mensaje y busca su personaje

Risks: Ninguno
Priority: MUST HAVE

═══════════════════════════════════════
R3: Narración broadcast al grupo
═══════════════════════════════════════
Descripción:
  El resultado de las acciones se comparte en el grupo para todos.
  Incluye: daño recibido, narración del DM, cambios de estado.

Criterio de aceptación:
  [ ] "/j Ataco al dragón" → resultado visible para TODOS en el grupo
  [ ] La narración incluye flavor text del DM (no solo números)
  [ ] Múltiples "/j" en secuencia → se resuelven en orden de llegada
  [ ] Si un jugador no está online, su acción se procesa cuando llegue

Risks: Race condition si 2 mandan /j simultáneo → usar timestamp
Priority: MUST HAVE

═══════════════════════════════════════
R4: DM Narration (Hermes como DM)
═══════════════════════════════════════
Descripción:
  Hermes genera narración rica para cada acción. Si no hay API key,
  usa templates procedurales.

Criterio de aceptación:
  [ ] Cada acción genera al menos 1-2 oraciones de narración
  [ ] Narra el resultado específico ("el dragón cae" no "el dragón recibe daño")
  [ ] Incluye detalles del world state ("Estás en el Throne Room, hay 3 NPC observando")
  [ ] Si no hay LLM → usa template mode ("Un resultado contundente")

Risks: LLM cost → solo narrar acciones principales, no cada dado
Priority: MUST HAVE

═══════════════════════════════════════
R5: World State compartido
═══════════════════════════════════════
Descripción:
  Todas las acciones modifican un estado mundial compartido.
  Los cambios persisten entre sesiones.

Criterio de aceptación:
  [ ] HP del dragón baja cuando Hernán ataca
  [ ] Cuando Ana usa sigilo, el world state registra su posición
  [ ] Los NPCs recuerdan interacciones previas
  [ ] El timeline registra todas las acciones de la sesión

Risks: Ninguno (state_manager ya existe)
Priority: MUST HAVE

═══════════════════════════════════════
R6: Creación de campaña + unirse
═══════════════════════════════════════
Descripción:
  Un jugador crea la campaña y los demás se unen con un código.

Criterio de aceptación:
  [ ] Hernán: "/newgame fantasy" → crea campaña + share campaign_id
  [ ] Ana + Leo + Miguel: "/join DRAGON42" → se unen a la campaña
  [ ] Campaign_id visible para todos los joined players
  [ ] Cada jugador recibe un personaje generado según la setting
  [ ] Hermes mantiene mapping: user_id → character_id

Risks: campaign_id puede ser adivinado → usar UUID corto
Priority: MUST HAVE

═══════════════════════════════════════
R7: Configuración de campaña
═══════════════════════════════════════
Descripción:
  Los jugadores pueden configurar difficulty, tone, timer, etc.

Criterio de aceptación:
  [ ] /configuracion free on/off → ASCII vs MiniMax art
  [ ] /configuracion dificultad easy/normal/hard → DC modifier
  [ ] /configuracion tono serious/funny/dark/epic → estilo DM
  [ ] /configuracion timer 0-300 → segundos por turno
  [ ] Config persistida en JSON entre sesiones

Risks: Ninguno
Priority: SHOULD HAVE

═══════════════════════════════════════
R8: Image Generation (dual mode)
═══════════════════════════════════════
Descripción:
  En momentos dramáticos, generación de imagen.

Criterio de aceptación:
  [ ] "free on" → pyfiglet ASCII art (instantáneo, gratis)
  [ ] "free off" → MiniMax image gen (30-90s, pago)
  [ ] Momento dramático definido por scene_classifier
  [ ] Imagen enviada al grupo

Risks: Ninguno (ya existe en codebase)
Priority: SHOULD HAVE
```

---

## MODO D — TURN-BASED SYNC D&D

### Concepto

Party en la misma ubicación física (o conectada por video). Turnos definidos.
Timer activo. Iniciativa clara. Todos ven la misma narrativa al mismo tiempo.
Opcional: cámara apunta a la mesa y Hermes describe lo que ve.

### Experiencia del jugador

```
 GRUPO TELEGRAM: "D&D Night" (4 jugadores + Hermes)
───────────────────────────────────────────────────────────

 Pedro [desde casa, conectado por Telegram]:
    Listo para la sesión

 [La cámara de Hernán apunta a la mesa]
 Hernán sube foto: la mesa con 4 minis, dados, mini del dragón

 Hermes → GRUPO:
 📸 "Veo la mesa del dungeon. 4 heroes en formación de combate:
    🧙 María (wizard), ⚔️ Hernán (fighter), 🏹 Leo (ranger),
    🛡️ Sofía (paladin). En el trono, el Dragón Negro.
    Hay dados espalhados. Hernán: tira iniciativa."

 Leo: /roll 1d20
 Leo: 18

 Hernán: /roll 1d20
 Hernán: 12

 María: /roll 1d20
 María: 7

 Sofía: /roll 1d20
 Sofía: 15

 Hermes → GRUPO:
 🎯 INICIATIVA:
 1. Leo: 18 ✅
 2. Hernán: 12 ✅
 3. Sofía: 15 ✅
 4. María: 7 ✅
 5. Dragón: 10 ✅

 ⏱️ TURNO 1 — RONDA 1
 🕐 Timer: 90 segundos para Leo

 Leo: Ataco al dragón con mi arco
 Leo: /roll 1d20+6
 Leo: 19

 Hermes → GRUPO:
 🏹 ¡ARCO IMPACTANTE! 19+6=25 vs AC 18
 💥 1d8+4 = 10 damage
 🐉 HP: 85 → 75

 ⏱️ TURNO 2 — Hernán (72s restantes)
 Hernán: Apaño la внимание del dragón con mi escudo
 Hernán: /roll 1d20+5

 Hermes → GRUPO:
 🛡️ Hernán brandeja su escudo...
 17 → ¡ÉXITO! El dragón se enfoca en Hernán.

 ⏱️ TURNO 3 — Sofía (55s restantes)
 Sofía: /cast healing_word a Hernán
 Sofía: /roll 1d20

 [La cámara detecta que Sofía tira un dado diferente — verde]
 Hermes → GRUPO:
 ✨ Sofía canaliza poder divino...
 ❤️ Hernán HP: 45 → 52 (recuperó 7 HP)

 ⏱️ TURNO 4 — María (39s restantes)
 María: Fireball al dragón
 María: /roll 1d20
 María: 4

 Hermes → GRUPO:
 🔥 María lanza FIREBALL...
 💥 8d6 = 28 fire damage
 🐉 HP: 75 → 47

 ⏱️ TURNO 5 — Dragón (18s restantes)
 [Hermes no recibe mensaje del dragón — es NPC]
 Hermes → GRUPO:
 🐉 El Dragón Negro respira fuego sobre la formación!
 💀 DC 14 DEX SAVE → cada jugador tira

 Leo: /roll 1d20+2 → 8 (fallo)
 Hernán: /roll 1d20 → 15 (éxito)
 Sofía: /roll 1d20+3 → 12 (fallo)
 María: /roll 1d20 → 19 (éxito)

 Hermes → GRUPO:
 🔥 FIRE BREATH:
 ⚠️ Leo: 28 damage (half = 14) — GRAVEMENTE HERIDO
 ✅ Hernán: 0 damage (saving throw)
 ⚠️ Sofía: 14 damage
 ✅ María: 0 damage (saving throw)

 🏥 HP UPDATE:
 Leo: 31 → 3 (CRÍTICO)
 Sofía: 18 → 4

 ⏱️ TURNO 6 — Leo (66s restantes) [CASI MUERTO]
 Leo: Uso poción de curación

 Hermes → GRUPO:
 🧪 Leo bebe la poción...
 ❤️ Leo HP: 3 → 18

 ═══════════════════════════════════════
 🏆 RONDA 2 — Iniciativa unchanged
 ═══════════════════════════════════════
```

### Comandos Modo D

| Comando | Quien | Visible | Descripción |
|---------|-------|---------|-------------|
| `/roll <dado>` | Jugador | Grupo | Tiro de dados (con iniciativa) |
| `/mj <narración>` | Hermes | Grupo | Narración del DM |
| `/turn` | Jugador | Grupo | Ver cuyo turno es |
| `/initiative` | Hermes | Grupo | Mostrar orden de iniciativa |
| `/camera` | Jugador | Grupo | Subir foto de la mesa (Hermes describe) |
| `/timer` | Hermes | Grupo | Ver tiempo restante del turno |
| `/endturn` | Jugador | Grupo | Terminar turno (pasa al siguiente) |
| `/status [@player]` | Jugador | DM al que pregunta | HP del player mencionado |
| `/map` | Jugador | Grupo | Describir ubicación actual |

### Requirements MODO D

```
═══════════════════════════════════════
R9: Initiative Queue
═══════════════════════════════════════
Descripción:
  Al iniciar combate, cada jugador tira iniciativa (d20).
  Hermes determina el orden. Se respeta estrictaente.

Criterio de aceptación:
  [ ] Al decir "/mj ¡Combate!" Hermes pide iniciativa a todos
  [ ] Cada jugador tira /roll 1d20
  [ ] Hermes muestra tabla ordenada: "1. Leo(18), 2. Hernán(12)..."
  [ ] El turno pasa en orden, sin skips
  [ ] Si un jugador no tira, tiene 60s de timer antes de skip

Risks: Timer muy corto → frustración
Priority: MUST HAVE

═══════════════════════════════════════
R10: Turn Timer
═══════════════════════════════════════
Descripción:
  Cada turno tiene un timer configurable (default 90s).
  Si no actúa, pierde el turno.

Criterio de aceptación:
  [ ] Timer visible en grupo: "⏱️ Turno de Leo — 72s"
  [ ] A los 30s → recordatorio: "⏰ 30s restantes Leo"
  [ ] A los 0s → "⏱️ Leo pierde el turno por timeout"
  [ ] Timer configurable: /configuracion timer 0-300
  [ ] Timer 0 = sin timer (modo relax)

Risks: Timer demasiado corto para jugadores lentos
Priority: MUST HAVE

═══════════════════════════════════════
R11: Turn Queue + Round Tracking
═══════════════════════════════════════
Descripción:
  Sistema claro de turnos y rondas. Visible para todos.

Criterio de aceptación:
  [ ] Hermes muestra: "TURNO 1 — RONDA 2" claramente
  [ ] Cuando todos actuóron → nueva ronda comienza
  [ ] Al final de cada ronda: "═══ RONDA 3 ═══"
  [ ] Combatender puede /endturn voluntariamente

Risks: Ninguno
Priority: MUST HAVE

═══════════════════════════════════════
R12: Camera Vision — Mesa Analysis
═══════════════════════════════════════
Descripción:
  Los jugadores suben fotos de la mesa y Hermes describe lo que ve
  (minis, dados, posición del dragón, etc.)

Criterio de aceptación:
  [ ] /camera → sube foto de la mesa
  [ ] Hermes analiza con vision → describe: "Veo 4 heroes, dragón, dados"
  [ ] Describe cambios: "El dragón perdió HP, hay sangre en el mapa"
  [ ] Si hay dados, menciona: "Hay un d20 mostrando 18"
  [ ] Funciona sin API key (vision description simple)

Risks: Fot blur → descripción incorrecta → usar confidence threshold
Priority: SHOULD HAVE

═══════════════════════════════════════
R13: Dice Recognition (por voz o foto)
═══════════════════════════════════════
Descripción:
  Opcional: Hermes detecta qué número sacó un dado físico via foto.

Criterio de aceptación:
  [ ] Jugador sube foto de dados tirados
  [ ] Hermes usa vision para detectar el dado + número
  [ ] Hermes confirma: "¿Sacaste 18 con el d20? Lo registro."
  [ ] Alternativa: jugador escribe "/roll 1d20" y Hermes confía el número
  [ ] Ambos válidos — uno es más inmersivo

Risks: OCR imperfecto → verificar siempre con el jugador
Priority: NICE TO HAVE

═══════════════════════════════════════
R14: Round/Reward Summary
═══════════════════════════════════════
Descripción:
  Al final de cada ronda, Hermes resume lo que pasó.

Criterio de aceptación:
  [ ] Al final de ronda: resumen de 2-3 oraciones
  [ ] "En esta ronda: Leo usó su arco, Hernán absorbió daño,
       Sofía curó a Hernán, María lanzó fireball"
  [ ] Sirve como recap para el que se perdió

Risks: Ninguno
Priority: SHOULD HAVE
```

---

## COMMON REQUIREMENTS (ambos modos)

```
═══════════════════════════════════════
R15: Character Classes (6)
═══════════════════════════════════════
Descripción: 6 clases D&D 5e simplificadas

Criterio de aceptación:
  [ ] Fighter — más HP, melee attacks
  [ ] Rogue — sneak attack, dex优先
  [ ] Wizard — spellcasting, int-based
  [ ] Cleric — healing spells, wisdom
  [ ] Ranger — ranged + survival
  [ ] Paladin — mix melee + divine smite
  [ ] Cada clase tiene: HP base, AC, saving throws, skills, spells

Risks: Ninguno (ya existe)
Priority: MUST HAVE

═══════════════════════════════════════
R16: Spell System
═══════════════════════════════════════
Descripción: 6 spells básicos por clase

Criterio de aceptación:
  [ ] Fireball, Magic Missile, Healing Word, Cure Wounds,
       Shield of Faith, Sacred Flame
  [ ] Cada spell: name, damage/heal, DC, range, components
  [ ] /cast fireball → tirar damage + narration

Risks: Ninguno (ya existe)
Priority: MUST HAVE

═══════════════════════════════════════
R17: World Settings (5)
═══════════════════════════════════════
Descripción: 5 settingspre-hechas para /newgame

Criterio de aceptación:
  [ ] Fantasy: The Kingdom of Valdris
  [ ] Dungeon: The Sunken Tomb of Khar-Annul
  [ ] Tavern: The Gilt Goblet
  [ ] Horror: Ravenmoor Abbey
  [ ] Sci-fi: Station Erebus-7

Risks: Ninguno (ya existe en state/templates.py)
Priority: MUST HAVE

═══════════════════════════════════════
R18: NPC Memory System
═══════════════════════════════════════
Descripción: NPCs recuerdan interacciones pasadas

Criterio de aceptación:
  [ ] Si Hernán salva a Erna (barkeep), Erna lo recuerda
  [ ] Si Leo ataca a un NPC, el NPC es hostil a Leo después
  [ ] add_npc_memory() validacontradicciones
  [ ] NPC disposition cambia según acciones del party

Risks: Ninguno (ya existe en state_validator.py)
Priority: MUST HAVE

═══════════════════════════════════════
R19: World Continuity
═══════════════════════════════════════
Descripción: Timeline de eventos, factions, persistencia

Criterio de aceptación:
  [ ] add_world_event() registra cada acción importante
  [ ] Faction tracking: thieves_guild puede estar RISING/DECLINING
  [ ] /recap muestra resumen de lo que pasó hasta ahora
  [ ] Estado persiste en JSON entre sesiones

Risks: Ninguno (ya existe)
Priority: MUST HAVE

═══════════════════════════════════════
R20: Hermes Agent IS the DM
═══════════════════════════════════════
Descripción: Hermes Agent recibe mensajes y responde como DM

Criterio de aceptación:
  [ ] Hermes recibe update de Telegram (polling o webhook)
  [ ] Hermes parsea el mensaje (Modo B: /j, Modo D: /roll)
  [ ] Hermes llama al game_engine para resolver
  [ ] Hermes genera narración (LLM o template)
  [ ] Hermes responde por Telegram
  [ ] NINGÚN paso requiere intervención manual

Risks: Polling latency → delay en respuestas
Priority: MUST HAVE
```

---

## HERMES AGENT INTEGRATION

### Cómo Hermes recibe mensajes de Telegram

```
OPCIONES (evaluar):
├── A) Hermes polling cada N segundos
│   ├── Cron job: cada 5s llama Telegram API getUpdates
│   ├── Filtra mensajes ya procesados por last_update_id
│   └── Simple pero polling puede ser costoso
│
├── B) Telegram webhook → Hermes endpoint
│   ├── Telegram llama a URL cuando llega mensaje
│   ├── Hermes tiene HTTP server escuchando
│   └── Más eficiente pero requiere HTTPS endpoint público
│
└── C) Hermes Gateway ya tiene Telegram (VIGENTE)
    └── gateway_state muestra session agent:main:telegram:dm:7267426377
        Sherman Y YO estamos chatting ahora mismo por Telegram
        → EL GATEWAY YA RECIBE LOS MENSAJES
        → Solo necesitamos que Hermes agent-process mensajes
           como acciones de DM cuando el chat_id sea un GROUP
```

** Recomendación: OPCIÓN C** — el gateway ya está conectado.
El problema es que el gateway está en startup_failed para Telegram.
Necesitamos arreglar eso primero.

### Skill Interface (cómo Hermes usa el game engine)

```python
# hermesdm/skill/dm_skill.py — funciones expuestas a Hermes

class HermesDMSkill:
    """Skill que Hermes carga cuando detecta que es una sesión de D&D."""

    @staticmethod
    def new_game(chat_id: str, setting: str) -> str:
        """Crea nueva campaña. Returns campaign_id."""

    @staticmethod
    def join_game(chat_id: str, campaign_id: str, player_name: str) -> str:
        """Un jugador se une a campaña existente."""

    @staticmethod
    def process_action(
        chat_id: str,
        player_id: int,
        action: str,       # texto del "/j ..."
        mode: str          # "B" o "D"
    ) -> ActionResult:
        """Procesa acción del jugador. Returns result para Telegram."""

    @staticmethod
    def get_status(chat_id: str, player_id: int) -> str:
        """Retorna status del personaje (para DM privado)."""

    @staticmethod
    def get_narrative(chat_id: str, scene: str) -> str:
        """Genera narración de escena (usa LLM o templates)."""

    @staticmethod
    def start_combat(chat_id: str) -> str:
        """Inicia modo D (combate con iniciativa)."""

    @staticmethod
    def next_turn(chat_id: str) -> TurnInfo:
        """Avanza al siguiente turno."""

    @staticmethod
    def end_turn(chat_id: str, player_id: int) -> str:
        """El jugador termina su turno."""

    @staticmethod
    def analyze_table(photo_path: str) -> str:
        """Usa vision para describir la mesa (modo D)."""
```

---

## EDGE CASES

### MODO B
- **2 mandan /j simultáneo:** timestamp de llegada al servidor, orden FIFO
- **Jugador se va:** su personaje queda en standby, otro puede usar "/j [nombre] hizo X"
- **HP no puede ser negativo:** se fija en max (max_hp) y min (0)
- **Muerte de personaje:** death saves, si falla 3 → muerto, puede respawnear
- **Narración sin API key:** template mode con placeholders
- **campaign_id errado:** "No encontré esa campaña. Verificá el código."
- **HP muy alto/bajo:** state_validator lo corrige automáticamente

### MODO D
- **Jugador timeout:** pierde turno, se registra "lost_turn: True"
- **Jugador se desconecta:** timer sigue, si vuelve → puede catch up
- **Dados no leídos por cámara:** jugador ingresa manualmente, Hermes confía
- **Turno de NPC:** Hermes narra auto, no necesita input
- **Todos mueren:** game over, opción de restart
- **Timer a 0:** modo relax, sin presión

---

## OUT OF SCOPE

- Voice input (solo texto inicialmente)
- Mapas visuales generados (ASCII art es suficiente)
- AR overlays reales (más allá de cámara + descripción)
- Multiple campaigns simultáneas por same player (futuro)
- Export/import de campaigns
- Battlemap interactivo (D&D Beyond style)
- Roll20 integration

---

## TIEMPO ESTIMADO

| Fase | Descripción | Estimado |
|------|-------------|----------|
| F1 | Fix Telegram gateway + test polling | S |
| F2 | game_engine/core.py refactor + tests | M |
| F3 | MODO B adapter completo + tests | M |
| F4 | Phase 4 SDD — Combat commands (auto-combat + timer + new commands) | ✅ COMPLETADO |
| F5 | HermesDM skill + templates | M |
| F6 | Integration tests end-to-end | L |
| F7 | Demo + polish | M |

**Total: M — Large** (~2-3 sesiones de trabajo intenso)

---

## PHASE 4 — Combat Commands (18 April 2026)

### Nuevos comandos

| Comando | Descripción |
|---------|-------------|
| `/startcombat [enemigo1] [enemigo2]` | Inicia combate con iniciativa y enemigos |
| `/begincombat` | Alias de /startcombat |
| `/endcombat` | Termina combate activo + cancela timer |
| `/endturn` | Pasa al siguiente turno + reinicia timer |

### Auto-inicio de combate

Cuando un jugador usa `/attack <target>` y no hay combate activo, el sistema inicia combate automáticamente con:
- Todos los personajes jugadores registrados
- El `<target>` como enemigo
- Muestra orden de iniciativa inmediatamente

### Timer de turno (JobQueue)

- Al iniciar combate → se agenda timer de 120s para el primer combatiente
- Al usar `/endturn` → se cancela timer anterior y se agenda nuevo
- Cuando timer expira → bot nudgea al grupo y pasa al siguiente turno automáticamente
- Configurable via `/configuracion timer <segundos>` (0 = desactivado)
- `/endcombat` cancela todos los timers pendientes

### Implementación

```python
# ApplicationBuilder con JobQueue
app = ApplicationBuilder()\
    .token(settings.TELEGRAM_BOT_TOKEN)\
    .job_queue(True)\
    .build()

# Programar timer de turno
job_queue.run_once(
    _turn_timer_callback,
    timer_seconds,
    name="turn_timer",
    data={"current_turn": current, "chat_id": chat_id},
)

# Cancelar timer
for job in job_queue.get_jobs_by_name("turn_timer"):
    job.schedule_removal()
```

### Archivos modificados

- `bot/telegram_handler.py` — +3 comandos + auto-combat + timer JobQueue
- `tests/test_telegram_handler.py` — mock `.job_queue()` + handler count 21→24
- **Tests: 236 passing**

---

## CRITERIOS DE ÉXITO

```
✅ Sherman puede crear campaña, unirse, y jugar una partida completa
✅ Hermes genera narración para cada acción
✅ HP persiste entre sesiones
✅ Modo B: 3 jugadores pueden jugar async sin coordinación
✅ Modo D: 4 jugadores pueden jugar sync con turnos claros
✅ Modo D: /camera funciona y Hermes describe la mesa
✅ No se cae (pm2 + self-healing)
✅ 0 errores de Telegram en logs
✅ Sherman dice: "esto está buenísimo"
```

---

## PHASE 5 — Cierre Narrativo de Campaña (v1 + v2)

### Problema

No existe forma de terminar una campaña de manera narrativa. `/quit` solo dice "👋 hasta la próxima" — no hay epílogo, no se marca como completada, el mundo queda "vivo" para siempre.

### Solución v1 — Auto Epilogue (`/end`)

**Comando:** `/end`

**Flujo:**
1. Carga estado completo de la campaña (characters, NPCs, quests, history, world_timeline)
2. Construye contexto de cierre
3. Genera epílogo via LLM (`NarrativeGenerator.generate_closure()`)
4. Envía narrativa al grupo
5. Marca campaña como `"status": "completed"` en JSON
6. Imagen de cierre si corresponde

**Contexto que se alimenta al LLM:**
```python
{
    "characters": [
        {"name": "Valdric", "status": "alive", "hp": 24, "level": 5,
         "transformation": "De mercenario a caballero de la orden"},
        {"name": "Lyra", "status": "dead", "cause": "caída en el abismo"},
    ],
    "npcs": [
        {"name": "Rey Aldric", "status": "dead", "killed_by": "Valdric"},
        {"name": "Mago Zirex", "status": "alive", "new_role": "consejero del trono"},
    ],
    "completed_quests": [
        {"id": "save_princess", "objective": "Rescatar a la princesa", "outcome": "success"},
    ],
    "incomplete_quests": [
        {"id": "findartifact", "objective": "El artifacto perdido", "outcome": "inconclusive"},
    ],
    "world_changes": [
        "El Reino de Valdris recupera su trono tras 10 años de guerra civil",
        "El dragón de Shadowpeak ha muerto — el norte goza de paz por primera vez en décadas",
    ],
    "arc_summary": "La party partió como mercenarios buscando pago...",
    "tone": "epic",  # de campaign_settings
}
```

**Prompt al LLM:**
```
Eres HermesDM, un DM de D&D 5e experto en cierres épicos.

Esta campaña ha terminado. Escribe un EPÍLOGO que:
1. Muestre el destino de cada personaje (vivo, muerto, transformado)
2. Resuelva o deje abierta cada quest
3. Describa cómo el mundo cambió por las acciones del grupo
4. Termine con una línea final memorable (mic drop)
5. Mantén el tono de la campaña ({tone})

Tono: {tone}
Personajes: {characters}
NPCs relevantes: {npcs}
Consecuencias: {world_changes}

Requisitos:
- 4-8 oraciones
- Narrativa en segunda persona ("Tus acciones resonaron por generaciones...")
- Sin preguntas, termina en afirmación poderosa
- No introduzcas nuevos personajes ni tramas
```

**Nuevo SceneType:**
```python
class SceneType(str, Enum):
    EPILOGUE = "EPILOGUE"        # nuevo
    CAMPAIGN_CLOSE = "CAMPAIGN_CLOSE"  # nuevo
```

**API del generator:**
```python
def generate_closure(
    self,
    state: GameState,
    language: Language = Language.ES,
) -> dict:
    """
    Returns:
        {
            "narrative": str,           # texto del epílogo
            "quest_closure": dict,       # {quest_id: "completed"|"failed"|"inconclusive"}
            "npc_fates": dict,           # {npc_id: "alive"|"dead"|"transformed"}
            "character_summaries": dict, # {char_id: "summary string"}
            "triggered_image": bool,
        }
    """
```

**Integración en telegram_handler:**
```python
async def cmd_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /end — cierra campaña con epílogo."""
    # 1. Verificar campaña activa
    # 2. Generar closure
    closure = ng.generate_closure(state)
    # 3. Enviar narrativa
    await update.message.reply_text(closure["narrative"])
    # 4. Marcar como completada
    state["campaign"]["status"] = "completed"
    state["campaign"]["completed_at"] = timestamp
    save_state(campaign_id, state)
    # 5. Imagen si corresponde
    if closure["triggered_image"]:
        queue_async_image_gen(build_closure_image_prompt(state, closure))
```

**Estado en campaign JSON:**
```json
{
  "campaign": {
    "status": "completed",
    "completed_at": "2026-04-21T00:00:00Z",
    "epilogue": "texto completo del cierre..."
  }
}
```

---

### Solución v2 — Manual Player Epilogues (pendiente)

**Concepto:** Después del combate/clímax final, antes de generar el epílogo automático, el DM le pide a cada jugador que contribuya con el cierre de su personaje.

**Flujo completo:**
```
1. Combat final termina
2. Bot dice: "🎭 CIERRE DE CAMPÑA — El destino de los héroes"
3. Para cada personaje vivo:
   Bot → "[Nombre], ¿cómo termina tu historia? (1-2 líneas)"
   Jugador → responde con su visión del final
4. Hermes toma todas las respuestas
5. Genera epílogo unificado que incorpora las respuestas de los jugadores
6. Envía epílogo final al grupo
7. Marca campaign como completed
```

**Comando adicional:** `/endmanual` (o `/end --manual`)

**Estado en JSON:**
```json
{
  "epilogue_contributions": {
    "valdric": "Se retira a su pueblo natal y abre una taberna",
    "lyra": "Lidera la nueva orden de magos en la capital",
  }
}
```

**Casos de uso:**
- Jugadores que quieren control creativo sobre el destino de su personaje
- Campañas largas donde el epílogo automático no captura la visión del jugador
- Momentos emotivos personalizados ("murió protegiendo a su hermana")

**Nota:** Para one-shots probablemente sea overkill. Auto mode debería ser suficiente para la mayoría de los casos. Manual es para campañas donde hay inversión emocional fuerte en los personajes.

---

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `dm/narrative_generator.py` | +`SceneType.EPILOGUE` + `generate_closure()` |
| `dm/image_prompt_builder.py` | + `build_closure_image_prompt()` |
| `bot/telegram_handler.py` | + `cmd_end()` |
| `state/state_manager.py` | + campo `status: completed` en campaign |
| `campaign_settings.py` | + dataclass `CampaignStatus` (active/completed/paused) |
| `SPEC.md` | Este documento |

**Tests:** +8 nuevos tests para `generate_closure()` y `cmd_end`

---

## PHASE 6 — Transferencia de Items entre Jugadores

### Problema

No existe forma de transferir items entre personajes. Un jugador puede decir "/me le da su espada a Valdric" pero no hay efecto mecánico real.

### Solución

**Comando:** `/give <personaje> <item> [cantidad]`

**Flujo:**
1. El giver especifica quién recibe y qué item
2. Sistema valida que el item exista en su inventario
3. Remueve el item del giver, agrega al receiver
4. Responde con confirmación narrativa

**Integración en telegram_handler:**
```python
async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /give <personaje> <item> [cantidad] — transfiere item."""
    # 1. Parsear args: /give Valdric Espada Larga
    # 2. Buscar personaje receiver en cs.characters
    # 3. Buscar item en inventario del giver
    # 4. Character.remove_item() + receiver.add_item()
    # 5. Guardar estado
    # 6. Responder con confirmación
```

**Validaciones:**
- El receiver debe existir en la party
- El giver debe tener el item en su inventario
- Cantidad > 0, no excede lo que tiene el giver

**Respuesta:**
```
🎁 *Transferencia realizada*
Valdric le da 1x Espada Larga +1 a Lyra.
Inventario actualizado.
```

**Comando adicional:** `/trade <jugador> <item> <item>` (intercambio bidireccional) — v2

---

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `bot/telegram_handler.py` | + `cmd_give()` |

**Tests:** +4 tests para `cmd_give`
