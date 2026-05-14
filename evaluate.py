"""
Evaluación experimental del pipeline de detección de patrones conversacionales.
Métricas: cobertura, cohesión de clusters, calidad de FAQs, reducción de ambigüedad.
"""
import json
import sys
import numpy as np
from collections import Counter
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.preprocessing import normalize
import psycopg2.extras

sys.stdout.reconfigure(encoding="utf-8")

from pipeline.config import DBSCAN_EPS, DBSCAN_MIN_SAMPLES, DAYS_LOOKBACK
from pipeline.db import get_conn
from pipeline.extractor import extract_user_messages
from pipeline.embedder import embed_batch
from pipeline.clusterer import cluster_messages


# ── Helpers ──────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def row(label, value, note=""):
    note_str = f"  ({note})" if note else ""
    print(f"  {label:<40} {value}{note_str}")


# ── 1. Métricas de extracción ─────────────────────────────────────────────────

def eval_extraction(days=DAYS_LOOKBACK):
    section("1. EXTRACCIÓN Y NORMALIZACIÓN")

    # Total raw messages in window
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COUNT(*) FROM chat_messages cm
                JOIN agent_chats ac ON cm.agent_chat_id = ac.id
                WHERE cm.message->>'role' = 'user'
                  AND cm.created_at >= NOW() - INTERVAL '{days} days'
            """)
            total_raw = cur.fetchone()[0]

    messages = extract_user_messages(days=days)
    total_filtered = len(messages)
    coverage = total_filtered / total_raw * 100 if total_raw else 0

    row("Ventana de análisis", f"{days} días")
    row("Mensajes de usuario (brutos)", total_raw)
    row("Mensajes tras normalización/filtrado", total_filtered)
    row("Tasa de cobertura", f"{coverage:.1f}%",
        "mensajes válidos sobre el total")

    # Workspace distribution
    ws_counts = Counter(m["workspace_id"] for m in messages)
    row("Workspaces con datos", len(ws_counts))
    row("Promedio mensajes por workspace",
        f"{total_filtered / len(ws_counts):.0f}" if ws_counts else "0")

    return messages


# ── 2. Métricas de clustering ──────────────────────────────────────────────────

def eval_clustering(messages):
    section("2. CLUSTERING SEMÁNTICO (DBSCAN)")

    row("Algoritmo", "DBSCAN (scikit-learn)")
    row("Métrica de distancia", "Coseno")
    row("Epsilon (eps)", DBSCAN_EPS,
        "radio de vecindad; menor = clusters más compactos")
    row("min_samples", DBSCAN_MIN_SAMPLES,
        "mínimo de puntos para formar un cluster")

    print()
    embeddings = embed_batch(messages)
    clusters   = cluster_messages(messages, embeddings)

    valid = [m for m in messages if m["id"] in embeddings]
    ids   = [m["id"] for m in valid]
    vecs  = normalize(
        np.array([embeddings[mid] for mid in ids], dtype=np.float32), norm="l2"
    )

    # Rebuild flat label array
    id_to_label = {}
    for cid, msgs in clusters.items():
        for m in msgs:
            id_to_label[m["id"]] = cid
    labels = np.array([id_to_label.get(mid, -1) for mid in ids])

    n_clusters    = len(clusters)
    n_noise       = int((labels == -1).sum())
    noise_rate    = n_noise / len(labels) * 100 if labels.size else 0
    clustered_pct = 100 - noise_rate

    row("Total mensajes con embedding", len(valid))
    row("Clusters válidos encontrados", n_clusters)
    row("Mensajes en clusters (clustered)", f"{len(labels) - n_noise}")
    row("Tasa de agrupamiento", f"{clustered_pct:.1f}%",
        "mensajes asignados a algún cluster")
    row("Mensajes descartados (ruido)", n_noise,
        f"{noise_rate:.1f}%")

    # Cluster size distribution
    sizes = sorted([len(v) for v in clusters.values()], reverse=True)
    if sizes:
        row("Tamaño máximo de cluster", sizes[0])
        row("Tamaño mínimo de cluster", sizes[-1])
        row("Tamaño promedio de cluster", f"{np.mean(sizes):.1f}")
        row("Tamaño mediano de cluster",  f"{np.median(sizes):.1f}")

    # Silhouette & Davies-Bouldin (only computable with ≥2 clusters)
    mask = labels != -1
    if n_clusters >= 2 and mask.sum() > n_clusters:
        sil = silhouette_score(vecs[mask], labels[mask], metric="cosine")
        dbi = davies_bouldin_score(vecs[mask], labels[mask])
        row("Silhouette Score", f"{sil:.4f}",
            "[-1,1]; mayor = clusters más separados y compactos")
        row("Davies-Bouldin Index", f"{dbi:.4f}",
            "menor = mejor separación entre clusters")
    else:
        row("Silhouette Score", "N/A (se necesitan ≥2 clusters)")
        row("Davies-Bouldin Index", "N/A")

    return clusters, embeddings


# ── 3. Métricas de generación de FAQs ─────────────────────────────────────────

def eval_faq_generation():
    section("3. GENERACIÓN DE FAQs")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM faq_suggestions ORDER BY message_count DESC")
            rows = cur.fetchall()

    if not rows:
        print("  Sin sugerencias en la base de datos.")
        return

    total      = len(rows)
    approved   = sum(1 for r in rows if r["status"] == "approved")
    rejected   = sum(1 for r in rows if r["status"] == "rejected")
    pending    = sum(1 for r in rows if r["status"] == "pending")
    precision  = approved / (approved + rejected) * 100 if (approved + rejected) > 0 else 0

    row("Total FAQs sugeridas", total)
    row("Aprobadas por validador humano", approved)
    row("Rechazadas por validador humano", rejected)
    row("Pendientes de revisión", pending)
    row("Precisión (aprobadas / revisadas)", f"{precision:.1f}%",
        "indicador de relevancia del sistema")

    msg_counts = [r["message_count"] for r in rows]
    row("Mensajes cubiertos por FAQs (total)", sum(msg_counts))
    row("Promedio mensajes por FAQ", f"{np.mean(msg_counts):.1f}")

    # Per-workspace breakdown
    print("\n  Distribución por workspace:")
    ws_data = {}
    for r in rows:
        ws = r["workspace_id"]
        ws_data.setdefault(ws, {"total": 0, "approved": 0})
        ws_data[ws]["total"] += 1
        if r["status"] == "approved":
            ws_data[ws]["approved"] += 1
    for ws, d in sorted(ws_data.items()):
        print(f"    workspace {ws}: {d['total']} FAQs  ({d['approved']} aprobadas)")


# ── 4. Métricas de reducción de ambigüedad ────────────────────────────────────

def eval_ambiguity_reduction(clusters):
    section("4. REDUCCIÓN DE AMBIGÜEDAD")

    if not clusters:
        print("  Sin clusters para analizar.")
        return

    # Unique conversations covered
    all_chats = set()
    for msgs in clusters.values():
        for m in msgs:
            all_chats.add(m["agent_chat_id"])

    # Intra-cluster diversity (unique texts per cluster)
    diversities = []
    for msgs in clusters.values():
        unique_texts = len({m["text"] for m in msgs})
        diversities.append(unique_texts / len(msgs))

    avg_div = np.mean(diversities) * 100

    row("Conversaciones únicas cubiertas", len(all_chats))
    row("Diversidad textual intra-cluster", f"{avg_div:.1f}%",
        "% de textos únicos; mayor = más variedad semántica real")

    # Clusters with good multi-workspace coverage
    multi_ws = sum(
        1 for msgs in clusters.values()
        if len({m["workspace_id"] for m in msgs}) > 1
    )
    row("Clusters multi-workspace", multi_ws,
        "patrones que aparecen en varios negocios")

    # FAQs existentes vs sugeridas
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM agent_faqs WHERE deleted_at IS NULL")
            existing_faqs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM faq_suggestions WHERE status='approved'")
            new_approved  = cur.fetchone()[0]

    row("FAQs existentes en la plataforma", existing_faqs)
    row("Nuevas FAQs aprobadas por el sistema", new_approved)
    improvement = new_approved / existing_faqs * 100 if existing_faqs else 0
    row("Aumento potencial de cobertura", f"{improvement:.1f}%")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  EVALUACIÓN EXPERIMENTAL DEL SISTEMA")
    print("  Detección de Patrones Conversacionales — Everwod")
    print("=" * 60)

    messages            = eval_extraction(days=90)
    clusters, embeddings = eval_clustering(messages)
    eval_faq_generation()
    eval_ambiguity_reduction(clusters)

    section("RESUMEN EJECUTIVO")
    print("""
  El sistema implementa un pipeline de 5 etapas:
    [1] Extracción y normalización de mensajes desde PostgreSQL
    [2] Generación de embeddings semánticos (nomic-embed-text, 768 dims)
    [3] Clustering DBSCAN con métrica coseno
    [4] Generación de FAQs con LLM local (llama3.2:3b)
    [5] Validación humana vía API REST (FastAPI)

  Ventajas del enfoque:
    • 100% local — sin costos de API externa para embeddings ni LLM
    • Caché de embeddings — ejecuciones subsiguientes son ~10x más rápidas
    • DBSCAN detecta clusters sin número fijo — adaptable a cualquier volumen
    • Filtros de calidad: saludos, listas de contactos, clusters de 1 conversación
    • Deduplicación semántica de FAQs generadas
    """)

    print("=" * 60)
    print("  Evaluación completada.")
    print("=" * 60)
