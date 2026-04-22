"""
main.py — Entry point for HermesDM bot.
Currently a text-based REPL for local testing (no Telegram).
Run: python main.py
"""
import textwrap

from bot.dice_engine import resolve_check, roll
from dm.world_builder import create_campaign
from state.state_manager import list_campaigns, load_state


def print_wrapped(text: str, width: int = 80):
    wrapped = textwrap.fill(text, width=width)
    print(wrapped)
    print()


def cmd_newgame(args: list) -> str:
    setting = args[0] if args else "fantasy"
    result = create_campaign(setting)
    cid = result["campaign_id"]
    state = result["state"]
    return (
        f"Campaign created: {state['campaign']['name']}\n"
        f"ID: {cid}\n"
        f"Setting: {setting}\n"
        f"Location: {state['campaign']['current_location']}\n"
        f"NPCs: {', '.join(state['npcs'].keys())}"
    )


def cmd_roll(args: list) -> str:
    dice_str = args[0] if args else "d20"
    try:
        r = roll(dice_str)
        parts = [f"Rolling {r['str']}..."]
        parts.append(f"  Rolls: {r['rolls']}")
        if r['modifier'] != 0:
            parts.append(f"  Modifier: {r['modifier']:+d}")
        parts.append(f"  Total: {r['total']}")
        if r.get('is_crit'):
            parts.append("  >> NATURAL 20! CRITICAL! <<")
        elif r.get('is_fumble'):
            parts.append("  >> NATURAL 1! FUMBLE! <<")
        return "\n".join(parts)
    except Exception as e:
        return f"Roll error: {e}"


def cmd_check(args: list) -> str:
    """ /check 15 or /check 15 advantage """
    try:
        dc = int(args[0]) if args else 15
        advantage = "advantage" in args
        disadvantage = "disadvantage" in args
        dice_str = args[1] if len(args) > 1 and not args[1].startswith("adv") else "d20"
        r = roll(dice_str)
        result = resolve_check(r, dc, advantage, disadvantage)
        note = result['note']
        rolls_str = ' '.join(str(x) for x in result['rolls'])
        return (
            f"Rolling {r['str']} vs DC {dc}...\n"
            f"  Rolls: {rolls_str}\n"
            f"  Total: {result['total']} vs DC {dc}\n"
            f"  {note}"
        )
    except Exception as e:
        return f"Check error: {e}"


def cmd_status(args: list) -> str:
    campaigns = list_campaigns()
    if not campaigns:
        return "No active campaigns. Run /newgame first."
    lines = ["Active campaigns:"]
    for c in campaigns:
        lines.append(f"  [{c['id']}] {c['name']} — {c['setting']}")
    return "\n".join(lines)


def cmd_load(args: list) -> str:
    if not args:
        return "Usage: /load campaign_id"
    cid = args[0]
    state = load_state(cid)
    if state is None:
        return f"Campaign '{cid}' not found."
    camp = state["campaign"]
    npcs = list(state["npcs"].keys())
    return (
        f"Campaign: {camp['name']}\n"
        f"ID: {cid}\n"
        f"Setting: {camp['setting']}\n"
        f"Location: {camp.get('current_location', 'unknown')}\n"
        f"NPCs: {', '.join(npcs)}"
    )


COMMANDS = {
    "/newgame": (cmd_newgame, "[setting] — Create new campaign (fantasy/scifi/horror)"),
    "/roll": (cmd_roll, "[dice] — Roll dice (e.g. 2d6+3, d20)"),
    "/check": (cmd_check, "<dc> [dice] [advantage|disadvantage] — Skill check vs DC"),
    "/status": (cmd_status, "— List active campaigns"),
    "/load": (cmd_load, "<campaign_id> — Load a campaign"),
    "/help": (lambda a: "\n".join(f"{k}: {v[1]}" for k, v in COMMANDS.items()), "— Show this help"),
    "/exit": (lambda a: ("__EXIT__", "Goodbye!")[1], "— Exit HermesDM"),
    "/quit": (lambda a: ("__EXIT__", "Goodbye!")[1], "— Exit HermesDM"),
}


def repl():
    print_wrapped("HermesDM — AI Dungeon Master (Local Test REPL)")
    print("Type /help for commands. Ctrl+C to exit.\n")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd not in COMMANDS:
            print(f"Unknown command: {cmd}. Type /help.\n")
            continue

        handler = COMMANDS[cmd][0]
        result = handler(args)
        if result == "__EXIT__":
            print("Goodbye!")
            break
        print(result + "\n")


if __name__ == "__main__":
    repl()
