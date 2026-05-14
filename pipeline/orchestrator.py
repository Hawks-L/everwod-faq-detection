import json

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from pipeline.db import get_conn, create_faq_suggestions_table
from pipeline.extractor import extract_user_messages
from pipeline.embedder import embed_batch, _embed_single
from pipeline.clusterer import cluster_messages
from pipeline.generator import generate_all_faqs

# FAQs with question cosine similarity above this threshold are considered duplicates
_DEDUP_THRESHOLD = 0.85


def run_pipeline(workspace_id=None, days=None):
    print("\n" + "=" * 55)
    print("  PIPELINE: Detección de Patrones Conversacionales")
    print("=" * 55)

    print("\n[1/5] Preparando base de datos...")
    create_faq_suggestions_table()

    print(f"\n[2/5] Extrayendo mensajes de usuarios...")
    messages = extract_user_messages(workspace_id=workspace_id, days=days)
    print(f"  Mensajes extraídos: {len(messages)}")
    if not messages:
        print("  Sin mensajes para procesar. Pipeline finalizado.")
        return []

    print(f"\n[3/5] Generando embeddings semánticos...")
    embeddings = embed_batch(messages)

    print(f"\n[4/5] Aplicando clustering DBSCAN...")
    clusters = cluster_messages(messages, embeddings)
    if not clusters:
        print("  No se encontraron clusters. Ajusta DBSCAN_EPS o DBSCAN_MIN_SAMPLES.")
        return []

    print(f"\n[5/5] Generando sugerencias de FAQs con LLM...")
    faqs = generate_all_faqs(clusters)

    faqs = _deduplicate_faqs(faqs)

    saved = _save_suggestions(faqs)
    print(f"\n{'=' * 55}")
    print(f"  Pipeline completado: {saved} FAQs guardadas en faq_suggestions.")
    print("=" * 55)
    return faqs


def _deduplicate_faqs(faqs):
    """Remove FAQs whose questions are semantically too similar to each other."""
    if len(faqs) <= 1:
        return faqs

    questions = [f["question"] for f in faqs]
    vectors   = np.array([_embed_single(q) for q in questions], dtype=np.float32)
    vectors   = normalize(vectors, norm="l2")
    sim       = cosine_similarity(vectors)

    keep = []
    dropped_ids = set()
    for i, faq in enumerate(faqs):
        if i in dropped_ids:
            continue
        keep.append(faq)
        for j in range(i + 1, len(faqs)):
            if sim[i, j] >= _DEDUP_THRESHOLD:
                dropped_ids.add(j)

    removed = len(faqs) - len(keep)
    if removed:
        print(f"  FAQs duplicadas eliminadas: {removed}")
    return keep


def _save_suggestions(faqs):
    if not faqs:
        return 0

    sql = """
        INSERT INTO faq_suggestions
            (workspace_id, question, suggested_answer, cluster_id, message_count, sample_messages)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    count = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for faq in faqs:
                cur.execute(sql, (
                    faq["workspace_id"],
                    faq["question"],
                    faq["suggested_answer"],
                    faq["cluster_id"],
                    faq["message_count"],
                    json.dumps(faq["sample_messages"], ensure_ascii=False),
                ))
                count += 1
    return count
