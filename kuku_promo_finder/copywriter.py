"""Deterministic copywriter: turn a Window into human hook / cliffhanger / why
lines with NO LLM. This is the offline default so the whole tool runs with
zero network and zero cost. An LLM can replace these strings (llm.py) but the
timestamps and scores always come from the rules engine.
"""
from __future__ import annotations

from .parser import Episode, fmt_sec
from .scoring import Window, _text_for, _OPEN_STRONG, CUE_NAMES


def _cue_labels(w: Window) -> list[str]:
    """Human-readable names for the top open/close cues, for the 'why' line."""
    labels = []
    for c in w.cues:
        if c["zone"] not in ("open", "close"):
            continue
        labels.append(CUE_NAMES.get(c["name"], c["name"]))
        if len(labels) >= 3:
            break
    return labels


def write_copy(w: Window, ep: Episode) -> dict:
    fb, lb = ep.beats[w.i0], ep.beats[w.i1]
    first = _text_for(fb.kind, fb.text)
    last = _text_for(lb.kind, lb.text)

    # ---- hook line
    if fb.kind == "dialogue":
        if w.opens_on_strong:
            hook = f"Hard stop-hook: {first!r} lands on the very first frame"
        else:
            hook = f"Stops the scroll with {fb.speaker.title()}'s {first!r} in the first 3 seconds"
    else:
        if w.opens_on_strong:
            hook = f"Hard stop-hook: {first[:80]}"
        else:
            hook = f"Opens mid-action: {first[:100]}"

    # ---- cliffhanger line
    if lb.kind == "dialogue":
        cliff = f"Cuts on {lb.speaker.title()}'s unanswered {last!r}"
    elif "to black" in last.lower() or "fades to black" in last.lower():
        cliff = f"Ends on a hard cut to black right after: {last[:70]}"
    else:
        cliff = f"Cuts on an unresolved beat: {last[:100]}"

    # ---- why it works
    reasons = []
    if w.opens_on_strong:
        reasons.append("instant pay-off in frame 1")
    top = _cue_labels(w)
    if top:
        reasons.append("driven by " + " + ".join(top))
    if w.cliff >= 0.75:
        reasons.append("cut lands before the reveal, so viewers must press play")
    if w.stand >= 0.6:
        reasons.append("readable without prior context")
    why = "Works because: " + "; ".join(reasons) if reasons else "Works because: sustained tension with a high-stakes payoff"

    return {"hook": hook, "cliffhanger": cliff, "why": why}
