"""Quality checking: audit every promo against hard constraints + soft heuristics.

The brief asks "Where does your tool pick badly?". This implements that as
real, reproducible code:

  HARD checks (a failure = a bug, verdict 'reject'):
    - duration within [20, 60]s
    - start < end, both within the episode
    - at least one dialogue beat inside the window (standalone legibility)
  SOFT checks (flagged 'review' for a human editor, not discarded):
    - low hook / low cliff scores
    - ends on a resolved/calm beat (the resolution cap fired)
    - spans 3+ settings / very little dialogue
    - nearly the whole episode is the clip
"""
from __future__ import annotations

from .parser import Episode, fmt_sec

MIN_D, MAX_D = 20.0, 60.0


def _ts(s: str) -> float:
    m, sec = s.split(":")
    return int(m) * 60 + float(sec)


def audit(rec: dict, ep: Episode | None) -> dict:
    hard, soft = [], []
    start, end, dur = _ts(rec["start"]), _ts(rec["end"]), rec["duration_s"]

    if not (MIN_D - 0.5 <= dur <= MAX_D + 0.5):
        hard.append(f"duration {dur}s outside {MIN_D:.0f}-{MAX_D:.0f}s")
    if start >= end:
        hard.append("start >= end")
    if ep and (start > ep.duration + 0.3 or end > ep.duration + 0.3):
        hard.append("end exceeds episode duration")

    n_dialogue = n_settings = None
    if ep:
        in_win = [b for b in ep.beats if start - 0.2 <= b.start <= end + 0.2]
        n_dialogue = sum(1 for b in in_win if b.kind == "dialogue")
        n_settings = len({b.scene_heading for b in in_win if b.scene_heading})
        if in_win and n_dialogue == 0:
            hard.append("no dialogue in window (likely not standalone)")

    if "weak cliff" in " ".join(rec.get("flags", [])):
        soft.append("ending beat reads as resolved/calm (weak cliff)")
    if rec.get("hook_score", 0) < 0.5:
        soft.append(f"low hook ({rec['hook_score']}) — opening may not stop a scroll")
    if rec.get("cliffhanger_score", 0) < 0.4:
        soft.append(f"low cliff ({rec['cliffhanger_score']}) — may not end unresolved")
    if "spans 3 settings" in " ".join(rec.get("flags", [])):
        soft.append("spans 3 settings — check standalone clarity")
    if n_dialogue is not None and n_dialogue <= 1:
        soft.append("little/no dialogue in window — context-dependent")
    if rec.get("episode_duration_s") and dur > 0.95 * rec["episode_duration_s"]:
        soft.append("nearly the whole episode is the clip")

    verdict = "reject" if hard else ("review" if soft else "ok")
    return {"hard_ok": not hard, "hard_violations": hard, "soft_flags": soft,
            "verdict": verdict, "dialogue_beats": n_dialogue, "settings": n_settings}


def audit_pack(result: dict, eps: list[Episode]) -> dict:
    by_ep = {e.number: e for e in eps}
    counts = {"ok": 0, "review": 0, "reject": 0}
    flag_counts: dict[str, int] = {}
    for p in result["ranked"]:
        a = audit(p, by_ep.get(p["episode"]))
        p["audit"] = a
        counts[a["verdict"]] += 1
        for f in a["soft_flags"]:
            key = f.split(" (")[0]
            flag_counts[key] = flag_counts.get(key, 0) + 1
    result["quality"] = {"total": len(result["ranked"]), **counts,
                         "soft_flag_counts": dict(sorted(flag_counts.items(), key=lambda x: -x[1]))}
    return result


def failure_notes(result: dict, limit: int = 40) -> list[dict]:
    """Concrete 'where it picks badly' examples for the doc + human review."""
    out = []
    for p in result["ranked"]:
        a = p.get("audit", {})
        if a.get("hard_violations") or a.get("soft_flags"):
            out.append({"episode": p["episode"], "start": p["start"], "end": p["end"],
                        "rank": p.get("score"), "verdict": a.get("verdict"),
                        "problems": (a.get("hard_violations") or []) + (a.get("soft_flags") or []),
                        "hook": p.get("hook"), "cliff": p.get("cliffhanger")})
    out.sort(key=lambda x: 0 if x["verdict"] == "reject" else 1)
    return out[:limit]
