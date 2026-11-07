"""Score beats and candidate 20-60s windows for promo-ness.

Two-tier design (this is the core product decision):

  RULES (always on, deterministic, explainable, offline)
      A weighted cue lexicon marks which beats are high-value, and a window
      search finds every 20-60s stretch whose EDGES land on beats, then
      scores each window on the three things the brief names:
        hook         -- a strong cue inside the first 3 seconds
        cliffhanger  -- an unresolved/unsettling final beat
        standalone   -- a viewer who's never seen the show can follow it
      The rules engine OWNS all timestamps and scores.

  LLM (optional, swappable, OFF by default)
      Only rewords the human-facing copy and can re-rank within an episode.
      It never invents cut points, so a weak or absent model can't corrupt
      the data. See llm.py.

The cue weights are the tunable knobs; they live in one place so an editor or
the team can adjust them per genre without touching the search logic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .parser import Beat, Episode, fmt_sec


# ---------------------------------------------------------------------------
# Cue lexicon. Each cue: (weight, compiled regex, which beat kinds it fits).
# "open"  cues reward a hit near the window START (hooks).
# "close" cues reward a hit near the window END  (cliffhangers).
# "any"   cues add to overall engagement / standalone-ness.
# Kept to ~14 families so the output stays explainable.
# ---------------------------------------------------------------------------
import re


def _cx(name: str, *pats: str, kinds: str = "", weight: float = 0.5,
        zone: str = "any") -> dict:
    return {"name": name, "weight": weight, "zone": zone,
            "rx": re.compile("|".join(pats), re.I),
            "kinds": set(kinds.split(",")) if kinds else None}


CUES: list[dict] = [
    # --- HOOKS (open) ---
    _cx("physical_confrontation",
        r"\bslap\w*", r"\bpunch\w*", r"\bknock ?(out|him|her)\w*", r"\bstab\w*",
        r"\bstrike[sd]?\b.{0,15}(her|him|guard|thug)\b", r"\bdagger\b", r"\bblade[sd]?",
        r"\bkick\w*", r"\bseiz\w*.{0,15}(her|him|the)\b", r"\bgrabs?\b.{0,15}(her|him|the)",
        kinds="action,camera,sfx", weight=1.0, zone="open"),
    _cx("emotional_break",
        r"\btears?\b", r"\bweep\w*", r"\bsob\w*", r"\bshriek\w*", r"\bscream\w*",
        r"\bgasps?\b", r"\bbreathless\b", r"\bhysteri\w*", r"\bcollapses?\b",
        r"\bcrumpl\w*", r"\bknocks? (out|him|her)", r"\bfaint\w*",
        kinds="action,camera,dialogue,sfx", weight=0.8, zone="open"),
    _cx("reveal_secret",
        r"\bexposed?\b", r"\breveal\w*", r"\bsecrets?\b", r"\btruth\b", r"\bconspir\w*",
        r"\bimpost\w*", r"\bimpostor\b", r"\bpretend\w*", r"\bbetray\w*",
        r"\bwas (dead|gone|murdered|killed|poisoned)\b", r"\bno one (knew|suspect)\b",
        r"\borchestrat\w*", r"\bcoveting?\b",
        r"\breal (son|heir|father|mother|duke)\b", r"\bbirthright\b",
        kinds="dialogue,action", weight=0.9, zone="open"),
    _cx("high_stakes_fate",
        r"\bexecut\w*", r"\btrial\b", r"\bsentence[d]?\b.{0,20}(death|execution|life)",
        r"\bexiled?\b", r"\bimprison\w*", r"\bdethron\w*", r"\btraitor\w*",
        r"\bpoison\w*", r"\bbribe\w*", r"\bseiz\w*.{0,15}(the|ducal)\b", r"\bdungeon\b",
        r"\bducal\b", r"\bthrone\b", r"\bcrown\b", r"\bduchy\b", r"\bduke\b", r"\bduchess\b",
        kinds="dialogue,action,camera", weight=0.55, zone="open"),

    # --- CLIFFHANGERS (close) ---
    _cx("cut_to_black",
        r"\bcut ?(to |hard to )?black\b", r"\bfades? to black\b", r"\bgoes dark\b",
        r"\bscreen ?goes dark\b", r"\bto black\b",
        kinds="camera,sfx", weight=0.95, zone="close"),
    _cx("score_cliff",
        r"\bcliffhanger\b", r"\bomenace?\b.{0,40}\bhold\b",
        r"\bswells? .{0,25}(cliffhanger|silence|omen|crescendo)",
        r"\b(intense|ominous|menacing) .{0,20}(hold|swell|sting)",
        r"\bclimax\b",
        kinds="camera,sfx", weight=0.95, zone="close"),
    _cx("unanswered_question",
        r"\?\s*$", r"\blet me (in|explain|see)\??\s*$", r"\bwhat do you mean\??\s*$",
        r"\bwhy\??\s*$", r"\bhow dare\??\s*$", r"\bimpossible\??\s*$",
        r"\bwho is (he|she|it)\b.{0,20}\??\s*$", r"\bi never\b.{0,20}\??\s*$",
        r"\bthen who\b.{0,20}\??\s*$",
        kinds="dialogue", weight=0.9, zone="close"),
    _cx("shock_reaction",
        r"\bhorrified\b.{0,30}\b(secret|lethal)\b", r"\brealization (hits|dawns)\w*",
        r"\bdread\b", r"\b(gasps?|silence)s? (in )?(sheer )?(dread|shock|terror)\b",
        r"\bmouth (open|parts).{0,20}(gasps?|silence)\b",
        kinds="camera,action", weight=0.85, zone="close"),

    # --- ENGAGEMENT / STAKES (any) ---
    _cx("rising_tension",
        r"\btears?\b", r"\bgrief\b", r"\bagony\b", r"\bshattering\b", r"\bheartbreak\w*",
        r"\bdefiance\b", r"\bdanger\w*", r"\bfatal\b", r"\blethal\b",
        r"\bvenom\w*", r"\bmerciless\b", r"\bstricken\b", r"\btrembl\w*", r"\bquavering\b",
        r"\bshaken (face|expression)\b", r"\bominous\b", r"\bmenacing\b", r"\bsuspense\b",
        kinds="camera,action,sfx", weight=0.4, zone="any"),
    _cx("sudden_movement",
        r"\bstumbles?\b", r"\bbrushing?\b", r"\bcharges?\b", r"\bbacks? (him|her) into\b",
        r"\bpulls? (her|him|back)\b", r"\bstorms?\b",
        kinds="action", weight=0.4, zone="any"),
    _cx("wedding_stakes",
        r"\baltar\b", r"\bbetroth\w*", r"\bridal\b", r"\bgroom\b", r"\bmarriag\w*",
        r"\bceremony\b", r"\bveiled\b", r"\bchapel\b",
        kinds="dialogue,action,camera", weight=0.5, zone="any"),
    _cx("veiled_threat",
        r"\bdestroy (you|him|her|the)\b", r"\bi'?ll (see to it|make sure|ruin)\b",
        r"\bbow (to me|before)\b", r"\bkneel\b.{0,30}\b(bow|kneel|beg)\b",
        r"\bwished .{0,20}(dead|silent)\b", r"\bsilent grave\b",
        r"\bblood .* (be spilled|flow)\b", r"\bpay .{0,15}(for|the debt)\b",
        r"\bregret\b.{0,25}(this|it)\b", r"\bnothing to offer\b", r"\bi cannot marry\b",
        r"\bchoose your next words\b", r"\btoo (late|weak|plain)\b", r"\bfarewell\b",
        r"\bnever going to\b", r"\bnever (get|have|leave)\b",
        r"\b(your|his|her|the) (last|final) (words?|chance|breath)\b",
        kinds="dialogue", weight=0.75, zone="any"),
]

# Map cue name -> human label (also used by copywriter + JSON "cues" field).
CUE_NAMES = {
    "physical_confrontation": "physical confrontation",
    "emotional_break": "emotional break",
    "reveal_secret": "a big reveal / secret",
    "high_stakes_fate": "high-stakes fate",
    "cut_to_black": "cut to black",
    "score_cliff": "score swells to a cliff",
    "unanswered_question": "an unanswered question",
    "shock_reaction": "shock reaction",
    "rising_tension": "rising tension",
    "sudden_movement": "sudden movement",
    "wedding_stakes": "wedding stakes",
    "veiled_threat": "a veiled threat",
    "close_question": "an unanswered question",
    "trailing_off": "a trailing-off line",
}


# A closing beat that RESOLVES the tension (calm exodus) is the wrong kind of
# ending for a cliffhanger; we cap its cliffhanger score so a window that ends
# "exhales in relief / walks away" can't dress up as a cliff.
_RESOLUTION = re.compile(
    r"\bexhal\w* (in relief|with relief)\b"
    r"|\brelie(f|ved|ving)\b.{0,20}\b(shoulder|sigh)\b"
    r"|\bheads to the (door|exit|street)\b"
    r"|\bturns? (to|away) (leave|go)\b"
    r"|\bcalms? (down|to)\b",
    re.I,
)

# A hard stop-hook in the very first frame: one of these on the opening beat.
_OPEN_STRONG = re.compile(
    r"\b(slap|struck?|stab|blade|dagger|blood|shriek|scream|gasps?"
    r"|reveal|exposed?|secret|truth|traitor|betray|accus|guilty|execut|poison|impossible"
    r"|bow to me|kneel|destroy you|real son|throne|crown|altar|groom|who sent you)\b"
    r"|^\s*\"?\s*(What|Why|How dare|No !?)\b",
    re.I,
)


def _text_for(kind: str, text: str) -> str:
    """Dialogue is stored with literal surrounding quotes in the source; strip
    them so question-mark / boundary matching works. Other kinds verbatim."""
    if kind == "dialogue":
        return text.strip().strip('"').strip()
    return text


def cue_hits(beat: Beat) -> dict[str, float]:
    """Return {cue_name: weight} for cues that fire on this beat."""
    hits: dict[str, float] = {}
    text = _text_for(beat.kind, beat.text)
    low = text.lower()
    for cue in CUES:
        kinds = cue["kinds"]
        if kinds and beat.kind not in kinds:
            continue
        if cue["rx"].search(text) or cue["rx"].search(low):
            hits[cue["name"]] = cue["weight"]
    # trailing question mark on dialogue = unresolved ending
    if beat.kind == "dialogue" and low.endswith("?"):
        hits["close_question"] = 0.9
    if beat.kind == "dialogue" and low.endswith(("...", "…")):
        hits.setdefault("trailing_off", 0.55)
    return hits


@dataclass
class Window:
    start: float
    end: float
    i0: int
    i1: int
    hook: float = 0.0
    cliff: float = 0.0
    stand: float = 0.0
    rank: float = 0.0
    cues: list = field(default_factory=list)   # [{name, weight, beat_text, zone}]
    opens_on_strong: bool = False
    flags: list = field(default_factory=list)

    @property
    def dur(self) -> float:
        return self.end - self.start

    def as_record(self, ep: Episode, per_rank: int, copy: dict, why: str) -> dict:
        fb = ep.beats[self.i0]
        lb = ep.beats[self.i1]
        fb_txt = _text_for(fb.kind, fb.text)
        lb_txt = _text_for(lb.kind, lb.text)
        return {
            "episode": ep.number,
            "start": fmt_sec(self.start),
            "end": fmt_sec(self.end),
            "duration_s": round(self.dur, 2),
            "score": round(self.rank * 100, 2),
            "hook_score": round(self.hook, 3),
            "cliffhanger_score": round(self.cliff, 3),
            "standalone_score": round(self.stand, 3),
            "per_ep_rank": per_rank,
            "hook": copy.get("hook", ""),
            "cliffhanger": copy.get("cliffhanger", ""),
            "why": why,
            "hook_source": (fb.label + " " + fb_txt).strip(),
            "cliffhanger_source": (lb.label + " " + lb_txt).strip(),
            "cues": self.cues[:6],
            "flags": self.flags,
            "copy_engine": "rules",
        }


def _window(beat: Beat) -> float:
    return 0.0


def _snapped_windows(ep: Episode, i0: int, i1: int) -> tuple[float, float]:
    """Candidate edge times: prefer snapped-to-beat, keep monotonic."""
    b0, b1 = ep.beats[i0], ep.beats[i1]
    start, end = b0.start, b1.end
    return start, end


def find_windows(ep: Episode, top_per_ep: int = 3,
                 min_score: float = 0.32,
                 dedup_overlap: float = 0.40,
                 max_gap: float = 14.0) -> list[Window]:
    """Enumerate every 20-60s window whose edges land on beat boundaries and
    return the de-duplicated, ranked best candidates."""
    beats = ep.beats
    n = len(beats)
    hits = [cue_hits(b) for b in beats]

    # Precompute per-beat max cue weight by zone (open/close/any).
    zone_max = {z: [0.0] * n for z in ("open", "close", "any")}
    for i, h in enumerate(hits):
        for name, wt in h.items():
            z = zone_of(name)
            zone_max[z][i] = max(zone_max[z][i], wt)

    wins: list[Window] = []
    for i0 in range(n):
        s0 = beats[i0].start
        for i1 in range(i0 + 1, n):
            b1 = beats[i1]
            # stop once we're comfortably over the 60s cap (granularity-safe)
            if b1.end - s0 > 61.0:
                break
            if b1.end - s0 < 20.0:
                continue
            # monotonic guard: skip weird out-of-order closes
            if i1 > 0 and b1.start < beats[i0].start:
                continue
            w = _score_window(ep, i0, i1, zone_max, hits, beats)
            if w is not None:
                wins.append(w)

    wins.sort(key=lambda x: x.rank, reverse=True)
    kept: list[Window] = []
    for w in wins:
        for k in kept:
            ov = max(0.0, min(w.end, k.end) - max(w.start, k.start))
            overlap = ov / min(w.dur, k.dur)
            if abs(w.start - k.start) < max_gap or overlap > dedup_overlap:
                break
        else:
            kept.append(w)
    kept.sort(key=lambda x: x.rank, reverse=True)
    return kept[:top_per_ep]


# helper zone map (a cue's zone is decided by its name)
_ZONE_BY_NAME: dict[str, str] = {}


def _build_zone_map() -> None:
    for cue in CUES:
        _ZONE_BY_NAME[cue["name"]] = cue["zone"]
    _ZONE_BY_NAME["close_question"] = "close"
    _ZONE_BY_NAME["trailing_off"] = "close"


_build_zone_map()


def zone_of(name: str) -> str:
    return _ZONE_BY_NAME.get(name, "any")


def cues_match_zone(name: str, z: str) -> bool:
    return zone_of(name) == z or zone_of(name) == "any"


def _score_window(ep, i0, i1, zone_max, hits, beats) -> Window | None:
    b0, b1 = beats[i0], beats[i1]
    # trim an out-of-order trailing close beat
    i1_used = i1
    if i1 > i0 and beats[i1].start >= b0.end and beats[i1].end < b0.end + 30:
        i1_used = i1 - 1
        b1 = beats[i1_used]
    start, end = b0.start, b1.end
    dur = end - start
    if not (20.0 <= dur <= 60.0):
        return None

    n_win = i1_used - i0 + 1
    w = Window(start=start, end=end, i0=i0, i1=i1_used)

    # ---- HOOK: strongest cue within first 3s; bonus for a named hook type
    hook = 0.0
    open_beat_idxs = [j for j in range(i0, i1_used + 1)
                      if beats[j].start - start <= 3.0]
    for j in open_beat_idxs:
        hook = max(hook, zone_max["open"][j], zone_max["any"][j])
    if _OPEN_STRONG.search(_text_for(beats[i0].kind, beats[i0].text)):
        w.opens_on_strong = True
        hook = max(hook, 0.9)
    if beats[i0].kind == "dialogue":
        hook = max(hook, 0.75)      # a shocking line is a named hook type
    elif beats[i0].kind == "camera":
        hook *= 0.85
    w.hook = min(1.0, hook)

    # ---- CLIFF: strongest close-zone cue in the last 2 beats
    cliff = 0.0
    for j in range(max(i0, i1_used - 1), i1_used + 1):
        cliff = max(cliff, zone_max["close"][j])
    last_txt = _text_for(beats[i1_used].kind, beats[i1_used].text)
    if last_txt.rstrip().endswith("?"):
        cliff = max(cliff, 0.75)
    if b1.end >= ep.duration - 1.5 and ep.beats[-1].end == b1.end:
        cliff = max(cliff, 0.8)
    if _RESOLUTION.search(last_txt):
        cliff = min(cliff, 0.35)
        w.flags.append("ends on a resolved/calm beat — weak cliff")
    w.cliff = round(min(1.0, cliff), 3)

    # ---- STANDALONE: dialogue share, speaker diversity, settings, in-window heat
    win = [beats[j] for j in range(i0, i1_used + 1)]
    dialogue = [b for b in win if b.kind == "dialogue"]
    d_ratio = len(dialogue) / n_win
    speakers = len({b.speaker for b in dialogue if b.speaker})
    settings = len({b.scene_heading for b in win if b.scene_heading})
    heat = max([zone_max["any"][j] for j in range(i0, i1_used + 1)], default=0.0)
    stand = 0.25 * min(1.0, d_ratio * 1.6)
    stand += 0.2 if 2 <= speakers <= 4 else (0.1 if speakers == 1 else 0.05)
    stand += 0.15 * (1.0 / settings if settings else 1.0)
    stand += 0.40 * heat
    w.stand = round(min(1.0, stand), 3)

    w.rank = 0.45 * w.hook + 0.35 * w.cliff + 0.20 * w.stand

    # record which cues fired (top contributors) for explainability
    contrib = []
    for j in range(i0, i1_used + 1):
        zone = "open" if beats[j].start - start <= 3.0 else (
            "close" if start + dur - beats[j].end <= 3.5 else "mid")
        for name, wt in hits[j].items():
            contrib.append({"name": CUE_NAMES.get(name, name), "weight": wt,
                            "zone": zone, "beat": beats[j].text[:100]})
    contrib.sort(key=lambda c: c["weight"], reverse=True)
    # dedup by cue name, keep the best
    seen = set(); top = []
    for c in contrib:
        if c["name"] in seen:
            continue
        seen.add(c["name"]); top.append(c)
    w.cues = top[:6]

    if settings >= 3:
        w.flags.append(f"spans {settings} settings — check standalone clarity")
    if d_ratio < 0.15:
        w.flags.append("little dialogue — context-dependent")
    return w
