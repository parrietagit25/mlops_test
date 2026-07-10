"""Runtime mínimo de agentes: registro y ejecución de skills por nombre.

No es un orquestador de grafos ni un planner multi-paso (eso queda fuera de
la Fase 1, ver docs/architecture.md). Es, a propósito, lo más simple que
puede llamarse "runtime de agentes": un registro + validación de entrada +
ejecución + metadata de resultado. Referencia (dict de string -> objeto),
inspirado en el registro de tools/skills que usan pydantic-ai y LangGraph a
alto nivel, sin reutilizar su código.
"""

from pydantic import ValidationError

from agents.skills.base import Skill, SkillResult
from agents.skills.rag_qa_skill import RagQASkill
from agents.skills.summarizer_skill import SummarizerSkill


class SkillNotFoundError(Exception):
    pass


class AgentRuntime:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        for skill in (SummarizerSkill(), RagQASkill()):
            self.register(skill)

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def list_skills(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    def run_skill(self, name: str, raw_payload: dict) -> SkillResult:
        if name not in self._skills:
            raise SkillNotFoundError(f"Skill '{name}' no registrada.")
        skill = self._skills[name]
        try:
            payload = skill.input_model(**raw_payload)
        except ValidationError as exc:
            raise ValueError(f"Payload inválido para skill '{name}': {exc}") from exc
        return skill.run(payload)


_runtime: AgentRuntime | None = None


def get_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime
