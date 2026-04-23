# SPEC.md — HermesDM Web Companion v2.0
## Full Audit & Remediation Plan

**Document version:** 2.0  
**Date:** 2026-04-23  
**Author:** Auditoría automática + fixes planificados  
**Scope:** Backend (`server.py`) + Frontend (`static/index.html`) + Infra (`Dockerfile`, `docker-compose.yml`)  
**Target state:** Production-ready, sin bugs críticos, escalable hasta ~50 conexiones simultáneas.

---

## 1. Executive Summary

El HermesDM Web Companion es un dashboard FastAPI + vanilla JS que lee `state.json` de HermesDM. Tras auditoría de 8 archivos se detectaron **12 issues**: 6 críticos (rompen UX o son inseguros), 6 menores (deuda técnica / UX rota). Este SPEC detalla cada fix, su implementación, y los tests de verificación.

**Estado actual:** NO apto para producción.  
**Estado post-fix:** Deployable en VPS en <5 min con `docker compose up`.

---

## 2. Issues Catalogue

### 🔴 P0 — Críticos (sin esto no sirve)

| ID | Issue | Archivo | Líneas | Impacto |
|---|---|---|---|---|
| P0-1 | **Player selector destruido por `renderCharacterSheet`** | `index.html` | 905–926, 929–955 | Al cambiar de personaje, el `<select>` desaparece. No se puede volver a cambiar. |
| P0-2 | **CSS variable `--text-dim` no definida** | `index.html` | ~20 usos | Texto fallback a `inherit` — colores rotos en pantalla de selección, fallback de NPCs, quests vacías. |
| P0-3 | **Polling duplica entradas de log** | `index.html` | 1114–1131 | Si SSE falla y reconecta, o si hay múltiples entradas nuevas entre polls, el log se corrompe con duplicados o saltos. |
| P0-4 | **N poll tasks por cliente SSE** | `server.py` | 111–156, 229–263 | Con N jugadores = N× lecturas de disco/seg por campaign. I/O thrashing. |
| P0-5 | **Dead code `state_changed_event`** | `server.py` | 92–104 | Función y diccionario `sse_clients` nunca usados. Basura arquitectónica que confunde mantenimiento. |
| P0-6 | **Double JSON encoding en SSE events** | `server.py` | 135–152 | `data` se serializa a JSON string, luego `EventSourceResponse` lo vuelve a serializar. Frágil, depende de escaping correcto. |

### 🟡 P1 — Menores (deuda técnica / UX)

| ID | Issue | Archivo | Fix rápido |
|---|---|---|---|
| P1-1 | **CORS abierto `allow_origins=["*"]`** | `server.py` L42 | Restringir a `FRONTEND_ORIGIN` o default `localhost` en dev. |
| P1-2 | **`parseDice` no tolera espacios** | `index.html` L1163 | `.replace(/\s/g, '')` antes de regex. |
| P1-3 | **`renderCharacterSheet()` llamado sin arg en `selectCampaign`** | `index.html` L877 | Llamada: `renderCharacterSheet(state.characters[keys[0]])`. |
| P1-4 | **Docker-compose mount path mismatch** | `docker-compose.yml` L7 | Mount `~/.hermes/hermesdm/campaigns:/data/campaigns` directamente. |
| P1-5 | **SPEC v1.0 desactualizado** | `SPEC.md` | Reemplazar por este documento. |
| P1-6 | **Ventana de race: SSE + polling paralelos** | `index.html` | `disconnectSSE()` debe matar polling SIEMPRE antes de reconectar. |

---

## 3. Technical Design

### 3.1 Fix P0-1: Player Selector Persistence

**Problema:** `buildPlayerSelect()` inyecta un `<div class="player-select">` dentro de `$charSheet`. Luego `renderCharacterSheet()` hace `$charSheet.innerHTML = '...'` destruyendo el selector.

**Solución:** Mover el selector a un contenedor DOM separado, fuera del panel de character sheet.

```html
<!-- NUEVO contenedor en index.html, dentro de .left-column pero ANTES del panel -->
<div id="playerSelectContainer"></div>
```

```javascript
// buildPlayerSelect() ahora usa playerSelectContainer en vez de prepend a $charSheet
document.getElementById('playerSelectContainer').appendChild(div);
```

```javascript
// renderCharacterSheet() solo muta $charSheet, el selector queda intacto
```

---

### 3.2 Fix P0-2: CSS Variable Definition

**Solución:** Agregar a `:root`:

```css
:root {
  /* ...existing vars... */
  --text-dim: #5a5245;   /* NUEVO: entre muted y secondary */
}
```

Revisar todos los usos de `var(--text-dim)` y asegurar que no haya typos adicionales (audit: `--text-dim` usado 5 veces, ningún otro typo detectado).

---

### 3.3 Fix P0-3 + P1-6: Log Deduplication + SSE/Polling Race

**Problema:** El polling usa `JSON.stringify(data)` completo como fingerprint. Si cambia cualquier campo, se asume "nuevo estado" y se hace `appendLogEntry(last)` — aunque `last` ya esté en el DOM.

**Solución:** Usar contador de eventos en vez de string comparison.

```javascript
// state:
lastLogLength: 0,   // ← NUEVO

// startPolling:
if (data.history && data.history.length > state.lastLogLength) {
  const newEntries = data.history.slice(state.lastLogLength);
  newEntries.forEach(e => appendLogEntry(e));
  state.lastLogLength = data.history.length;
}
```

**Race fix:** En `connectSSE()`, llamar `disconnectSSE()` ANTES de crear el `EventSource` nuevo. Asegurar que `disconnectSSE()` limpie pollingTimer.

```javascript
function connectSSE() {
  disconnectSSE(); // ← garantiza que polling no corra
  // ...crear EventSource...
}
```

---

### 3.4 Fix P0-4: Global Single Polling per Campaign

**Problema:** Cada cliente SSE crea su propia coroutine `poll_state_file` que lee disco cada 1s.

**Solución:** Un solo `campaign_watchers: dict[str, asyncio.Task]` a nivel de módulo.

```python
# Global
_campaign_watchers: dict[str, asyncio.Task] = {}
_campaign_queues: dict[str, list[asyncio.Queue]] = {}

async def ensure_campaign_watcher(campaign_id: str, state_path: Path):
    if campaign_id in _campaign_watchers:
        return
    task = asyncio.create_task(_poll_state_global(campaign_id, state_path))
    _campaign_watchers[campaign_id] = task
    _campaign_queues[campaign_id] = []

def register_queue(campaign_id: str, queue: asyncio.Queue):
    if campaign_id not in _campaign_queues:
        _campaign_queues[campaign_id] = []
    _campaign_queues[campaign_id].append(queue)

def unregister_queue(campaign_id: str, queue: asyncio.Queue):
    _campaign_queues[campaign_id].remove(queue)
    if not _campaign_queues[campaign_id]:
        _campaign_watchers[campaign_id].cancel()
        del _campaign_watchers[campaign_id]
        del _campaign_queues[campaign_id]

async def _poll_state_global(campaign_id: str, state_path: Path):
    """Un único polling task por campaign. Notifica a todas las queues."""
    last_mtime = None
    last_content = None
    while True:
        try:
            if state_path.exists():
                current_mtime = state_path.stat().st_mtime
                if last_mtime is None:
                    last_mtime = current_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    with open(state_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content != last_content:
                        last_content = content
                        state = json.loads(content)
                        events = _build_events_from_state(state)
                        for queue in _campaign_queues.get(campaign_id, [])[:]:
                            for ev in events:
                                try:
                                    await queue.put(ev)
                                except Exception:
                                    pass
        except Exception as e:
            logger.error(f"Poll error {campaign_id}: {e}")
        await asyncio.sleep(1)
```

---

### 3.5 Fix P0-5: Eliminar Dead Code

**Eliminar:**
- Diccionario `sse_clients: dict[str, list]` (línea 93)
- Función `state_changed_event` (líneas 96–104)
- Import `time` si solo se usaba ahí (revisar: se usa en otras partes, mantener)

---

### 3.6 Fix P0-6: SSE Single Serialization

**Problema:** `poll_state_file` pone `json.dumps({...})` en `data`, luego `EventSourceResponse` serializa de nuevo.

**Solución:** Pasar dict nativo y dejar que `sse_starlette` maneje la serialización.

```python
# ANTES (roto/doble encode):
await queue.put({"event": "new_narrative", "data": json.dumps({"text": ...})})

# DESPUÉS:
await queue.put({"event": "new_narrative", "data": {"text": ...}})
```

El frontend ya hace `JSON.parse(e.data)` — con single encoding funciona igual. Con double encoding funciona por accidente (el string escapado es parseable).

---

### 3.7 Fix P1-1: CORS Restriction

```python
# ANTES:
allow_origins=["*"]

# DESPUÉS:
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:3000").split(",")
allow_origins=ALLOWED_ORIGINS
```

---

### 3.8 Fix P1-2: Dice Parser Whitespace Tolerance

```javascript
function parseDice(expr) {
  expr = expr.trim().toLowerCase().replace(/\s/g, '');  // ← NUEVO: quitar espacios
  // ...resto igual
}
```

---

### 3.9 Fix P1-3: Explicit Character Selection

```javascript
// En selectCampaign, L877:
if (keys.length > 0 && !state.currentPlayerId) {
  state.currentPlayerId = keys[0];
  renderCharacterSheet(state.characters[keys[0]]);  // ← pasar char explícito
}
```

---

### 3.10 Fix P1-4: Docker Compose Mount Fix

```yaml
# ANTES:
volumes:
  - ~/.hermes/hermesdm:/data

# DESPUÉS:
volumes:
  - ~/.hermes/hermesdm/campaigns:/data/campaigns
```

---

## 4. File Change Matrix

| Archivo | Cambios | Líneas aprox |
|---|---|---|
| `server.py` | Refactor SSE polling a global watcher, eliminar dead code, fix double JSON, CORS | ~60 cambios, ~20 eliminaciones |
| `static/index.html` | Nuevo contenedor player-select, fix CSS var, fix log dedup, fix dice parser, fix SSE/polling race | ~40 cambios |
| `docker-compose.yml` | Fix mount path | 1 línea |
| `SPEC.md` | Reemplazar por este documento | 190 líneas nuevas |

---

## 5. Implementation Order

**Phase 1 — Frontend fixes rápidos (5 min):**
1. P0-2: Agregar `--text-dim` al CSS
2. P1-2: `parseDice` whitespace
3. P1-3: `renderCharacterSheet` con arg explícito
4. P0-1: Mover player-select a contenedor separado

**Phase 2 — Backend SSE refactor (15 min):**
5. P0-5: Eliminar `sse_clients` y `state_changed_event`
6. P0-6: Fix double JSON encoding
7. P0-4: Implementar `_poll_state_global` + `_campaign_watchers`
8. P1-1: CORS restriction

**Phase 3 — Frontend sync fixes (5 min):**
9. P0-3 + P1-6: Log dedup con `lastLogLength` + race fix

**Phase 4 — Infra (2 min):**
10. P1-4: Docker compose mount path
11. P1-5: Actualizar SPEC.md

**Phase 5 — Verification (5 min):**
12. Smoke tests (ver sección 6)

**Total estimado:** ~32 min de trabajo activo + tests.

---

## 6. Verification Tests

### 6.1 Smoke Test — Backend Levanta
```bash
cd hermesdm-web
PORT=9999 python3 server.py &
sleep 2
curl -s http://localhost:9999/api/campaigns | python3 -m json.tool | head -5
curl -s http://localhost:9999/api/campaign/campaign_0040bc60 | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'history' in d, 'history missing'
assert 'characters' in d, 'characters missing'
assert isinstance(d['history'], list), 'history not list'
print('Backend OK')
"
pkill -f "PORT=9999 python3 server.py"
```

### 6.2 Smoke Test — SSE Stream
```bash
curl -N -H "Accept: text/event-stream" \
  http://localhost:9999/api/campaign/campaign_0040bc60/stream &
CURL_PID=$!
sleep 3
# Verificar que recibió al menos un keepalive o state_update
kill $CURL_PID 2>/dev/null
```

### 6.3 Functional Test — Frontend (manual checklist)
1. Abrir `http://localhost:9999/`
2. Seleccionar campaign → dashboard visible
3. Verificar que aparece **player selector** si hay múltiples personajes
4. Cambiar de personaje en el selector → character sheet cambia sin desaparecer el selector
5. Tirar dado con quick button → animación + resultado
6. Tirar dado con input `"2d6 + 3"` (con espacios) → funciona
7. Enviar acción desde Telegram → log se actualiza sin duplicados
8. Desconectar/red conectar → SSE reconecta, no hay polling paralelo

### 6.4 Load Test — Scalability
```bash
# Abrir 10 conexiones SSE simultáneas
for i in {1..10}; do
  curl -N http://localhost:9999/api/campaign/campaign_0040bc60/stream > /dev/null &
done
# Verificar con `ps aux | grep curl` que todas reciben eventos
# Verificar con `lsof` que solo hay 1 proceso leyendo state.json
```

---

## 7. Acceptance Criteria

- [ ] Player selector persiste después de cambiar de personaje 10 veces seguidas
- [ ] `--text-dim` renderiza color correcto en pantalla de selección (inspeccionar elemento)
- [ ] Log no duplica entradas tras 5 minutos de SSE + polling
- [ ] 10 clientes SSE simultáneos generan ≤1 lectura de disco/seg por campaign
- [ ] `curl http://localhost:9999/api/campaign/{id}/stream` recibe eventos parseables
- [ ] `docker compose up` levanta sin errores de mount path
- [ ] `2d6 + 3` (con espacios) parsea correctamente
- [ ] CORS rechaza origen no permitido en prod mode

---

## 8. Risks & Mitigations

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Refactor SSE introduce race condition en desconexión | Media | Alta | Usar `try/finally` + `asyncio.shield` en cleanup |
| Global watcher no se cancela al quedarse sin clientes | Media | Media | `unregister_queue` con reference counting |
| Frontend DOM refactor rompe layout mobile | Baja | Media | Testear `@media (max-width: 768px)` |
| State.json cambia de estructura en futuro HermesDM | Baja | Alta | Frontend usar safe accessors (`obj?.field ?? default`) |

---

## 9. Post-Fix Future Work (Out of Scope v2.0)

- Mapa con tokens/grid (complejidad alta)
- Auth / login (URL como token es suficiente por ahora)
- Edición de character sheets desde web
- WebSocket nativo (SSE es suficiente para <100 conexiones)
- Notas privadas por jugador

---

*SPEC generado por auditoría automática. Todos los fixes son reversibles via git.*
