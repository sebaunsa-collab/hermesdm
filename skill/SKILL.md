# HermesDM — Game Command Handler

Skill para manejar comandos de D&D desde Telegram sin necesidad de un proceso separado.

## Mensajes que debo interceptar

Cuando recibo un mensaje de texto (no comando con `/`) que empieza con `!`, lo interpreto como comando de juego.

## Comandos disponibles

### !roll [XdY+Z]
Tira dados.

```
!roll 1d20        → tirada simple
!roll 2d6+3       → con modificador
!roll d20+5       → equivalente a 1d20+5
```

**Módulo:** `bot.dice_engine.roll(notación)`
**Retorna:** `{"total": N, "rolls": [...], "modifier": Z, "natural": X, "is_crit": bool, "is_fumble": bool, "notation": "XdY+Z", "str": "XdY+Z"}`

### !attack [objetivo] [AC]
Resuelve un ataque cuerpo a cuerpo.

```
!attack orco 15
```

**Módulo:** `bot.combat_engine.resolve_attack(atacante, defensor, attack_roll, weapon, advantage, disadvantage, defender_ac, rage_bonus)`
Para tirar el d20 antes: `bot.dice_engine.roll("1d20")`

### !spell [hechizo] [DC]
Lanza un hechizo.

```
!spell magic_missile 14
```

**Módulo:** `bot.combat_engine.resolve_spell(spell_name, spell_roll, target_dc)`
Para tirar: `bot.dice_engine.roll("1d20")`

## Cómo ejecutar

Usa `execute_code` (hermes_tools) para ejecutar el código. El path de HermesDM es `/home/hermes/hermesdm`.

```python
import sys
sys.path.insert(0, '/home/hermes/hermesdm')
from bot.dice_engine import roll
result = roll('1d20')
# result['total'] → número final
# result['rolls'] → lista de valores individuales
# result['is_crit'] → True si fue nat 20
# result['is_fumble'] → True si fue nat 1
```

## Formato de respuesta

Para `!roll`:
```
🎲 [XdY+Z]
Total: N
Rolls: [valores]
[+Z modificador]
[💥 Nat 20! / 💀 Nat 1!]
```

Para `!attack`:
```
⚔️ Ataque de [atacante] contra [defensor] (CA: AC)
[Hit/Miss]! [Daño] daño
[Notas]
```

Para `!spell`:
```
🔮 [Hechizo] vs DC [DC]
[Save success/fail]. [Daño] daño
```

## Notas importantes

- Solo interceptar mensajes que vienen por texto (no comandos Telegram con `/`)
- En grupo: el mensaje llega como texto plain, yo lo proceso
- El prefijo `!` evita conflictos con comandos de Telegram
- Los módulos son stateless — no guardan estado de partida (eso lo manejó yo con memoria)
