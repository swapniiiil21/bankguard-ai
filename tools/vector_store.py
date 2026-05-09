"""
tools/vector_store.py
Pinecone vector store — init, upsert, and similarity query.
Uses HuggingFace sentence-transformers for embeddings.
"""

import logging
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_HOST = os.getenv("PINECONE_HOST", "")        # e.g. https://name-xxx.svc.xxx.pinecone.io
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1-aws")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "bankguard-fraud-cases")
HF_MODEL = os.getenv("HUGGINGFACE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_embedding_model():
    """Lazy-load the sentence transformer (heavy import, cache it)."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    logger.info("Loading embedding model: %s", HF_MODEL)
    return SentenceTransformer(HF_MODEL)


def embed_text(text: str) -> list[float]:
    """Encode text to a dense vector using the HuggingFace model."""
    model = _get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


# ---------------------------------------------------------------------------
# Pinecone client
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_pinecone_index():
    """Initialize Pinecone and return the target index object.

    Connection priority:
    1. Host URL (PINECONE_HOST) — fastest; works even without a full API key
       by calling pc.Index(host=...) directly.
    2. Index name lookup via PINECONE_API_KEY — creates the index if absent.
    """
    try:
        from pinecone import Pinecone, ServerlessSpec  # noqa: PLC0415

        if not PINECONE_API_KEY or PINECONE_API_KEY.startswith("your_"):
            # No API key — skip gracefully
            logger.warning("PINECONE_API_KEY not set — vector store disabled.")
            return None

        pc = Pinecone(api_key=PINECONE_API_KEY)

        # ── Prefer direct host connection (no list_indexes() call needed) ──
        if PINECONE_HOST:
            logger.info("Connecting to Pinecone index via host: %s", PINECONE_HOST)
            return pc.Index(host=PINECONE_HOST)

        # ── Fallback: look up by name, create if missing ──────────────────
        existing = [idx.name for idx in pc.list_indexes()]
        if PINECONE_INDEX not in existing:
            logger.info("Creating Pinecone index: %s", PINECONE_INDEX)
            pc.create_index(
                name=PINECONE_INDEX,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        return pc.Index(PINECONE_INDEX)
    except Exception as exc:
        logger.error("Pinecone init failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def upsert_case(case_id: str, case_summary: str, metadata: dict[str, Any]) -> bool:
    """
    Embed a fraud case summary and upsert it into Pinecone.

    Args:
        case_id: Unique identifier for the case.
        case_summary: Plain-text description of the fraud case.
        metadata: Additional fields (name, dob, recommendation, etc.).

    Returns:
        True if successful, False otherwise.
    """
    index = _get_pinecone_index()
    if index is None:
        logger.warning("Pinecone unavailable — skipping upsert for case %s", case_id)
        return False

    try:
        vector = embed_text(case_summary)
        index.upsert(vectors=[{"id": case_id, "values": vector, "metadata": metadata}])
        logger.info("Upserted case %s to Pinecone.", case_id)
        return True
    except Exception as exc:
        logger.error("Pinecone upsert failed: %s", exc)
        return False


def query_similar_cases(
    query_text: str,
    top_k: int = 5,
    score_threshold: float = 0.70,
) -> list[dict[str, Any]]:
    """
    Query Pinecone for fraud cases similar to query_text.

    Returns:
        List of dicts with keys: id, score, metadata.
    """
    index = _get_pinecone_index()
    if index is None:
        logger.warning("Pinecone unavailable — returning empty similar cases.")
        return []

    try:
        vector = embed_text(query_text)
        results = index.query(vector=vector, top_k=top_k, include_metadata=True)
        matches = [
            {"id": m["id"], "score": round(m["score"], 4), "metadata": m.get("metadata", {})}
            for m in results.get("matches", [])
            if m["score"] >= score_threshold
        ]
        return matches
    except Exception as exc:
        logger.error("Pinecone query failed: %s", exc)
        return []
