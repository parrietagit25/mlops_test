"""Evaluación mínima del pipeline RAG del laboratorio, usando Ragas 100% local.

Flujo:
1. Toma un set fijo de preguntas de ejemplo (con "ground truth" esperado).
2. Llama al gateway propio (/rag/query y /agents/rag_qa/run) para obtener
   el contexto recuperado y la respuesta generada.
3. Arma un Dataset de HuggingFace en el formato que espera Ragas.
4. Corre las métricas faithfulness, answer_relevancy, context_precision y
   context_recall usando el modelo local (Ollama) como LLM evaluador y como
   modelo de embeddings, vía langchain-openai apuntando al endpoint
   compatible con OpenAI de Ollama.

Nota honesta (ver docs/testing-playbook.md): con un modelo pequeño local
las métricas de Ragas son una señal aproximada, no un ground truth
absoluto. Sirven para detectar regresiones grandes (ej. faithfulness cae de
0.9 a 0.3 tras un cambio de prompt), no para comparar contra benchmarks
publicados con GPT-4.

Ejecutar: scripts/run_ragas.sh
"""

import os

import requests
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

EVAL_SET = [
    {
        "question": "¿Qué se debe hacer antes de integrar un prompt nuevo a un agente?",
        "ground_truth": "Debe pasar al menos un caso de prueba en Promptfoo.",
    },
    {
        "question": "¿Con qué herramienta se debe escanear un modelo de terceros antes de cargarlo?",
        "ground_truth": "Con ModelScan.",
    },
    {
        "question": "¿Dónde corre el laboratorio durante la Fase 1?",
        "ground_truth": "Corre completamente en local, usando Docker Compose.",
    },
]


def build_dataset() -> Dataset:
    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    for item in EVAL_SET:
        query_resp = requests.get(
            f"{API_BASE_URL}/rag/query", params={"q": item["question"], "top_k": 3}, timeout=30
        )
        query_resp.raise_for_status()
        contexts = [r["text"] for r in query_resp.json()["results"]] or ["(sin contexto)"]

        answer_resp = requests.post(
            f"{API_BASE_URL}/agents/rag_qa/run",
            json={"payload": {"question": item["question"], "top_k": 3}},
            timeout=60,
        )
        answer_resp.raise_for_status()
        answer = answer_resp.json()["output"]

        rows["question"].append(item["question"])
        rows["answer"].append(answer)
        rows["contexts"].append(contexts)
        rows["ground_truth"].append(item["ground_truth"])

    return Dataset.from_dict(rows)


def main() -> None:
    dataset = build_dataset()

    llm = ChatOpenAI(
        base_url=f"{OLLAMA_BASE_URL.rstrip('/')}/v1",
        api_key="not-needed",
        model=CHAT_MODEL,
        temperature=0.0,
    )
    embeddings = OpenAIEmbeddings(
        base_url=f"{OLLAMA_BASE_URL.rstrip('/')}/v1",
        api_key="not-needed",
        model=EMBED_MODEL,
    )

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )

    df = result.to_pandas()
    print(df.to_string())
    df.to_csv("evals/ragas/last_run_results.csv", index=False)
    print("\nResultados guardados en evals/ragas/last_run_results.csv")


if __name__ == "__main__":
    main()
