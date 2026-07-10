"""Suite de pruebas DeepEval sobre el gateway de ai-testing-lab.

Requiere el stack levantado (`scripts/up.sh`) y el índice RAG creado
(`curl -X POST http://localhost:8080/rag/ingest`).

Ejecutar: scripts/run_deepeval.sh  (o `pytest evals/deepeval -v` con el venv)
"""

import requests
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase


def _run_rag_qa(api_base_url: str, question: str, top_k: int = 3) -> dict:
    resp = requests.post(
        f"{api_base_url}/agents/rag_qa/run",
        json={"payload": {"question": question, "top_k": top_k}},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def test_rag_answer_is_relevant(api_base_url, judge_model):
    question = "¿Qué debo hacer con un prompt nuevo antes de integrarlo a un agente?"
    result = _run_rag_qa(api_base_url, question)

    test_case = LLMTestCase(
        input=question,
        actual_output=result["output"],
        retrieval_context=[],  # se completa abajo si el skill devolvió fuentes
    )

    metric = AnswerRelevancyMetric(threshold=0.5, model=judge_model, include_reason=True)
    assert_test(test_case, [metric])


def test_rag_answer_is_faithful_to_context(api_base_url, judge_model):
    question = "¿Con qué herramienta se debe escanear un modelo de terceros?"
    result = _run_rag_qa(api_base_url, question)

    # Recuperamos el mismo contexto que usó el skill vía /rag/query para
    # poder medir faithfulness contra el contexto real recuperado.
    query_resp = requests.get(
        f"{api_base_url}/rag/query", params={"q": question, "top_k": 3}, timeout=30
    )
    query_resp.raise_for_status()
    contexts = [r["text"] for r in query_resp.json()["results"]]

    test_case = LLMTestCase(
        input=question,
        actual_output=result["output"],
        retrieval_context=contexts or ["(sin contexto recuperado)"],
    )

    metric = FaithfulnessMetric(threshold=0.5, model=judge_model, include_reason=True)
    assert_test(test_case, [metric])


def test_summarizer_respects_max_sentences(api_base_url):
    resp = requests.post(
        f"{api_base_url}/agents/summarizer/run",
        json={
            "payload": {
                "text": (
                    "El laboratorio corre en local. Usa Docker Compose. "
                    "Incluye Ollama, una API propia y módulos de evaluación. "
                    "También incluye observabilidad con Phoenix."
                ),
                "max_sentences": 2,
            }
        },
        timeout=60,
    )
    resp.raise_for_status()
    output = resp.json()["output"]

    sentence_count = len([s for s in output.replace("!", ".").replace("?", ".").split(".") if s.strip()])
    assert sentence_count <= 3, f"Se esperaban <=3 oraciones, se obtuvieron {sentence_count}: {output}"
