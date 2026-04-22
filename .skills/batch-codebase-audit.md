# SKILL — Batch Codebase Audit con Subagentes

## Cuándo usar

Proyecto Python grande (10+ módulos, 200+ tests) donde necesitás un inventario completo de:
- TODOs / FIXME pendientes
- Bugs obvios o código incompleto
- Imports faltantes
- Type errors
- Features faltantes entre módulos

## Método — Auditoría paralela en 4 waves

### Wave 1: Core + Tests (paralelo)
```
Task A: dm/ y adapters/
Task B: bot/ handlers
Task C: state/ + entry points
```
(3 subagentes en parallel via `tasks=[...]`)

### Wave 2: Scripts + Integración
```
Task: scripts/, run.py, main.py
```

### Wave 3: Consolidar resultados
Juntar outputs → priorizar por severidad:
- 🔴 CRÍTICO: crashes, TypeErrors en runtime, imports faltantes
- 🟡 ALTO: lógica incorrecta (daño, HP, etc.)
- 🟡 MEDIO: features incompletas (no rompen pero no funcionan)
- 🟢 BAJO: code smell, duplicación

### Wave 4: Fixear en orden
siempre verificar tests después de cada fix:

```bash
python3 -m pytest tests/ -x -q
```

## Findings comunes en proyectos Python heredados

1. **`import uuid`** a veces ausente si se usa `uuid.uuid4()` sin imports
2. **Código después de `return`** — imposible de detectar sin leer línea por línea
3. **Dataclass duplicadas fuera del decorator** — runtime crash
4. **MagicMock en tests** — no provee todos los attrs que el código real usa
5. **`field(default_factory=list)`** vs `field(default=list)` —后者 es error común

## Verificación post-fixes

Siempre correr tests completos después de cada fix individual o batch:

```bash
python3 -m pytest tests/ -q
```

Si rompe, identificar exact line con `--tb=short` antes de continuar.

## Notas

- Subagentes no tienen acceso al conversation history — todo contexto va en `goal` + `context`
- Tests que fallan post-fix:往往是 test desactualizado (espera old behavior), no bug en el fix
- Concurrency: hasta 3 subagentes paralelos por default
