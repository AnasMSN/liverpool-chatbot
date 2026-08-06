"""
Reads every .txt file under data/raw/, splits it into overlapping chunks,
embeds each chunk with a local sentence-transformers model, and stores
everything in a local ChromaDB collection at data/processed/chroma_db.

Run this after scrape_wikipedia.py and fetch_football_api.py, and again
any time the raw data changes.
"""

import os
import glob
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "chroma_db")
COLLECTION_NAME = "liverpool_fc"

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 150    # characters of overlap between consecutive chunks

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # small, fast, runs fine on CPU or 8GB GPU


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def load_documents() -> list[dict]:
    docs = []
    for path in glob.glob(os.path.join(RAW_DIR, "**", "*.txt"), recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        docs.append({"source": os.path.relpath(path, RAW_DIR), "text": text})
    return docs


def main() -> None:
    print("Loading raw documents...")
    documents = load_documents()
    if not documents:
        raise SystemExit(
            "No .txt files found in data/raw/. Run scrape_wikipedia.py and "
            "fetch_football_api.py first."
        )
    print(f"  found {len(documents)} source files")

    print(f"Loading embedding model '{EMBEDDING_MODEL}'...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Chunking documents...")
    all_chunks, all_ids, all_metadatas = [], [], []
    for doc_idx, doc in enumerate(documents):
        chunks = chunk_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)
        for chunk_idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"doc{doc_idx}_chunk{chunk_idx}")
            all_metadatas.append({"source": doc["source"]})
    print(f"  produced {len(all_chunks)} chunks")

    print("Embedding chunks (this may take a minute)...")
    embeddings = model.encode(all_chunks, show_progress_bar=True, batch_size=32).tolist()

    print("Writing to local ChromaDB...")
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)

    # Start fresh each build so stale chunks don't linger
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    batch = 500
    for i in tqdm(range(0, len(all_chunks), batch)):
        collection.add(
            ids=all_ids[i:i + batch],
            embeddings=embeddings[i:i + batch],
            documents=all_chunks[i:i + batch],
            metadatas=all_metadatas[i:i + batch],
        )

    print(f"\nDone. Vector store saved to: {os.path.abspath(DB_DIR)}")
    print(f"Total chunks indexed: {len(all_chunks)}")


if __name__ == "__main__":
    main()
