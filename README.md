# Liverpool FC RAG Chatbot

A retrieval-augmented chatbot that answers questions about Liverpool FC —
history, players, trophies, and (near-)current stats. Embeddings and the
vector store run locally (or on whatever host runs the app); LLM inference
runs on [Groq](https://groq.com)'s free-tier API, so there's no local GPU
or Ollama install required.

## How it works

```
Wikipedia + Football API data
        │
        ▼
   build_vector_store.py  ──► embeddings (sentence-transformers)
        │
        ▼
   ChromaDB (vector store, committed under data/processed/chroma_db)
        │
        ▼
   query_engine.py  ──► retrieves relevant chunks
        │
        ▼
   Groq API (openai/gpt-oss-120b)  ──► generates the final answer
        │
        ▼
   app.py (Streamlit chat UI)
```

## 1. Prerequisites

- Python 3.10+ (the committed `venv/` here is pinned to 3.9.19 — see
  `CLAUDE.md` for the compatibility gotchas that come with that)
- A free [Groq](https://console.groq.com) account and API key

## 2. Setup

```bash
# clone / cd into this folder
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

pip install -r requirements.txt

# get a free API key from https://console.groq.com/keys and set it
export GROQ_API_KEY="your_key_here"         # Windows: set GROQ_API_KEY=your_key_here

# get a free API key from football-data.org and set it
export FOOTBALL_API_KEY="your_key_here"     # Windows: set FOOTBALL_API_KEY=your_key_here
```

Both keys can instead go in a `.env` file in the repo root:

```
GROQ_API_KEY=your_key_here
FOOTBALL_API_KEY=your_key_here
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

Every page a web search turns up also gets scraped once and cached under
`data/raw/web_cache/` (tracked in `data/processed/web_cache_index.json`),
so the same URL is never fetched twice — a repeat or similar question
reuses the saved page instead of hitting the site (or Tavily) again. Run
`make build-db` periodically to fold those cached pages into the local
vector store permanently, the same as Wikipedia/API data.

Tavily calls are metered against `TAVILY_MONTHLY_LIMIT` (defaults to
1,000, Tavily's free-tier quota) — the sidebar in the app shows a live
used/limit count, and once it's used up the chatbot automatically falls
back to local-only retrieval until the quota resets next month. Bump
`TAVILY_MONTHLY_LIMIT` in `.env` if you upgrade your Tavily plan.

## Deploying (Streamlit Community Cloud)

The app has no local-only dependency left (Groq handles inference over
the network), so it can run on a small free host instead of your own
machine:

1. Push this repo to GitHub (the `data/processed/chroma_db/` and
   `data/raw/` directories are already committed, so the deployed app
   has a working knowledge base out of the box — no build step needed).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and create a new app pointing at this repo's `app.py`.
3. In the app's **Settings → Secrets**, paste:
   ```toml
   GROQ_API_KEY = "your_key_here"
   FOOTBALL_API_KEY = "your_key_here"
   # optional:
   WEB_SEARCH_ENABLED = "true"
   TAVILY_API_KEY = "your_key_here"
   ```
   Root-level keys in Streamlit Cloud's secrets are exposed as real
   environment variables at runtime, so `rag/query_engine.py`'s
   `load_dotenv()` + `os.environ` reads work unchanged — no code
   changes needed to support this.
4. Deploy. Rebuilding the dataset (`make data`) still has to happen on
   a machine that can run the scraper/fetcher — commit the refreshed
   `data/` directory and push to update the deployed app, since
   football fixtures/standings go stale and Streamlit Cloud has no
   built-in scheduler to re-run `fetch_football_api.py` for you.

## Notes on scaling down / up

- **Want a faster/cheaper model?** Swap `LLM_MODEL` in
  `rag/query_engine.py` for `openai/gpt-oss-20b`. Check
  [Groq's deprecations page](https://console.groq.com/docs/deprecations)
  before depending on any model long-term — free-tier models get
  retired on a rolling basis.
- **Want higher quality answers and don't mind an API cost?** Swap the
  Groq call in `rag/query_engine.py` for an Anthropic/OpenAI API call.
  Retrieval logic doesn't need to change at all.

## Legal / scraping etiquette

- Wikipedia content is CC BY-SA — usable with attribution.
- Respect `robots.txt` and rate limits on any site you scrape directly.
- Prefer official APIs (football-data.org, API-Football) over scraping
  live scores/news sites where possible.
