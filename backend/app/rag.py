"""
Step 1b — Retrieval-Augmented Generation (RAG) store
Embeds chunks with a local sentence-transformer model and stores them
in a local Chroma vector database, one collection per uploaded document set.
"""

from __future__ import annotations
from typing import List, Optional
import chromadb
from chromadb.utils import embedding_functions

from .ingestion import Chunk

# All-MiniLM is small, fast, free, and good enough for lesson-material retrieval.
_EMBED_MODEL = "all-MiniLM-L6-v2"

_client = chromadb.PersistentClient(path="./data/chroma")
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=_EMBED_MODEL
)


class MaterialStore:
    """
    Wraps a Chroma collection for one learning-material set
    (e.g. everything a student uploaded for a single session).
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.collection = _client.get_or_create_collection(
            name=f"session_{session_id}",
            embedding_function=_embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: List[Chunk]) -> int:
        if not chunks:
            return 0
        self.collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "location": c.location} for c in chunks],
        )
        return len(chunks)

    def retrieve(self, query: str, k: int = 5) -> List[dict]:
        """
        Return the top-k most relevant chunks for a query, each with
        its source/location so the teacher can ground and cite explanations.
        """
        if self.collection.count() == 0:
            return []
        results = self.collection.query(query_texts=[query], n_results=min(k, self.collection.count()))
        out = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            out.append({
                "text": doc,
                "source": meta["source"],
                "location": meta["location"],
                "relevance": round(1 - dist, 3),  # cosine similarity
            })
        return out

    def has_material(self) -> bool:
        return self.collection.count() > 0

    def clear(self):
        _client.delete_collection(name=f"session_{self.session_id}")
