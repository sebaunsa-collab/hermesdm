# 🎲 HermesDM — Tu Dungeon Master con IA en Telegram

<p align="center">
<img width="600" alt="HermesDM Banner" src="https://i.imgur.com/placeholder-banner.png"/>
<br/>

> **¿Quién necesita D&D Beyond cuando podés tener un DM con IA corriendo en tu grupo de Telegram?**

[![D&D 5e](https://img.shields.io/badge/D%26D-5e-960020?style=flat-square)](https://dnd.wizards.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=fff)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-274%20%E2%9C%85-brightgreen?style=flat-square)](tests/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=flat-square&logo=telegram&logoColor=fff)](https://t.me/)
[![Twitter](https://img.shields.io/badge/Author-@TheShugarBoy-1DA1F2?style=flat-square&logo=twitter&logoColor=fff)](https://twitter.com/TheShugarBoy)

</p>

---

## ⚡ TL;DR — Así se ve una partida real

```
🧙 Sherman → /create Valdric Wizard
⚔️ Valdric creado! HP: 6 | AC: 13 | Slots: 4/4/3/3/3

🧙 Sherman → /j attack dragon
🎲 Tiras ataque... [d20+5 → 19+5=24] ¡GOLPE CRÍTICO!
   🔥 "Valdric atraviesa el corazón del dragón anciano..."
   🖼️ [Imagen generada automáticamente]

🧙 Sherman → /cast fireball goblins
✨ Fireball! [8d6=38 daño] ¡3 goblins eliminados!
   🧙 Slots consumidos: Lv3 → 2 restantes
```

**No necesitás Roll20, D&D Beyond, ni ninguna otra app. Solo Telegram.** 📱

---

## 🤔 Por qué HermesDM?

| | Roll20 | D&D Beyond | **HermesDM** |
|---|:---:|:---:|:---:|
| 💰 Costo | ~$10/mes | ~$15/mes | **Gratis** |
| 🎲 Dados reales | ⚠️ Manual | ⚠️ Manual | **Automático** |
| 🧙 Spell slots | ⚠️ Manual | ✅ Automático | **✅ Automático** |
| 🖼️ Imágenes | ❌ No tiene | ❌ No tiene | **✅ Auto-generadas** |
| 📱 En Telegram | ❌ No | ❌ No | **✅ 100% Telegram** |
| 💾 Persistencia | ⚠️ Sesión | ⚠️ Sesión | **✅ Entre sesiones** |
| 🧠 Narración LLM | ❌ No | ❌ No | **✅ Sí** |

> **Spoiler:** HermesDM no reemplaza una mesa de amigos. Pero si jugás solo o con gente que no tiene cara de dados, es otra historia. 👀

---

## 🎮 Demo en Vivo — Campaign: "The Dragon's Lair"

```
⏱️ Sesión real — combate contra Ancient Dragon (HP: 180, AC: 19)

🧙 Sherman → /join
⚔️ COMBATE INICIADO: Valdric vs Ancient Dragon

🧙 Sherman → /j attack dragon (Ventaja)
🎲 [2d20+7 → 18, 19+7=26] ¡NATURAL 20! 💥
🔥 "Valdric delivers a devastating blow, the dragon crashing
   down from the sky in flames — dramatic cinematic battle scene"
🖼️ [MiniMax image → grupo de Telegram]

💀 Sherman → HP: 12/68 (-56)
⚔️ Dragon's Turn → Breath Weapon [54 daño]
💀 Sherman → HP: 0/68 — ¡CAE AL SUELO!
☠️  VALDRIC ESTÁ MUERTO
🖼️ [Imagen de muerte enviada]

🎲 Death Save: 2 successes, 1 failure
💀 Valdric stabilized... barely.
```

---

## 🧠 Cómo Funciona — Arquitectura General

```
┌─────────────────────────────────────────────────────┐
│                    TELEGRAM                          │
│   Sherman escribe: /j attack dragon                 │
└─────────────────────┬───────────────────────────────┘
                      │ 📬 Polling (getUpdates)
                      ▼
┌─────────────────────────────────────────────────────┐
│              bot/telegram_handler.py                 │
│  1. Recibe update de Telegram                        │
│  2. Parsea comando (/j, /cast, /create...)          │
│  3. Delega al módulo correspondiente                  │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌───────────┐
   │ combat_  │  │  spell_  │  │character_ │
   │ engine   │  │ manager  │  │  sheet    │
   └────┬────┘  └────┬─────┘  └─────┬─────┘
        │            │              │
        └────────────┼──────────────┘
                     ▼
        ┌────────────────────────┐
        │  adapters/mode_b/      │
        │  action_router.py      │
        │  → Clasifica la acción │
        │  → arma resultado unif │
        └────────────┬───────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌─────────┐ ┌──────────┐ ┌──────────┐
   │  dice   │ │ narrative│ │ image_    │
   │ roller  │ │ generator│ │ event_h.. │
   └────┬────┘ └────┬────┘ └────┬─────┘
        │           │           │
        │           ▼           │
        │    ┌───────────┐      │
        │    │ LLM call  │      │
        │    │(narrative)│      │
        │    └─────┬─────┘      │
        │          │            │
        └──────────┴────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Image Provider         │
        │  (Pollinations/MiniMax/│
        │   Flux/NanoBanana)     │
        └────────────┬───────────┘
                     │ ⏱️ +5 min cooldown
                     ▼
              ┌──────────────┐
              │  Telegram    │
              │  Bot sends   │
              │  photo       │
              └──────────────┘
```

### 🔄 Flujo Detallado de una Acción de Combate

```
1. Sherman → /j attack dragon
       │
2. action_router.route("attack dragon")
       │ Clasifica: action_type="attack", target="dragon"
       ▼
3. combat_engine.roll_attack(character, target, advantage=False)
       │ → Parses "dragon" → busca en combat state
       │ → Obtiene AttackBonus del weapon equipped
       │ → Lanza: 1d20 + attack_bonus
       │ → Result: {total: 24, natural: 19, is_crit: True}
       ▼
4. combat_engine.resolve_crit()
       │ natural=19 → critica! → rollea damage 2x
       ▼
5. character_sheet.apply_damage(character, damage)
       │ → HP -= damage
       │ → Check muerte (HP <= 0)
       ▼
6. narrative_generator.generate_scene()
       │ → arma prompt con: action, result, character, target, genre
       │ → LLM → narración dramática del momento
       ▼
7. image_event_handler.maybe_generate()
       │ → nat_20=True → triggered=True
       │ → Check cooldown (5 min)
       │ → Build scene prompt + genre style
       ▼
8. image_provider.generate()
       │ → build_scene_prompt() → prompt de detalle
       │ → API call (Pollinations/MiniMax/Flux)
       │ → Guarda en /tmp/hermesdm_*.png
       ▼
9. telegram_handler.send_photo()
       │ → Envía imagen al grupo de Telegram
       ▼
10. Sherman ve:
       🎲 [1d20+5 → 19+5=24] ¡GOLPE CRÍTICO!
       🔥 "Valdric atraviesa el corazón del dragón..."
       🖼️ [ imagen del momento ]
```

### 🧠 Flujo de un Hechizo

```
1. Sherman → /cast fireball goblins
       │
2. spell_manager.parse_spell("fireball")
       │ → spell_data["fireball"] = {damage: "8d6", save: "DEX", dc: 15}
       ▼
3. spell_manager.check_slots(character, spell_level)
       │ → character.spell_slots[3] > 0 ?
       │ → Si no hay slot: "No tenés slots de nivel 3"
       ▼
4. spell_manager.cast_spell()
       │ → Consume 1 slot del nivel correspondiente
       │ → Muestra: ✨ Fireball! [8d6=38 daño]
       ▼
5. narrative_generator + image generation
       │ (mismo flujo que combate)
```

---

## ✨ Features

| Feature | Status | Detalle |
|---------|:------:|---------|
| 🎲 **Dados reales** | ✅ | 1d4 → 1d20+, ventaja, desventaja, saves, crits |
| 📋 **Hojas de personaje** | ✅ | HP, XP, inventario, condiciones, death saves |
| 🧙 **Spell slots** | ✅ | Wizard, Cleric, Warlock, Paladin, Druid, Bard |
| 💀 **Death saves persistentes** | ✅ | Sobreviven reinicios del bot |
| 🧙 **NPCs con memoria** | ✅ | Notas, diálogos, memoria entre sesiones |
| ⚔️ **Combate por turnos** | ✅ | Iniciativa, ataques, daño, crits |
| 📖 **Narración LLM** | ✅ | Escenas dinámicas según el género |
| 🖼️ **Generación de imágenes** | ✅ | Pollinations, MiniMax, Flux, NanoBanana |
| 💾 **Estado en JSON** | ✅ | Persiste entre sesiones en `~/.hermes/` |
| 🏰 **5 géneros de campaña** | ✅ | fantasy, dungeon, horror, tavern, scifi |
| 💬 **100% Telegram** | ✅ | Ninguna app externa necesaria |

---

## 🚀 Quick Start — Arrancá en 2 minutos

```bash
# 1. Clonar e instalar
git clone https://github.com/sebaunsa-collab/hermesdm.git
cd hermesdm
pip install -e .

# 2. Configurar tokens
cp .env.example .env
# ✏️  Editar .env y poner:
#   TELEGRAM_BOT_TOKEN=tu_token_de_botfather
#   MINIMAX_API_KEY=***  (opcional, usa Pollinations si no está)

# 3. Correr
hermesdm
# O directamente: python -m bot.telegram_handler

# 4. Abrí Telegram → buscá tu bot → /start
```

### ⚙️ Requisitos

| Requisito | Necesario? |Dónde conseguirlo|
|-----------|:----------:|----------------|
| 🐍 **Python 3.12+** | ✅ Siempre | [python.org](https://www.python.org/) |
| 📱 **Telegram Bot Token** | ✅ Siempre | [@BotFather](https://t.me/BotFather) |
| 🎨 **MiniMax API Key** | ❌ Opcional | [MiniMax](https://platform.minimaxi.com) — si no está, usa Pollinations (gratis) |
| 🤖 **OpenAI Token** | ❌ Opcional | [OpenAI](https://platform.openai.com/) — para narración LLM más rica |

---

## 🎯 Guía de Comandos

### 🏠 Inicio de Partida
| Comando | Descripción |
|---------|-------------|
| `/start` | Lanzar el wizard de nueva campaña |
| `/campaign` | Ver info de la campaña activa |
| `/newgame` | Reiniciar y empezar campaña fresca |
| `/end` | Terminar sesión — genera epílogo + imagen |
| `/settings` | Cambiar dificultad, tono, provider de imágenes |

### 👤 Personajes
| Comando | Descripción |
|---------|-------------|
| `/create <nombre> <clase>` | Crear personaje (Nv 1, standard array) |
| `/delete <nombre>` | Eliminar personaje |
| `/chars` | Listar todos los personajes |
| `/char <nombre>` | Hoja de personaje completa |
| `/hp <nombre> [valor]` | Ver o modificar HP |
| `/xp <nombre> [valor]` | Ver o modificar XP |
| `/levelup <nombre>` | Subir de nivel (recalcula HP automático) |
| `/conditions <nombre> [add/remove]` | Condiciones (poisoned, stunned...) |
| `/deathsave <nombre> [success/fail]` | Saving throw de muerte |
| `/rest` | Descanso largo (recupera todo) |
| `/shortrest` | Descanso corto (1 hit die + MOD CON) |

### 🎒 Inventario
| Comando | Descripción |
|---------|-------------|
| `/inventory <nombre>` | Mostrar inventario |
| `/item <nombre> <item>` | Agregar item |
| `/give <nombre> <item>` | Alias para `/item` |
| `/drop <nombre> <item>` | Remover item |
| `/equip <nombre> <item>` | Equipar item |
| `/unequip <nombre> [item]` | Desequipar item(s) |

### 🎲 Dados & Chequeos
| Comando | Descripción |
|---------|-------------|
| `/roll <dado>` | Tirar dados (ej: `2d6+3`, `1d20+5`) |
| `/r <dado>` | Alias corto |
| `/flip` | Moneda (1d2) |
| `/check <stat> [adv/dis]` | Chequeo de skill (str, dex, con...) |
| `/save <stat> [dc]` | Saving throw (default DC 10) |

### ✨ Magia & Spellcasting
| Comando | Descripción |
|---------|-------------|
| `/cast <nombre> <spell> [target]` | Lanzar hechizo (consume slot si aplica) |
| `/spells` | Listar hechizos disponibles por nivel |

**Spells disponibles:**
- **Cantrips:** Fire Bolt 🔥, Sacred Flame ✨, Shocking Grasp ⚡, Mind Sliver 🧠, Thaumaturgy 📢
- **Nv 1:** Magic Missile 🎯, Guiding Bolt 🌟, Healing Word 💚, Thunderwave 💨, Shield 🛡️, Sleep 😴
- **Nv 2:** Scorching Ray 🔴, Spiritual Weapon ⚔️, Hold Person ⏸️, Misty Step 💨
- **Nv 3:** Fireball 💥, Counterspell 🚫, Mass Healing Word 💖
- **Nv 4:** Polymorph 🐉, Wall of Fire 🔥
- **Nv 5:** Cone of Cold ❄️, Flame Strike 🌋

**Sistema de Spell Slots:**
| Clase | Nv1 | Nv2 | Nv3 | Nv4 | Nv5 |
|-------|-----|-----|-----|-----|-----|
| 🧙 Wizard | 4 | 3 | 3 | 3 | 3 |
| ⛪ Cleric/Druid/Bard | 4 | 3 | 3 | 3 | 3 |
| ⚔️ Paladin/Ranger | 4 | 3 | 3 | 2 | 2 |
| 🔮 Warlock | Pact slot (short rest) | — | — | — | — |

### ⚔️ Combate
| Comando | Descripción |
|---------|-------------|
| `/combat` | Estado del combate activo |
| `/join` | Unirse al combate |
| `/attack <target>` | Atacar (alias: `/j`) |
| `/endturn` | Terminar tu turno |
| `/flee` | Huir del combate |
| `/status` | HP, AC, condiciones del grupo |
| `/summon <nombre> [tipo]` | Invocar monstruo genérico |
| `/monster <nombre> [HP] [AC]` | Invocar monstruo custom |
| `/remove <nombre>` | Remover criatura del combate |
| `/monsters` | Listar monstruos en combate |

### 🧙 NPCs
| Comando | Descripción |
|---------|-------------|
| `/npc <nombre>` | Consultar o crear NPC |
| `/npcs` | Listar NPCs activos |
| `/npcnote <nombre> <nota>` | Agregar nota del DM sobre NPC |
| `/talk <npc> <mensaje>` | Hablar con un NPC (diálogo LLM) |
| `/npcsearch <query>` | Buscar NPCs por nombre/título |
| `/npcmemory <nombre> <key> <valor>` | Registrar memoria sobre NPC |

### 🖼️ Narración & Imágenes
| Comando | Descripción |
|---------|-------------|
| `/act <accion>` | Narrar una acción en el mundo |
| `/scene <descripcion>` | Describir la escena actual |
| `/image <prompt>` | Generar imagen manualmente |
| `/sceneimage` | Auto-generar imagen de la escena actual |

---

## 🌍 Géneros de Campaña

Cuando ejecutás `/newgame`, elegís un género. Cada uno tiene system prompts únicos para el LLM:

| Género | Vibe | Descripción |
|--------|------|-------------|
| 🏰 `fantasy` | Medieval | Aventuras de alta fantasía — dragones, magia, quest épicos |
| 🗝️ `dungeon` | Exploración | Mazmorras, puzzles, trampas, tesoros ocultos |
| 🍺 `tavern` | Intriga | Missions políticas desde la taberna, RPG social |
| 👻 `horror` | Terror | Horror psicológico, supervivencia, criaturas oscuras |
| 🚀 `scifi` | Space Opera | Sci-fi, cyberpunk, naves espaciales, IA rebelde |

---

## 🖼️ Generación Automática de Imágenes

El DM genera imágenes **automáticamente** en momentos narrativamente importantes — sin que lo pidas.

### 🎯 Eventos que Disparan Imágenes

| Evento | Imagen? | Por qué? |
|--------|:-------:|----------|
| 🎲 **Natural 20** (crítico) | ✅ | Momento épico — hay que mostrarlo |
| 💀 **Natural 1** (pifia) | ✅ | Caos y humor — el LLM narra el ridículo |
| ☠️ **Muerte de personaje** | ✅ | Impacto emocional máximo |
| 🐉 **Combate contra boss** | ✅ | Cada golpe importante se narra visualmente |
| 🗺️ **Nueva ubicación/NPC** | ✅ | Contextualiza el descubrimiento |
| 🏁 **Fin de sesión** | ✅ | Epílogo visual del momento |
| ❤️ **HP < 25%** | ✅ | Tensión — momento de peligro |
| 🎲 Turno normal | ❌ | No spam — cooldown de 5 min |

### 🔌 Providers Soportados

| Provider | Calidad | Velocidad | Costo | Notas |
|----------|:------:|:----------:|:-----:|-------|
| 🌸 **Pollinations** | Buena ⭐⭐⭐ | ~1s | Gratis | Default, no necesita API key |
| 🎨 **MiniMax** | Excelente ⭐⭐⭐⭐⭐ | ~10s | API key | Recomendado para campañas serias |
| ⚡ **Flux** | Alta ⭐⭐⭐⭐ | Variable | Local | Requiere servidor local |
| 🍌 **NanoBanana** | ??? | ??? | ??? | Experimental |

### ⚙️ Configuración

```yaml
# config.yaml
image_provider: "pollinations"   # default (gratis)
minimax_api_key: "tu-key"        # opcional
flux_endpoint: "http://localhost:7860"  # opcional
```

O en runtime via `/settings image_provider minimax`.

---

## 💾 Estado de Campaña — Persistencia

Todo el estado vive en `~/.hermes/hermesdm_state.json`:

```json
{
  "campaign_id": "uuid",
  "name": "The Dragon's Lair",
  "genre": "fantasy",
  "status": "active",
  "difficulty": "normal",
  "tone": "serious",
  "current_location": "Dark Forest",
  "image_provider": "pollinations",
  "auto_image_triggers": {
    "nat_20": true,
    "death": true,
    "boss_combat": true,
    "discovery": true,
    "session_end": true
  },
  "characters": {
    "Valdric": {
      "class": "Wizard",
      "level": 5,
      "hp": 28,
      "max_hp": 34,
      "ac": 13,
      "xp": 6500,
      "spell_slots": { "1": 4, "2": 3, "3": 3, "4": 1 },
      "inventory": ["Spellbook", "Staff"],
      "conditions": [],
      "death_saves": { "successes": 0, "failures": 0 }
    }
  },
  "npcs": {
    "Eldara": {
      "title": "The Witch",
      "description": "Ancient sorceress living in the swamp",
      "memory": { "met": "2024-03-15", "quest_given": "Find the crystal orb" }
    }
  },
  "combat": {
    "active": true,
    "turn": 2,
    "entities": []
  }
}
```

**Importante:** Si el bot se cae o se reinicia, el estado se recupera automáticamente. Los death saves, HP, NPCs y posición en combate se mantienen. 💾

---

## 🏗️ Estructura del Proyecto

```
hermesdm/
├── bot/                          # 🎮 Lógica del juego (Telegram side)
│   ├── telegram_handler.py       # 🚪 Entry point — recibe mensajes, routing
│   ├── character_sheet.py       # 📋 HP, XP, inventory, conditions, death saves
│   ├── combat_engine.py         # ⚔️ Iniciativa, ataque, daño, crits
│   ├── diceRoller.py            # 🎲 Parsing y tirada de dados
│   ├── skill_checks.py          # 🎯 Skill checks, saving throws
│   ├── spell_manager.py         # ✨ Spellcasting, damage, saves
│   └── monsters.py              # 👹 Definiciones de monstruos
│
├── dm/                           # 🧠 Motor de IA (brain del DM)
│   ├── narrative_generator.py   # 📖 Llamadas al LLM — narración y diálogos
│   ├── world_builder.py         # 🌍 Generación de mundo/NPCs por género
│   ├── image_provider.py        # 🖼️ ABC + Pollinations/MiniMax/Flux/NanoBanana
│   └── image_event_handler.py   # 🎬 Lógica de triggers + cooldown
│
├── adapters/mode_b/              # 🔀 Capa de abstracción de acciones
│   └── action_router.py         # → Clasifica /j attack dragon → ActionResult
│
├── state/                        # 💾 Persistencia
│   └── state_manager.py         # Lee/escribe JSON, validate_state()
│
├── config.yaml                   # ⚙️ Configuración del bot
├── .env.example                  # 🔑 Template de variables de entorno
├── requirements.txt              # 📦 Dependencias Python
│
└── tests/                        # 🧪 274 tests
    ├── test_combat_engine.py
    ├── test_character_sheet.py
    └── test_diceRoller.py
```

---

## 🛠️ Desarrollo

```bash
# Correr todos los tests
python -m pytest tests/ -v

# Con coverage
python -m pytest tests/ --cov=bot --cov=dm --cov=adapters

# Validar campaign state
python -c "from state.state_manager import validate_state; validate_state()"

# Lint con ruff
ruff check bot dm adapters

# Type check con mypy
mypy bot dm --ignore-missing-imports

# Verificar sintaxis de config
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### 🔄 Flujo de Contribución

```
1. Fork → branch feat/mi-feature
2. Hackear
3. ruff check + mypy --ignore-missing-imports
4. pytest tests/ -v (todos green ✅)
5. PR → reviewers
6. Merge → CI corre ruff + mypy + pytest
```

---

## 📚 Especificaciones Detalladas

| Spec | Descripción |
|------|-------------|
| 📄 [SPEC_SPELL_SLOTS.md](SPEC_SPELL_SLOTS.md) | Sistema de spell slots D&D 5e completo |
| 📄 [SPEC_NPC_PERSISTENCE.md](SPEC_NPC_PERSISTENCE.md) | NPCs con memoria que persiste entre sesiones |
| 📄 [SPEC_IMAGE_GENERATION.md](SPEC_IMAGE_GENERATION.md) | Sistema de imágenes automáticas — triggers, cooldown, providers |
| 📄 [SPEC_DEATH_SAVES_PERSISTENCE.md](SPEC_DEATH_SAVES_PERSISTENCE.md) | Death saves sobreviven reinicios del bot |
| 📄 [SPEC_DICE_ANIMATION.md](SPEC_DICE_ANIMATION.md) | Renderizado animado de dados (slot machine style) |
| 📄 [SPEC_PLAN_B.md](SPEC_PLAN_B.md) | Plan B: Hermes Agent como DM cuando Pollinations falla |
| 📄 [PROJECT_PLAN.md](PROJECT_PLAN.md) | Roadmap completo del proyecto |

---

## 🤝 Autor

<p align="center">
<strong>Sherman</strong> — [@TheShugarBoy](https://twitter.com/TheShugarBoy) 🐦
<br/>
Desarrollado con Python 🐍, Telegram Bots API, y MiniMax LLM.
</p>

¿Encontraste un bug? 🐛 Abrí un [issue](https://github.com/sebaunsa-collab/hermesdm/issues) o mandame un DM en [Twitter](https://twitter.com/TheShugarBoy).

---

## 📜 Licencia

MIT — usalo, modificalo, compartilo. Si lo usás para algo copado, mandame un mensaje y contame. 🎲
