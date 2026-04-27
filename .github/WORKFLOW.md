# HERMESDM — RULES OF ENGAGEMENT

## propósito

Este documento existe por una razón: en la sesión del 27/04/2026, pasamos 3 horas
rompiendo y arreglando en loop. Sin tests, sin git log, sin scope, sin rollback.
Sherman lo dijo: "por que rompemos cosas arreglando otras?"

Este documento es la respuesta. Son las reglas que SIEMPRE se cumplen cuando se
trabaja en HermesDM. No son sugerencias. Son el mínimo aceptable.

---

## REGLA 0 — WHOLE TEAM

Estas reglas aplican a TODOS los que trabajen en HermesDM, incluyendo agents como yo.
Si ves que se violan, pará y denunciá.

---

## REGLA 1 — NUNCA TOCAR CÓDIGO SIN SABER EN QUÉ ESTADO ESTÁ EL REPO

### Antes de hacer cualquier cosa:

```bash
# 1. Estado actual del repo
git status

# 2. Últimos commits — ¿qué cambió recientemente?
git log --oneline -10

# 3. Si el error es nuevo, buscar en el historial del archivo específico
git log --oneline -5 -- dm/world_builder.py

# 4. Si hay cambios sin commit, STASHEAR o COMMITEAR antes de continuar
git stash   # si no estás listo para commitear
# o
git add -A && git commit -m "WIP: lo que sea que estaba haciendo"
```

### Por qué:

La indentation bug del Layer 3 en world_builder.py — ¿la causamos nosotros o ya estaba?
No lo sabemos porque nadie miró el git log antes de tocar. Si hubiéramos mirado,
sabríamos si el problema era nuevo o antiguo.

### Critério:

Antes de escribir UNA LÍNEA de código, los 4 comandos de arriba ya se ejecutaron.
No hay excepción.

---

## REGLA 2 — UN PROBLEMA = UNA HIPÓTESIS = UN SCOPE = UN FIX

### El anti-patrón que prohibimos:

```
SHERMAN: "el setup falla"
AGENTE:  "ah bueno voy a tocar _is_echo, _try_close_json, max_tokens,
          Layer 3 parsing Y la genre validation — a ver cual era"
```

Eso no es debugging. Eszaratapeleo. Cada cambio que hacés toca algo que no
entendés, y cuando algo se rompe después, no sabés cuál fue el culpable.

### Protocolo para cada bug:

```
PASO 1 — Identificar el error exacto
  - ¿Qué input produce qué output?
  - ¿Cuál es el traceback completo? (no la última línea)
  - ¿En qué línea del código falla?

PASO 2 — Formular UNA hipótesis
  - "El problema es X porque Y"
  - No: "capaz es X o Y o Z"

PASO 3 — Definir el SCOPE del fix
  - ¿Qué líneas se tocan?
  - ¿Qué funciones se ven afectadas?
  - ¿Qué tests deberían pasar después?

PASO 4 — Hacer el fix
  - Un archivo a la vez
  - Un concepto a la vez

PASO 5 — Verificar
  - ¿Los tests pasan?
  - ¿El fix resuelve el problema exacto del PASO 1?
```

### Critério:

Si no podés explicar en una frase cuál es el problema, cuál es la causa, y cuál
es la solución — no toques código. Pedí clarification primero.

---

## REGLA 3 — TESTS ANTES DE FIX (TDD LITE)

### Esta es la regla más violada y la más importante.

Cada vez que encontrás un bug, el proceso es:

```
1. Escribir un test que REPRODUCE el bug
2. Ver que el test falla
3. Hacer el fix
4. Ver que el test pasa
5. Correr la suite completa
```

### No hay paso 6 donde "después testeamos en Telegram".

### Ejemplo real del problema que tuvimos:

BUG: generate_setup_with_ai con "piratas" generaba "samurai" y crasheaba.

PROCESO CORRECTO:
```python
# tests/test_world_builder.py
def test_genre_validation_respects_user_genre():
    """Layer 1 debe rechazar contenido que no matchea el género solicitado."""
    with pytest.raises(GenreValidationError):
        generate_setup_with_ai("samurai fight", ...)
    # El test falla — porque ahora el código SÍ genera samurai
    # Entonces arreglamos el código
    # Ahora el test pasa
```

PROCESO QUE TUVIMOS:
1. Mandamos mensaje en Telegram
2. Vimos el error
3. Tocamos 5 archivos
4. Levantamos el bot de nuevo
5. Mandamos otro mensaje
6. ¿Funcionó? Capaz.

### Excepciones aceptables:

- Fixes triviales de typos, renombres, comments
- Cambios en archivos de tests
- Cuando NO hay test coverage para ese código y escribirlo tomaría >30min
  (en ese caso: agregar un ticket al backlog para test coverage)

### Critério:

Todo fix que dure más de 15 minutos requiere un test. Siempre.

---

## REGLA 4 — LA SUITE DE TESTS DEBE PASAR ANTES DE DEPLOYAR

### Running the test suite:

```bash
# Unit tests (fast, sin API calls)
python3 -m pytest tests/test_world_builder.py -v --tb=short

# Integration tests (pueden necesitar API keys)
python3 -m pytest tests/ -v --tb=short -x   # -x para en el primer failure

# Un módulo específico
python3 -m pytest tests/test_world_builder.py tests/test_world_builder_echo.py -v
```

### Estado actual (27/04/2026):

```
tests/test_world_builder.py      — 28 passed (usa mocks)
tests/test_world_builder_echo.py — 9 failed (API real, 400 errors)
tests/                          — ~230 tests total, algunos outdated
```

Los tests de `test_world_builder_echo.py` que fallan con 400 son esperados —
son tests de integración que requieren API real. No bloquean el deploy de
fixes a `world_builder.py` si los unit tests pasan.

### Critério:

- pytest en modo fail-fast (`-x`) hasta que la suite pase verde
- Si un test falla, NO COMMITEAR hasta que pase o esté marcado como skip
- Si un test estaba marcado como skip, documentar POR QUÉ

---

## REGLA 5 — ROLLBACK SIEMPRE DISPONIBLE

### Antes de hacer cambios:

```bash
# Opción A: git stash (para cambios sin commit)
git stash
# ...haces los fixes...
# ...testaste todo...
git stash pop   # si todo está bien
# o
git stash drop  # si quisiste descartar

# Opción B: branch por feature (preferido para fixes importantes)
git checkout -b fix/setup-genre-validation
# ...trabajás...
# ...testaste todo...
git checkout main && git merge fix/setup-genre-validation
# Si algo se rompe: git checkout main y el branch queda como backup
```

### Commit messages significativos:

```
❌ git commit -m "fix"
❌ git commit -m "arreglo"
❌ git commit -m "updates"

✓ git commit -m "fix: Layer 3 genre validation false positive on genre mismatch"
✓ git commit -m "fix: _is_echo threshold 0.60→0.75 to reduce false positives"
✓ git commit -m "test: add regression test for genre validation on samurai input"
```

### Critério:

Nunca hacer un fix sin saber cómo volver atrás. Si no hay git stash o branch,
el fix no está listo.

---

## REGLA 6 — REFACTORING = SEPARADO DEL BUG FIX

### El anti-patrón:

```
"Ya que estoy tocando el código, voy a limpiar las partes que están feas."
```

### Por qué está mal:

Cuando mezclás refactoring con bug fixing, si algo se rompe después, no sabés
si fue el refactor o el fix. Y reviewers no pueden hacer diff limpio.

### Regla:

1. Bug fix: en su propio commit, con su propio test
2. Refactoring: en su propio commit, sin cambio de comportamiento
3. Mejora de features: en su propio commit

Si querés hacer refactoring Y hay un bug — arreglá el bug primero, commit,
después el refactoring.

### Critério:

Si un commit mezcla "fix X" con "también limpié Y" — ese commit se rechaza.

---

## REGLA 7 — DOCUMENTAR DECISIONES, NO SOLO RESULTADOS

### El problema:

Cuando rompimos el echo threshold de 0.60 a 0.75, no quedó registrado POR QUÉ
ese número. Un future developer (o future us) ve "0.75" y no sabe si era
arbitrario o fundado.

### Cómo documentar:

1. **En el commit message**: explicar el razonamiento, no solo el qué

```bash
git commit -m "fix: _is_echo threshold 0.60→0.75

Razón: 'tesoro' en prompt de piratas重叠 0.60 con respuesta, causando
falso positivo. Stopword filtering ayude pero no alcanza.
Threshold 0.75 filtra el caso real sin perder detección real.

Ver: https://github.com/sebaunsa-collab/hermesdm/issues/XXX"
```

2. **En el código**: comments para decisiones no obvias

```python
# The 0.75 threshold was set empirically: 'tesoro' in pirate prompts
# triggered overlap=0.60, which was at the old 0.60 threshold.
# 'piratas', 'tesoro', 'rey' in same prompt → max overlap ~0.67.
# 0.75 gives headroom without losing real echo detection.
ECHO_THRESHOLD = 0.75
```

3. **SPECs para features nuevas**: antes de implementar, escribir qué se va a
   construir y por qué. SPEC.md ya existe — mantenerlo actualizado.

### Critério:

Después de 6 meses, un nuevo developer (o vos mismo) debería poder leer el
git log y entender cada decisión sin tener que preguntar.

---

## REGLA 8 — DEPENDENCY RULE (quién toca qué)

```
telecom_handler.py  →  NUNCA tocar sin leer todo el flujo primero
world_builder.py   →  función grande, frágil — tests OBLIGATORIOS antes de tocar
state_manager.py   →  core del juego — cualquier cambio requiere tests
narrative_generator.py → LLM calls — puede romper sin errores visibles
provider_client.py →  API wrapper — cambios aquí afectan todo el DM
```

### Por qué importa:

world_builder.py tiene 3 capas de fallback, validación de género, echo detection,
parsing de JSON. Eso no es una función — es un mini-sistema. Cuando hacés un
cambio ahí, interactúa con todo lo demás.

### Critério:

Antes de tocar cualquier archivo de arriba, verificá que hay test coverage o
escribí uno.

---

## REGLA 9 — 6 PUNTOS CRUZADOS (NUESTRO CASO ESPECÍFICO)

Esta es la auditoría de lo que salió mal el 27/04/2026 y cómo se podría
haber evitado:

| # | Problema | Regla que lo hubiera prevenido | Qué hacer |
|---|----------|-------------------------------|-----------|
| 1 | No hay test suite | REGLA 3 | tests/test_world_builder.py YA EXISTE con 28 tests passing. Ejecutar ANTES de deployar. |
| 2 | No hay REPL | REGLA 3 + REGLA 1 | `python3 -c "from dm.world_builder import generate_setup_with_ai; ..."` antes de tocar código |
| 3 | No miramos git log | REGLA 1 | git log --oneline -10 Y git log --oneline -5 -- <archivo> antes de cualquier cosa |
| 4 | Mezclamos debugging con fixing | REGLA 2 | UN problema, UNA hipótesis, UN scope. No tocar 5 archivos a la vez. |
| 5 | Deuda técnica (función gigante) | REGLA 6 + REGLA 8 | generate_setup_with_ai necesita refactor. Marcarlo como deuda. Mientras tanto: tests. |
| 6 | No hacemos rollback | REGLA 5 | git stash antes de cambiar. Branch por feature para fixes importantes. |

---

## REGLA 10 — CUANDO NO ESTÉS SEGURO, PARÁ Y PREGUNTÁ

Si después de aplicar las reglas 1-9 no estás seguro de qué hacer,:
1. No guess
2. No "voy a tocar a ver qué pasa"
3. Preguntás

El objetivo es que en 6 meses no haya "se rompió no sé por qué" ni
"el que lo wrote ya no está". Cada decisión se explica en el commit,
cada bug se reproduce en un test, cada fix tiene rollback.

---

## CHECKLIST ANTES DE COMMITEAR

```
[ ] git status — sin cambios inesperados
[ ] git log --oneline -3 — todos los commits tienen mensaje claro
[ ] pytest tests/test_world_builder.py -v — 28 tests passing
[ ] pytest tests/test_world_builder_echo.py -v — 9 failing (known, con 400 API errors)
[ ] Si toqué world_builder.py — hay test que reproduce el bug fix
[ ] Si toqué telecom_handler.py — probé al menos un comando manualmente
[ ] No hay mezcla de refactoring + bug fix en el mismo commit
[ ] El commit message explica EL POR QUÉ, no solo EL QUÉ
```

---

## ARCHIVOS DEL PROYECTO

```
HERMESDM
├── SPEC.md                    — Especificación oficial (fuente de verdad)
├── SPEC-*.md                  — Especificaciones de features individuales
├── SDD-*.md                   — System Design Documents
├── references/
│   ├── PIPELINE.md            — Pipeline de generation de contenido
│   ├── ANTI-PATTERNS.md       — Known bad patterns
│   └── CRAFT.md               — Sistema CRAFT de generación
├── dm/
│   ├── world_builder.py       — CRÍTICO: 3 capas fallback, frágil
│   ├── narrative_generator.py — LLM calls, puede romper sin errores
│   └── provider_client.py     — API wrapper, todo pasa por acá
├── bot/
│   └── telecom_handler.py     — Entry point del bot, 4000+ líneas
├── state/
│   └── state_manager.py       — Core del juego
├── game_engine/               — Motor de juego (futuro)
└── tests/
    ├── test_world_builder.py  — Unit tests (28 passing, USA MOCKS)
    ├── test_world_builder_echo.py — Integration tests (9 failing, API real)
    └── ...                    — Otros módulos
```

---

## VERSION

Fecha: 27/04/2026
Autor: Hermes Agent (revisión Sherman)
Estado: ACTIVO — todas las sesiones de trabajo en HermesDM deben seguir estas reglas
Revisión: Cada 30 días o después de cada incidente de "rompimos algo arreglando otra cosa"
