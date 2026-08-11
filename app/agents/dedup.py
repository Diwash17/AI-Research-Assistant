# app/agents/dedup.py
import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.schemas.models import Finding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 0.92  # findings above this cosine similarity are duplicates

_EMBEDDING_MODEL = "gemini-embedding-001"

# Module-level embedder — one instance, picks up GOOGLE_API_KEY from env
# (already loaded by app.config at startup).
_embedder = GoogleGenerativeAIEmbeddings(model=_EMBEDDING_MODEL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Return an (N x N) cosine-similarity matrix for *vectors* (N x D).

    Each row is L2-normalised first so the dot product equals cosine similarity.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # Avoid division by zero for zero-length vectors
    norms = np.where(norms == 0, 1.0, norms)
    normalised = vectors / norms
    return normalised @ normalised.T  # shape (N, N)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dedup_findings(findings: list[Finding]) -> list[Finding]:
    """Return *findings* with near-duplicate entries removed.

    Strategy
    --------
    1. Embed all finding contents in a single batched API call.
    2. Build an (N x N) cosine-similarity matrix with numpy.
    3. Walk findings in order; keep a finding only if it has cosine similarity
       ≤ SIMILARITY_THRESHOLD with every already-kept finding.  This preserves
       the original insertion order and keeps the *first* occurrence of any
       near-duplicate cluster.

    Parameters
    ----------
    findings:
        Raw (possibly duplicate) findings from the researcher step.

    Returns
    -------
    list[Finding]
        Deduplicated findings in their original relative order.
    """
    if len(findings) <= 1:
        return list(findings)

    texts = [f.content for f in findings]

    # One batched call — GoogleGenerativeAIEmbeddings.embed_documents accepts a list
    raw_embeddings: list[list[float]] = _embedder.embed_documents(texts)
    vectors = np.array(raw_embeddings, dtype=np.float32)  # shape (N, D)

    sim_matrix = _cosine_similarity_matrix(vectors)  # shape (N, N)

    kept_indices: list[int] = []

    for i in range(len(findings)):
        is_duplicate = False
        for j in kept_indices:
            if sim_matrix[i, j] > SIMILARITY_THRESHOLD:
                is_duplicate = True
                break
        if not is_duplicate:
            kept_indices.append(i)

    return [findings[i] for i in kept_indices]
