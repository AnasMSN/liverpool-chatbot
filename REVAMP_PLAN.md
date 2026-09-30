# Revamp plan: Liverpool FC chatbot → personal career chatbot

This repo is being repurposed from a Liverpool FC RAG chatbot into a
personal chatbot that answers questions about the owner's professional
background, skills, and career goals. The RAG architecture (embed →
retrieve → Groq) doesn't change — only the data, prompts, and branding
do.

## 1. Decisions to lock in before implementing

- [ ] **Scope/guardrails** — should the bot only answer career/professional
      questions and decline personal-life questions (health, family,
      finances), or is broader fair game?
- [ ] **Access** — keep it fully public like now, or gate it (password
      check in `app.py`, or Cloudflare Access in front of
      `chat.anasmahasin.site`) since it'll carry a real name/domain?
- [ ] **Live web search** — keep the Tavily integration (e.g. to cite
      LinkedIn/portfolio pages live) or strip it out to reduce complexity?
- [ ] **Naming** — rename the GitHub repo / Streamlit Cloud app away from
      "liverpool-chatbot"? Cosmetic only, since visitors only see
      `chat.anasmahasin.site` through the iframe wrapper.

## 2. Data to prepare

Everything goes in as plain `.txt`/`.md` files under a new
`data/raw/profile/` directory — the pipeline chunks anything under
`data/raw/`, format-agnostic. Write in third person or as clean factual
statements; that retrieves and answers better than stream-of-consciousness
prose.

- [ ] **Bio / About Me** — who you are, current role, one-paragraph summary
- [ ] **Full work history** — per job: company, title, dates,
      responsibilities, concrete achievements with metrics where possible
- [ ] **Skills & tools** — grouped (languages, frameworks, domains, soft
      skills)
- [ ] **Education & certifications**
- [ ] **Projects/portfolio** — description, tech used, role, outcome, link
      if public
- [ ] **Career goals** — target roles/industries, what you're looking for
      next, dealbreakers, what kind of team/company you want (directly
      answers "what do you want to pursue")
- [ ] **Working style & values** — strengths, what motivates you, how you
      like to work (covers the "softer" questions well)
- [ ] **FAQ** — common recruiter/interview questions with answers in your
      own voice, so the bot's tone matches how you'd actually respond
- [ ] Optional: publications, talks, awards, recommendations/testimonials

The more specific and factual each file, the better retrieval works —
vague marketing language retrieves poorly.

## 3. Code/repo changes

| File | Change |
|---|---|
| `scripts/scrape_wikipedia.py`, `scripts/fetch_football_api.py` | Delete — no equivalent needed; prepared files are dropped straight into `data/raw/profile/` |
| `scripts/build_vector_store.py` | No logic change (already data-source-agnostic); rename collection `liverpool_fc` → `career_profile` |
| `rag/query_engine.py` | Rewrite `SYSTEM_PROMPT` for the new persona/scope, rename `COLLECTION_NAME`; retrieval/condense/Groq call logic stays identical |
| `rag/web_search.py`, `rag/web_cache.py`, `rag/web_usage.py` | Keep as-is or remove, per the web-search decision above |
| `app.py` | New title, caption, page icon |
| `data/raw/wikipedia/`, `data/raw/football_api/`, `data/processed/chroma_db/` | Delete — replaced by new profile data and a rebuilt vector store |
| `Makefile`, `README.md` | Rewrite targets/docs for the new purpose |
| `CLAUDE.md` | Full rewrite to describe the new bot (governs how future work in this repo is approached) |
| `.env` / Streamlit Cloud secrets | Drop `FOOTBALL_API_KEY`; keep `GROQ_API_KEY` (+ Tavily vars if web search is kept) |
| `index.html` | Update `<title>` / branding text |

## 4. Rebuild & ship

1. Drop prepared data files into `data/raw/profile/`.
2. `make build-db` to rebuild the ChromaDB collection from scratch.
3. `make run` to smoke-test locally.
4. Commit + push to `main`.
5. CI (`.github/workflows/ci.yml`) runs automatically.
6. Streamlit Community Cloud auto-redeploys from `main`.
7. Live at `chat.anasmahasin.site` — the domain/iframe setup is unaffected
   by what's behind it.

## 5. Privacy considerations

Since this runs under a real name and domain:

- Exclude sensitive PII: phone number, home address, salary figures,
  anything under an NDA, other people's private details.
- The system prompt should explicitly instruct the model to decline
  off-topic or sensitive questions — a public bot answering "as you" can
  otherwise be steered into saying things that weren't intended.
- Consider `noindex`/`robots.txt` on the wrapper page so it doesn't end up
  indexed by search engines under your name.

## Status

Data collection and the decisions in section 1 are pending. Code changes
in section 3 have not been started.
