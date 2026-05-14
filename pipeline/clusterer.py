import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize

from pipeline.config import DBSCAN_EPS, DBSCAN_MIN_SAMPLES


def cluster_messages(messages, embeddings_map):
    """
    Group messages by semantic similarity using DBSCAN.
    Returns {cluster_id: [message_dicts]}.
    """
    # Keep only messages that have an embedding
    valid = [m for m in messages if m["id"] in embeddings_map]
    if not valid:
        return {}

    ids     = [m["id"] for m in valid]
    vectors = np.array([embeddings_map[mid] for mid in ids], dtype=np.float32)

    # L2-normalize so cosine distance = euclidean on unit sphere
    vectors_norm = normalize(vectors, norm="l2")

    labels = DBSCAN(
        eps=DBSCAN_EPS,
        min_samples=DBSCAN_MIN_SAMPLES,
        metric="cosine",
        n_jobs=-1,
    ).fit_predict(vectors_norm)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise    = int((labels == -1).sum())
    print(f"  Clusters detectados: {n_clusters}  |  mensajes descartados (ruido): {n_noise}")

    msg_by_id = {m["id"]: m for m in valid}
    clusters: dict[int, list] = {}
    for mid, label in zip(ids, labels):
        if label == -1:
            continue
        clusters.setdefault(int(label), []).append(msg_by_id[mid])

    # Drop clusters where all messages come from a single conversation
    # (one user repeating the same message, not a real pattern)
    before = len(clusters)
    clusters = {
        cid: msgs for cid, msgs in clusters.items()
        if len({m["agent_chat_id"] for m in msgs}) >= 2
    }
    dropped = before - len(clusters)
    if dropped:
        print(f"  Clusters de conversación única descartados: {dropped}")

    return clusters
