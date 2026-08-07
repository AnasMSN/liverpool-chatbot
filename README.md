# Liverpool FC RAG Chatbot

A local, retrieval-augmented chatbot that answers questions about Liverpool FC —
history, players, trophies, and (near-)current stats — designed to run entirely
on a single PC with an 8GB GPU.

## How it works

```
Wikipedia + Football API data
        │
        ▼
   chunk_and_embed.py  ──► embeddings (sentence-transformers)
        │
        ▼
   ChromaDB (local vector store)
        │
        ▼
   query_engine.py  ──► retrieves relevant chunks
        │
        ▼
   Ollama (Qwen 3.5 9B, Q4_K_M)  ──► generates the final answer
        │
        ▼
   app.py (Streamlit chat UI)
```

## 1. Prerequisites

- Python 3.10+
- An NVIDIA GPU with 8GB VRAM (CPU-only also works, just slower)
- [Ollama](https://ollama.com) installed

## 2. Setup

```bash
# clone / cd into this folder
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

pip install -r requirements.txt

# pull the local LLM (about 6.6GB on disk)
ollama pull qwen2.5:7b          # or qwen3.5:9b if available on your Ollama version

# get a free API key from football-data.org and set it
export FOOTBALL_API_KEY="your_key_here"     # Windows: set FOOTBALL_API_KEY=your_key_here
```

## 3. Build the dataset

```bash
# pulls history/player/club pages from Wikipedia
python scripts/scrape_wikipedia.py

# pulls recent fixtures, results, standings from football-data.org
python scripts/fetch_football_api.py

# chunks everything and builds the local Chroma vector store
python scripts/build_vector_store.py
```

This populates `data/raw/` (source text) and `data/processed/chroma_db/`
(the vector index the chatbot queries at runtime).

## 4. Run the chatbot

```bash
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

## 5. Re-running to keep data fresh

Football data goes stale fast. Re-run `fetch_football_api.py` and
`build_vector_store.py` (e.g., daily via cron / Task Scheduler) to keep
fixtures and standings current. Wikipedia content changes slowly, so
re-scraping weekly is plenty.

## 6. Optional: live web search citations

By default the chatbot only answers from the local dataset. To let it also
pull in fresh web results (cited by URL) via the [Tavily](https://tavily.com)
API (free tier: 1,000 searches/month):

```bash
# in .env
WEB_SEARCH_ENABLED=true
TAVILY_API_KEY=your_key_here
```

Set `WEB_SEARCH_ENABLED=false` (or leave `TAVILY_API_KEY` empty) to turn it
back off — the chatbot silently falls back to local-only retrieval.

After changing `.env`, restart the app (`Ctrl+C`, then `streamlit run
app.py` again) — Streamlit doesn't reload `.env` on its own for a
running session.

## Notes on scaling down / up

- **Less VRAM headroom?** Swap the model in `rag/query_engine.py` for
  `phi4-mini` (~3.5GB) — small quality tradeoff, much more headroom.
- **Want higher quality answers and don't mind an API cost?** Swap the
  Ollama call in `rag/query_engine.py` for an Anthropic/OpenAI API call.
  Retrieval logic doesn't need to change at all.

## Legal / scraping etiquette

- Wikipedia content is CC BY-SA — usable with attribution.
- Respect `robots.txt` and rate limits on any site you scrape directly.
- Prefer official APIs (football-data.org, API-Football) over scraping
  live scores/news sites where possible.
