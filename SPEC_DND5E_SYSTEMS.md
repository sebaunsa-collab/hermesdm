═══════════════════════════════════════
SPEC — D&D 5e Real: XP, Leveling, Items
═══════════════════════════════════════

## 1. XP & Leveling

### XP Table (D&D 5e oficial)

| Level | XP Required |
|-------|------------|
| 1 | 0 |
| 2 | 300 |
| 3 | 900 |
| 4 | 2,700 |
| 5 | 6,500 |
| 6 | 14,000 |
| 7 | 23,000 |
| 8 | 34,000 |
| 9 | 48,000 |
| 10 | 64,000 |
| 11 | 85,000 |
| 12 | 100,000 |
| 13 | 120,000 |
| 14 | 140,000 |
| 15 | 165,000 |
| 16 | 195,000 |
| 17 | 225,000 |
| 18 | 265,000 |
| 19 | 305,000 |
| 20 | 355,000 |

### Proficiency Bonus (D&D 5e oficial)

| Level | Prof Bonus |
|-------|-----------|
| 1-4 | +2 |
| 5-8 | +3 |
| 9-12 | +4 |
| 13-16 | +5 |
| 17-20 | +6 |

### Level Up — HP

HP nivel 1 = HP base de clase + CON mod.
HP por nivel subsequente = Hit Die de clase + CON mod (mínimo 1).

### Level Up — Qué gana el personaje

Cada nivel: +HP (según hit die), +Proficiency Bonus (según tabla), possible +feature de clase.

Para esta spec: nos centramos en HP y Proficiency. Features narrativas se manejan via DM.

---

## 2. Character Fields (cambios)

### Character: campos nuevos

```python
@dataclass
class Character:
    # ...existing fields...

    # XP / Leveling
    xp: int = 0                          # experiencia actual
    level: int = 1                       # nivel actual (1-20)

    # HP (cambia: ahora es objeto HP con más métodos)
    # hp ya existe como HP (max/current/temp) — sin cambios

    # Spellcasting (para classes con spell slots)
    spell_slots: dict[int, int] = field(default_factory=dict)  # {1: 4, 2: 3, 3: 2, 4: 1}

    # Items
    carried_gold: int = 0
    weight_carried: float = 0.0
    inventory: list[Item] = field(default_factory=list)

    # Magic items detectados (para narrativa)
    magic_items: list[str] = field(default_factory=list)
```

### HP: métodos nuevos

```python
class HP:
    max: int
    current: int
    temp: int
    hit_die_faces: int = 8   # d4/d6/d8/d10/d12
    hit_dice_remaining: int = 0  # para Short Rest

    def level_up(self, con_mod: int, hit_die_faces: int) -> int:
        """Sube de nivel. Retorna HP ganado."""
        roll = random.randint(1, hit_die_faces)
        gained = roll + con_mod
        self.max += max(1, gained)  # mínimo 1 HP
        self.current = self.max    # cur-full al subir
        return max(1, gained)

    def short_rest(self) -> None:
        """Recupera Hit Dice (no más de level//2)."""
        # No implementado por ahora — placeholder
        pass

    def full_heal(self) -> None:
        """Curación completa."""
        self.current = self.max
        self.temp = 0
```

---

## 3. XP System

### Awarding XP

XP se maneja manualmente por el DM. Comandos:
```
/xp Marco 100
/xp todos 50
/xp see
```

El DM decide qué otorga XP y cuánto.

### Level Up Check

Cada vez que se modifica XP (vía `/xp`), se verifica si cruzó el umbral.

```python
XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000,
                48000, 64000, 85000, 100000, 120000, 140000,
                165000, 195000, 225000, 265000, 305000, 355000]

PROFICIENCY_BY_LEVEL = [0, 2, 2, 2, 2, 3, 3, 3, 3, 4,
                         4, 4, 4, 5, 5, 5, 5, 6, 6, 6]
```

Al subir de nivel:
1. Se recalcula HP máximo (level_up)
2. Se recalcula Proficiency Bonus
3. Se muestra mensaje de level up al player
4. HP actual se pone al nuevo máximo (curación parcial)

---

## 4. Items System

### Item Fields

```python
@dataclass
class Item:
    name: str
    quantity: int = 1
    weight: float = 0.0           # pounds
    rarity: str = "common"        # common/uncommon/rare/very rare/legendary
    is_equipped: bool = False
    armor_class: int | None = None  # si es armadura
    attack_bonus: int | None = None  # si es weapon
    damage_dice: str | None = None   # "1d8" si es weapon
    description: str = ""
    is_magic: bool = False
    is_consumable: bool = False    # poción, comida, etc.
```

### Equip/Unequip

```
/equip Marco espada larga
/unequip Marco espada larga
```

Al equipar:
- `equipped_weapon` se actualiza
- `equipped_armor` se actualiza (y recalcula AC)
- Se marca `is_equipped=True` en el item

### Inventory

```
/inv Marco
→ Inventario de Marco:
  • Espada larga (x1) — equipada
  • Poción de curación (x2) — 0.5 lb ea
  • Armadura de cuero (x1) — equipada, AC 11+DEX
  — Peso total: 15.5 lb | Oro: 25 gp
```

- Máximo peso carry: STR × 15 lbs (D&D 5e standard)
- Si supera el peso → disadvantage en Athletics para Dodge/Dash/Shove

---

## 5. Magic Items

Magic items son narrativa + bonuses, no cambios mecánicos automáticos (salvo que el DM lo decida).

El DM puede otorgar un magic item con:
```
/item Marco "Espada Flamígera" legendary
```

Mensaje narrativo automático: "Marco recibe: Espada Flamígera (legendary)"

---

## 6. Cambios en Archivos

### `bot/character_sheet.py`
- Agregar `XP_THRESHOLDS`, `PROFICIENCY_BY_LEVEL`
- Agregar `xp`, `spell_slots`, `carried_gold`, `weight_carried`, `magic_items` a `Character`
- Modificar `HP` class: `hit_die_faces`, `hit_dice_remaining`, `level_up()`
- Modificar `Item`: `weight`, `rarity`, `is_equipped`, `armor_class`, `attack_bonus`, `damage_dice`, `is_magic`, `is_consumable`
- Método `level_up_character(char, con_mod)` global
- Método `get_xp_to_next_level(level)` helper
- `to_dict()` y `from_dict()` actualizados

### `bot/telegram_handler.py`
- `cmd_xp()` — `/xp <nombre> <cantidad>` — awarding XP
- `cmd_inventory()` — `/inv` — ver inventario
- `cmd_equip()` — `/equip <item>` — equipar item
- `cmd_unequip()` — `/unequip <item>` — desequipar
- `cmd_give_item()` — `/item <nombre> <item>` — DM otorga item
- `_format_character_sheet()` — mostrar XP/Level/Proficiency/Inventory

### `state/state_manager.py`
- `CampaignSettings` puede crecer, pero para estas specs no cambia

---

## 7. DM Commands Resumidos

| Comando | Descripción |
|---------|-------------|
| `/xp Marco 100` | Dar 100 XP a Marco |
| `/xp todos 50` | Dar 50 XP a todos los players |
| `/xp see Marco` | Ver XP/Level de Marco |
| `/inv Marco` | Ver inventario completo |
| `/item Marco Poción de curacíon x3` | Dar item a Marco |
| `/equip Marco espada` | Equipar item |
| `/unequip Marco espada` | Desequipar |
| `/levelup Marco` | Forzar level up (DM decide) |

---

## 8. Lo que NO cambia (sigue igual)

- Sistema de acciones (/act)
- Sistema de combate (turnos, iniciativa, countdown)
- Sistema de condiciones (blinded, prone, etc.)
- Sistema de death saves
- Sistema de clases (dinámicas — sin cambios)
- Narrative generator

---

## Aprobado por: Sherman
## Fecha: Apr 22, 2026
