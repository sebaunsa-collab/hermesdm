# SDD: Comando /begin + Actualización de README

**Autor:** Sherman (Hermes Agent)  
**Fecha:** 2025-04-24  
**Repo:** /home/hermes/hermesdm  
**Branch:** feat/begin-command-readme-sync

---

## 1. Problema

### 1.1 Falta comando de inicio de aventura
El flujo actual es:
1. `/setup` → crea campaña
2. DM dice "perfecto" → campaña pasa a status "active"
3. Jugadores `/join` → crean personajes
4. **NADA** → no hay comando para iniciar la primera escena narrativa

Los jugadores se unen pero la aventura nunca "arranca" con una narrativa inicial. La narrativa solo se genera cuando alguien usa `/j` (ataque), lo cual es incorrecto — debería haber una escena de apertura antes de cualquier acción.

### 1.2 README desactualizado
El README lista comandos que NO existen en el código y omite comandos que SÍ existen.

**Comandos en README pero NO en código (~20 fantasmas):**
/create, /chars, /char, /xp, /levelup, /conditions, /deathsave, /rest, /shortrest, /combat, /flee, /summon, /spells, /r, /flip, /check, /item, /drop, /equip, /unequip, /configuracion, /settings

**Comandos en código pero NO en README:**
/countdown, /me, /startcombat, /endcombat

**Comandos con nombre diferente:**
README dice `/combat` → código tiene `/startcombat`
README dice `/r` → código solo tiene `/roll`

---

## 2. Solución Propuesta

### 2.1 Nuevo comando: `/begin`

**Función:** Iniciar la aventura generando la escena inicial de narrativa.

**Flujo:**
```
1. Verificar que exista campaña activa (status == "active")
2. Verificar que haya al menos 1 personaje unido
3. Generar escena inicial usando:
   - hook de la campaña (de setup_data)
   - premisa de la campaña
   - personajes presentes
   - ubicación inicial
4. Guardar escena en state["scenes"][]
5. Broadcast narrativa al grupo
6. Trigger imagen de escena inicial si está activado
7. Responder: "🎭 La aventura comienza..."
```

**Restricciones:**
- Solo funciona si campaign.status == "active"
- Solo funciona si hay ≥1 personaje
- Solo funciona UNA VEZ (guardar flag `adventure_started` en state)
- Si se llama de nuevo → "La aventura ya comenzó. Usá /recap para recordar."

**Handler:** `cmd_begin()` en `bot/telegram_handler.py`

**Integración con NarrativeGenerator:**
- Usar `NarrativeGenerator.generate_scene()` con `SceneType.STORY_BEAT`
- Contexto: hook + premisa + location + personajes
- Fallback: narrativa template si AI falla

### 2.2 Actualización de README

**Cambios:**
1. Eliminar comandos fantasmas del README
2. Agregar comandos faltantes (/countdown, /me, /startcombat, /endcombat)
3. Renombrar /combat → /startcombat
4. Agregar /begin al listado
5. Actualizar flujo de inicio para incluir /begin

---

## 3. Especificación Técnica

### 3.1 cmd_begin()

```python
async def cmd_begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia la aventura generando la escena inicial."""
```

**Lógica:**
1. Load state de campaña activa
2. Check status == "active"
3. Check len(characters) > 0
4. Check state.get("adventure_started") != True
5. Build context para NarrativeGenerator:
   ```python
   ctx = {
       "campaign_name": campaign_name,
       "premise": setup["premise"],
       "hook": setup["hook"],
       "location": setup["lore"]["starting_location"],
       "characters": [c.name for c in characters],
       "scene_type": "opening",
   }
   ```
6. Generate narrative via `NarrativeGenerator`
7. Save to state["scenes"] and state["adventure_started"] = True
8. Broadcast to group
9. Trigger image generation if enabled

### 3.2 State additions

```json
{
  "adventure_started": true,
  "scenes": [
    {
      "type": "opening",
      "narrative": "...",
      "timestamp": "...",
      "characters_present": ["..."]
    }
  ]
}
```

### 3.3 README changes

**Sección: Guía de Comandos**
- Reemplazar tabla actual con lista real de 33 comandos
- Agrupar por categoría: Setup, Personaje, Combate, Mundo, Admin
- Agregar `/begin` en sección Setup

**Sección: Quick Start**
- Paso 3: agregar `/begin` después de `/join`

---

## 4. Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `bot/telegram_handler.py` | Agregar `cmd_begin()`, registrar en dispatcher |
| `README.md` | Actualizar lista de comandos, agregar /begin a flujo |
| `state/state_manager.py` | Opcional: helper para escenas |

---

## 5. Testing

- [ ] `/begin` sin campaña activa → error
- [ ] `/begin` con campaña en setup → error
- [ ] `/begin` sin personajes → error
- [ ] `/begin` con todo listo → narrativa generada
- [ ] `/begin` llamado 2 veces → "ya comenzó"
- [ ] NarrativeGenerator recibe contexto correcto
- [ ] README refleja comandos reales

---

## 6. Criterios de Aceptación

1. El comando `/begin` existe y funciona
2. Genera narrativa de apertura usando hook/premisa/ubicación
3. Guarda flag para prevenir doble inicio
4. El README lista exactamente los comandos que existen en el código
5. No hay comandos fantasmas en el README
6. El flujo de Quick Start incluye `/begin`
