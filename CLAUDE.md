# Liverpool FC RAG Chatbot — repo context

Local, retrieval-augmented chatbot answering questions about Liverpool FC
(history, players, trophies, near-current fixtures/standings). Everything
runs on-machine: local embeddings, local vector store, local LLM via Ollama.

## Pipeline

```
scripts/scrape_wikipedia.py     -> data/raw/wikipedia/*.txt
scripts/fetch_football_api.py   -> data/raw/football_api/*.txt
                                        |
                                        v
scripts/build_vector_store.py   -> data/processed/chroma_db/  (ChromaDB, collection "liverpool_fc")
                                        |
                                        v
rag/query_engine.py (RAGEngine) -> embeds question, retrieves top-k chunks, asks Ollama
                                        |
                                        v
app.py                          -> Streamlit chat UI, holds st.session_state.messages
```

Run the whole thing with `make all` (see `Makefile`), or step by step with
`make scrape`, `make fetch`, `make build-db`, `make run`.

## Key files

- **`rag/query_engine.py`** — the entire RAG logic lives here.
  - `RAGEngine.__init__`: loads `sentence-transformers` model
    (`all-MiniLM-L6-v2`) and opens the ChromaDB collection.
  - `RAGEngine.retrieve(question)`: embeds `question` and does a top-`TOP_K`
    (5) similarity query against ChromaDB.
  - `RAGEngine._condense_question(question, history)`: when there's chat
    history, asks the LLM to rewrite a short follow-up (e.g. "not mo
    salah?") into a standalone question *before* retrieval. Without this,
    follow-ups embed poorly and retrieve the wrong/irrelevant chunks.
  - `RAGEngine.answer(question, history)`: condenses (if history present),
    retrieves from ChromaDB, optionally appends live web results (see
    below), builds a `Context:\n...\n\nQuestion: ...` user message, sends
    `[system, *history, user]` to `ollama.chat(model=LLM_MODEL, ...)`.
  - `SYSTEM_PROMPT`: instructs the model to answer only from retrieved
    context but also to use chat history to interpret intent, and to cite
    URLs when a context item came from web search. `LLM_MODEL =
    "qwen2.5:7b"` — swap to `phi4-mini` for less VRAM, or swap the
    `ollama.chat` call for an Anthropic/OpenAI call if you don't mind API
    cost (retrieval logic doesn't need to change).
- **`rag/web_search.py`** — optional live web search via the
  [Tavily](https://tavily.com) API (free tier: 1,000 searches/month),
  gated by two env vars:
  - `WEB_SEARCH_ENABLED=true|false` — the on/off switch.
  - `TAVILY_API_KEY=...` — from https://app.tavily.com.
  When both are set, `RAGEngine.answer()` runs `search_web()` on the
  (condensed) question and appends `{"text": content, "source": url}`
  results to the local ChromaDB chunks before building context — so the
  model can cite a real URL instead of only local filenames. Any failure
  (missing key, network error, rate limit) is caught and logged, falling
  back to local-only retrieval rather than crashing the answer. `sources`
  in the returned dict will contain a mix of local paths and URLs;
  `app.py` renders them with `st.markdown` so URLs show as clickable
  links. `rag/query_engine.py` calls `load_dotenv()` at import time so
  these flags reach `os.environ` under `streamlit run app.py` too (see
  gotcha below).
- **`rag/web_cache.py`** — every URL that `web_search.py` gets back from
  Tavily is scraped (via `requests` + `BeautifulSoup`, stripping
  script/style/nav/footer/header) and saved as a `.txt` file under
  `data/raw/web_cache/`, with the outcome recorded by URL in
  `data/processed/web_cache_index.json`:
  - already `"scraped"` → reused straight from disk, no network call.
  - already `"failed"` → not retried that session; `web_search.py` just
    falls back to Tavily's own snippet for that turn.
  Because the cached pages live under `data/raw/`, the next `make
  build-db` run folds them into the ChromaDB collection like any other
  source — so a site that answered one question becomes part of the
  *local* knowledge base for similar future questions, instead of
  needing a fresh web search + scrape every time. `web_cache/` and
  `web_cache_index.json` are gitignored: unlike the Wikipedia data
  (CC BY-SA), scraped news/club-site content isn't necessarily
  redistributable, so it's kept local-only.
- **`rag/web_usage.py`** — meters Tavily calls against
  `TAVILY_MONTHLY_LIMIT` (default 1000, Tavily's free-tier quota) in
  `data/processed/tavily_usage.json`, resetting automatically each
  calendar month. `web_search.py` calls `record_search()` once per
  actual Tavily request (a request spends a credit even with no useful
  results) and checks `quota_exceeded()` before making one at all — once
  the quota's used up, `web_search_available()` goes `False` and the
  chatbot quietly falls back to local-only retrieval until next month.
  `app.py`'s sidebar calls `web_search_status()` to show a live
  used/limit count (and a warning once exhausted), so this is visible in
  the UI, not just the logs. Gitignored like the other local-state
  files.
- **`scripts/scrape_wikipedia.py`** — pulls the page titles listed in
  `PAGES` via `wikipediaapi.Wikipedia(...)` and writes plain text to
  `data/raw/wikipedia/`. Add/remove titles there to change coverage. Note:
  "Kop (stand)" is currently skipped — that Wikipedia page title doesn't
  exist (pre-existing, not a bug to fix blindly).
- **`scripts/fetch_football_api.py`** — hits football-data.org (team id 64
  = Liverpool) for recent/upcoming matches and Premier League standings.
  Requires `FOOTBALL_API_KEY` in `.env` (loaded via `python-dotenv`).
  Football data goes stale fast — re-run regularly (README suggests daily).
- **`scripts/build_vector_store.py`** — chunks every `.txt` under
  `data/raw/` (800 chars, 150 overlap), embeds with
  `all-MiniLM-L6-v2`, and rewrites the `liverpool_fc` ChromaDB collection
  from scratch (`delete_collection` then `create_collection` — always a
  full rebuild, not incremental). Re-run this any time raw data changes.
- **`app.py`** — Streamlit UI. Keeps only the last 6 messages
  (`st.session_state.messages[-6:-1]`) as history passed into
  `engine.answer()`, to bound LLM context size.

## Environment gotcha: Python 3.9

`venv/` is pinned to **Python 3.9.19**. PEP 604 union syntax (`X | Y` in
type hints) is evaluated eagerly at import/class-definition time on 3.9 and
will crash with `TypeError: unsupported operand type(s) for |: ...`. Any
new code using `dict | None`, `list[dict] | None`, etc. needs either:

- `from __future__ import annotations` at the top of the file (already
  added to `scripts/fetch_football_api.py` and `rag/query_engine.py`), or
- old-style `Optional[dict]` / `Union[...]` from `typing`.

`Wikipedia-API` is pinned to `==0.7.3` in `requirements.txt` for the same
reason — 0.10.0+ uses PEP 604 syntax internally and breaks on 3.9.

## Environment gotcha: `.env` isn't loaded automatically everywhere

Python doesn't read `.env` files by itself — something has to call
`load_dotenv()`. `scripts/fetch_football_api.py` does this, but
`app.py`/`streamlit` never did, so env vars like `WEB_SEARCH_ENABLED` and
`TAVILY_API_KEY` sat in `.env` but never reached `os.environ` for the
Streamlit process, silently keeping web search off even when the flag was
set to `true`. Fixed by adding `load_dotenv()` to `rag/query_engine.py`
(imported by both `app.py` and the CLI scripts), so it's covered
regardless of entry point. If you add a new script that reads a `.env`
var directly (not through `rag/query_engine.py`), it needs its own
`load_dotenv()` call too.

## Running things

```bash
make install      # venv + pip install -r requirements.txt
make pull-model   # ollama pull qwen2.5:7b
make data         # scrape + fetch + build-db (needs FOOTBALL_API_KEY in .env)
make run          # streamlit run app.py
```

`.env` holds `FOOTBALL_API_KEY` — never committed (`.gitignore` excludes
`.env`, `venv`, `_screenshot`).

## Known limitations

- Retrieval has no re-ranking; it's a single dense-embedding top-k query.
- The vector store rebuild is always a full wipe-and-reinsert — fine at
  this data size (~15 wiki pages + 2 API text files), would need
  incremental upsert logic at larger scale.
- Conversation history is truncated to the last 6 messages client-side in
  `app.py`; there's no token-based budgeting.
