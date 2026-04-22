# SPEC — Image Generation System (Auto-Narrative Driven)

## Objetivo

Cuando sucede un momento narrativamente interesante en la partida, HermesDM genera automáticamente una imagen que acompaña la narración y la envía al grupo de Telegram.

El sistema decide SOLO qué momentos merecen imagen. No hay comando manual.

---

## Arquitectura

```
dm/narrator.py
       ↓ (event detected)
dm/image_event_handler.py
       ↓ (scene analysis + prompt)
ImageProvider.generate(prompt, scene_type)
       ↓
   ┌──────────────────────────────┐
   │ PollinationsProvider (default)│
   │ MiniMaxProvider              │
   │ FluxProvider                 │
   │ NanoBananaProvider           │
   └──────────────────────────────┘
       ↓ (local PNG path)
telegram_handler.py → reply_photo()
```

---

## ImageProvider Interface

```python
class ImageProvider(ABC):
    name: str  # "pollinations", "minimax", "flux", etc.

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs,
    ) -> str:
        """
        Genera imagen desde prompt.
        Returns: ruta absoluta al archivo de imagen local (PNG/JPG).
        Raises: ImageGenerationError si falla.
        """
```

---

## Auto-Detection: ¿Cuándo generar imagen?

```python
# Configurable por campaña (None = usar defaults)
AUTO_IMAGE_TRIGGERS = {
    "nat_20": True,           # Crítico del jugador → SI
    "nat_1": True,            # Fumble del jugador → SI
    "player_death": True,     # Jugador llega a 0 HP → SI
    "npc_death": True,        # NPC importante muere → SI
    "boss_intro": True,       # Primer turno de boss → SI
    "boss_death": True,       # Boss muere → SI
    "session_start": True,    # Inicio de sesión → SI
    "session_end": True,      # Fin de sesión → SI
    "discovery": True,        # Nueva ubicación/NPC importante → SI
    "critical_wound": True,   # HP baja de 25% → SI
    "dramatic_victory": True, # Victoria difícil → SI
    "normal_turn": False,     # Turno normal → NO
}

# Para desactivar completamente:
/setup [descripción]
edit auto_image: off
```

---

## Prompt Builder

```python
def build_scene_prompt(
    narrative: str,
    scene_type: str,
    genre: str,  # "fantasy", "cyberpunk", "zombie", "romance"
    characters: list[str],
    mood: str,   # "dark", "epic", "tender", "tense"
) -> str:
    """
    Convierte narrativa + contexto en prompt de imagen.
    Mantiene < 400 caracteres para evitar 404 en Pollinations.
    """
```

**Ejemplos:**

| narrativa | genre | scene_type | prompt |
|---|---|---|---|
| Valdric cae al dragón con su espada | fantasy | nat_20_crit | `wounded knight strikes down dragon with sword burning castle cinematic 4k` |
| El zombi ataca a Marco | zombie | combat | `zombie horde attacks survivor in abandoned hospital dark apocalyptic 4k` |
| Sofía besa a Carlos bajo la lluvia | romance | discovery | `couple kissing in rain city lights night romantic cinematic 4k` |
| Rex hackea el sistema de seguridad | cyberpunk | normal_turn | `hacker in neon cyberpunk server room green terminals` |

---

## ImageEventHandler

```python
class ImageEventHandler:
    def __init__(
        self,
        provider: ImageProvider,
        triggers: dict[str, bool] | None = None,
        cooldown_seconds: int = 15,  # Min 15s entre imágenes
    ):
        self.provider = provider
        self.triggers = triggers or AUTO_IMAGE_TRIGGERS
        self.cooldown_seconds = cooldown_seconds
        self._last_image_time: float = 0  # Unix timestamp

    async def maybe_generate(
        self,
        context: ImageContext,
    ) -> str | None:
        """
        Evalúa si el contexto merece imagen.
        Si sí y pasó suficiente tiempo desde la última → genera.
        Returns: ruta de imagen o None.
        """
```

**ImageContext:**
```python
@dataclass
class ImageContext:
    scene_type: str          # "nat_20", "boss_death", etc.
    narrative: str           # Texto narrativo generado
    characters: list[str]    # Nombres de personajes en escena
    genre: str               # Genre de la campaña
    mood: str                # "dark", "epic", "tense", "tender"
    combat_state: bool       # Está en combate?
    metadata: dict           # Libre para context adicional
```

---

## Provider Implementations

### 1. PollinationsProvider (DEFAULT)

```python
class PollinationsProvider(ImageProvider):
    name = "pollinations"
    BASE_URL = "https://image.pollinations.ai/prompt/{prompt_encoded}"

    async def generate(self, prompt: str, scene_type: str, **kwargs) -> str:
        output_path = f"/tmp/hermes_img_{int(time.time())}.png"
        # Usa el script existente /home/hermes/scripts/image_from_scene.py
        # O llama directo: curl/wget → save PNG
        return output_path
```

**Pros:** Gratis, rápido (0.5-2s), sin API key
**Cons:** Calidad media, prompts largos dan 404

### 2. MiniMaxProvider

```python
class MiniMaxProvider(ImageProvider):
    name = "minimax"
    BASE_URL = "https://api.minimax.io/v1/image_generation"

    async def generate(self, prompt: str, scene_type: str, **kwargs) -> str:
        # Usa skill minimax-image-generation
        # $0.02-0.05 por imagen
        # ~90 segundos
        return output_path
```

### 3. FluxProvider

```python
class FluxProvider(ImageProvider):
    name = "flux"
    BASE_URL = "http://localhost:7860"  # o HF endpoint

    async def generate(self, prompt: str, scene_type: str, **kwargs) -> str:
        # Stable Diffusion local o API
        return output_path
```

### 4. NanoBananaProvider + others

```python
class NanoBananaProvider(ImageProvider):
    name = "nanobanana"

    async def generate(self, prompt: str, scene_type: str, **kwargs) -> str:
        # Generic REST: POST /generate con {prompt, ...}
        # Cada provider define sus propios kwargs
        return output_path
```

---

## Configuración de Campaña

```python
# En setup de campaña:
/setup Campaña zombie, auto_image: on, image_provider: pollinations
/setup Campaña cyberpunk premium, image_provider: minimax, image_api_key: sk-...

# Runtime:
edit auto_image: off   # Desactiva completamente
edit image_provider: flux
```

**Guardado en:** `campaign["settings"]["image_provider"]`, `campaign["settings"]["auto_image_triggers"]`

---

## Integración en dm/narrator.py

En `_generate_narrative()` o justo después de `_build_mechanic_message()`:

```python
async def _generate_narrative(...):
    narrative = await llm.generate(...)
    
    # post-narrative: evaluar imagen
    if self.image_handler and self.image_handler.should_generate(context):
        image_path = await self.image_handler.maybe_generate(ImageContext(...))
        if image_path:
            await self._send_scene_image(image_path, narrative)

    return narrative
```

---

## Envío a Telegram

```python
# En telegram_handler.py
async def _send_scene_image(image_path: str, narrative: str):
    with open(image_path, "rb") as f:
        await update.message.reply_photo(
            photo=f,
            caption=f"🎨 *{narrative[:200]}...*",
            parse_mode=ParseMode.MARKDOWN,
        )
```

---

## Rate Limiting / Cooldown

- Mínimo 15 segundos entre imágenes (para no spamear)
- Máximo 5 imágenes por combate
- Si el cooldown está activo: el evento se RECORDATORIA pero no genera imagen inmediatamente
- O mejor: se encola y la próxima ventana libre genera la imagen más reciente

---

## Archivos a crear/modificar

### Nuevos
- `dm/image_provider.py` — ABC + todas las implementaciones
- `dm/image_event_handler.py` — Auto-detection logic

### Modificar
- `dm/narrator.py` — integrar image_handler en post-narrative
- `bot/telegram_handler.py` — `_send_scene_image()`
- `state/state_manager.py` — guardar image_provider en campaign settings

---

## Sin cambios

- Sistema de acciones (/act)
- Countdown de combate
- Animación de dados
- XP/Leveling
- Sistema de clases dinámicas
- Inventory/Items

---

## Aprobado: Sherman — Abr 22, 2026
