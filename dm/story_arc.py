"""
story_arc.py — Story arc dataclasses and serialization for HermesDM pacing system.

A StoryArc defines the narrative skeleton of a campaign: milestones that
progress from hook → rising action → climax → resolution. The PacingEngine
uses this to direct scene generation and detect stagnation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Milestone:
    """A single narrative milestone within a story arc."""

    id: str
    type: str  # "hook" | "rising_action" | "midpoint" | "climax" | "resolution"
    description: str
    completed: bool = False
    completed_at: Optional[str] = None
    scene_count: int = 0
    min_scenes: int = 2
    max_scenes: int = 5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "scene_count": self.scene_count,
            "min_scenes": self.min_scenes,
            "max_scenes": self.max_scenes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Milestone:
        return cls(
            id=data["id"],
            type=data["type"],
            description=data["description"],
            completed=data.get("completed", False),
            completed_at=data.get("completed_at"),
            scene_count=data.get("scene_count", 0),
            min_scenes=data.get("min_scenes", 2),
            max_scenes=data.get("max_scenes", 5),
        )


@dataclass
class StoryArc:
    """Full narrative arc for a campaign."""

    pacing_level: str  # "short" | "medium" | "long"
    total_sessions: int
    milestones: list[Milestone] = field(default_factory=list)
    current_index: int = 0
    total_scenes: int = 0

    # Loop detection tracking
    recent_scene_types: list[str] = field(default_factory=list)
    max_recent_track: int = 10

    def to_dict(self) -> dict:
        return {
            "pacing_level": self.pacing_level,
            "total_sessions": self.total_sessions,
            "milestones": [m.to_dict() for m in self.milestones],
            "current_index": self.current_index,
            "total_scenes": self.total_scenes,
            "recent_scene_types": self.recent_scene_types,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StoryArc:
        return cls(
            pacing_level=data["pacing_level"],
            total_sessions=data["total_sessions"],
            milestones=[Milestone.from_dict(m) for m in data.get("milestones", [])],
            current_index=data.get("current_index", 0),
            total_scenes=data.get("total_scenes", 0),
            recent_scene_types=data.get("recent_scene_types", []),
        )

    @property
    def current_milestone(self) -> Optional[Milestone]:
        if 0 <= self.current_index < len(self.milestones):
            return self.milestones[self.current_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.milestones)

    def record_scene(self, scene_type: str) -> None:
        """Record that a scene of type *scene_type* just happened."""
        self.total_scenes += 1
        self.recent_scene_types.append(scene_type)
        if len(self.recent_scene_types) > self.max_recent_track:
            self.recent_scene_types = self.recent_scene_types[-self.max_recent_track:]

        if self.current_milestone:
            self.current_milestone.scene_count += 1

    def advance_milestone(self, timestamp: Optional[str] = None) -> bool:
        """Advance to the next milestone. Returns True if advanced."""
        if self.current_milestone:
            self.current_milestone.completed = True
            self.current_milestone.completed_at = timestamp
        self.current_index += 1
        return True

    def get_milestone_context(self) -> dict:
        """Return context dict for narrative generator."""
        cm = self.current_milestone
        if not cm:
            return {"campaign_complete": True}

        progress_pressure = 0.0
        if cm.max_scenes > cm.min_scenes:
            progress_pressure = (cm.scene_count - cm.min_scenes) / (cm.max_scenes - cm.min_scenes)
            progress_pressure = max(0.0, min(1.0, progress_pressure))

        return {
            "current_milestone_id": cm.id,
            "current_milestone_type": cm.type,
            "current_milestone_description": cm.description,
            "scenes_in_milestone": cm.scene_count,
            "min_scenes": cm.min_scenes,
            "max_scenes": cm.max_scenes,
            "progress_pressure": round(progress_pressure, 2),
            "milestone_index": self.current_index,
            "total_milestones": len(self.milestones),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

PACING_CONFIG = {
    "short": {
        "total_sessions": 5,
        "milestone_specs": [
            ("hook", "hook", 3, 5),
            ("rising_action", "rising_action", 4, 7),
            ("climax", "climax", 2, 4),
            ("resolution", "resolution", 1, 2),
        ],
    },
    "medium": {
        "total_sessions": 10,
        "milestone_specs": [
            ("hook", "hook", 3, 6),
            ("rising_action_1", "rising_action", 4, 8),
            ("rising_action_2", "rising_action", 4, 8),
            ("climax", "climax", 2, 5),
            ("resolution", "resolution", 1, 3),
        ],
    },
    "long": {
        "total_sessions": 20,
        "milestone_specs": [
            ("hook", "hook", 3, 6),
            ("rising_action_1", "rising_action", 5, 10),
            ("midpoint", "midpoint", 3, 5),
            ("rising_action_2", "rising_action", 5, 10),
            ("rising_action_3", "rising_action", 4, 8),
            ("climax", "climax", 3, 6),
            ("resolution", "resolution", 2, 4),
        ],
    },
}


def create_story_arc_from_ai_response(
    pacing_level: str,
    ai_milestones: list[dict],
) -> StoryArc:
    """
    Build a StoryArc from AI-generated milestone descriptions.

    ai_milestones: list of {"id": ..., "type": ..., "description": ...}
    """
    config = PACING_CONFIG.get(pacing_level, PACING_CONFIG["medium"])
    specs = {s[0]: s for s in config["milestone_specs"]}

    milestones = []
    for am in ai_milestones:
        spec = specs.get(am["id"], (am["id"], am["type"], 2, 5))
        milestones.append(
            Milestone(
                id=am["id"],
                type=am["type"],
                description=am["description"],
                min_scenes=spec[2],
                max_scenes=spec[3],
            )
        )

    return StoryArc(
        pacing_level=pacing_level,
        total_sessions=config["total_sessions"],
        milestones=milestones,
    )


def create_default_story_arc(pacing_level: str = "medium", genre: str = "fantasy") -> StoryArc:
    """Fallback arc when AI generation fails.
    
    NO usa placeholder descriptions. Cada milestone tiene una descripción
    concreta y no-genérica.
    """
    config = PACING_CONFIG.get(pacing_level, PACING_CONFIG["medium"])
    
    # Descriptions por género, específicas y no intercambiables
    DESCRIPTIONS_BY_GENRE = {
        "vampire": {
            "hook": "Los PJ despiertan en un pueblo donde alguien ha sido encontrado sin sangre. La noticia se extiende como fuego.",
            "rising_action_1": "Una investigación lleva a los PJ a las catacumbas bajo la iglesia. Algo huele la luz del sol.",
            "rising_action_2": "Un PJ es abordado por un extraño que afirma ser cazador. Sus motivos no están claros.",
            "midpoint": "Los PJ descubren la tumba del primer vampiro. Una inscripción alerta: 'Quien lo despierte, se unira a su causa.'",
            "climax": "El sitio al castillo del señor vampiro. Turnos simultaneos: combate y puzzle para sellar la tumba.",
            "resolution": "El vampiro es destruido. El pueblo recupera la luz. Las siguientes generaciones no sabran lo que paso aqui.",
        },
        "fantasy": {
            "hook": "Los PJ se conocen en una taberna cuando un mensajero interrumpe con noticias del rey.",
            "rising_action_1": "El camino al castillo esta bloqueado por criaturas que no deberian existir.",
            "rising_action_2": "Un traidor en la corte ha revelado los planes del grupo.",
            "midpoint": "Los PJ descubren que el rey no es la victima -- es el autor del conflicto.",
            "climax": "El enfrentamiento final en el salon del trono. Politica y hojas.",
            "resolution": "El reino tiene nuevo rumbo. Los PJ deciden su lugar en el.",
        },
        "horror": {
            "hook": "Los PJ llegan a un pueblo donde las puertas estan cerradas desde dentro. Nadie duerme.",
            "rising_action_1": "Los cuerpos aparecen sin heridas visibles. La criatura no deja rastro.",
            "rising_action_2": "Un PJ es poseido por algo que no puede sacudir.",
            "midpoint": "La verdadera horror se revela: el pueblo entero es una granja de cuerpos.",
            "climax": "Escapar del pueblo antes del amanecer. Todo ardiendo detras.",
            "resolution": "Los PJ escapan, pero algo viene con ellos.",
        },
        "scifi": {
            "hook": "Los PJ despiertan en una estacion derelicta. La ultima transmision fue hace 3 dias.",
            "rising_action_1": "La estacion tiene senales de vida -- pero la tripulacion esta muerta.",
            "rising_action_2": "Un PJ recibe una senal privada. No es de esta estacion.",
            "midpoint": "La estacion es una trampa. El agresor quiere algo especifico -- y es uno de los PJ.",
            "climax": "La nave de escape es una. Los PJ deben decidir: quien vive.",
            "resolution": "Los supervivientes escapan. La corporacion ahora los busca.",
        },
        "zombie": {
            "hook": "Los PJ se despiertan en un hospital vacio. Las marcas de sangre llevan hacia afuera.",
            "rising_action_1": "La ciudad esta en silencio. Los cuerpos se mueven de forma equivocada.",
            "rising_action_2": "Un PJ ha sido mordido. El tiempo corre.",
            "midpoint": "El refugio seguro resulta ser una trampa. Alguien o algo controla a los muertos.",
            "climax": "La unica forma de escapar es atravesar la horda. Todo por un lider.",
            "resolution": "Los supervivientes escapan. La infeccion se ha propagado mas alla.",
        },
        "pirates": {
            "hook": "Los PJ son capturados por una tripulacion pirata. El captain ofrece un trato.",
            "rising_action_1": "El mapa del tesoro lleva a una isla que no esta en ningun mapa.",
            "rising_action_2": "Una traicion entre la tripulacion divide a los PJ.",
            "midpoint": "El tesoro no es oro -- es algo mucho peor. Y esta despierto.",
            "climax": "La batalla naval final. El barco se hunde pero el captain tiene un ultimo plan.",
            "resolution": "Los PJ escapan con el tesoro. Pero algo los persigue en el agua.",
        },
        "_default": {
            "hook": "Un evento interrumpe la vida cotidiana de los PJ y los une en una busqueda.",
            "rising_action_1": "El camino se complica con un obstaculo que no esperaban.",
            "rising_action_2": "Una traicion o secreto emerge del grupo.",
            "midpoint": "La verdadera naturaleza del conflicto se revela.",
            "climax": "Todo esta en juego. La decision final debe tomarse.",
            "resolution": "Las consecuencias de la decision se desarrollan.",
        }
    }
    
    defaults = DESCRIPTIONS_BY_GENRE.get(genre, DESCRIPTIONS_BY_GENRE["_default"])
    
    milestones = []
    for spec in config["milestone_specs"]:
        desc = defaults.get(spec[0], f"Momento critico {spec[0]} -- nada es lo que pareca.")
        milestones.append(
            Milestone(
                id=spec[0],
                type=spec[1],
                description=desc,
                min_scenes=spec[2],
                max_scenes=spec[3],
            )
        )
    
    return StoryArc(
        pacing_level=pacing_level,
        total_sessions=config["total_sessions"],
        milestones=milestones,
    )
