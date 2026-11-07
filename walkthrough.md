# Walkthrough script (3 minutes, your own voice)

> Record this while actually running the tool, in three beats: **why → run → the one honest
> failure.** Keep it conversational; ~330 words at a normal pace. The commands below are what
> you run on camera (adjust the input path to wherever the 50-episode folder lives).

---

**[0:00] Why this problem, and the one decision behind everything** (~30s)

"I built a promo finder for Kuku's Problem 1. I chose it because it's the most testable: real
input, clear criteria. But the real question the brief was asking is how much of this should
live in AI. My answer: *the model decides how to say it, never where to cut.* So the clip
discovery and ranking are a deterministic rules engine — every timestamp and score is
reproducible and explainable — and a swappable LLM is an optional layer that only rewords the
human copy. If the model is weak or absent, the tool still works. If Kuku plugs in a stronger
model later, it's one environment variable."

**[0:30] Run it on all 50 episodes** (~60s)

"Now I'll run it on the full input pack."

    python -m kuku_promo_finder "path/to/episode-folder" -o output

"Done in a second or two, no installs, no API. It found 144 candidate promos across all 50
episodes — three per episode, de-duplicated so they don't all point at the same moment. Here's
the 'post first' list: Episode 32 opens on 'Why?!' and cuts mid-confrontation; Episode 47 opens
on 'Juliana, she tried to destroy you!'; Episode 28 opens on 'I was poisoned!'. Each one is a
20-to-60 second window, opens on a scroll-stopping line or action in the first three seconds, and
cuts on an unresolved beat. And these aren't hand-picked — they're the ranked output of a cue
lexicon: violence, reveals, power stakes, and cliffhanger markers."

**[1:45] Open the prototype and one clip** (~45s)

"This is the board — a single HTML file, no server, so anyone can open the link."  *(open
output/board.html)*  "I can filter by episode, by the quality verdict, or search any cue. Let me
pull up one…  *(click a top card)*  Notice each card shows the *exact source lines* the clip
opens on and cuts on. An editor can verify the cut in seconds, not by re-watching an episode."

**[2:30] The honest failure — this is the part that matters** (~45s)

"I didn't just show what it gets right. On this run, 19 clips got flagged 'review' by its own
audit, not a human. The biggest one: it used to score a *calm* fade-to-black the same as an
*ominous* one, so some 'cliffhangers' were just… peaceful. I fixed that with a resolution cap
and re-ran. And the remaining 'low cliff' flags — like Episode 13 cutting on Gerald shouting down
into a garden — are genuine judgment calls where a human should look. That's the design working:
the tool tells you exactly where it's unsure instead of pretending it isn't. And in my doc I
named one place the AI genuinely got me wrong — it misread the timestamp format as
hours:minutes, not minutes:seconds, and I caught it against the scene math."

**[3:00] Close**

"Rules for the cuts, optional LLM for the words, and a self-audit for the failures — that's the
whole idea. It runs on real inputs today, and it scales to a new show by pointing it at the
folder."

---

## Things to do *before* recording (so the demo is clean)
- `python -m kuku_promo_finder <episode-folder> -o output`  → then `python make_board.py output`
- Have `output/board.html` open in a browser tab and `output/digest.md` ready.
- Pre-type the EP13 example in the board's search box so the "low cliff" flag is visible in one click.
- If you recorded, cut to 3:00; the [ ] marks are target timestamps, not hard cuts.

## Why this structure (for your notes, not the video)
The brief's evaluation lenses are: *problem choice, AI vs. code split, quality-checking honesty,
working prototype, communication*. This script walks each lens in order, leads with the framing
that an interviewer will probe in the follow-up, and spends the last 45s on a real failure —
which is explicitly what the reviewers reward ("a simple, honest submission that works and is
clear about its limits will beat a polished one that overpromises").
