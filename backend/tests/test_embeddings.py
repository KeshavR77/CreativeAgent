"""Embeddings service tests.

Keyless default is deterministic mock hash-vectors (no heavy deps). The TF-IDF
backend is pure-Python; the `auto`/`minilm` backend lazy-imports
sentence-transformers and falls back to TF-IDF when it is absent (it is, here).
"""

from __future__ import annotations

from app.services.embeddings import embed


def test_mock_embeddings_deterministic(clean_env) -> None:
    assert embed(["sustainable running shoe"]) == embed(["sustainable running shoe"])


def test_mock_embeddings_distinguish_texts(clean_env) -> None:
    (a,) = embed(["alpha beta gamma"])
    (b,) = embed(["delta epsilon zeta"])
    assert a != b


def test_mock_embeddings_shape(clean_env) -> None:
    vecs = embed(["one two", "three four", "five six"])
    assert len(vecs) == 3
    assert all(isinstance(x, float) for x in vecs[0])


def test_tfidf_backend_is_pure_python(clean_env) -> None:
    clean_env.setenv("EMBEDDINGS_BACKEND", "tfidf")
    vecs = embed(["red shoe", "blue shoe"])
    assert len(vecs) == 2
    assert vecs[0] != vecs[1]
    # deterministic
    assert embed(["red shoe", "blue shoe"]) == vecs


def test_auto_falls_back_to_tfidf_when_minilm_absent(clean_env) -> None:
    # sentence-transformers is not installed -> ImportError -> TF-IDF, never raises.
    clean_env.setenv("EMBEDDINGS_BACKEND", "auto")
    vecs = embed(["earthy grounded", "sleek chrome"])
    assert len(vecs) == 2
