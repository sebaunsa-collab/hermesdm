---
name: hermesdm-dev-patterns
description: HermesDM development patterns — file editing gotchas, dataclass restructuring, animation patterns, and command conventions.
tags:
  - hermesdm
  - development
  - patterns
required_environment_variables: []
required_commands: []
setup_needed: false
---

# HermesDM Development Patterns

## Patching Large Dataclass Structures

**PROBLEMA:** `character_sheet.py` tiene `@dataclass class DeathSaves` seguido inmediatamente de `@dataclass class Character`. Cuando hacés patch en una sección que contiene el decorator de DeathSaves, el match puede agarrar también el `@dataclass` y mezclar ambas clases.

**LECCIÓN APRENDIDA:** Para archivos con múltiples `@dataclass` muy cercanos, no hacer targeted patches de "solo lo que cambia". Si necesitás reestructurar una sección que tiene `@dataclass` decorators, reemplazá toda la sección desde el inicio de la clase anterior hasta el final de la siguiente.

**PATRÓN CORRECTO para estos archivos:**
```python
# Reemplazar toda la sección problemática de un solo patch
patch(
    old_string="""@dataclass
class DeathSaves:
    successes: int = 0

@dataclass
class Character:
    name: str
    player_class: str
    # viejo bloque completo""",
    new_string="""@dataclass
class DeathSaves:
    successes: int = 0
    failures: int = 0

    def reset(self) -> None:
        ...

@dataclass
class Character:
    name: str
    player_class: str
    # nueva versión completa""",
)
```

## Dice Animation (Slot Machine)

Implementado en `bot/dice_animation.py`. Patrón de countdown existente:
1. Mandar mensaje inicial con `reply_text`
2. Encadenar `job_queue.run_once` con delays de 0.1s
3. Cada job edita el mensaje anterior
4. Frame final: resultado completo con formato rico

No usar `asyncio.sleep` — usar `job_queue.run_once`.

## Dynamic Classes System

- `normalize_class_name()` usa `_to_ascii()` propia (no `unidecode`) para evitar dependencia externa
- No hay `unidecode` en el sandbox — si aparece, usar implementación propia

## Import Circular

`dm/world_builder.py` importa de `bot/character_sheet.py`. No crear circular imports.

## Handler Offset para Comandos Personalizados

Cuando creás un nuevo comando con un nombre de N letras, el offset del slice del texto es N+2 (para skip "/xx ").
- `/j` → offset 3 (skip "/j ")
- `/act` → offset 5 (skip "/act ")
- `/attack` → offset 8 (skip "/attack ")

## Character — Patrón de Sub-Dataclasses

El Character dataclass usa composición de dataclasses más pequeños:
```python
@dataclass
class DeathSaves:
    successes: int = 0
    failures: int = 0

@dataclass
class SpellSlotTrack:
    total: list[int] = field(default_factory=lambda: [0]*9)
    used: list[int] = field(default_factory=lambda: [0]*9)

@dataclass
class Character:
    name: str
    hp: HP = field(default_factory=HP)          # sub-dc
    death_saves: DeathSaves = field(default_factory=DeathSaves)  # sub-dc
    spell_slots: SpellSlotTrack = field(default_factory=SpellSlotTrack)  # sub-dc
```

Siempre incluir `from_dict()` + `to_dict()` para serialización JSON.

## Crit Damage — Attack Bonus NO se Duplica

D&D 5e: en crítico, SOLO los dados de daño se duplican. El attack bonus NO.

```python
# ❌ WRONG — duplica todo
total = sum(crit_rolls) + attack_bonus * 2

# ✅ CORRECTO — solo dados duplicados
total = sum(crit_rolls) + attack_bonus  # bonus normal
```

## Short Rest — CON Modifier No Incluido

PHB: recuperar HP en short rest = Hit Die + CON modifier.

```python
# ❌ WRONG — solo el dado
recovered = random.randint(1, hit_die_faces)

# ✅ CORRECTO — dado + CON mod
recovered = random.randint(1, hit_die_faces) + self.con_mod
```

## Tests

274+ tests. Correr con:

```bash
cd /path/to/hermesdm && PYTHONPATH="" python3 -m pytest tests/ -x -q
```

## Python 3.10 Compatibility

- **No `\n` inside f-string `{}`** — valid syntax in Python 3.12+, syntax error on 3.10
  - Use `chr(10)` instead: `f"{'hi'}{chr(10)}text"`
  - Ruff rule: `F-invalid-escape-sequence` (syntax error, not auto-fixable)
- **Forward references** — use `TYPE_CHECKING` guard for imports only needed for type hints:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from state.npc_store import NPCStore  # Only for type hints, not runtime
  ```
