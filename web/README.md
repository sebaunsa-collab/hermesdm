# HermesDM Web Companion

Dashboard companion para HermesDM — character sheet visual, game log, dice roller y quest tracker. Lee del mismo `state.json` que HermesDM. No modifica el core.

**No reemplaza Telegram** — lo complementa. Los jugadores acceden via navegador.

---

## Quick Start

### 1. Clonar e instalar

```bash
git clone <repo-url> hermesdm-web
cd hermesdm-web
pip install -r requirements.txt
```

### 2. Configurar

```bash
cp .env.example .env
# Editar .env:
# HERMESDM_STATE_DIR=~/.hermes/hermesdm/campaigns
# PORT=8080
```

### 3. Correr

```bash
python server.py
# Abre http://localhost:8080
```

### 4. Docker (alternativa)

```bash
docker compose up -d
```

---

## Usage

- **Sin campaign en URL** → pantalla de selección de campaigns
- **Con campaign** → `http://localhost:8080/campaign/campaign_abc123`
- **Parámetro URL** → `http://localhost:8080/?campaign=campaign_abc123`

---

## Features

| Feature | Descripción |
|---------|-------------|
| **Campaign selector** | Lista todas las campaigns desde `state.json` |
| **Game log** | Narración completa con tipos (narration/combat/dice/system) |
| **Dice roller** | Botones d4-d20 + input custom con animación |
| **Quest tracker** | Quests activas y completadas |
| **Real-time** | SSE + polling fallback (actualiza cada 3s) |
| **Dark theme** | Tema D&D dark con gold accent |

---

## API Endpoints

```
GET /                           → index.html
GET /campaign/{id}              → redirect a /?campaign={id}
GET /api/campaigns              → lista de campaigns
GET /api/campaign/{id}          → state normalizado (history en formato {text, type, timestamp})
GET /api/campaign/{id}/stream   → SSE real-time events
```

---

## Data Source

Lee directamente de `~/.hermes/hermesdm/campaigns/{id}/state.json` — no toca el código de HermesDM.

**Nota:** Character sheets requieren que HermesDM persista characters en `state.json`. Si `characters` está vacío, se muestra world info y NPCs en su lugar.

---

## Deploy en VPS

```bash
# En el VPS
git clone <repo-url> hermesdm-web
cd hermesdm-web
pip install -r requirements.txt
cp .env.example .env
# Editar HERMESDM_STATE_DIR al path correcto

# Producción (con gunicorn o nginx)
pip install gunicorn
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 server:app
```

O usar `docker compose up -d` para un deploy autocontenido.

---

## Requirements

- Python 3.10+
- fastapi>=0.100.0
- uvicorn>=0.23.0
- sse-starlette>=1.8.0
- python-dotenv>=1.0.0

---

## Frontend

100% vanilla JS + CSS — cero dependencias externas, cero build step. Todo en un solo archivo `static/index.html`.
