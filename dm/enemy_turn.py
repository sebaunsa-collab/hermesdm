"""
enemy_turn.py — Enemy Turn Resolution for HermesDM.

After every player action in combat, enemies resolve their turns.
Each enemy attacks a player target, rolling attack and damage.

This transforms combat from a one-sided damage simulator into a real D&D game.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from dm.conditions import (
    has_disadvantage_on_attacks,
    has_advantage_on_attacks_against,
    is_incapacitated,
    get_condition,
)

if TYPE_CHECKING:
    from bot.character_sheet import Character


@dataclass
class EnemyAttackResult:
    """Result of a single enemy attack."""
    attacker: str
    defender: str
    attack_roll: int = 0
    attack_bonus: int = 0
    total: int = 0
    hit: bool = False
    damage: int = 0
    damage_roll: str = ""
    actual_damage: int = 0
    target_hp: int = 0
    target_max_hp: int = 0
    critical: bool = False
    fumble: bool = False


@dataclass
class EnemyTurnResult:
    """Combined result of all enemy turns in a round."""
    narrative: str = ""
    total_damage: int = 0
    events: list = field(default_factory=list)
    players_unconscious: list = field(default_factory=list)
    players_dead: list = field(default_factory=list)


class EnemyTurnResolver:
    """Resolves enemy turns after a player action in combat.

    Usage:
        resolver = EnemyTurnResolver(state, characters)
        result = resolver.resolve_enemies()
        # result.narrative → text describing enemy attacks
        # result.total_damage → total damage dealt to players
        # result.players_unconscious → list of player names at 0 HP
    """

    def __init__(self, state: dict, characters: dict):
        """
        Args:
            state: Full game state dict (from state.json)
            characters: dict of {name: Character} from ChatState.characters
        """
        self.state = state
        self.characters = characters
        self.combat = state.get("combat", {})
        self.enemies = state.get("enemies", {})
        self.initiative = self.combat.get("initiative_order", [])

    def resolve_enemies(self) -> EnemyTurnResult:
        """Resolve all enemy turns after the player's action.

        Returns EnemyTurnResult with narrative and damage info.
        """
        events = []
        players_unconscious = []
        players_dead = []
        total_damage = 0

        # Process enemies in initiative order AFTER the player
        player_found = False
        for combatant in self.initiative:
            name = combatant.get("name", "")
            is_player = combatant.get("is_player", False)

            if is_player:
                player_found = True
                continue  # Skip players — they already acted

            # Only process enemies that come AFTER the player in initiative
            # (enemies before the player acted last round)
            if not player_found:
                continue

            # Get enemy data from state
            enemy_data = self.enemies.get(name, {})
            if not enemy_data or enemy_data.get("hp_current", 0) <= 0:
                continue  # Dead enemies don't act

            # Determine number of attacks
            attacks_data = enemy_data.get("attacks", [])
            multiattack = enemy_data.get("multiattack", 1)
            num_attacks = min(multiattack, 3)  # Cap at 3 to prevent spam

            # Pick target
            target = self._pick_target(name, enemy_data)
            if not target:
                continue  # No valid target

            # Resolve each attack
            for atk_idx in range(num_attacks):
                atk_data = attacks_data[atk_idx] if atk_idx < len(attacks_data) else (
                    attacks_data[0] if attacks_data else None
                )

                result = self._resolve_enemy_attack(name, enemy_data, target, atk_data)
                events.append(result)

                if result.hit and result.actual_damage > 0:
                    total_damage += result.actual_damage

                    # Check if player fell unconscious
                    if result.target_hp <= 0:
                        # Check if it's from full HP (massive damage) or already low
                        if result.target_max_hp > 0 and result.actual_damage >= result.target_max_hp:
                            players_dead.append(result.defender)
                        else:
                            players_unconscious.append(result.defender)

        # Build narrative
        narrative = self._build_narrative(events, players_unconscious, players_dead)

        return EnemyTurnResult(
            narrative=narrative,
            total_damage=total_damage,
            events=events,
            players_unconscious=players_unconscious,
            players_dead=players_dead,
        )

    def _pick_target(self, enemy_name: str, enemy_data: dict) -> Optional["Character"]:
        """Simple AI: attack the weakest living player.

        Priority:
        1. If only 1 player → attack that player
        2. If multiple → attack the one with lowest HP percentage
        """
        living_players = []
        for name, char in self.characters.items():
            if hasattr(char, 'hp') and char.hp and char.hp.current > 0:
                living_players.append(char)

        if not living_players:
            return None

        if len(living_players) == 1:
            return living_players[0]

        # Attack weakest by HP percentage
        living_players.sort(key=lambda c: c.hp.current / max(c.hp.max, 1))
        return living_players[0]

    def _resolve_enemy_attack(
        self,
        enemy_name: str,
        enemy_data: dict,
        target: "Character",
        atk_data: Optional[dict] = None,
    ) -> EnemyAttackResult:
        """Resolve a single enemy attack.

        Args:
            enemy_name: Name of the attacking enemy
            enemy_data: Enemy dict from state["enemies"]
            target: Target Character object
            atk_data: Attack dict {name, to_hit, damage, type} or None for default

        Returns:
            EnemyAttackResult with attack and damage info
        """
        result = EnemyAttackResult(
            attacker=enemy_name,
            defender=target.name if target else "?",
        )

        if not target or not target.hp:
            return result

        # Get attack bonus
        attack_bonus = 0
        damage_dice = "1d6"  # Default fallback
        damage_bonus = 0

        if atk_data:
            attack_bonus = atk_data.get("to_hit", 0)
            damage_dice = atk_data.get("damage", "1d6")
            # Parse bonus from damage string if present (e.g., "2d4+2")
            if "+" in damage_dice:
                parts = damage_dice.split("+")
                damage_dice = parts[0]
                try:
                    damage_bonus = int(parts[1])
                except (ValueError, IndexError):
                    damage_bonus = 0
            else:
                damage_bonus = 0
        else:
            # Default attack: d20 + CR-based bonus
            cr = enemy_data.get("cr", 1)
            attack_bonus = max(2, int(cr * 1.5) + 1)

        result.attack_bonus = attack_bonus

        # ── Check advantage/disadvantage from conditions ────
        # Enemy conditions (poisoned, frightened, etc.)
        enemy_char_obj = type('SimpleObj', (), {'conditions': enemy_data.get('features', [])})()
        # Actually, enemy conditions aren't tracked in state yet. Use features as proxy.
        # For now, check if enemy has disadvantage keywords in features
        enemy_features = " ".join(enemy_data.get("features", [])).lower()
        enemy_has_disadv = any(w in enemy_features for w in ["poisoned", "frightened", "blinded", "prone"])

        # Player conditions
        target_has_disadv = has_disadvantage_on_attacks(target) if hasattr(target, 'conditions') else False
        target_has_adv_against = has_advantage_on_attacks_against(target) if hasattr(target, 'conditions') else False

        # Determine advantage/disadvantage
        advantage = False
        disadvantage = False

        # If target is prone → melee advantage, ranged disadvantage
        if hasattr(target, 'conditions') and "prone" in getattr(target, 'conditions', []):
            advantage = True  # Assume melee for simplicity

        # If target is invisible → attacks against have disadvantage
        if hasattr(target, 'conditions') and "invisible" in getattr(target, 'conditions', []):
            disadvantage = True

        # If enemy is poisoned/blinded/frightened → disadvantage on attacks
        if enemy_has_disadv:
            disadvantage = True

        # Roll attack with advantage/disadvantage
        if advantage and not disadvantage:
            d20_a = random.randint(1, 20)
            d20_b = random.randint(1, 20)
            d20 = max(d20_a, d20_b)
        elif disadvantage and not advantage:
            d20_a = random.randint(1, 20)
            d20_b = random.randint(1, 20)
            d20 = min(d20_a, d20_b)
        else:
            d20 = random.randint(1, 20)

        result.attack_roll = d20
        result.critical = (d20 == 20)
        result.fumble = (d20 == 1)

        # Natural 20 = automatic hit + critical
        # Natural 1 = automatic miss
        if d20 == 1:
            result.total = 1
            result.hit = False
            return result

        if d20 == 20:
            result.total = 20 + attack_bonus
            result.hit = True
        else:
            target_ac = self._get_target_ac(target)
            result.total = d20 + attack_bonus
            result.hit = (result.total >= target_ac)

        if not result.hit:
            return result

        # Roll damage
        if result.critical:
            # Critical: roll damage dice twice
            base_damage = self._roll_damage(damage_dice, double=True)
        else:
            base_damage = self._roll_damage(damage_dice, double=False)

        total_damage = base_damage + damage_bonus
        result.damage = total_damage
        result.damage_roll = damage_dice

        # Apply damage to target
        actual = target.hp.apply_damage(total_damage)
        result.actual_damage = actual
        result.target_hp = target.hp.current
        result.target_max_hp = target.hp.max

        return result

    def _get_target_ac(self, target: "Character") -> int:
        """Get target's AC. Uses character's AC if set, else defaults to 10."""
        if hasattr(target, 'ac') and target.ac:
            return target.ac
        # Try to calculate from equipment
        if hasattr(target, 'get_ac'):
            return target.get_ac()
        return 10

    def _roll_damage(self, dice_str: str, double: bool = False) -> int:
        """Roll damage dice.

        Args:
            dice_str: Dice notation like "2d4", "1d6+2", "1d8"
            double: If True, roll twice (for critical hits)

        Returns:
            Total damage rolled
        """
        try:
            # Parse dice notation
            if "d" in dice_str:
                parts = dice_str.split("d")
                num_dice = int(parts[0])
                sides_str = parts[1].split("+")[0].split("-")[0]
                sides = int(sides_str)

                total = 0
                rolls = num_dice * (2 if double else 1)
                for _ in range(rolls):
                    total += random.randint(1, sides)
                return max(1, total)  # Minimum 1 damage
            else:
                # Flat damage
                base = int(dice_str)
                return base * (2 if double else 1)
        except (ValueError, IndexError):
            return 4  # Fallback: 1d4

    def _build_narrative(
        self,
        events: list[EnemyAttackResult],
        players_unconscious: list[str],
        players_dead: list[str],
    ) -> str:
        """Build a readable narrative from enemy attack results."""
        if not events:
            return ""

        lines = ["⚔️ *Turno de los enemigos:*"]

        for event in events:
            if event.fumble:
                lines.append(f"  🎲 {event.attacker} falla estrepitosamente ({event.attack_roll})")
                continue

            if not event.hit:
                lines.append(f"  🛡️ {event.attacker} ataca a {event.defender} pero falla ({event.total})")
                continue

            crit_note = " 💥 *CRÍTICO!*" if event.critical else ""
            lines.append(
                f"  ⚔️ {event.attacker} golpea a {event.defender} "
                f"({event.total}) → {event.actual_damage} dmg "
                f"(HP: {event.target_hp}/{event.target_max_hp}){crit_note}"
            )

        # Add unconscious/death messages
        for name in players_unconscious:
            lines.append(f"\n  💀 *{name} cae inconsciente!* Death saves activados...")
        for name in players_dead:
            lines.append(f"\n  ☠️ *{name} ha MUERTO!* (daño masivo)")

        return "\n".join(lines)
