# Kuku Promo Finder

Finds the best **20–60 second promo clips** in a microdrama, ranks them, and
explains why each one works — built for Kuku's "Find the Promos (Ads)" problem
(Problem 1 of the AI Generalist assignment).

It reads a folder of timestamped screenplays, and for every episode it:

1. **Parses** each beat (camera / action / sound / dialogue) into a timeline.
2. **Scores** beats against a weighted **cue lexicon** (violence, reveals,
   power stakes, unresolved endings, …).
3. **Searches** every 20–60s window whose edges snap to beat boundaries,
   scoring each on **hook** (a stop-scroller in the first 3s),
   **cliffhanger** (a cut on an unresolved beat), and **standalone**
   (followable by someone who's never seen the show).
4. **Dedups** overlapping windows and keeps the top per episode.
5. **Writes copy** (hook / cliffhanger / why) deterministically.
6. **Audits** every pick against hard constraints + soft heuristics, and
   reports the ones it flags as weak — this directly answers the brief's
   "where does your tool pick badly?".

## The core product decision

The **rules engine owns all timestamps and scores.** An LLM is *optional* and
*swappable*: when you point it at any OpenAI-compatible endpoint it only
**rewords the copy** and can nudge rank within an episode — it never invents a
cut point. So a bad or absent model can't corrupt the data, the tool runs fully
offline and costs nothing, and the human editor stays in the loop (the audit
flags "review" clips that are worth a second look). This is the shape the brief
asks for: clear thinking, explainable, and a model that's trivial to swap.

## Quick start

No third-party deps for the core. Python 3.9+.

```bash
# from this folder, point it at the 50-episode input pack
python -m kuku_promo_finder "/path/to/episode-folder" -o output

# then open the raw outputs
cat output/digest.md
less output/promos_all.json        # every field: scores, cues, provenance, audit
```

`output/` contains:
- `promos_all.json` — the full ranked, audited raw output
- `promos_post_first.json` — the top-N "post first" picks, one line each
- `per_episode/EPxx.json` — one file per episode
- `failure_notes.json` — clips the tool itself flags as weak (self-critique)
- `quality_summary.json` — ok / review / reject counts + flag histogram
- `digest.md` — a human-readable top-10

## The optional LLM refiner (copy only, swappable)

```bash
# Free options (no paid API):
#   Ollama, local:   KUKU_LLM_BASE_URL=http://localhost:11434/v1 \
#                   KUKU_LLM_MODEL=qwen2.5:7b KUKU_USE_LLM=on
#   OpenRouter free: KUKU_LLM_BASE_URL=https://openrouter.ai/api/v1 \
#                   KUKU_LLM_API_KEY=*** KUKU_LLM_MODEL=<model>:free KUKU_USE_LLM=on

python -m kuku_promo_finder <dir> -o output --llm auto --llm-limit 20
```

The `copy_engine` field on each record tells you which engine wrote the copy
(`rules` or `llm:<model>`). Timestamps are identical either way.

## Prototype UI

```bash
pip install -r requirements.txt   # streamlit
streamlit run app.py
```

The board renders the raw JSON so an editor can filter by episode / verdict /
score, read the exact source lines each cut lands on, and copy timestamps.

## Tuning

All the levers live in `kuku_promo_finder/scoring.py`:
- `CUES` — the cue families and their weights / which beat kinds they fit.
  Raise `physical_confrontation` for an action-heavy show, raise
  `reveal_secret` for a mystery, etc.
- `find_windows(..., min_score, dedup_overlap, top_per_ep)` — how aggressive
  the search is.
- `candidate` blend weights in `_score_window` (45/35/20 hook/cliff/standalone).

## What it's honest about (limitations)

- **Rules only in the default copy.** The human lines are templates, not prose;
  that's deliberate (offline + zero cost). The LLM refiner upgrades this.
- **Cliffhanger detection is cue-driven.** It fires on "cut to black", an
  unanswered question, or a score swelling to a cliff. A subtle, quiet cliff
  (a character simply leaving the frame) may under-score — those surface in
  `failure_notes.json` as "low cliff" for a human to confirm.
- **One continuous stretch.** The brief allows joining several moments; this
  tool deliberately picks the strongest *single* stretch (most ReelShort /
  DramaBox promos are too). Multi-segment joins are a documented next step.
- **Standalone = heuristic.** It's estimated from dialogue share, speaker
  diversity and settings; a human should still glance at flagged clips.
