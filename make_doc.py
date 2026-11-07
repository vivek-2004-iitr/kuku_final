"""Render the required 2-page solution doc (solution_doc.pdf) with reportlab."""
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, KeepTogether)

W, H = A4
MARG = 16 * mm

INK = colors.HexColor("#1a1a2e")
ACC = colors.HexColor("#58a6ff")
MUT = colors.HexColor("#5a5a6a")
OK = colors.HexColor("#2ea043")

s_title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK)
s_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, leading=13, textColor=MUT)
s_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=INK,
                     spaceBefore=8, spaceAfter=3)
s_b = ParagraphStyle("b", fontName="Helvetica", fontSize=9.2, leading=12.4, textColor=INK)
s_mono = ParagraphStyle("mono", fontName="Courier", fontSize=8.2, leading=10.5, textColor=colors.HexColor("#24292f"))


def P(t, s=s_b):
    return Paragraph(t, s)


def build(path: str) -> None:
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARG, rightMargin=MARG,
                            topMargin=MARG, bottomMargin=MARG,
                            title="Kuku — Find the Promos (Problem 1) — Solution doc")

    story = []
    story.append(P("Find the Promos — Kuku AI Generalist, Problem 1", s_title))
    story.append(Spacer(1, 2))
    story.append(P("A rules-engine promo detector with a swappable LLM refiner, run on all 50 episodes of "
                   "<i>I Married a Broken Soldier</i>. Author: vivek.", s_sub))
    story.append(Spacer(1, 4))

    # ---- why this problem
    story.append(P("Why Problem 1, and the framing", s_h))
    story.append(P(
        "I picked Problem 1 because it's the most bounded and checkable: a concrete input (50 screenplays), "
        "clear success criteria (20–60s clips that open on a hook and end on a cliffhanger, standalone), and "
        "a natural way to show careful AI use. The core question I framed it around: <b>how much do you give "
        "to AI vs. keep as code?</b> My answer — the model should never decide <i>where to cut</i>, only "
        "<i>how to say why</i>. So a deterministic, explainable rules engine finds and ranks every clip, and "
        "an optional LLM only rewrites the human copy. That keeps a bad model from ever corrupting a timestamp."))

    # ---- assumptions
    story.append(P("Assumptions I made where the brief was silent", s_h))
    story.append(P(
        "(1) &ldquo;Promo&rdquo; = one continuous 20–60s stretch, so I find the single strongest stretch per moment and "
        "de-dup overlaps — most ReelShort/DramaBox clips work this way; multi-segment joins are a flagged next "
        "step. (2) &ldquo;Standalone&rdquo; is scored heuristically from dialogue share, speaker diversity and settings, "
        "since I can't watch footage. (3) Timestamps in the source are <b>M:SS.ss</b> (the seconds field carries "
        "its own decimal) and some headers are all-caps — both handled. (4) &ldquo;Rank&rdquo; = a 45/35/20 blend of "
        "hook / cliff / standalone; the top-N across the pack is the &ldquo;post first&rdquo; list."))

    # ---- how it works
    story.append(P("How it works", s_h))
    rows = [
        ["Stage", "What it does"],
        ["parse", "Every CAMERA/ACTION/SOUND/character beat -> a timeline; episodes = 50."],
        ["score", "~14 weighted cue families (violence, reveal, power stakes, unresolved endings...) mark each beat."],
        ["search", "All 20–60s windows whose edges snap to beats; score each on hook (first 3s), cliff (last beat), standalone."],
        ["dedup + rank", "Drop clips sharing &gt;40% of a stronger one; keep top-3 per episode; global rank."],
        ["copy", "Deterministic hook/cliff/why lines (offline, zero cost). Optional LLM rewords copy only."],
        ["audit", "Hard checks (duration, in-bounds, has dialogue) + soft flags (weak cliff, 3+ settings) -> ok/review/reject."],
    ]
    t = Table(rows, colWidths=[26 * mm, 122 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.4), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8ccd4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
    ]))
    story.append(t)

    story.append(Spacer(1, 4))
    story.append(P("Running it (zero installs; Python 3.9+):", s_b))
    story.append(P(
        'python -m kuku_promo_finder &lt;episode-folder&gt; -o output   # core, stdlib only<br/>'
        'python make_board.py output   # self-contained board.html, no dependencies<br/>'
        'streamlit run app.py   # optional interactive board (pip install streamlit)', s_mono))

    # ---- page break
    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    # ---- scaling
    story.append(P("How it scales to every show we make", s_h))
    story.append(P(
        "The pipeline is O(episodes x beats<super>2</super>) and each episode is &le; ~120 beats, so a full show runs in "
        "well under a second, no paid API, no GPU — it's a batch job you can point at a week's new shows. Cost at "
        "volume stays near zero; the only optional paid piece is copy-polish via an LLM, and I cap it (--llm-limit) "
        "and default it off. Because the model is a single swappable endpoint (any OpenAI-compatible API: Ollama "
        "local, OpenRouter free-tier, or a Kuku-provided API in the interview), swapping to a stronger model is one "
        "env var. To scale to new genres, the whole tuning surface is one lexicon (CUES) in scoring.py — raise "
        "reveal_secret for mysteries, physical_confrontation for action — without touching the search."))

    # ---- quality / evidence
    story.append(P("How I know it's good — and where it fails", s_h))
    story.append(P(
        "I ran it on all 50 episodes and reviewed the picks by hand, then built the self-critique into the tool "
        "rather than the doc. On this pack: <b>144 promos, 125 clean / 19 flagged for review / 0 rejected.</b> "
        "Every clip is 20–60s and on-beat. The &ldquo;post first&rdquo; list reads like a real cut sheet — e.g. EP32 &ldquo;Why?!&rdquo; "
        "opening, EP47 &ldquo;Juliana, she tried to destroy you!&rdquo;, EP28 &ldquo;I was poisoned!&rdquo; — each cut lands on a "
        "genuinely unresolved beat. The 19 &ldquo;review&rdquo; flags are exactly the soft spots: 14 are &ldquo;low cliff&rdquo; (the "
        "tool cut on a calm/quiet moment, e.g. EP13 ends on &ldquo;Gerald shouting down into the garden&rdquo; — plausible but "
        "I'd want a human to confirm it hooks), and the rest are &ldquo;spans 3 settings&rdquo; or &ldquo;low hook&rdquo;."))
    story.append(Spacer(1, 2))
    story.append(P("Honest failure I caught and fixed", s_h))
    story.append(P(
        "My first pass scored a &ldquo;cliffhanger&rdquo; as high whenever the episode simply ended. A calm fade-to-black "
        "looked identical to an ominous one, so I added a <b>resolution cap</b> (calm/exhale/leave endings clamp the "
        "cliff score) plus a question-mark/ellipsis cue, which removed the false cliffs. I also caught a parser bug "
        "where &ldquo;Scene end&rdquo; headers under-counted episode length (a trailing out-of-order SFX beat ran past them); "
        "I anchored episode start/end to the beats themselves, which took the reject count to 0. These are in the "
        "git history and the audit."))

    # ---- AI use
    story.append(P("Where I used AI — and one place it got it wrong", s_h))
    story.append(P(
        "I used Claude to scaffold the code and reason about the lexicon, and to generate this doc. One place it got "
        "it wrong: it proposed treating a beat&rsquo;s End timestamp as &ldquo;hours:minutes.tenths&rdquo; (H:MM.F), reading "
        "00:04.80 as ~4 minutes. It's actually M:SS.ss (04.80 seconds) — the seconds field has its own decimal. I "
        "verified against the logline + scene math and corrected the parser; the LLM had no way to know the format, "
        "so I anchored it to the data rather than its guess. I also deliberately kept the copywriter rule-based "
        "(Claude prose would over-sell clips); the model only refines copy if an endpoint is configured."))

    # ---- submission checklist
    story.append(P("What's in the submission", s_h))
    story.append(P(
        "Working prototype: this repo (<code>kuku_promo_finder</code>) with clear run steps + a dependency-free "
        "board.html and an optional Streamlit app. Raw outputs: <code>output/</code> (promos_all.json, post_first, "
        "per-episode, failure_notes, quality_summary, digest.md). Docs: this 2-page PDF + walkthrough script. "
        "It runs on real inputs and produces output an editor can use: copy the timestamps straight to an NLE."))

    doc.build(story)


if __name__ == "__main__":
    import os
    build(os.path.join(os.path.dirname(__file__), "solution_doc.pdf"))
    print("wrote solution_doc.pdf")
