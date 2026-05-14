import json
import re
import time

import requests

from pipeline.config import OLLAMA_URL, LLM_MODEL, MAX_MESSAGES_PER_CLUSTER, LLM_TIMEOUT, LLM_RETRIES

_PROMPT = """Eres un asistente experto en atención al cliente para negocios latinoamericanos.
Analiza los siguientes mensajes reales enviados por clientes via WhatsApp y genera una pregunta frecuente (FAQ).

Mensajes de clientes:
{messages}

Instrucciones:
1. Identifica el tema o consulta común entre los mensajes.
2. Formula UNA pregunta canónica clara y concisa en español.
3. Redacta una respuesta útil y genérica (sin datos específicos del negocio).

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional:
{{"question": "¿Pregunta aquí?", "answer": "Respuesta aquí."}}"""


def _call_llm(prompt):
    last_exc = None
    for attempt in range(1, LLM_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=LLM_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < LLM_RETRIES:
                wait = 5 * attempt
                print(f"[reintento {attempt}/{LLM_RETRIES} en {wait}s]", end=" ")
                time.sleep(wait)
    raise last_exc


def _parse_json(raw):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def generate_faq_for_cluster(cluster_messages):
    sample = cluster_messages[:MAX_MESSAGES_PER_CLUSTER]
    bullet_list = "\n".join(f"- {m['text']}" for m in sample)
    prompt = _PROMPT.format(messages=bullet_list)
    raw = _call_llm(prompt)
    return _parse_json(raw)


def generate_all_faqs(clusters):
    faqs = []
    total = len(clusters)

    for i, (cluster_id, msgs) in enumerate(clusters.items(), 1):
        print(f"  FAQ {i}/{total}  (cluster {cluster_id}, {len(msgs)} mensajes)...", end=" ")

        # Dominant workspace_id in this cluster
        ws_counts: dict = {}
        for m in msgs:
            ws_counts[m["workspace_id"]] = ws_counts.get(m["workspace_id"], 0) + 1
        workspace_id = max(ws_counts, key=ws_counts.get)

        try:
            result = generate_faq_for_cluster(msgs)
        except Exception as exc:
            print(f"ERROR ({type(exc).__name__}) — cluster omitido")
            continue

        if result and result.get("question"):
            faqs.append({
                "workspace_id":    workspace_id,
                "cluster_id":      cluster_id,
                "question":        result["question"],
                "suggested_answer": result.get("answer", ""),
                "message_count":   len(msgs),
                "sample_messages": [m["text"] for m in msgs[:5]],
            })
            print("OK")
        else:
            print("sin resultado")

    return faqs
