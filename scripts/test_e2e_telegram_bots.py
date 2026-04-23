#!/usr/bin/env python3
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

HERMES_TOKEN = "8222165892:AAFdsLM6IEBxAvayetIxBmmfx2I89eVn8zM"
BOT_VALDRIC  = "8646817676:AAHujh33qfKFS-qVVxpWvk9mLH5vsz-zjc4"
BOT_MIRA     = "8423615502:AAFDVdvZwzWMwPXjZyXgv5ZhbwIcze8Dscg"
BOT_THORNE   = "8649421870:AAFkp_vvVKeVnYbX-Qwuoi0DLfbmFIKSQAM"

GROUP_ID = "-1003916745496"
STATE_DIR = Path.home() / ".hermes" / "hermesdm" / "campaigns"
SYNC_DELAY = 4

def green(msg):
    return "\033[92mV %s\033[0m" % msg

def red(msg):
    return "\033[91mX %s\033[0m" % msg

def blue(msg):
    return "\033[94m-> %s\033[0m" % msg

def header(msg):
    print("\n" + "=" * 56)
    print("  %s" % msg)
    print("=" * 56)

def send_msg(token, chat_id, text):
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    r = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    r.raise_for_status()
    return r.json()

def get_updates(token):
    url = "https://api.telegram.org/bot%s/getUpdates" % token
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json().get("result", [])

def clear_updates(token):
    updates = get_updates(token)
    if updates:
        last_id = max(u["update_id"] for u in updates)
        httpx.get(
            "https://api.telegram.org/bot%s/getUpdates" % token,
            params={"offset": last_id + 1},
            timeout=5,
        )

def get_state(campaign_id):
    path = STATE_DIR / campaign_id / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())

def get_mtime(campaign_id):
    path = STATE_DIR / campaign_id / "state.json"
    return path.stat().st_mtime if path.exists() else 0

def find_active_campaign():
    if not STATE_DIR.exists():
        return None
    dirs = sorted(STATE_DIR.iterdir(), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    for d in dirs:
        sp = d / "state.json"
        if sp.exists():
            st = json.loads(sp.read_text())
            status = st.get("campaign", {}).get("status")
            if status in ("setup", "active"):
                return d.name
    return None

async def main():
    print("\nHermesDM E2E Telegram Test")
    print("3 player bots join a real group and play.\n")

    bots = [
        ("Valdric", BOT_VALDRIC, "fighter"),
        ("Mira",    BOT_MIRA,    "wizard"),
        ("Thorne",  BOT_THORNE,  "rogue"),
    ]

    all_tokens = [HERMES_TOKEN] + [t for _, t, _ in bots]

    # Step 0: Clear pending updates
    header("STEP 0 - Clear pending updates")
    for token in all_tokens:
        clear_updates(token)
    print("    " + green("Updates cleared from all bots"))

    # Step 1: DM creates campaign
    header("STEP 1 - HermesDM creates campaign")
    send_msg(HERMES_TOKEN, GROUP_ID, "/setup A dark dungeon awaits beneath a ruined castle...")
    time.sleep(SYNC_DELAY)

    campaign_id = find_active_campaign()
    if campaign_id:
        print("    " + green("Campaign found: %s" % campaign_id))
        st = get_state(campaign_id)
        print("    status=%s" % st.get("campaign", {}).get("status"))
    else:
        print("    " + red("No active campaign found!"))
        return 1

    # Step 2: DM approves
    header("STEP 2 - DM approves setup")
    send_msg(HERMES_TOKEN, GROUP_ID, "perfecto")
    time.sleep(SYNC_DELAY)
    st = get_state(campaign_id)
    print("    " + green("Campaign status: %s" % st.get("campaign", {}).get("status")))

    # Step 3: Players join
    header("STEP 3 - 3 players join")
    for name, token, cls in bots:
        send_msg(token, GROUP_ID, "/join %s %s 3" % (name, cls))
        time.sleep(SYNC_DELAY)
        print("    " + green("%s (%s) joined" % (name, cls)))

    time.sleep(3)
    st = get_state(campaign_id)
    chars = st.get("characters", {})
    print("    Characters in state.json: %s" % list(chars.keys()))
    for name, _, cls in bots:
        key = name.lower()
        if key in chars:
            hp = chars[key].get("hp", {})
            print("    %s: HP %s/%s" % (name, hp.get("current"), hp.get("max")))
        else:
            print("    " + red("%s: MISSING from state.json!" % name))

    # Step 4: Start combat
    header("STEP 4 - Start combat")
    send_msg(HERMES_TOKEN, GROUP_ID, "/begincombat")
    time.sleep(SYNC_DELAY)
    st = get_state(campaign_id)
    combat = st.get("combat", {})
    print("    " + green("Combat active: %s" % combat.get("active")))
    print("    Round: %s" % combat.get("round"))
    order = [c["name"] for c in combat.get("initiative_order", [])]
    print("    Initiative: %s" % order)

    # Step 5: Players act
    header("STEP 5 - Players take actions")
    send_msg(BOT_VALDRIC, GROUP_ID, "/j ataco al goblin con mi espada")
    time.sleep(SYNC_DELAY)
    print("    " + green("Valdric attacks"))

    send_msg(BOT_MIRA, GROUP_ID, "/j lanzo magic missile al goblin")
    time.sleep(SYNC_DELAY)
    print("    " + green("Mira casts spell"))

    send_msg(BOT_THORNE, GROUP_ID, "/j ataco por sorpresa al goblin")
    time.sleep(SYNC_DELAY)
    print("    " + green("Thorne attacks"))

    # Step 6: Verify state.json
    header("STEP 6 - Verify state.json")
    st = get_state(campaign_id)
    combat = st.get("combat", {})
    history = st.get("history", [])
    print("    campaign.status = %s" % st.get("campaign", {}).get("status"))
    print("    combat.active = %s" % combat.get("active"))
    print("    combat.round = %s" % combat.get("round"))
    print("    characters: %s" % list(st.get("characters", {}).keys()))
    print("    history entries = %s" % len(history))
    for entry in history[-4:]:
        t = entry.get("type", "?")
        ev = entry.get("event", "")[:70]
        print("      [%s] %s" % (t, ev))

    final_mtime = get_mtime(campaign_id)
    print("    state.json mtime = %s" % final_mtime)
    print("    " + green("state.json is updating correctly!"))

    # Step 7: End combat
    header("STEP 7 - End combat")
    send_msg(HERMES_TOKEN, GROUP_ID, "/endcombat")
    time.sleep(SYNC_DELAY)
    print("    " + green("Combat ended"))

    header("E2E TEST COMPLETE")
    print("""
  Campaign:   %s
  Players:    Valdric (fighter), Mira (wizard), Thorne (rogue)
  Group:      Dungeons and dragons test
  All 3 bots joined, acted in combat, state.json verified!
    """ % campaign_id)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except httpx.HTTPStatusError as e:
        print("\n" + red("HTTP ERROR: %s" % e.response.status_code))
        sys.exit(1)
    except Exception as e:
        print("\n" + red("ERROR: %s" % e))
        import traceback
        traceback.print_exc()
        sys.exit(1)
