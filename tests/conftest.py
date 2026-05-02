import pytest
import sys


# ── Canonical dice roll dict helper ──────────────────────────────────────────

def roll_dice_dict(total=15, rolls=None, modifier=0, natural=15,
                   is_crit=False, is_fumble=False, notation="1d20",
                   str_val=None):
    """Return a dict matching the structure of bot.dice_engine.roll().

    All keys from the real roll() function are represented.
    """
    if rolls is None:
        rolls = [natural] if natural is not None else [total - modifier]
    if str_val is None:
        str_val = notation + (f"{modifier:+d}" if modifier else "")
    return {
        "total": total,
        "rolls": rolls,
        "modifier": modifier,
        "natural": natural,
        "is_crit": is_crit,
        "is_fumble": is_fumble,
        "notation": notation,
        "str": str_val,
    }


# ── Global state reset fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_telegram_globals():
    """Reset telegram_handler module-level singletons between tests.

    Resets _narrative_generator and _AUTO_IMAGE_HANDLER which use a
    lazy-init pattern (set to None and recreated on next access).
    Also removes any fake bot.dice_engine module injected into
    sys.modules by other test files.
    """
    # --- PRE-TEST: reset globals ---
    try:
        import bot.telegram_handler as th
        th._narrative_generator = None
        th._AUTO_IMAGE_HANDLER = None
    except Exception:
        pass

    # --- PRE-TEST: remove fake bot.dice_engine if present ---
    _cleanup_fake_dice_module()

    yield

    # --- POST-TEST: reset globals again for safety ---
    try:
        import bot.telegram_handler as th
        th._narrative_generator = None
        th._AUTO_IMAGE_HANDLER = None
    except Exception:
        pass

    _cleanup_fake_dice_module()


def _cleanup_fake_dice_module():
    """If bot.dice_engine was replaced with a MagicMock in sys.modules,
    remove it so subsequent tests re-import the real module."""
    if "bot.dice_engine" in sys.modules:
        mod = sys.modules["bot.dice_engine"]
        # A MagicMock has a __class__.__module__ of 'unittest.mock'
        if hasattr(mod, '__class__') and 'unittest.mock' in str(type(mod)):
            del sys.modules["bot.dice_engine"]
