<img width="240" height="240" alt="5134172295139101640" src="https://github.com/user-attachments/assets/1e18c38e-d4ed-4a4d-a51b-c0c3b2ab892b" />

# HermesDM — AI Dungeon Master via Telegram

> Motor de D&D 5e controlado por IA via Telegram. Dados reales, hojas de personaje, combate por turnos, continuidad del mundo, narración LLM, y generación automática de imágenes contextuales.

## Quick Start

```bash
# 1. Clone e instala
git clone https://github.com/sherman/hermesdm.git
cd hermesdm
pip install -e .

# 2. Configura tokens en config.yaml
cp config.yaml.example config.yaml
# Edita TELEGRAM_BOT_TOKEN y LLM_API_KEY

# 3. Ejecuta
python -m bot.telegram_bot
```

## Comandos

### Gestión de Partida
| Comando | Descripción |
|---------|-------------|
| `/start` | Inicia wizard de nueva campaña |
| `/campaign` | Muestra info de campaña activa |
| `/newgame` | Resetea y empieza nueva campaña |
| `/end` | Termina sesión (genera epílogo + imagen) |
| `/settings` | Ver/editar dificultad, tono, módulos |

### Personajes
| Comando | Descripción |
|---------|-------------|
| `/create <nombre> <clase>` | Crea personaje (Lvl 1, standard array) |
| `/delete <nombre>` | Elimina personaje |
| `/chars` | Lista personajes de la campaña |
| `/char <nombre>` | Muestra hoja de personaje completa |
| `/hp <nombre> [valor]` | Ver o modificar HP |
| `/xp <nombre> [valor]` | Ver o modificar XP |
| `/levelup <nombre>` | Subir nivel (auto recalcula HP) |
| `/conditions <nombre> [agregar/quitar]` | Gestionar condiciones |
| `/deathsave <nombre> [exito/fallo]` | Tirada de muerte |

### Inventario
| Comando | Descripción |
|---------|-------------|
| `/inventory <nombre>` | Muestra inventario |
| `/item <nombre> <item>` | Agrega item al inventario |
| `/give <nombre> <item>` | Alias de `/item` |
| `/drop <nombre> <item>` | Elimina item del inventario |
| `/equip <nombre> <item>` | Equipa item |
| `/unequip <nombre> [item]` | Desequipa item(es) |

### Dados
| Comando | Descripción |
|---------|-------------|
| `/roll <dado>` | Tira dados (ej: `2d6+3`) |
| `/r <dado>` | Alias corto |
| `/flip` | Moneda (1d2) |

### Habilidades (Skill Checks)
| Comando | Descripción |
|---------|-------------|
| `/check <stat> [ventaja/desventaja]` | Skill check (fuerza, destreza, etc.) |
| `/save <stat> [dc]` | Saving throw (default DC 10) |

### Magia
| Comando | Descripción |
|---------|-------------|
| `/cast <nombre> <hechizo> [objetivo]` | Lanza hechizo |
| `/spells` | Lista hechizos disponibles |

### Combate
| Comando | Descripción |
|---------|-------------|
| `/combat` | Estado del combate actual |
| `/join` | Únete al combate activo |
| `/attack <objetivo>` | Ataca en combate |
| `/j <objetivo>` | Alias de `/attack` |
| `/endturn` | Termina tu turno |
| `/flee` | Huir del combate |
| `/status` | HP, AC, condiciones del grupo |

### NPCs
| Comando | Descripción |
|---------|-------------|
| `/npc <nombre>` | Consulta o crea NPC |
| `/npcs` | Lista NPCs activos |
| `/npcnote <nombre> <nota>` | Anota información sobre NPC |

### Naración
| Comando | Descripción |
|---------|-------------|
| `/act <acción>` | Narración de acción en mundo |
| `/scene <descripción>` | Describe escena actual |
| `/image <prompt>` | Genera imagen manualmente |
| `/sceneimage` | Genera imagen de la escena actual |
| `/end` | Fin de sesión (epílogo + imagen automática) |

### Monstruos
| Comando | Descripción |
|---------|-------------|
| `/summon <nombre> [tipo]` | Invoca monstruo genérico |
| `/monster <nombre> [HP] [AC]` | Invoca monstruo custom |
| `/remove <nombre>` | Elimina criatura del combate |
| `/monsters` | Lista monstruos en combate |

### Restauración
| Comando | Descripción |
|---------|-------------|
| `/rest` | Descanso largo (recupera todo) |
| `/shortrest` | Descanso corto (1 hit die + CON mod HP) |

## Clases Disponibles

| Clase | Hit Die | Skills |
|-------|---------|--------|
| `fighter` | d10 | Athletics, Survival |
| `wizard` | d6 | Arcana, History |
| `rogue` | d8 | Stealth, Sleight of Hand |
| `cleric` | d8 | Religion, Medicine |
| `barbarian` | d12 | Athletics, Intimidation |

## Géneros de Campaña

`/newgame` ofrece 5 settings con prompts de system únicos:

| Genre | Descripción |
|-------|-------------|
| `fantasy` | Aventuras medievales de alta fantasía |
| `dungeon` | Dungeons crawling, puzzles, trampas |
| `tavern` | Intriga política, missions desde taberna |
| `horror` | Terror psicológico, survival horror |
| `scifi` | Ciencia ficción, space opera, cyberpunk |

## Sistema de Imágenes Automáticas

El DM genera imágenes **automáticamente** cuando ocurren momentos narrativamente importantes.

### Providers Soportados

| Provider | Calidad | Velocidad | Costo |
|----------|---------|-----------|-------|
| `pollinations` | Buena | ~1s | Gratis |
| `minimax` | Excelente | ~10s | API key requerida |
| `flux` | Alta | Variable | Local |
| `nanobanana` | Variable | Variable | API key |

### Triggers Automáticos (configurables)

```python
# En campaign settings:
auto_image_triggers:
  nat_20: true        # Crítico en ataque — SI
  nat_1: true         # Fumble — SI
  death: true         # HP llega a 0 — SI
  boss_combat: true   # Inicio de boss fight — SI
  discovery: true     # Nueva ubicación/NPC — SI
  session_end: true   # Fin de sesión — SI
  dramatic: true      # HP < 25% HP — SI
  normal_turn: false  # Turno normal — NO
```

### Configuración

```yaml
# En config.yaml
image_provider: "pollinations"  # default
minimax_api_key: "your-key"     # opcional
```

O en runtime via `/settings`:
```
image_provider: minimax
```

### Prompt Building

El prompt se construye automáticamente desde el contexto:

```
"Valdric delivers a devastating blow to a wounded dragon,
the beast crashing down from the sky in flames,
dramatic cinematic battle scene 4k"
```

Se adapta al género de campaña (cyberpunk → "neon lights", horror → "dark fog").

## Arquitectura

```
hermesdm/
├── bot/
│   ├── telegram_handler.py   # Entry point, command routing
│   ├── character_sheet.py     # Character dataclass, HP, inventory, XP
│   ├── combat_engine.py        # Initiative, attack resolution, crits
│   ├── diceRoller.py          # Dice parsing, rolling, formatted output
│   ├── skill_checks.py        # Skill checks, saving throws
│   ├── spell_manager.py       # Spellcasting, damage, saves
│   └── monsters.py            # Monster definitions, summon
├── dm/
│   ├── narrative_generator.py # LLM narration, NPC dialogue
│   ├── world_builder.py       # World/NPC generation per genre
│   ├── image_provider.py      # ABC + Pollinations/MiniMax/Flux providers
│   ├── image_event_handler.py # Auto-trigger logic + cooldown
│   └── image_generator.py     # Legacy scene image generation
├── adapters/
│   └── mode_b/
│       └── action_router.py   # /j action routing, ActionResult
├── state/
│   └── state_manager.py       # Campaign state, persistence (JSON)
├── tests/
│   ├── test_combat_engine.py
│   ├── test_character_sheet.py
│   ├── test_diceRoller.py
│   ├── test_skill_checks.py
│   ├── test_action_router.py
│   ├── test_integration_flow.py
│   └── test_telegram_handler.py
└── SPEC_*.md                  # Specs detalladas por feature
```

### Flujo de una Acción de Combate

```
/j attack dragon
  → action_router.route()     # Parsea acción, determina tipo
  → combat_engine.resolve()    # Tira dados, calcula daño
  → narrative_generator.generate_scene()  # LLM narration
  → image_event_handler.maybe_generate() # ¿Generar imagen?
  → telegram_handler._maybe_send_scene_image()  # Envía si corresponde
```

### Flujo de Imagen Automática

```
NarrativeGenerator.generate_scene()
  → Result {narrative, triggered_image, scene_type}
      ↓ triggered_image = True
ImageEventHandler.maybe_generate()
  → Check cooldown (5 min default)
  → Check trigger rules (nat_20, death, etc.)
      ↓ allowed
ImageProvider.generate()
  → build_scene_prompt()        # Contexto + género → prompt
  → Pollinations/MiniMax/Flux  # API call
  → /tmp/hermesdm_*.png        # Archivo local
      ↓
TelegramBot.send_photo()
  → Imagen al grupo
```

## Estado de Campaña

El estado se guarda en `~/.hermes/hermesdm_state.json`:

```python
{
  "campaign_id": "uuid",
  "name": "The Dragon's Lair",
  "genre": "fantasy",
  "status": "active",        # "setup" | "active" | "paused" | "completed"
  "difficulty": "normal",
  "tone": "serious",
  "current_location": "Dark Forest",
  "image_provider": "pollinations",
  "auto_image_triggers": {...},
  "characters": {...},
  "npcs": {...},
  "timeline": [...],
  "combat": {...},
}
```

## Configuración

```yaml
# config.yaml
telegram_bot_token: "TU_TELEGRAM_TOKEN"
llm_provider: "minimax"       # o "openai", "anthropic"
llm_model: "minimax-01"
llm_api_key: "TU_API_KEY"
image_provider: "pollinations"
```

## Spell System (D&D 5e Spell Slots)

Sistema completo de spell slots por clase — los hechizos de nivel 1+ consumen slots.

### Slots por Clase
| Clase | Lv1 | Lv2 | Lv3 | Lv4 | Lv5 | Lv6-9 |
|-------|-----|-----|-----|-----|-----|-------|
| Wizard | 4 | 3 | 3 | 3 | 3 | progresivo |
| Cleric/Druid/Bard | 4 | 3 | 3 | 3 | 3 | progresivo |
| Paladin/Ranger | 4 | 3 | 3 | 2 | 2 | — |
| Warlock | Pact (restored on short rest) | | | | | |

### Comandos de Magia
| Comando | Descripción |
|---------|-------------|
| `/cast Fireball` | Lanza hechizo (consume slot si aplica) |
| Hechizo de daño | Lanza dados de daño según spell |
| Save DC | Objetivo tira save o recibe daño completo |

### Hechizos Disponibles
- **Cantrips**: Fire Bolt, Sacred Flame, Shocking Grasp, Mind Sliver, Thaumaturgy
- **Lv1**: Magic Missile, Guiding Bolt, Healing Word, Thunderwave, Shield, Sleep
- **Lv2**: Scorching Ray, Spiritual Weapon, Hold Person, Misty Step
- **Lv3**: Fireball, Counterspell, Mass Healing Word
- **Lv4**: Polymorph, Wall of Fire
- **Lv5**: Cone of Cold, Flame Strike

### Recuperación de Slots
- **Long rest**: Todos los slots recuperados
- **Warlock**: Pact slot se recupera con short rest

## NPC Persistence System

Los NPCs ahora son persistentes — sobreviven restarts del bot y se guardan en el campaign state.

### Comandos de NPC
| Comando | Descripción |
|---------|-------------|
| `/talk <npc> <mensaje>` | Hablar con un NPC |
| `/npcs` | Lista todos los NPCs del mundo |
| `/npcsearch <query>` | Busca NPCs por nombre/título/descripción |
| `/npcnote <nombre> <nota>` | Agrega nota del DM a un NPC |
| `/npcmemory <nombre> <key> <valor>` | Registra memoria sobre un NPC |

### Datos Persistentes por NPC
- `name`, `title`, `description`, `personality`, `motivation`
- `secret` (agenda oculta)
- `location` (ubicación actual en el mundo)
- `memory[]` — entradas de memoria con clave/valor/timestamp
- `tags[]` — etiquetas (merchant, quest_giver, criminal...)
- `mood`, `disposition` (friendly/hostile/indifferent)
- `notes` — notas libres del DM

### Flujo
```
/newgame → WorldBuilder genera NPCs → se guardan en state["npcs"]
/talk Gorin → NPCStore busca por nombre → diálogo
/npcmemory Gorin secret_weakness "Le teme al fuego"
→ Gorin sobrevive restarts del bot
```

## Auto-Image Generation (Background)

Imágenes generadas automáticamente según eventos del juego. No interrumpe el flujo de combate.

### Providers
- `pollinations` (default, gratis)
- `minimax` (alta calidad)
- `flux` (local)

### Triggers Automáticos
| Evento | Imagen |
|--------|--------|
| Nat 20 (crítico) | ✅ |
| Nat 1 (fumble) | ✅ |
| Muerte (HP=0) | ✅ |
| Boss combat | ✅ |
| Descubrimiento de ubicación | ✅ |
| Fin de sesión | ✅ |
| HP < 25% | ✅ |
| Turno normal | ❌ |

### Config por Campaña
```python
image_provider: "pollinations"  # cambiar a "minimax"
auto_image_triggers:
  nat_20: true
  death: true
  boss_combat: true
```

## Development

```bash
# Tests
python -m pytest tests/ -v

# Con coverage
python -m pytest tests/ --cov=bot --cov=dm --cov=adapters

# Validación de estado
python -c "from state.state_manager import validate_state; validate_state()"
```

## Specs Disponibles

- `SPEC_IMAGE_GENERATION.md` — Sistema de generación automática de imágenes
- `SPEC_ACTION_ROUTER.md` — Sistema de routing de acciones `/j`
- `SPEC_CHARACTER_SHEET.md` — Sistema de hojas de personaje y XP/level up
- `SPEC_NARRATIVE_SYSTEM.md` — Sistema de narración LLM
- `SPEC_SPELL_SYSTEM.md` — Sistema de hechizos y magia
- `SPEC_SPELL_SLOTS.md` — Sistema de spell slots 5e
- `SPEC_DEATH_SAVES_PERSISTENCE.md` — Death saves que sobreviven restarts
- `SPEC_NPC_PERSISTENCE.md` — NPC persistence con NPCStore/NPCRecord
- `SPEC_COMBAT_ENGINE.md` — Engine de combate D&D 5e
- `SPEC_WORLD_BUILDER.md` — Generador de mundos y NPCs
