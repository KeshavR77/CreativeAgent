"""Text embeddings for the divergence engine (§8.8).

Backend resolves from ``EMBEDDINGS_BACKEND``:
  * unset / ``mock`` / unknown -> deterministic hash-bucket vectors (no deps);
  * ``tfidf``                  -> pure-Python TF-IDF over the batch vocabulary;
  * ``auto`` / ``minilm``      -> lazy-import sentence-transformers MiniLM, and
                                  fall back to TF-IDF on ImportError.

No heavy import at module load — MiniLM is imported only when actually selected,
so the keyless-first boot never pulls torch/sentence-transformers.
"""

from __future__ import annotations

import hashlib
import math

from app.config import get_settings

_HASH_DIM = 64


def _backend() -> str:
    return (get_settings().EMBEDDINGS_BACKEND or "").strip().lower()


def _tokens(text: str) -> list[str]:
    return text.lower().split()


def _hash_vector(text: str, dim: int = _HASH_DIM) -> list[float]:
    """Deterministic bag-of-tokens hashed into ``dim`` buckets (md5, cross-process
    stable — unlike the salted builtin ``hash``)."""
    vec = [0.0] * dim
    for tok in _tokens(text):
        bucket = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % dim
        vec[bucket] += 1.0
    return vec


def _tfidf_vectors(texts: list[str]) -> list[list[float]]:
    docs = [_tokens(t) for t in texts]
    vocab = sorted({w for doc in docs for w in doc})
    index = {w: i for i, w in enumerate(vocab)}
    n_docs = len(docs)
    df = {w: sum(1 for doc in docs if w in doc) for w in vocab}
    vectors: list[list[float]] = []
    for doc in docs:
        vec = [0.0] * len(vocab)
        counts: dict[str, int] = {}
        for w in doc:
            counts[w] = counts.get(w, 0) + 1
        for w, c in counts.items():
            tf = c / len(doc) if doc else 0.0
            idf = math.log((1 + n_docs) / (1 + df[w])) + 1.0
            vec[index[w]] = tf * idf
        vectors.append(vec)
    return vectors


def _minilm_vectors(texts: list[str]) -> list[list[float]]:
    # Lazy import: only reached when EMBEDDINGS_BACKEND selects auto/minilm.
    from sentence_transformers import SentenceTransformer  # noqa: F401

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return [list(map(float, v)) for v in model.encode(texts)]


def embed(texts: list[str]) -> list[list[float]]:
    """Embed each text to a vector. Keyless default is deterministic hash vectors."""
    backend = _backend()
    if backend in ("auto", "minilm"):
        try:
            return _minilm_vectors(texts)
        except ImportError:
            return _tfidf_vectors(texts)
    if backend == "tfidf":
        return _tfidf_vectors(texts)
    return [_hash_vector(t) for t in texts]
