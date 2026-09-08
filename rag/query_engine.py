"""
Core RAG logic: embed the user's question, retrieve the most relevant
chunks from ChromaDB, and ask a Groq-hosted LLM to answer using only
that retrieved context.
"""

from __future__ import annotations

import os
import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from .web_search import search_web, web_search_available

load_dotenv()

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "chroma_db")
COLLECTION_NAME = "liverpool_fc"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Free-tier Groq model (30 req/min, 1K req/day as of Sept 2026). Swap for
# "openai/gpt-oss-20b" for faster/cheaper responses at lower quality.
# Check https://console.groq.com/docs/deprecations before relying on a
# model long-term — Groq retires free-tier models on a rolling basis.
LLM_MODEL = "openai/gpt-oss-120b"

TOP_K = 5

SYSTEM_PROMPT = """You are a knowledgeable Liverpool FC assistant.
Answer the user's question using ONLY the context provided below, and use the
conversation history above it to understand what the user means (e.g. a short
follow-up like "not him?" refers back to the previous turn). If the context
doesn't contain the answer, say you don't have that information rather than
guessing. Keep answers concise and factual, and mention specifics (names,
dates, scores) when they're in the context. Some context items are from live
web search and are labeled with a URL as their source — when you use one of
those, cite the URL in your answer.
"""

CONDENSE_PROMPT = """Given the conversation history and a follow-up question,
rewrite the follow-up into a standalone question that captures the user's full
intent, using the history for context. If the follow-up is already standalone,
return it unchanged. Reply with ONLY the rewritten question, nothing else.
"""


class RAGEngine:
    def __init__(self) -> None:
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=DB_DIR)
        self.collection = client.get_collection(COLLECTION_NAME)
        # Reads GROQ_API_KEY from the environment (set via .env locally,
        # or via Streamlit Community Cloud's app secrets when deployed).
        self.llm_client = Groq()

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

    def _condense_question(self, question: str, history: list[dict]) -> str:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        messages = [
            {"role": "system", "content": CONDENSE_PROMPT},
            {
                "role": "user",
                "content": f"Conversation so far:\n{convo}\n\nFollow-up question: {question}",
            },
        ]
        response = self.llm_client.chat.completions.create(model=LLM_MODEL, messages=messages)
        return response.choices[0].message.content.strip()

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        search_question = self._condense_question(question, history) if history else question

        retrieved = self.retrieve(search_question)
        if web_search_available():
            retrieved = retrieved + search_web(search_question)

        context = "\n\n---\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in retrieved
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {search_question}",
            }
        )

        response = self.llm_client.chat.completions.create(model=LLM_MODEL, messages=messages)

        return {
            "answer": response.choices[0].message.content,
            "sources": sorted({c["source"] for c in retrieved}),
        }


if __name__ == "__main__":
    # quick manual test: python -m rag.query_engine
    engine = RAGEngine()
    result = engine.answer("Who is Liverpool's current manager?")
    print(result["answer"])
    print("\nSources:", result["sources"])
