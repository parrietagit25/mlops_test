"""Contrato base para "skills" (capacidades reutilizables de agente).

Diseño e inspiración (patrón, no código):
- Giskard-AI/giskard-skills: idea de unidades de capacidad pequeñas,
  independientes y testeables por separado.
- pydantic-ai: uso de modelos pydantic para tipar entradas/salidas de forma
  estricta en vez de dicts sueltos.
- langchain-ai/langgraph: idea de nodos con un contrato de entrada/salida
  bien definido, componibles en un grafo/flujo mayor.

Nada de código de esos repos fue copiado. Esta es una implementación propia,
deliberadamente pequeña: un ABC con `name`, `description`, `input_model` y
`run()`. No hay orquestador de grafos en la Fase 1 (ver docs/architecture.md,
"qué se deja fuera y por qué") — eso se evalúa para una fase posterior si el
laboratorio lo necesita.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class SkillResult(BaseModel):
    output: str
    metadata: dict = {}


class Skill(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, payload: BaseModel) -> SkillResult:
        """Ejecuta la skill con un payload ya validado por `input_model`."""
        raise NotImplementedError
