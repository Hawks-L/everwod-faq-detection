import hashlib
import pickle
from pathlib import Path

import requests

from pipeline.config import OLLAMA_URL, EMBED_MODEL

CACHE_FILE = Path("embeddings_cache.pkl")


def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    return {}


def _save_cache(cache):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)


def _embed_single(text, retries=2):
    # Truncate texts that are too long for the model (>2000 chars)
    text = text[:2000]
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            if attempt < retries:
                continue
            raise e


def embed_batch(messages, batch_size=50):
    """Return {message_id: embedding_vector} for all messages."""
    cache = _load_cache()
    results = {}
    pending = []
    skipped = 0

    for msg in messages:
        key = hashlib.md5(msg["text"].encode()).hexdigest()
        if key in cache:
            results[msg["id"]] = cache[key]
        else:
            pending.append((key, msg))

    total = len(pending)
    print(f"  Mensajes a embeber: {total}  |  en caché: {len(messages) - total}")

    for i, (key, msg) in enumerate(pending):
        try:
            emb = _embed_single(msg["text"])
            cache[key] = emb
            results[msg["id"]] = emb
        except Exception:
            skipped += 1

        if (i + 1) % batch_size == 0 or (i + 1) == total:
            _save_cache(cache)
            print(f"  Progreso: {i + 1}/{total}", end="\r")

    if total:
        print()
    if skipped:
        print(f"  Mensajes omitidos por error: {skipped}")

    return results
