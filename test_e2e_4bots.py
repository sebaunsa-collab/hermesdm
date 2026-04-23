#!/usr/bin/env python3
"""
E2E Test: 4 bots playing a real campaign.
Simulates: DM creates campaign, 4 players join, actions, combat.
"""
import asyncio
import json
import os
import time
from pathlib import Path

# ── Bot tokens ──────────────────────────────────────────────────────────────
BOTS = {
    "hermesdm":  "8222165892:AAFdsLM6IEBxAvayetIxBmmfx2I89eVn8zM",
    "juan":      "8646817676:AAHujh33qfKFS-qVVxpWvk9mLH5vsz-zjc4",
    "chochua":   "8423615502:AAFDVdvZwzWMwPXjZyXgv5ZhbwIcze8Dscg",
    "eltuta":    "8649421870:AAFkp_vvVKeVnYbX-Qwuoi0DLfbmFIKSQAM",
}

GROUP_ID = -1003916745496  # Dungeons and dragons test
HERMES_STATE_DIR = Path.home() / ".hermes" / "hermesdm" / "campaigns"

async def send_message(token: str, chat_id: int, text: str) -> dict:
    """Send message via Telegram Bot API directly."""
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        return r.json()

async def get_updates(token: str, timeout: int = 5) -> list:
    """Get updates from bot (polling)."""
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/getUpdates",
            json={"timeout": timeout, "allowed_updates": ["message"]},
            timeout=timeout + 5,
        )
        return r.json().get("result", [])

async def delete_webhook(token: str) -> None:
    """Ensure no webhook is set (needed for polling)."""
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")

def latest_campaign() -> Path | None:
    """Return the most recently modified campaign directory."""
    if not HERMES_STATE_DIR.exists():
        return None
    dirs = sorted(HERMES_STATE_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
    # Filter out non-campaign dirs
    for d in reversed(dirs):
        if (d / "state.json").exists():
            return d
    return None

def read_state(campaign_path: Path) -> dict:
    return json.loads((campaign_path / "state.json").read_text())

def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

async def step(bot_name: str, token: str, action: str, delay: float = 3) -> dict:
    """Send an action and wait."""
    log(f"  [{bot_name}] {action}")
    result = await send_message(token, GROUP_ID, action)
    await asyncio.sleep(delay)
    return result

async def wait_for_response(token: str, keyword: str, timeout: int = 15) -> str | None:
    """Poll until we see keyword in updates, or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        updates = await get_updates(token)
        for u in updates:
            msg = u.get("message", {})
            text = msg.get("text", "") or ""
            if keyword.lower() in text.lower():
                return text
        await asyncio.sleep(2)
    return None

async def main():
    print("=" * 60)
    print("E2E TEST: 4 BOTS - CAMPAIGN SIMULATION")
    print("=" * 60)

    # Step 0: Verify tokens + delete webhooks
    print("\n[0] Verifying tokens...")
    import httpx
    for name, token in BOTS.items():
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            data = r.json()
            ok = data.get("ok")
            username = data.get("result", {}).get("username", "?")
            print(f"  [{name}] {'OK' if ok else 'FAIL'} — @{username}")
            if ok:
                await delete_webhook(token)
                await asyncio.sleep(0.5)

    # Step 1: DM creates campaign
    print("\n[1] DM creates campaign...")
    await step("hermesdm", BOTS["hermesdm"], "/newgame", delay=5)

    # Find the new campaign
    await asyncio.sleep(2)
    campaign = latest_campaign()
    if campaign is None:
        print("  FAIL: No campaign created!")
        return
    campaign_id = campaign.name
    print(f"  Campaign created: {campaign_id}")
    state = read_state(campaign)
    print(f"  Status: {state.get('campaign', {}).get('status', '?')}")

    # Step 2: DM configures campaign (approve it)
    print("\n[2] DM approves campaign...")
    await step("hermesdm", BOTS["hermesdm"], f"/setup\nname: The Dragon's Lair\nsetting: fantasy", delay=5)
    await step("hermesdm", BOTS["hermesdm"], "/approve", delay=5)

    state = read_state(campaign)
    status = state.get("campaign", {}).get("status", "?")
    print(f"  Status after /approve: {status}")

    # Step 3: Players join
    print("\n[3] Players join...")
    await step("juan",    BOTS["juan"],    "/join Juan Salas fighter 2",      delay=4)
    await step("chochua", BOTS["chochua"], "/join Chochua cleric 2",          delay=4)
    await step("eltuta",  BOTS["eltuta"],  "/join El Tuta rogue 3",           delay=4)

    # Verify characters in state
    await asyncio.sleep(2)
    state = read_state(campaign)
    chars = list(state.get("characters", {}).keys())
    print(f"  Characters in state: {chars}")

    # Step 4: Start combat
    print("\n[4] DM starts combat...")
    await step("hermesdm", BOTS["hermesdm"], "/startcombat", delay=5)

    state = read_state(campaign)
    combat = state.get("combat", {})
    print(f"  Combat active: {combat.get('active', False)}")
    print(f"  Initiative order: {[c['name'] for c in combat.get('initiative_order', [])]}")

    # Step 5: Player actions
    print("\n[5] Player actions...")
    await step("juan",    BOTS["juan"],    "/j I attack the goblin with my sword", delay=6)
    await step("eltuta",  BOTS["eltuta"], "/j I try to sneak past the guard",    delay=6)
    await step("chochua", BOTS["chochua"], "/cast magic-missile goblin",         delay=6)

    state = read_state(campaign)
    history = state.get("history", [])
    print(f"  History entries: {len(history)}")
    for h in history[-3:]:
        print(f"    [{h['type']}] {h['event'][:80]}...")

    # Step 6: Check state persistence
    print("\n[6] Verifying state persistence...")
    state = read_state(campaign)
    print(f"  Characters persisted: {list(state.get('characters', {}).keys())}")
    print(f"  Combat persisted: {state.get('combat', {}).get('active')}")
    print(f"  History entries: {len(state.get('history', []))}")
    print(f"  Round: {state.get('combat', {}).get('round', 0)}")

    print("\n" + "=" * 60)
    print("E2E TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
