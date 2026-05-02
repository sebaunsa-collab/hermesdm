"""
reactions.py — D&D 5e Reaction System for HermesDM.

Reactions are special actions taken OUTSIDE your turn in response to triggers.
Each creature gets ONE reaction per round (restored at the start of their turn).

Types of reactions:
  - Opportunity Attack: When a creature leaves your melee reach
  - Shield (spell): +5 AC when hit by an attack
  - Counterspell: Interrupt a spell being cast
  - Ready Action: Trigger you pre-declared on your turn
  - Uncanny Dodge (rogue): Halve damage from an attack

Design: ReactionEngine resolves ALL reaction triggers in the correct order
after a triggering event. It checks conditions, rolls, and returns results.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bot.character_sheet import Character


# -- Reaction Types -----------------------------------------------------------

REACTION_OPPORTUNITY_ATTACK = "opportunity_attack"
REACTION_SHIELD = "shield"
REACTION_COUNTERSPELL = "counterspell"
REACTION_READY = "ready"
REACTION_UNCANNY_DODGE = "uncanny_dodge"

ALL_REACTIONS = [
    REACTION_OPPORTUNITY_ATTACK,
    REACTION_SHIELD,
    REACTION_COUNTERSPELL,
    REACTION_READY,
    REACTION_UNCANNY_DODGE,
]


# -- Data Classes ------------------------------------------------------------

@dataclass
class ReactionResult:
    """Result of a single reaction resolution."""
    reaction_type: str
    actor: str               # who uses the reaction
    trigger: str             # what triggered it
    success: bool = True
    roll: int = 0
    total: int = 0
    damage: int = 0          # for opportunity attacks
    ac_bonus: int = 0        # for Shield
    spell_level: int = 0     # for Counterspell
    narrative: str = ""
    used_reaction: bool = True  # did it consume the reaction?

    def to_dict(self) -> dict:
        return {
            "reaction_type": self.reaction_type,
            "actor": self.actor,
            "trigger": self.trigger,
            "success": self.success,
            "roll": self.roll,
            "total": self.total,
            "damage": self.damage,
            "ac_bonus": self.ac_bonus,
            "spell_level": self.spell_level,
            "narrative": self.narrative,
            "used_reaction": self.used_reaction,
        }


@dataclass
class ReactionState:
    """Tracks which combatants have used their reaction this round."""
    used_this_round: dict = field(default_factory=dict)  # name -> bool

    def has_reaction(self, name: str) -> bool:
        return not self.used_this_round.get(name, False)

    def use_reaction(self, name: str) -> None:
        self.used_this_round[name] = True

    def restore_all(self) -> None:
        """Restore all reactions at start of new round."""
        self.used_this_round.clear()

    def to_dict(self) -> dict:
        return {"used_this_round": dict(self.used_this_round)}

    @classmethod
    def from_dict(cls, data: dict) -> "ReactionState":
        return cls(used_this_round=data.get("used_this_round", {}))


# -- Reaction Engine ----------------------------------------------------------

class ReactionEngine:
    """
    Resolves all possible reactions to a triggering event.

    Usage:
        engine = ReactionEngine(state)
        results = engine.check_opportunity_attack(
            leaver_name='Valdric',
            leaver_is_player=True,
            enemies=state['enemies'],
            player_char=valdric_char,
        )
    """

    def __init__(self, state: dict) -> None:
        self.state = state
        self._reaction_state = ReactionState.from_dict(
            state.get("reactions", {})
        )

    def save(self) -> None:
        """Persist reaction state back to game state."""
        self.state["reactions"] = self._reaction_state.to_dict()

    # -- Opportunity Attack ---------------------------------------------------

    def check_opportunity_attack(
        self,
        leaver_name: str,
        leaver_is_player: bool,
        enemies: dict,
        player_char: Optional["Character"] = None,
    ) -> list[ReactionResult]:
        """
        Check if any creature in melee range gets an opportunity attack
        when a creature moves out of reach.

        D&D 5e rules:
        - Only triggers when willingly moving out of reach (not forced/pushed)
        - The attacker gets ONE melee attack against the leaving creature
        - Disengage action prevents all opportunity attacks

        Args:
            leaver_name: Name of creature leaving reach
            leaver_is_player: True if the leaver is a player character
            enemies: dict of enemy data from state["enemies"]
            player_char: Player Character object (for AC check, taking damage)

        Returns:
            List of ReactionResult (usually 0 or 1)
        """
        results = []

        # Check if leaver disengaged
        if leaver_is_player and player_char:
            if player_char.has_disengaged:
                return results

        # Enemies attacking player as they leave
        if leaver_is_player:
            for enemy_id, enemy_data in enemies.items():
                if not self._reaction_state.has_reaction(enemy_data.get("name", enemy_id)):
                    continue
                if self._is_incapacitated(enemy_data):
                    continue

                result = self._resolve_enemy_opportunity_attack(
                    enemy_data, player_char
                )
                if result:
                    results.append(result)
                    self._reaction_state.use_reaction(enemy_data.get("name", enemy_id))
        else:
            # Player gets opportunity attack against enemy leaving
            if player_char and self._reaction_state.has_reaction(player_char.name):
                if not player_char.has_disengaged:
                    result = self._resolve_player_opportunity_attack(
                        player_char, leaver_name, enemies
                    )
                    if result:
                        results.append(result)
                        self._reaction_state.use_reaction(player_char.name)

        self.save()
        return results

    def _resolve_enemy_opportunity_attack(
        self, enemy_data: dict, player_char: Optional["Character"]
    ) -> Optional[ReactionResult]:
        """Resolve a single enemy opportunity attack against the player."""
        enemy_name = enemy_data.get("name", "Enemy")

        attacks = enemy_data.get("attacks", [])
        if not attacks:
            return None

        attack = attacks[0]  # Use primary attack
        attack_bonus = attack.get("to_hit", 0)
        damage_dice = attack.get("damage", "1d6")
        damage_type = attack.get("type", "slashing")

        # Roll attack
        d20 = random.randint(1, 20)
        total = d20 + attack_bonus

        target_ac = 10
        if player_char:
            target_ac = player_char.get_ac()

        hit = total >= target_ac or d20 == 20
        critical = d20 == 20
        fumble = d20 == 1

        damage = 0
        if hit and not fumble:
            damage = self._roll_damage(damage_dice, critical)

        narrative = self._build_opportunity_narrative(
            enemy_name, total, hit, critical, fumble, damage, damage_type
        )

        return ReactionResult(
            reaction_type=REACTION_OPPORTUNITY_ATTACK,
            actor=enemy_name,
            trigger="target leaving melee reach",
            success=hit and not fumble,
            roll=d20,
            total=total,
            damage=damage,
            narrative=narrative,
        )

    def _resolve_player_opportunity_attack(
        self, player_char: "Character", enemy_name: str, enemies: dict
    ) -> Optional[ReactionResult]:
        """Resolve player opportunity attack against a leaving enemy."""
        enemy_data = None
        for eid, edata in enemies.items():
            if edata.get("name", eid) == enemy_name:
                enemy_data = edata
                break

        if not enemy_data:
            return None

        d20 = random.randint(1, 20)
        attack_mod = player_char.attack_bonus()
        total = d20 + attack_mod

        target_ac = enemy_data.get("ac", 10)
        hit = total >= target_ac or d20 == 20
        critical = d20 == 20
        fumble = d20 == 1

        damage = 0
        if hit and not fumble:
            weapon_dice = "1d4"
            if player_char.equipped_weapon:
                for item in player_char.inventory:
                    if item.name == player_char.equipped_weapon and item.damage_dice:
                        weapon_dice = item.damage_dice
                        break

            damage = self._roll_damage(weapon_dice, critical) + player_char.mod("str")
            damage = max(1, damage)

        narrative = self._build_player_opportunity_narrative(
            player_char.name, enemy_name, total, hit, critical, fumble, damage
        )

        return ReactionResult(
            reaction_type=REACTION_OPPORTUNITY_ATTACK,
            actor=player_char.name,
            trigger="enemy leaving melee reach",
            success=hit and not fumble,
            roll=d20,
            total=total,
            damage=damage,
            narrative=narrative,
        )

    # -- Shield Spell (Reaction) ---------------------------------------------

    def check_shield_spell(
        self,
        caster_name: str,
        incoming_attack_total: int,
        player_char: Optional["Character"] = None,
    ) -> Optional[ReactionResult]:
        """
        Shield spell: +5 AC as a reaction when hit by an attack.
        Triggers AFTER the attack hits but BEFORE damage is applied.

        Only usable if:
        1. Caster has Shield in known spells
        2. Has a Level 1+ spell slot
        3. Hasn't used reaction this round
        """
        if not player_char:
            return None
        if caster_name != player_char.name:
            return None
        if not self._reaction_state.has_reaction(caster_name):
            return None

        # Check if player knows Shield
        known = getattr(player_char, 'known_spells', [])
        if "shield" not in [s.lower() for s in known]:
            return None

        # Check spell slot availability
        if player_char.spell_slots.available(1) <= 0:
            return None

        # Consume slot
        player_char.spell_slots.use(1)

        self._reaction_state.use_reaction(caster_name)
        self.save()

        narrative = (
            f"\u2728 **{caster_name}** conjura **Shield** como reaccion! "
            f"+5 AC hasta el proximo turno."
        )

        return ReactionResult(
            reaction_type=REACTION_SHIELD,
            actor=caster_name,
            trigger=f"incoming attack (total {incoming_attack_total})",
            success=True,
            ac_bonus=5,
            narrative=narrative,
        )

    # -- Counterspell (Reaction) ---------------------------------------------

    def check_counterspell(
        self,
        caster_name: str,
        spell_level: int,
        player_char: Optional["Character"] = None,
        enemies: Optional[dict] = None,
    ) -> Optional[ReactionResult]:
        """
        Counterspell: Interrupt a spell as a reaction.
        D&D 5e rules:
        - Auto-succeed if counterspell level >= spell level
        - Auto-fail if counterspell level < spell level - 3
        """
        if not player_char:
            return None
        if not self._reaction_state.has_reaction(player_char.name):
            return None

        known = getattr(player_char, 'known_spells', [])
        if "counterspell" not in [s.lower() for s in known]:
            return None

        # Find best available slot for counterspell
        counterspell_level = 0
        for lvl in range(3, 10):
            if player_char.spell_slots.available(lvl) > 0:
                counterspell_level = lvl
                break

        if counterspell_level == 0:
            return None

        success = counterspell_level >= spell_level

        if success:
            player_char.spell_slots.use(counterspell_level)
            self._reaction_state.use_reaction(player_char.name)
            self.save()

            narrative = (
                f"\u2728 **{caster_name}** lanza **Counterspell** (Lv{counterspell_level}) "
                f"e interrumpe el conjuro de nivel {spell_level}!"
            )
            return ReactionResult(
                reaction_type=REACTION_COUNTERSPELL,
                actor=caster_name,
                trigger=f"enemy casting Lv{spell_level} spell",
                success=True,
                spell_level=counterspell_level,
                narrative=narrative,
            )

        return None

    # -- Ready Action Trigger ------------------------------------------------

    def check_ready_action(
        self,
        actor_name: str,
        trigger_event: str,
    ) -> Optional[ReactionResult]:
        """Check if any combatant has a readied action matching this trigger."""
        player_char_data = self.state.get("player", {})

        pending = player_char_data.get("pending_ready")
        if pending and actor_name != player_char_data.get("name", ""):
            trigger_desc = pending.get("trigger", "").lower()
            action_desc = pending.get("action", "")

            if self._trigger_matches(trigger_event, trigger_desc):
                player_char_data["pending_ready"] = None

                narrative = (
                    f"\u26a1 **{player_char_data.get('name', 'Player')}** ejecuta su "
                    f"accion preparada: {action_desc}"
                )

                return ReactionResult(
                    reaction_type=REACTION_READY,
                    actor=player_char_data.get("name", "Player"),
                    trigger=trigger_event,
                    success=True,
                    narrative=narrative,
                )

        return None

    # -- Uncanny Dodge (Rogue) -----------------------------------------------

    def check_uncanny_dodge(
        self,
        target_name: str,
        incoming_damage: int,
        player_char: Optional["Character"] = None,
    ) -> Optional[ReactionResult]:
        """
        Uncanny Dodge (Rogue level 5+): Halve incoming damage as a reaction.
        """
        if not player_char:
            return None
        if target_name != player_char.name:
            return None
        if player_char.player_class != "rogue" or player_char.level < 5:
            return None
        if not self._reaction_state.has_reaction(target_name):
            return None

        halved_damage = incoming_damage // 2
        self._reaction_state.use_reaction(target_name)
        self.save()

        narrative = (
            f"\U0001f6e1 **{target_name}** usa **Uncanny Dodge**! "
            f"Dano reducido de {incoming_damage} a {halved_damage}."
        )

        return ReactionResult(
            reaction_type=REACTION_UNCANNY_DODGE,
            actor=target_name,
            trigger=f"taking {incoming_damage} damage",
            success=True,
            damage=halved_damage,
            narrative=narrative,
        )

    # -- Bulk Reaction Check -------------------------------------------------

    def get_available_reactions(
        self, combatant_name: str, is_player: bool, char: Optional["Character"] = None
    ) -> list[str]:
        """List available reaction types for a combatant."""
        available = []
        if not self._reaction_state.has_reaction(combatant_name):
            return available

        if is_player and char:
            known = getattr(char, 'known_spells', [])
            known_lower = [s.lower() for s in known]
            if "shield" in known_lower and char.spell_slots.available(1) > 0:
                available.append(REACTION_SHIELD)
            if "counterspell" in known_lower:
                for lvl in range(3, 10):
                    if char.spell_slots.available(lvl) > 0:
                        available.append(REACTION_COUNTERSPELL)
                        break
            if char.player_class == "rogue" and char.level >= 5:
                available.append(REACTION_UNCANNY_DODGE)

        available.append(REACTION_OPPORTUNITY_ATTACK)
        return available

    # -- Round Management ---------------------------------------------------

    def on_new_round(self) -> None:
        """Restore all reactions at start of new round."""
        self._reaction_state.restore_all()
        self.save()

    # -- Helpers -------------------------------------------------------------

    def _roll_damage(self, damage_dice: str, critical: bool = False) -> int:
        """Roll damage from a dice string like '1d6+2'."""
        try:
            expr = damage_dice.lower().strip()
            bonus = 0
            if '+' in expr:
                dice_part, bonus_str = expr.split('+')
                bonus = int(bonus_str)
            else:
                dice_part = expr

            count_str, sides_str = dice_part.split('d')
            count = int(count_str) if count_str else 1
            sides = int(sides_str)

            if critical:
                count *= 2

            rolls = [random.randint(1, sides) for _ in range(count)]
            return sum(rolls) + bonus
        except Exception:
            return random.randint(1, 6)

    @staticmethod
    def _is_incapacitated(entity_data: dict) -> bool:
        """Check if entity has incapacitated condition."""
        conditions = entity_data.get("conditions", [])
        return "incapacitated" in conditions

    @staticmethod
    def _trigger_matches(event: str, trigger: str) -> bool:
        """Simple trigger matching for readied actions."""
        event_lower = event.lower()
        trigger_lower = trigger.lower()

        keywords = {
            "enemy attacks": ["attack", "attacks", "melee", "strike"],
            "enemy moves": ["moves", "approaches", "walks", "enters"],
            "ally hurt": ["damage", "hurt", "hit", "wounded"],
            "combat starts": ["combat", "fight", "battle", "initiative"],
        }

        for key, words in keywords.items():
            if key in event_lower:
                return any(w in trigger_lower for w in words)

        event_words = set(event_lower.split())
        trigger_words = set(trigger_lower.split())
        return bool(event_words & trigger_words)

    # -- Narrative Builders --------------------------------------------------

    @staticmethod
    def _build_opportunity_narrative(
        attacker: str, total: int, hit: bool, critical: bool,
        fumble: bool, damage: int, damage_type: str
    ) -> str:
        if fumble:
            return (
                f"\u2694\ufe0f **{attacker}** ataca de oportunidad -- tiro {total} -- "
                f"\u2b50 FALLO CRITICO! El golpe se va al aire."
            )
        if not hit:
            return (
                f"\u2694\ufe0f **{attacker}** ataca de oportunidad -- tiro {total} -- falla."
            )
        if critical:
            return (
                f"\u2694\ufe0f **{attacker}** ataca de oportunidad -- \u2b50 CRITICO (tiro {total})! "
                f"**{damage}** de dano {damage_type}!"
            )
        return (
            f"\u2694\ufe0f **{attacker}** ataca de oportunidad -- tiro {total} -- "
            f"impacta! **{damage}** de dano {damage_type}."
        )

    @staticmethod
    def _build_player_opportunity_narrative(
        player: str, enemy: str, total: int, hit: bool,
        critical: bool, fumble: bool, damage: int
    ) -> str:
        if fumble:
            return (
                f"\u2694\ufe0f **{player}** lanza ataque de oportunidad contra {enemy} -- "
                f"\u2b50 FALLO CRITICO!"
            )
        if not hit:
            return (
                f"\u2694\ufe0f **{player}** lanza ataque de oportunidad contra {enemy} -- falla (tiro {total})."
            )
        if critical:
            return (
                f"\u2694\ufe0f **{player}** lanza ataque de oportunidad contra {enemy} -- "
                f"\u2b50 CRITICO! **{damage}** de dano!"
            )
        return (
            f"\u2694\ufe0f **{player}** lanza ataque de oportunidad contra {enemy} -- "
            f"impacta! **{damage}** de dano."
        )
