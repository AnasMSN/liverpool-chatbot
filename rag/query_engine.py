"""
Core RAG logic: embed the user's question, retrieve the most relevant
chunks from ChromaDB, and ask a local Ollama model to answer using only
that retrieved context.
"""

from __future__ import annotations

import os
import chromadb
import ollama
from sentence_transformers import SentenceTransformer

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "chroma_db")
COLLECTION_NAME = "liverpool_fc"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Swap this for "phi4-mini" if you need more VRAM headroom,
# or point ollama.chat at a different host for a bigger/remote model.
LLM_MODEL = "qwen2.5:7b"

TOP_K = 5

SYSTEM_PROMPT = """You are a knowledgeable Liverpool FC assistant.
Answer the user's question using ONLY the context provided below.
If the context doesn't contain the answer, say you don't have that
information rather than guessing. Keep answers concise and factual,
and mention specifics (names, dates, scores) when they're in the context.
"""


class RAGEngine:
    def __init__(self) -> None:
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=DB_DIR)
        self.collection = client.get_collection(COLLECTION_NAME)

    def retrieve(self, question: str, top_k: int = TOP_K) -> list[dict]:
        query_embedding = self.embedder.encode([question]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
        )
        chunks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append({"text": doc, "source": meta.get("source", "unknown")})
        return chunks

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        retrieved = self.retrieve(question)
        context = "\n\n---\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in retrieved
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            }
        )

        response = ollama.chat(model=LLM_MODEL, messages=messages)

        return {
            "answer": response["message"]["content"],
            "sources": sorted({c["source"] for c in retrieved}),
        }


if __name__ == "__main__":
    # quick manual test: python -m rag.query_engine
    engine = RAGEngine()
    result = engine.answer("Who is Liverpool's current manager?")
    print(result["answer"])
    print("\nSources:", result["sources"])
