"""
narrative_generator.py — Template-based narrative generation for HermesDM.

Python handles template-based narrative generation for D&D scenes.
Scene types: EXPLORATION, COMBAT, DIALOGUE, STORY_BEAT, REST
Format: 2-4 sentences, ends with an open SITUATION (never a question).
"""

from __future__ import annotations

import random
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dm.provider_client import LLMClient
    from state.state_manager import GameState

from campaign_settings import Language


class SceneType(str, Enum):
    """Supported scene types for narrative generation."""

    EXPLORATION = "EXPLORATION"
    COMBAT = "COMBAT"
    DIALOGUE = "DIALOGUE"
    STORY_BEAT = "STORY_BEAT"
    REST = "REST"
    EPILOGUE = "EPILOGUE"
    CAMPAIGN_CLOSE = "CAMPAIGN_CLOSE"


# ---------------------------------------------------------------------------
# Narrative Templates (Multi-language)
# ---------------------------------------------------------------------------

_NARRATIVE_TEMPLATES: dict[Language, dict[SceneType, list[str]]] = {
    Language.ES: {
        SceneType.EXPLORATION: [
            "El {location} se extiende ante ti, {sensory_detail}. "
            "{character_present} {action_description}. "
            "El camino adelante está {obstacle}",
            "Te encuentras en {location}, donde {environmental_detail}. "
            "{npc_or_character_present} {reaction_description}. "
            "{ambient_threat} mientras consideras tu siguiente movimiento",
            "El {location} te recibe con {sensory_detail}. "
            "{character_present} {action_description}. "
            "Algo en este lugar se siente {emotional_tone}",
        ],
        SceneType.COMBAT: [
            "{attacker} se lanza hacia {defender}, {attack_description}. "
            "El {impact_type} resuena a través del {environment}. "
            "{defender_status}",
            "El caos estalla cuando {attacker} {attack_description} contra {defender}. "
            "{bystanders_react}. "
            "{tactical_situation}",
            "{attacker} ataca con {attack_descriptor}, {attack_description}. "
            "El {environment} ofrece {environmental_factor}. "
            "{defender_status}",
        ],
        SceneType.DIALOGUE: [
            "{speaker} se vuelve hacia ti, {speech_trait}. "
            '"{dialogue_excerpt}", dice, {gesture}. '
            "El aire entre ustedes se siente {emotional_tone}",
            "{speaker} te mira directamente, {character_mood}. "
            '"{first_words}" {speech_descriptor}. '
            "{listener_reaction}",
            "Encuentras a {speaker} {location_context}. "
            '"{opening_line}" {speaker_action}. '
            "{tension_point}",
        ],
        SceneType.STORY_BEAT: [
            "La verdad se revela ante ti: {revelation}. "
            "{affected_party} {reaction_to_truth}. "
            "Nada será igual después de esto",
            "Te llega noticias de {event_summary}. "
            "{stake_holder} {emotional_response}. "
            "Las piezas ya están en movimiento",
            "Un punto de inflexión llega cuando {incident_description}. "
            "{witness_or_participant} {response_to_incident}. "
            "{consequence_looming}",
        ],
        SceneType.REST: [
            "La relativa tranquilidad de {location} ofrece un momento para respirar. "
            "{healing_atmosphere}. "
            "{resources_available} para quien los busque",
            "Te refugias en {location}, donde {rest_comforts}. "
            "{party_status} mientras el cansancio se instala. "
            "El amanecer traerá nuevos desafíos",
            "El {location} proporciona respiro de tu viaje. "
            "{ambient_details}. "
            "{opportunity_available}",
        ],
    },
    Language.PT: {
        SceneType.EXPLORATION: [
            "O {location} se estende diante de você, {sensory_detail}. "
            "{character_present} {action_description}. "
            "O caminho à frente está {obstacle}",
            "Você se encontra em {location}, onde {environmental_detail}. "
            "{npc_or_character_present} {reaction_description}. "
            "{ambient_threat} enquanto considera seu próximo movimento",
            "O {location} o recebe com {sensory_detail}. "
            "{character_present} {action_description}. "
            "Algo neste lugar parece {emotional_tone}",
        ],
        SceneType.COMBAT: [
            "{attacker} avança contra {defender}, {attack_description}. "
            "O {impact_type} ecoa através do {environment}. "
            "{defender_status}",
            "Caos irrompe quando {attacker} {attack_description} contra {defender}. "
            "{bystanders_react}. "
            "{tactical_situation}",
            "{attacker} ataca com {attack_descriptor}, {attack_description}. "
            "O {environment} oferece {environmental_factor}. "
            "{defender_status}",
        ],
        SceneType.DIALOGUE: [
            "{speaker} se vira para você, {speech_trait}. "
            '"{dialogue_excerpt}", diz, {gesture}. '
            "O ar entre vocês parece {emotional_tone}",
            "{speaker} encontra seu olhar, {character_mood}. "
            '"{first_words}" {speech_descriptor}. '
            "{listener_reaction}",
            "Você encontra {speaker} {location_context}. "
            '"{opening_line}" {speaker_action}. '
            "{tension_point}",
        ],
        SceneType.STORY_BEAT: [
            "A verdade se revela diante de você: {revelation}. "
            "{affected_party} {reaction_to_truth}. "
            "Nada será igual depois disso",
            "Notícias chegam até você sobre {event_summary}. "
            "{stake_holder} {emotional_response}. "
            "As peças já estão em movimento",
            "Um ponto de inflexão chega quando {incident_description}. "
            "{witness_or_participant} {response_to_incident}. "
            "{consequence_looming}",
        ],
        SceneType.REST: [
            "A relativa quietude de {location} oferece um momento para respirar. "
            "{healing_atmosphere}. "
            "{resources_available} para quem os buscar",
            "Você se abriga em {location}, onde {rest_comforts}. "
            "{party_status} enquanto a fadiga se instala. "
            "O amanhecer trará novos desafios",
            "O {location} proporciona descanso de sua jornada. "
            "{ambient_details}. "
            "{opportunity_available}",
        ],
    },
    Language.EN: {
        SceneType.EXPLORATION: [
            "The {location} stretches before you, {sensory_detail}. "
            "{character_present} {action_description}. "
            "The path forward is {obstacle}",
            "You find yourself in {location}, where {environmental_detail}. "
            "{npc_or_character_present} {reaction_description}. "
            "{ambient_threat} as you consider your next move",
            "The {location} greets you with {sensory_detail}. "
            "{character_present} {action_description}. "
            "Something about this place feels {emotional_tone}",
        ],
        SceneType.COMBAT: [
            "{attacker} lunges toward {defender}, {attack_description}. "
            "The {impact_type} echoes through the {environment}. "
            "{defender_status}",
            "Chaos erupts as {attacker} {attack_description} against {defender}. "
            "{bystanders_react}. "
            "{tactical_situation}",
            "{attacker} strikes with {attack_descriptor}, {attack_description}. "
            "The {environment} provides {environmental_factor}. "
            "{defender_status}",
        ],
        SceneType.DIALOGUE: [
            "{speaker} turns to face you, {speech_trait}. "
            '"{dialogue_excerpt}", they say, {gesture}. '
            "The air between you feels {emotional_tone}",
            "{speaker} meets your gaze, {character_mood}. "
            '"{first_words}" {speech_descriptor}. '
            "{listener_reaction}",
            "You find {speaker} {location_context}. "
            '"{opening_line}" {speaker_action}. '
            "{tension_point}",
        ],
        SceneType.STORY_BEAT: [
            "The truth unfolds before you: {revelation}. "
            "{affected_party} {reaction_to_truth}. "
            "Nothing will be the same after this",
            "Word reaches you of {event_summary}. "
            "{stake_holder} {emotional_response}. "
            "The pieces are in motion now",
            "A turning point arrives as {incident_description}. "
            "{witness_or_participant} {response_to_incident}. "
            "{consequence_looming}",
        ],
        SceneType.REST: [
            "The relative quiet of {location} offers a moment to breathe. "
            "{healing_atmosphere}. "
            "{resources_available} for those who seek them",
            "You take shelter in {location}, where {rest_comforts}. "
            "{party_status} as fatigue settles in. "
            "Dawn will bring new challenges",
            "The {location} provides respite from your journey. "
            "{ambient_details}. "
            "{opportunity_available}",
        ],
    },
}

# ---------------------------------------------------------------------------
# Combat Result Narratives
# ---------------------------------------------------------------------------

_HIT_NARRATIVES = [
    "The blow lands clean, {damage_descriptor}!",
    "{attacker} strikes true, {damage_description}!",
    "A solid hit — {damage_detail}!",
]

_MISS_NARRATIVES = [
    "{attacker} swings wide, the attack missing by a breath.",
    "The strike glances off harmlessly.",
    "{attacker} overextends, leaving the attack incomplete.",
]

_KILL_NARRATIVES = [
    "{defender} crumples to the ground, {death_descriptor}.",
    "{defender} falls, {final_words}. Silence follows.",
    "{defender} is slain. {bystander_reaction}",
]

_NAT_20_NARRATIVES = [
    "A critical hit! The attack strikes with devastating precision!",
    "Natural 20! {attacker} delivers a devastating blow!",
    "Critical success — the attack lands with terrible force!",
]

# ---------------------------------------------------------------------------
# Skill Check Narratives
# ---------------------------------------------------------------------------

_SKILL_SUCCESS = [
    "{character} {skill_action} with practiced ease.",
    "Success! {character} {skill_result_description}.",
    "{character}'s expertise shows as they {skill_result_description}.",
]

_SKILL_FAILURE = [
    "{character} attempts to {skill_attempt}, but {failure_reason}.",
    "The check fails — {failure_detail}.",
    "{character} struggles, but {failure_reason}.",
]

# ---------------------------------------------------------------------------
# Dialogue Placeholder Templates
# ---------------------------------------------------------------------------

_DIALOGUE_RESPONSES = [
    "I have nothing more to say on this matter.",
    "You think I will bend to your will? Think again.",
    "The road ahead is long, and many have walked it before.",
]


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------


class NarrativeGenerator:
    """
    Generate narrative scenes for HermesDM campaigns.

    Supports two modes:
    - Template mode (default): fast, no API calls, deterministic
    - LLM mode: set llm_client to a real provider for AI-generated narratives

    Usage:
        # Template mode (default — no API calls)
        ng = NarrativeGenerator()
        result = ng.generate_scene(state, SceneType.EXPLORATION, context={"location": "Dark Forest"})

        # LLM mode — provider agnostic (usa MiniMax por defecto en HermesDM)
        from dm.provider_client import get_provider
        ng = NarrativeGenerator(llm_client=get_provider("minimax", api_key="..."))
        result = ng.generate_scene(state, SceneType.EXPLORATION, context={"location": "Dark Forest"})
    """

    SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """
        Args:
            llm_client: Optional LLM client for AI-powered narrative generation.
                       If None, falls back to template-based generation.
        """
        self._system_prompt: str | None = None
        self._load_system_prompt()
        self.llm_client = llm_client

    def _build_context(self, state: dict, overrides: dict) -> dict:
        """
        Build template context from state, applying overrides.

        Extracts location, characters present, NPCs nearby, and environmental
        details from state, then applies any context overrides.
        """
        campaign = state.get("campaign", {})
        location = campaign.get("current_location") or "an unknown place"
        characters = state.get("characters", {})
        npcs = state.get("npcs", {})

        # Format active characters
        char_summaries = []
        for cid, char in characters.items():
            hp = char.get("hp", 0)
            max_hp = char.get("max_hp", 0)
            name = char.get("name", cid)
            status = char.get("status", "ready")
            char_summaries.append(f"{name} (HP {hp}/{max_hp}, {status})")

        character_present = (
            ", ".join(char_summaries) if char_summaries else "The party stands ready"
        )

        # Format nearby NPCs
        npc_summaries = []
        for nid, npc in npcs.items():
            if npc.get("location") == location or not npc.get("location"):
                name = npc.get("name", nid)
                status = npc.get("status", "present")
                npc_summaries.append(f"{name} ({status})")

        npc_or_character = (
            f"{npc_summaries[0]} is here" if npc_summaries else character_present
        )

        context: dict = {
            "location": location,
            "sensory_detail": "shadows cling to every surface",
            "environmental_detail": "cold mist rolls between ancient stones",
            "ambient_threat": "A distant growl echoes",
            "obstacle": "obscured by undergrowth and memory",
            "character_present": character_present,
            "npc_or_character_present": npc_or_character,
            "action_description": "moves cautiously through the terrain",
            "reaction_description": "watches with guarded interest",
            "emotional_tone": "charged with unspoken tension",
            "speaker": "A voice emerges",
            "listener_reaction": "You weigh their words carefully.",
            "environment": state.get("world", {}).get(
                "current_environment", "battlefield"
            ),
            "tactical_situation": "Positioning becomes critical.",
            "revelation": "everything you believed was built on lies",
            "affected_party": "The weight of it settles over the party",
            "healing_atmosphere": "a fire crackles nearby",
            "resources_available": "Provisions and rest",
            "party_status": "Fatigue weighs heavy",
            "ambient_details": "The night passes slowly",
            "opportunity_available": "Training or preparation is possible",
        }

        # Apply state overrides
        for key, value in overrides.items():
            if key in context or key in [
                "location",
                "speaker",
                "defender",
                "attacker",
                "npc_name",
                "damage",
                "dc",
                "roll",
                "skill_name",
            ]:
                context[key] = value

        return context

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def generate_scene(
        self,
        state: GameState,
        scene_type: SceneType,
        context: dict | None = None,
        language: Language = Language.ES,
    ) -> dict:
        """
        Generate a narrative scene based on current state and scene type.

        Args:
            state: Full campaign state dict from state_manager
            scene_type: One of SceneType enum values
            context: Optional overrides for template variables
            language: Language for narrative templates (default: ES)

        Returns:
            dict with keys:
                - narrative (str): 2-4 sentence narrative ending in situation
                - triggered_image (bool): Whether an image should be generated
        """
        context = context or {}

        # Merge state-derived context
        full_context = self._build_context(state, context)

        # LLM mode: call AI provider
        if self.llm_client is not None:
            narrative = self._generate_with_llm(scene_type, full_context, language)
            triggered_image = self._should_trigger_image(scene_type, full_context)
            return {
                "narrative": narrative,
                "triggered_image": triggered_image,
            }

        # Template mode (default)
        template = self._select_template(scene_type, language)
        narrative = self._fill_template(template, full_context)

        # Determine if image should trigger
        triggered_image = self._should_trigger_image(scene_type, full_context)

        return {
            "narrative": narrative,
            "triggered_image": triggered_image,
        }

    def generate_closure(
        self,
        state: GameState,
        language: Language = Language.ES,
    ) -> dict:
        """
        Generate campaign closure (epilogue) narrative.

        Builds rich context from state (characters, NPCs, quests, history,
        world_changes, tone) and generates an epic closing narrative.

        Args:
            state: Full campaign state dict from state_manager
            language: Language for narrative (default: ES)

        Returns:
            dict with keys:
                - narrative (str): 4-8 sentence epilogue, second person, ends with
                  powerful affirmation, no questions
                - quest_closure (dict): {quest_id: "completed"|"failed"|"inconclusive"}
                - npc_fates (dict): {npc_id: "alive"|"dead"|"transformed"}
                - character_summaries (dict): {char_id: "summary string"}
                - triggered_image (bool): Whether an image should be generated
        """
        # Build closure context from state
        context = self._build_closure_context(state)

        # LLM mode: generate with AI
        if self.llm_client is not None:
            narrative = self._generate_closure_with_llm(context, language)
            triggered_image = True  # Closure always triggers an image
            return {
                "narrative": narrative,
                "quest_closure": context["quest_closure"],
                "npc_fates": context["npc_fates"],
                "character_summaries": context["character_summaries"],
                "triggered_image": triggered_image,
            }

        # Template mode fallback
        narrative = self._generate_closure_template(context, language)
        return {
            "narrative": narrative,
            "quest_closure": context["quest_closure"],
            "npc_fates": context["npc_fates"],
            "character_summaries": context["character_summaries"],
            "triggered_image": True,
        }

    def _build_closure_context(self, state: dict) -> dict:
        """Build rich context for closure generation from state."""
        campaign = state.get("campaign", {})
        characters = state.get("characters", {})
        npcs = state.get("npcs", {})
        quests = state.get("quests", {})
        history = state.get("history", [])
        world = state.get("world", {})

        # Tone from campaign settings
        settings = state.get("settings", {})
        tone = settings.get("narrative_tone", "epic")

        # Build character summaries
        character_summaries = {}
        for char_id, char in characters.items():
            char_name = char.get("name", char_id)
            char_status = char.get("status", "alive")
            char_hp = char.get("hp", 0)
            char_max_hp = char.get("max_hp", 1)
            char_level = char.get("level", 1)
            char_transformation = char.get("transformation", "")
            summary = {
                "name": char_name,
                "status": char_status,
                "hp": char_hp,
                "max_hp": char_max_hp,
                "level": char_level,
                "transformation": char_transformation,
            }
            character_summaries[char_id] = summary

        # Build NPC fates
        npc_fates = {}
        for npc_id, npc in npcs.items():
            npc_name = npc.get("name", npc_id)
            npc_status = npc.get("status", "alive")
            npc_fate = "alive"
            if npc_status == "dead":
                npc_fate = "dead"
            elif npc.get("new_role"):
                npc_fate = "transformed"
            npc_fates[npc_id] = {
                "name": npc_name,
                "fate": npc_fate,
                "killed_by": npc.get("killed_by"),
                "new_role": npc.get("new_role"),
            }

        # Build quest closures
        quest_closure = {}
        active_quests = quests.get("active", [])
        completed_quests = quests.get("completed", [])

        for quest in completed_quests:
            quest_id = quest.get("id", quest) if isinstance(quest, dict) else quest
            quest_closure[quest_id] = "completed"

        for quest in active_quests:
            quest_id = quest.get("id", quest) if isinstance(quest, dict) else quest
            quest_closure[quest_id] = "inconclusive"

        # Build world changes from history and world state
        world_changes = []

        # Extract significant events from history
        for entry in history[-20:]:  # Last 20 events
            event = entry.get("event", "")
            if event:
                world_changes.append(event[:200])

        # Add world-level changes
        main_threat = world.get("main_threat", "")
        if main_threat:
            world_changes.append(f"The main threat '{main_threat}' has been resolved.")

        # Build arc summary from history
        arc_summary = "The adventure began as a quest for glory and evolved into something far greater."
        if history:
            first_events = history[:3]
            arc_summary = " ".join(
                e.get("event", "")[:100] for e in first_events if e.get("event")
            )
            if len(arc_summary) > 150:
                arc_summary = arc_summary[:147] + "..."

        return {
            "tone": tone,
            "characters": character_summaries,
            "npcs": npc_fates,
            "completed_quests": completed_quests,
            "incomplete_quests": active_quests,
            "quest_closure": quest_closure,
            "world_changes": world_changes,
            "arc_summary": arc_summary,
            "campaign_name": campaign.get("name", "Unknown Campaign"),
        }

    def _generate_closure_with_llm(self, context: dict, language: Language) -> str:
        """Generate closure narrative using LLM."""
        tone = context["tone"]
        characters = context["characters"]
        npcs = context["npcs"]
        world_changes = context["world_changes"]
        arc_summary = context["arc_summary"]
        context["campaign_name"]

        # Format characters for prompt
        char_lines = []
        for char_id, char_data in characters.items():
            name = char_data["name"]
            status = char_data["status"]
            transformation = char_data.get("transformation", "")
            if transformation:
                char_lines.append(f"- {name}: {status}, transformed: {transformation}")
            else:
                char_lines.append(f"- {name}: {status}")
        characters_str = "\n".join(char_lines) if char_lines else "The heroes remain."

        # Format NPCs for prompt
        npc_lines = []
        for npc_id, npc_data in npcs.items():
            name = npc_data["name"]
            fate = npc_data["fate"]
            if fate == "dead" and npc_data.get("killed_by"):
                npc_lines.append(f"- {name}: died, killed by {npc_data['killed_by']}")
            elif fate == "transformed":
                npc_lines.append(
                    f"- {name}: transformed, new role: {npc_data.get('new_role', 'unknown')}"
                )
            else:
                npc_lines.append(f"- {name}: {fate}")
        npcs_str = "\n".join(npc_lines) if npc_lines else "No notable NPCs."

        # Format world changes
        changes_str = (
            "\n".join(f"- {c}" for c in world_changes[:5])
            if world_changes
            else "The world remains unchanged."
        )

        system = (
            "You are HermesDM, an expert D&D Fifth Edition Dungeon Master "
            "known for epic, emotional campaign closings."
        )

        user_prompt = f"""Eres HermesDM, un DM de D&D 5e experto en cierres épicos.

Esta campaña ha terminado. Escribe un EPÍLOGO que:
1. Muestre el destino de cada personaje (vivo, muerto, transformado)
2. Resuelva o deje abierta cada quest
3. Describa cómo el mundo cambió por las acciones del grupo
4. Termine con una línea final memorable (mic drop)
5. Mantén el tono de la campaña ({tone})

Tono: {tone}
Personajes:
{characters_str}

NPCs relevantes:
{npcs_str}

Consecuencias:
{changes_str}

Arc summary: {arc_summary}

Requisitos:
- 4-8 oraciones
- Narrativa en segunda persona ("Tus acciones resonaron por generaciones...")
- Sin preguntas, termina en afirmación poderosa
- No introduzcas nuevos personajes ni tramas
"""

        result = self.llm_client.text(
            prompt=user_prompt,
            system=system,
            max_tokens=512,
            temperature=0.8,
        )

        narrative = result.text.strip()

        # Ensure it doesn't end with a question mark
        if narrative.endswith("?"):
            narrative = narrative[:-1] + "."

        return narrative

    def _generate_closure_template(self, context: dict, language: Language) -> str:
        """Generate closure narrative using templates (fallback when no LLM)."""
        context["tone"]
        characters = context["characters"]
        world_changes = context["world_changes"]
        campaign_name = context["campaign_name"]

        # Build character fate lines
        char_lines = []
        for char_id, char_data in characters.items():
            name = char_data["name"]
            status = char_data["status"]
            if status == "alive":
                char_lines.append(
                    f"{name} lives on, their legend forever etched in history."
                )
            elif status == "dead":
                cause = char_data.get("cause", "in battle")
                char_lines.append(
                    f"{name} fell {cause}, but their sacrifice will never be forgotten."
                )
            else:
                char_lines.append(
                    f"{name}'s fate remains sealed in the annals of time."
                )

        chars_str = (
            " ".join(char_lines)
            if char_lines
            else "The heroes' deeds shall be remembered for generations."
        )

        # Build world change summary
        changes_str = (
            " ".join(world_changes[:3])
            if world_changes
            else "The world will never be the same."
        )

        templates_by_lang = {
            Language.ES: [
                "La campaña {campaign_name} ha llegado a su fin. {chars_str} {changes_str} Tus acciones resonaron por generaciones, y el mundo recordará esta historia para siempre.",
                "El telón cae sobre {campaign_name}. {chars_str} Las estrellas observan este momento sagrado donde los héroes descansan. La leyenda nunca morirá.",
            ],
            Language.EN: [
                "The campaign {campaign_name} has reached its end. {chars_str} {changes_str} Your actions echoed through generations, and the world will remember this story forever.",
                "The curtain falls on {campaign_name}. {chars_str} The stars witness this sacred moment as heroes rest. The legend never dies.",
            ],
            Language.PT: [
                "A campanha {campaign_name} chegou ao fim. {chars_str} {changes_str} Suas ações ecoaram por gerações, e o mundo nunca esquecerá esta história.",
                "O pano cai sobre {campaign_name}. {chars_str} As estrelas testemunham este momento sagrado enquanto os heróis descansam. A lenda nunca morre.",
            ],
        }

        templates = templates_by_lang.get(language, templates_by_lang[Language.EN])
        template = templates[0]
        return template.format(
            campaign_name=campaign_name,
            chars_str=chars_str,
            changes_str=changes_str,
        )

    def describe_combat_result(
        self,
        attack_result: dict,
        attacker_name: str,
        defender_name: str,
    ) -> str:
        """
        Narrate a combat attack result.

        Args:
            attack_result: Dict with keys {hit: bool, damage: int, nat_20: bool,
                         nat_1: bool, kill: bool, description: str}
            attacker_name: Name of the attacking character
            defender_name: Name of the defending character

        Returns:
            Narrative string describing the result
        """
        templates: list[str]

        if attack_result.get("nat_20"):
            templates = _NAT_20_NARRATIVES
            base = self._pick_template(templates)
            base = base.replace("{attacker}", attacker_name)
            return base

        if attack_result.get("kill"):
            templates = _KILL_NARRATIVES
            base = self._pick_template(templates)
            base = base.replace("{defender}", defender_name)
            if "{bystander_reaction}" in base:
                base = base.replace("{bystander_reaction}", "The ground grows still.")
            if "{death_descriptor}" in base:
                base = base.replace("{death_descriptor}", "life draining away")
            if "{final_words}" in base:
                base = base.replace("{final_words}", "no words remain")
            return base

        if attack_result.get("nat_1"):
            templates = _MISS_NARRATIVES
            base = self._pick_template(templates)
            base = base.replace("{attacker}", attacker_name)
            return base

        if attack_result.get("hit"):
            templates = _HIT_NARRATIVES
            base = self._pick_template(templates)
            base = base.replace("{attacker}", attacker_name)
            base = base.replace(
                "{damage_descriptor}", f"{attack_result.get('damage', 0)} damage dealt"
            )
            base = base.replace(
                "{damage_description}",
                f"dealing {attack_result.get('damage', 0)} damage",
            )
            base = base.replace(
                "{damage_detail}", f"{attack_result.get('damage', 0)} points of damage"
            )
            return base
        else:
            templates = _MISS_NARRATIVES
            base = self._pick_template(templates)
            base = base.replace("{attacker}", attacker_name)
            return base

    def describe_skill_result(
        self,
        skill_result: dict,
        character_name: str,
        skill_name: str,
    ) -> str:
        """
        Narrate a skill check result.

        Args:
            skill_result: Dict with keys {success: bool, modifier: int,
                         roll: int, dc: int, note: str}
            character_name: Name of the character making the check
            skill_name: Name of the skill being used

        Returns:
            Narrative string describing the result
        """
        if skill_result.get("success"):
            templates = _SKILL_SUCCESS
            base = self._pick_template(templates)
            base = base.replace("{character}", character_name)
            base = base.replace("{skill_action}", f"succeeds on the {skill_name} check")
            base = base.replace(
                "{skill_result_description}",
                f"succeeds at {skill_name} (rolled {skill_result.get('roll', 0)} vs DC {skill_result.get('dc', 0)})",
            )
            return base
        else:
            templates = _SKILL_FAILURE
            base = self._pick_template(templates)
            base = base.replace("{character}", character_name)
            base = base.replace("{skill_attempt}", f"{skill_name} check")
            base = base.replace(
                "{failure_reason}",
                f"rolled {skill_result.get('roll', 0)} against DC {skill_result.get('dc', 0)}",
            )
            base = base.replace(
                "{failure_detail}",
                f"rolled {skill_result.get('roll', 0)}, needed {skill_result.get('dc', 0)}",
            )
            return base

    def describe_npc_dialogue(
        self,
        npc_data: dict,
        player_message: str,
    ) -> str:
        """
        Generate placeholder NPC dialogue response.

        This is a template placeholder. In production, the LLM would generate
        the actual dialogue. This method provides structural consistency.

        Args:
            npc_data: Dict with keys {name, personality, speech_pattern, ...}
            player_message: What the player said to the NPC

        Returns:
            Placeholder dialogue string
        """
        npc_name = npc_data.get("name", "The stranger")
        _npc_type = npc_data.get("type", "figure")  # reserved for personality logic

        base = self._pick_template(_DIALOGUE_RESPONSES)
        response = f'"{base}"'

        return f"{npc_name} responds: {response}"

    def _select_template(self, scene_type: SceneType, language: Language) -> str:
        """Select a random template for the given scene type and language."""
        lang_templates = _NARRATIVE_TEMPLATES.get(
            language, _NARRATIVE_TEMPLATES[Language.EN]
        )
        templates = lang_templates.get(
            scene_type, lang_templates.get(SceneType.STORY_BEAT)
        )
        return random.choice(templates)

    def _pick_template(self, templates: list[str]) -> str:
        """Pick a random template from a list."""
        return random.choice(templates)

    def _fill_template(self, template: str, context: dict) -> str:
        """
        Fill in template placeholders with context values.

        Unfilled placeholders are left intact so partial templates
        still render sensibly.
        """
        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def _load_system_prompt(self) -> None:
        """Load system_prompt.md content for reference."""
        if self.SYSTEM_PROMPT_PATH and self.SYSTEM_PROMPT_PATH.exists():
            self._system_prompt = self.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            self._system_prompt = None

    def _generate_with_llm(
        self, scene_type: SceneType, context: dict, language: Language
    ) -> str:
        """
        Use the LLM client to generate a narrative scene.

        Builds a rich DM prompt from context + scene type, then calls the
        configured provider via LLMClient.
        """
        location = context.get("location", "an unknown place")
        characters = context.get("character_present", "The party")
        npcs = context.get("npcs_present", "No NPCs nearby")
        mood = context.get("emotional_tone", "tense")
        recent = context.get("recent_events", "The adventure continues")

        scene_type_str = scene_type.value.lower().replace("_", " ")

        user_prompt = (
            f"You are the Dungeon Master narrating a D&D Fifth Edition game.\n"
            f"Generate a vivid, {mood} narrative for a {scene_type_str} scene.\n\n"
            f"Location: {location}\n"
            f"Characters present: {characters}\n"
            f"NPCs present: {npcs}\n"
            f"Recent events: {recent}\n\n"
            "Requirements:\n"
            "- 2-4 sentences maximum\n"
            "- End with an open SITUATION that invites action (never end with a question mark)\n"
            '- Immersive, second-person perspective ("You notice...", "The air grows cold...")\n'
            "- No dice roll descriptions, no meta-commentary\n"
            "- Directly continue the story\n\n"
            "Narrate:"
        )

        system = (
            "You are Hermes, an expert D&D Fifth Edition Dungeon Master. "
            "You narrate in vivid, cinematic prose. 2-4 sentences. Open ending. Never a question."
        )

        result = self.llm_client.text(
            prompt=user_prompt,
            system=system,
            max_tokens=256,
            temperature=0.8,
        )

        narrative = result.text.strip()

        # Ensure it doesn't end with a question mark
        if narrative.endswith("?"):
            narrative = narrative[:-1] + "."

        return narrative

    def _should_trigger_image(self, scene_type: SceneType, context: dict) -> bool:
        """
        Determine if this scene should trigger an image generation.

        Uses scene type and presence of combatants or story beats.
        """
        if scene_type == SceneType.COMBAT:
            return True
        if scene_type == SceneType.STORY_BEAT:
            return True
        if scene_type == SceneType.EXPLORATION:
            # Trigger on first visit to a location
            return context.get("first_visit", False)
        return False

    def get_system_prompt_excerpt(self, max_chars: int = 500) -> str:
        """
        Return a snippet of the system prompt for injection into prompts.

        Used by the LLM layer to give context about voice, style, and rules.
        """
        if not self._system_prompt:
            return ""
        return (
            self._system_prompt[:max_chars] + "..."
            if len(self._system_prompt) > max_chars
            else self._system_prompt
        )
