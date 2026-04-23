"""
HermesDM Web - FastAPI Server v2.0
Reads state.json from HermesDM campaigns directory and exposes:
  GET /api/campaigns
  GET /api/campaign/{campaign_id}          — full state (history normalized)
  GET /api/campaign/{campaign_id}/character/{player_id}
  GET /api/campaign/{campaign_id}/stream  — SSE real-time updates
  GET /campaign/{campaign_id}              — redirect to static with ?id=
"""

import os
import json
import time
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
HERMESDM_STATE_DIR = os.getenv("HERMESDM_STATE_DIR", os.path.expanduser("~/.hermes/hermesdm/campaigns"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:3000").split(",")

app = FastAPI(title="HermesDM Web", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_state_dir() -> Path:
    return Path(HERMESDM_STATE_DIR).expanduser().resolve()


def read_state_json(campaign_id: str) -> dict:
    """Read state.json for a given campaign."""
    state_path = get_state_dir() / campaign_id / "state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_campaigns() -> list:
    """List all campaigns in the state directory."""
    base = get_state_dir()
    if not base.exists():
        return []
    campaigns = []
    for campaign_dir in base.iterdir():
        if campaign_dir.is_dir():
            state_file = campaign_dir / "state.json"
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    campaigns.append({
                        "id": campaign_dir.name,
                        "name": state.get("campaign", {}).get("name", campaign_dir.name),
                        "setting": state.get("campaign", {}).get("setting", "unknown")
                    })
                except Exception:
                    campaigns.append({
                        "id": campaign_dir.name,
                        "name": campaign_dir.name,
                        "setting": "unknown"
                    })
    return campaigns


def _build_events_from_state(state: dict) -> list:
    """Build SSE events from a parsed state dict."""
    events = []
    if "history" in state and state["history"]:
        latest = state["history"][-1]
        events.append({
            "event": "new_narrative",
            "data": {"text": latest.get("text", ""), "type": latest.get("type", "narration")}
        })
    if "combat" in state:
        events.append({
            "event": "combat_update",
            "data": state["combat"]
        })
    events.append({
        "event": "state_update",
        "data": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "location": state.get("campaign", {}).get("current_location", "")
        }
    })
    return events


# ---------------------------------------------------------------------------
# Global Campaign Watchers — single polling task per campaign
# ---------------------------------------------------------------------------

_campaign_watchers: dict[str, asyncio.Task] = {}
_campaign_queues: dict[str, list[asyncio.Queue]] = {}


async def _poll_state_global(campaign_id: str, state_path: Path):
    """Single polling task per campaign. Notifies all subscribed queues."""
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
                        try:
                            state = json.loads(content)
                        except json.JSONDecodeError:
                            continue
                        events = _build_events_from_state(state)
                        queues = _campaign_queues.get(campaign_id, [])
                        for queue in queues[:]:
                            for ev in events:
                                try:
                                    await queue.put(ev)
                                except Exception:
                                    pass
        except Exception as e:
            logger.error(f"Poll error for {campaign_id}: {e}")
        await asyncio.sleep(1)


async def ensure_campaign_watcher(campaign_id: str, state_path: Path):
    """Ensure there is exactly one polling task for this campaign."""
    if campaign_id in _campaign_watchers:
        return
    task = asyncio.create_task(_poll_state_global(campaign_id, state_path))
    _campaign_watchers[campaign_id] = task
    _campaign_queues[campaign_id] = []


def register_queue(campaign_id: str, queue: asyncio.Queue):
    """Register a client queue for a campaign."""
    if campaign_id not in _campaign_queues:
        _campaign_queues[campaign_id] = []
    _campaign_queues[campaign_id].append(queue)


def unregister_queue(campaign_id: str, queue: asyncio.Queue):
    """Unregister a client queue; cancel watcher if no clients left."""
    if campaign_id not in _campaign_queues:
        return
    try:
        _campaign_queues[campaign_id].remove(queue)
    except ValueError:
        pass
    if not _campaign_queues[campaign_id]:
        if campaign_id in _campaign_watchers:
            _campaign_watchers[campaign_id].cancel()
            del _campaign_watchers[campaign_id]
        if campaign_id in _campaign_queues:
            del _campaign_queues[campaign_id]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/campaigns")
def get_campaigns():
    """List all available campaigns."""
    return list_campaigns()


@app.get("/api/campaign/{campaign_id}")
def get_campaign(campaign_id: str):
    """Get full state of a campaign with normalized history."""
    state = read_state_json(campaign_id)
    if "history" in state and isinstance(state["history"], list):
        normalized = []
        for entry in state["history"]:
            if isinstance(entry, dict):
                event_text = entry.get("event", "")
                entry_type = _infer_entry_type(event_text)
                normalized.append({
                    "text": entry.get("event", ""),
                    "type": entry_type,
                    "timestamp": entry.get("timestamp", ""),
                    "session": entry.get("session"),
                })
            else:
                normalized.append({"text": str(entry), "type": "narration", "timestamp": ""})
        state["history"] = normalized
    return state


def _infer_entry_type(text: str) -> str:
    """Infer log entry type from text content."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["rolls", "roll", "🎲", "dice", "d20", "d6", "d8", "d4", "d10", "d12"]):
        return "dice_roll"
    if any(k in text_lower for k in ["combat", "attacks", "damage", "hit", "miss", "crit", "hp", "defeats"]):
        return "combat"
    if any(k in text_lower for k in ["joins", "leaves", "created", "starts", "connected"]):
        return "system"
    if any(k in text_lower for k in ['"', "says:", "asks:", "tells:", "explains:", "replies:"]):
        return "dialogue"
    return "narration"


@app.get("/api/campaign/{campaign_id}/character/{player_id}")
def get_character(campaign_id: str, player_id: str):
    """Get character sheet for a specific player."""
    state = read_state_json(campaign_id)
    characters = state.get("characters", {})

    if player_id in characters:
        char = characters[player_id]
        char["player_id"] = player_id
        return char

    for cid, char in characters.items():
        if char.get("player_id") == player_id or char.get("name", "").lower() == player_id.lower():
            char["player_id"] = cid
            return char

    raise HTTPException(status_code=404, detail=f"Character '{player_id}' not found in campaign '{campaign_id}'")


@app.get("/api/campaign/{campaign_id}/stream")
async def stream_campaign(campaign_id: str):
    """SSE stream for real-time campaign updates."""
    state_path = get_state_dir() / campaign_id / "state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    queue: asyncio.Queue = asyncio.Queue()
    await ensure_campaign_watcher(campaign_id, state_path)
    register_queue(campaign_id, queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield event
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": {}}
        finally:
            unregister_queue(campaign_id, queue)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/campaign/{campaign_id}")
async def campaign_redirect(campaign_id: str):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/?campaign={campaign_id}", status_code=302)


app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Dev: run locally
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
