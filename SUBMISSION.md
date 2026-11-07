# Submission checklist (Kuku AI Generalist — Problem 1)

| Required item | Where it is | Notes |
|---|---|---|
| **Solution doc** (PDF, ≤2 pp) | `solution_doc.pdf` | Problem choice, assumptions, how it works, scaling, quality + failure evidence, AI use + one mistake. Exactly 2 pages. |
| **Prototype link** | this repo — three ways to open it | (a) `output/board.html`: self-contained, dependency-free — host the repo on GitHub Pages or any static host and it works with zero build. (b) `streamlit run app.py` (Streamlit Community Cloud free tier) for the interactive board. (c) Plain CLI: `python -m kuku_promo_finder <episode-folder> -o output`. |
| **Raw outputs** | `output/` folder | Unedited outputs from a full run on all 50 episodes: `promos_all.json` (ranked + audited), `promos_post_first.json` (top 20), `per_episode/EP*.json` (50 files), `failure_notes.json` (self-critique), `quality_summary.json`, `digest.md`. Regenerate any time with the CLI. |
| **Walkthrough** (optional, ≤3 min) | `walkthrough.md` | Timestamped script for the screen recording + prep checklist. |

## Run it (any machine, Python 3.9+, stdlib only)

```bash
python -m kuku_promo_finder "/path/to/episode-folder" -o output
python make_board.py output     # -> output/board.html
```

Optional copy polish (free tiers; timestamps never change):

```bash
KUKU_LLM_BASE_URL=http://localhost:11434/v1 KUKU_LLM_MODEL=qwen2.5:7b \
KUKU_LLM_API_KEY=ollama KUKU_USE_LLM=on \
python -m kuku_promo_finder <dir> -o output --llm on --llm-limit 20
```

## What "works" means here (verified)
- 50/50 episodes parse (both header casings, M:SS.ss timestamps, out-of-order tail beats).
- 144 promos: every clip 20–60s, start < end, inside episode bounds, edges on beat boundaries.
- Audit: 125 ok / 19 review / 0 reject; the 19 are soft-flagged for a human, not hidden.
- LLM layer verified graceful: with no key set, output is identical to rules-only (copy_engine="rules").

## Known limitations (also in solution_doc.pdf + README)
- Quiet/cliff-less endings score low rather than high — by design, surfaced as "low cliff" flags.
- Single-continuous-stretch promos only (brief allows multi-segment; documented next step).
- "Standalone" is a heuristic from dialogue share / speaker diversity / settings.
