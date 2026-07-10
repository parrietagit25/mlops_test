"""Skill de ejemplo: resumen de texto libre."""

from pydantic import BaseModel, Field

from agents.skills.base import Skill, SkillResult
from core.llm_client import get_llm_client
from prompts.loader import load_prompt


class SummarizerInput(BaseModel):
    text: str = Field(..., min_length=1)
    max_sentences: int = Field(default=3, ge=1, le=10)


class SummarizerSkill(Skill):
    name = "summarizer"
    description = "Resume un texto libre en N oraciones, sin inventar datos."
    input_model = SummarizerInput

    def run(self, payload: SummarizerInput) -> SkillResult:
        llm = get_llm_client()
        prompt = load_prompt(
            "summarizer", text=payload.text, max_sentences=payload.max_sentences
        )
        output = llm.chat(messages=[{"role": "user", "content": prompt}])
        return SkillResult(output=output, metadata={"skill": self.name})
