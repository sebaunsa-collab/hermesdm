═══════════════════════════════════════
SPEC — Dice Roll Animation (Slot Machine)
═══════════════════════════════════════

## Resumen
Animación tipo slot machine para resultados de tiradas de dados.
El número "rueda" 6 frames antes de mostrar el resultado final.

## Contexto
- Sherman quiere que las tiradas de dados se sientan más dramáticas
- Actualmente el resultado aparece instantáneo — sin tensión
- El countdown ya usa `edit_message_text` en loop — reutilizamos ese patrón
- No hay APIs externas — todo local con `random` y `job_queue`

## Requirements

### R1: Animación slot machine de dados
**Descripción:** Cuando un personaje hace una tirada (ataque, skill check, etc.),
el resultado NO aparece directo. Primero "rueda" 6 valores rápidos (0.1s cada uno),
luego muestra el resultado final.
**Criterio de aceptación:**
- [ ] `/act attack` → valores parpadean 6 frames antes del resultado real
- [ ] `/act intimidate` → valores parpadean 6 frames antes del resultado real
- [ ] `/act investigate` → valores parpadean 6 frames antes del resultado real
- [ ] Cada frame tiene el formato: `🎲 Rolling... ⚄ ⚁ ⚀ ⚃ ⚅ ⚅`
- [ ] El ÚLTIMO frame muestra el resultado real (d20+mod=total vs DC)
**Priority:** must-have
**Risks:** Rate limit de Telegram (~30 edits/min). Si hay 10 jugadores tirando a la vez,
puede haber problemas. Mitigación: frames rápidos (0.1s), no más de 7 edits por tirada.

### R2: Unicode dice faces para frames de "rueda"
**Descripción:** Usar Unicode dice faces ⚀⚁⚂⚃⚄⚅ (U+2680-U+2685) para los frames de animación.
**Criterio de aceptación:**
- [ ] 6 valores aleatorios de ⚀⚁⚂⚃⚄⚅ aparecen en cada frame
- [ ] No se usa ASCII art de dados — solo Unicode chars
**Priority:** must-have
**Risks:** Ninguno — Unicode standard en todos los clientes Telegram

### R3: Formato del resultado final (post-animación)
**Descripción:** Después de los 6 frames, el mensaje final muestra el resultado completo
con formato rico y emoji. Reemplaza completamente el mensaje animado.
**Criterio de aceptación:**
- [ ] Ataque exitoso: `⚔️ ¡ACIERTO! | 🎲 d20+5+6=31 vs AC 18 | 💥 24 daño`
- [ ] Ataque fallido: `❌ ¡FALLAZO! | 🎲 d20+5+6=7 vs AC 18 | El golpe erra completamente.`
- [ ] Skill check exitoso: `✅ ¡ÉXITO! | 🎲 d20+8=23 vs DC 14 | +9 sobre el objetivo`
- [ ] Skill check fallido: `❌ ¡FALLA! | 🎲 d20+2=5 vs DC 15 | Fallas por 10.`
- [ ] Crítico (nat 20): `🌟 ¡CRÍTICO!` badge especial en el frame final
- [ ] Fumble (nat 1): `💀 ¡FUMBLE!` badge especial en el frame final
**Priority:** must-have
**Risks:** Ninguno

### R4: Sin animación para acciones sin dado
**Descripción:** Acciones que no tiran dado (disengage, dodge, dash, ready, help)
NO deben mostrar animación — van directo al resultado/confirmación.
**Criterio de aceptación:**
- [ ] `/act dodge` → sin animación, mensaje directo: "Valdric se prepara para esquivar. (hasta su próximo turno)"
- [ ] `/act dash` → sin animación, confirmación directa
- [ ] `/act hide` → SI tiene tirada de dado (stealth check), entonces SÍ anima
**Priority:** must-have
**Risks:** Ninguno

### R5: Detección de acciones que tiran dado
**Descripción:** El sistema determina si una acción tiene tirada de dado (y por tanto
debe animar) basándose en el `action_type` del `ActionRouter`.
**Criterio de aceptación:**
- [ ] `action_type` en {attack, cast, intimidate, persuade, deceive, investigate,
  medicine, history, arcana, religion, survival, sleight, athletics, acrobatics,
  animal, perception, shove, hide, use_object} → SÍ anima
- [ ] `action_type` en {disengage, dodge, dash, ready, help, rest, dialogue} → NO anima
**Priority:** must-have
**Risks:** Ninguno

### R6: Job queue para frames de animación
**Descripción:** Usar `application.job_queue.run_once()` con delay 0.1s para encadenar
los 6 frames de animación. Mismo patrón que `_countdown_edit`.
**Criterio de aceptación:**
- [ ] Frame 1 (0.1s): `🎲 Rolling... ⚄ ⚁ ⚀ ⚃ ⚅ ⚅`
- [ ] Frame 2 (0.2s): `🎲 Rolling... ⚁ ⚃ ⚅ ⚀ ⚄ ⚂`
- [ ] Frame 3 (0.3s): `🎲 Rolling... ⚃ ⚅ ⚂ ⚁ ⚀ ⚅`
- [ ] Frame 4 (0.4s): `🎲 Rolling... ⚅ ⚂ ⚀ ⚄ ⚁ ⚃`
- [ ] Frame 5 (0.5s): `🎲 Rolling... ⚂ ⚀ ⚄ ⚅ ⚃ ⚁`
- [ ] Frame 6 (0.6s): `🎲 Rolling... ⚀ ⚄ ⚁ ⚃ ⚂ ⚅`
- [ ] Frame 7 (0.7s): mensaje FINAL con resultado real
**Priority:** must-have
**Risks:** Rate limit — mitigado con solo 7 edits máx por tirada.

### R7: Acciones múltiples (ataque + daño)
**Descripción:** Cuando una tirada tiene DOS valores (ataque Y daño — como un crítico),
la animación muestra AMBOS valores rodando y resolviendo.
**Criterio de aceptación:**
- [ ] Ataque crítico: el d20 Y el daño parpadean, luego se resuelve el crítico
- [ ] Daño muestra sus dice rolls individuales: `2d6+4 = ⚅⚄+4 = 14`
**Priority:** should-have
**Risks:** Complejidad adicional — si no hay tiempo, se hace solo d20 rodando.

## Arquitectura propuesta

```
bot/
  dice_animation.py          # NUEVO — lógica de animación
    _DICE_FACES = ["⚀","⚁","⚂","⚃","⚄","⚅"]

    async def _dice_frame_edit(context, chat_id, message_id, frame_index, frames, final_text, parse_mode)
        → editar mensaje con frames[frame_index]
        → schedule next frame o final text

    async def animate_dice_roll(context, chat_id, message_id, roll_result, action_type, mechanic_inline, character_name)
        → determina si anima (check R5)
        → si NO anima: editar directamente con final_text
        → si SÍ anima: enviar initial message → chain 6 frame edits → final edit

telegram_handler.py
  _j_action_handler (modificado)
    → ActionRouter.route() — obtiene result
    → check if action_type needs animation (R5)
    → if needs animation: animate_dice_roll(context, chat_id, message_id, ...)
    → if not: reply_text directamente con result

  j_action_handler (modificado)
    → pasar context y message.message_id a animate_dice_roll
```

## Tech Stack
- Python `random` para seleccionar dice faces
- Python-telegram-bot `job_queue.run_once()` para encadenar frames
- `ParseMode.MARKDOWN` para formato rico
- No APIs externas, no dependencias nuevas

## Tiempo estimado
XS | S | M | L — Estimado: **S** (~1-2 horas)

## Edge cases a considerar
- **Rate limit**: Si 10 jugadores tiran dados simultáneamente, 70 edits en 1 segundo.
  No es probable en async Telegram, pero si pasa el bot puede recibir 429.
  Mitigación: los edits son tan rápidos (0.1s apart) que el riesgo es bajo.
- **Acciones sin dado**: dash/disengage/dodge/ready/help/rest — no animan,van directo.
- **Crítico + fumble simultáneo**: nat 20 en un ataque con daño crítico ya está manejado
  en `_resolve_attack`. El fumble badge (nat 1) también.
- **Mensaje demasiado largo**: frames de animación son cortos (`🎲 Rolling... ⚄⚁⚀⚃⚅⚅`),
  no superan límite de Telegram. El resultado final tiene ~200 chars, también OK.

## Out of scope
- Animación para el countdown de combate (ya existe y funciona)
- Animación para el `/roll` standalone (comando separado — diferente flujo)
- Narrativa del DM durante la animación
- Sonido o haptic feedback (Telegram no soporta)
- GIF o video de dados rodando (requeriría API externa)
- "Dramatic pause" antes de mostrar resultado — la animación ya crea la pausa

═══════════════════════════════════════
