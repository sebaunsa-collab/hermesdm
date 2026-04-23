# SPEC — Pacing System v1.0
## Fix 1: Historias con ritmo, dirección y anti-bucle

```
═══════════════════════════════════════════════════════════════════════════════
STATUS: SPEC v1.0 — Implementación en curso
═══════════════════════════════════════════════════════════════════════════════
```

---

## 1. PROBLEMA

- Historias se extienden infinitamente → aburrimiento
- Bucles narrativos: "exploro, exploro, exploro" sin progreso
- Sin climax definido → las campañas mueren de abandono, no de cierre
- El LLM narra escenas aisladas sin saber "dónde estamos en la historia"

## 2. SOLUCIÓN

**Estructura direccional con libertad de ejecución.**

Al inicio la AI genera un `story_arc` con milestones. El engine de pacing:
1. Decide qué tipo de escena toca ahora (anti-bucle, anti-stagnation)
2. Inyecta contexto al LLM sobre "dónde estamos en la historia"
3. Detecta cuando un milestone se completó y avanza al siguiente
4. Fuerza el climax cuando corresponde

## 3. ARQUITECTURA

### 3.1 Nuevos archivos

```
hermesdm/
├── dm/
│   ├── story_arc.py          # StoryArc + Milestone dataclasses
│   └── pacing_engine.py      # PacingEngine: decide scene_type, detecta bucles
│
├── state/
│   └── state_manager.py      # MODIFICAR: agregar story_arc al state
```

### 3.2 Archivos modificados

```
hermesdm/
├── dm/
│   ├── world_builder.py      # AI genera story_arc durante setup
│   └── narrative_generator.py # Recibe milestone_context del pacing engine
│
├── bot/
│   └── telegram_handler.py   # Hook: cada /j consulta pacing engine
```

## 4. MODELO DE DATOS

### 4.1 StoryArc

```python
@dataclass
class Milestone:
    id: str                       # "inciting_incident", "rising_action_1", etc.
    type: str                     # "hook" | "rising_action" | "climax" | "resolution"
    description: str              # Qué debe pasar en este milestone
    completed: bool = False
    completed_at: Optional[str] = None
    scene_count: int = 0          # Cuántas escenas se gastaron aquí
    min_scenes: int = 2           # Mínimo antes de poder completarse
    max_scenes: int = 5           # Máximo antes de forzar avance

@dataclass
class StoryArc:
    pacing_level: str             # "short" (5s) | "medium" (10s) | "long" (20s)
    total_sessions: int
    milestones: List[Milestone]
    current_index: int = 0
    total_scenes: int = 0
    loop_detection: dict          # Histórico de scene_types para anti-bucle
```

### 4.2 En state.json

```json
{
  "story_arc": {
    "pacing_level": "medium",
    "total_sessions": 10,
    "current_index": 1,
    "total_scenes": 7,
    "milestones": [
      {
        "id": "hook",
        "type": "hook",
        "description": "Encuentran el cuerpo del capitán en el muelle...",
        "completed": true,
        "scene_count": 3,
        "min_scenes": 2,
        "max_scenes": 4
      },
      {
        "id": "investigate",
        "type": "rising_action",
        "description": "Descubren la conspiración del almirante...",
        "completed": false,
        "scene_count": 4,
        "min_scenes": 3,
        "max_scenes": 6
      }
    ]
  }
}
```

## 5. PACING ENGINE

### 5.1 Anti-bucle

```python
def detect_loop(history: list[str]) -> str | None:
    """
    Si las últimas 4 escenas son del mismo tipo → forzar cambio.
    Si las últimas 6 escenas son EXPLORATION sin STORY_BEAT → forzar evento.
    Si las últimas 3 son COMBAT → forzar DIALOGUE o REST.
    """
```

### 5.2 Decisión de scene_type

```python
def get_next_scene_type(
    self,
    player_action: str,
    history: list[dict],
) -> SceneType:
    """
    Lógica:
    1. Anti-bucle: ¿estamos repitiendo? → forzar otro tipo
    2. Milestone pressure: ¿llevamos N escenas sin avanzar? → forzar STORY_BEAT
    3. Milestone context: ¿el milestone actual es "climax"? → forzar COMBAT
    4. Variedad natural: alternar EXPLORATION/COMBAT/DIALOGUE
    5. Default: inferir del player_action
    """
```

### 5.3 Avance de milestone

```python
def check_milestone_advance(self, context: dict) -> bool:
    """
    Un milestone se completa cuando:
    - scene_count >= min_scenes
    - Y (el LLM reporta progreso narrativo relevante
          O scene_count >= max_scenes → forzar)
    
    Avanza current_index++.
    Si era el último → trigger campaign closure.
    """
```

## 6. PROMPT DE AI PARA GENERAR STORY ARC

Durante `/setup`, el prompt al LLM incluye:

```
Además del setting, generá un STORY ARC con milestones.

Nivel de pacing: {pacing_level} → {total_sessions} sesiones estimadas.
Generá exactamente estos milestones:

1. "hook" — incidente que inicia la aventura (1-2 escenas)
2. "rising_action" — complicación principal (2-4 escenas)
3. "climax" — confrontación final (1-2 escenas)
4. "resolution" — cierre y consecuencias (1 escena)

Para "medium" agregar un segundo "rising_action".
Para "long" agregar dos "rising_action" y un "midpoint".

Cada milestone necesita: id, type, description (qué debe pasar).
```

## 7. INTEGRACIÓN CON NARRATIVA

El `narrative_generator` recibe `milestone_context`:

```python
milestone_context = {
    "current_milestone": "investigate",
    "milestone_type": "rising_action",
    "description": "Descubren la conspiración del almirante...",
    "scenes_in_milestone": 4,
    "progress_pressure": 0.6,  # 0-1, cuánta presión de avance
}
```

El prompt del LLM se enriquece con:
```
CONTEXTO DE PROGRESO:
- Estamos en: "investigate" (rising_action)
- Objetivo: Descubren la conspiración del almirante...
- Escenas aquí: 4/6
- Presión: avanza la trama, no te quedes en descripción pura
```

## 8. CRITERIOS DE ACEPTACIÓN

```
═══════════════════════════════════════
P1: Story arc se genera en /setup
═══════════════════════════════════════
  [ ] /setup con pacing "short" → genera 4 milestones
  [ ] /setup con pacing "medium" → genera 5 milestones
  [ ] milestones se guardan en state.json

═══════════════════════════════════════
P2: Pacing engine decide scene_type
═══════════════════════════════════════
  [ ] 4 exploraciones seguidas → fuerza STORY_BEAT
  [ ] 3 combates seguidos → fuerza DIALOGUE o REST
  [ ] milestone "climax" → fuerza COMBAT

═══════════════════════════════════════
P3: Milestones avanzan
═══════════════════════════════════════
  [ ] Después de min_scenes, el engine permite completar milestone
  [ ] Después de max_scenes, el engine fuerza completar milestone
  [ ] Al completar último milestone → sugerir cierre de campaña

═══════════════════════════════════════
P4: Contexto en narrativa
═══════════════════════════════════════
  [ ] El LLM recibe el milestone actual en su prompt
  [ ] La narración refleja el objetivo del milestone
  [ ] No hay bucles de "exploras más y no pasa nada"
```

## 9. PLAN DE IMPLEMENTACIÓN

```
PASO 1 — story_arc.py
  → Dataclasses Milestone + StoryArc
  → Serialization to/from dict
  → Factory: from_pacing_level(pacing_level, ai_response)

PASO 2 — pacing_engine.py
  → PacingEngine class
  → detect_loop(), get_next_scene_type(), check_milestone_advance()

PASO 3 — world_builder.py modificado
  → El prompt de setup pide story_arc
  → Parsea el JSON de respuesta y guarda story_arc en setup

PASO 4 — state_manager.py modificado
  → new_state() incluye story_arc: None por default
  → Guardar/cargar story_arc en state.json

PASO 5 — telegram_handler.py hook
  → Cada /j consulta PacingEngine antes de generar narrativa
  → Recibe scene_type sugerido y lo pasa a narrative_generator

PASO 6 — narrative_generator.py modificado
  → generate_scene() acepta milestone_context opcional
  → Incluye milestone_context en el prompt al LLM

PASO 7 — Test
  → Test de anti-bucle
  → Test de avance de milestone
  → Test E2E: /setup → /begin → /j × 10 → verificar progresión
```
