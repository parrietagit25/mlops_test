"""Skill de ejemplo: pregunta-respuesta apoyada en el pipeline de RAG."""

from pydantic import BaseModel, Field

from agents.skills.base import Skill, SkillResult
from core.llm_client import get_llm_client
from prompts.loader import load_prompt
from rag.retriever import retrieve


class RagQAInput(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class RagQASkill(Skill):
    name = "rag_qa"
    description = "Responde preguntas usando el índice RAG local como contexto."
    input_model = RagQAInput

    def run(self, payload: RagQAInput) -> SkillResult:
        chunks = retrieve(payload.question, top_k=payload.top_k)
        if not chunks:
            return SkillResult(
                output="No hay documentos indexados todavía. Ejecuta la ingesta primero.",
                metadata={"skill": self.name, "chunks_used": 0},
            )

        context = "\n---\n".join(c.text for c in chunks)
        llm = get_llm_client()
        prompt = load_prompt("rag_answer", context=context, question=payload.question)
        output = llm.chat(messages=[{"role": "user", "content": prompt}])

        return SkillResult(
            output=output,
            metadata={
                "skill": self.name,
                "chunks_used": len(chunks),
                "sources": [c.source for c in chunks],
            },
        )
