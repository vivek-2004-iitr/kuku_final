"""Screenplay -> structured beats.

Input format (Kuku microdrama script):
    EPISODE NUMBER: Episode 3
    EPISODE LOGLINE: ...
    CONTINUITY NOTES: ...
    --- SCRIPT START ---
    SCENE 02
    Scene heading: INT. CASTLE STUDY / LIBRARY – CONTINUOUS   (or ALL CAPS)
    Scene start: 00:42.50   (MM:SS.ss = minutes:seconds.centiseconds)
    Scene end: 00:58.90
    Actions and dialogue:
    **CAMERA:**            **ACTION:**  **SOUND FX:**
    **LADY JULIANA (Trembling, Pleading):**   <- speaker (delivery)
    Start: (00:21.80) | End: (00:23.50)
    "What do you mean?"

Observed edge cases (handled here, documented in README):
  * header lines appear in Title case and ALL CAPS in different files
  * timestamps are M:SS.ss (seconds field carries its own decimal)
  * a trailing beat can be out of time order (its start exceeds the episode's
    last monotonic end) — flagged and kept, since it may still be a valid
    closing beat
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TS = r"(\d{1,2}):(\d{1,2}\.\d{1,2})"


def ts_to_sec(mm: str, ss: str) -> float:
    """'02', '18.00' -> 138.0 (MM:SS.ss = minutes : seconds.centiseconds)."""
    return int(mm) * 60 + float(ss)


def fmt_sec(t: float) -> str:
    m = int(t // 60)
    s = round(t - m * 60, 2)
    return f"{m:02d}:{s:05.2f}"


@dataclass
class Beat:
    idx: int
    scene: int
    scene_heading: str
    label: str          # "CAMERA", "ACTION", "SOUND FX", or a character name
    speaker: str = ""   # for dialogue beats only
    delivery: str = ""  # parenthetical, e.g. "Cold, Commanding"
    start: float = 0.0
    end: float = 0.0
    text: str = ""
    kind: str = "other"  # camera | action | sfx | dialogue
    out_of_order: bool = False


@dataclass
class Episode:
    number: int
    logline: str
    continuity: str
    beats: list[Beat] = field(default_factory=list)
    n_scenes: int = 0
    start: float = 0.0
    end: float = 0.0
    source: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    def settings(self) -> list[str]:
        out, seen = [], set()
        for b in self.beats:
            if b.scene_heading and b.scene_heading not in seen:
                seen.add(b.scene_heading)
                out.append(b.scene_heading)
        return out


_LABEL = re.compile(r"^\*\*(?P<inner>.+?)\*\*$")
_TS_LINE = re.compile(rf"^Start:\s*\(?(?P<m>\d{{1,2}}):(?P<ms>\d{{1,2}}\.\d{{1,2}})\)?\s*\|\s*End:\s*\(?(?P<e>\d{{1,2}}):(?P<es>\d{{1,2}}\.\d{{1,2}})\)?$")


def parse_episode(path: str | Path) -> Episode:
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    m = re.search(r"EPISODE NUMBER:\s*(?:Episode\s+)?(\d+)", text, re.I)
    number = int(m.group(1)) if m else 0
    logline = _grep1(r"EPISODE LOGLINE:", text, 1) or ""
    continuity = _grep1(r"CONTINUITY NOTES:", text, 1) or ""
    ep = Episode(number=number, logline=logline.strip(),
                 continuity=continuity.strip(), source=p.name)

    body = text
    m = re.search(r"--- SCRIPT START ---(.*)--- SCRIPT END ---", text, re.S)
    if m:
        body = m.group(1)

    beats: list[Beat] = []
    scene, heading = 0, ""
    prev_end = 0.0
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()
        up = line.upper()

        if up.startswith("SCENE ") and re.match(r"^SCENE \d+\s*$", up):
            scene = int(up.split()[1])
            ep.n_scenes = max(ep.n_scenes, scene)
            heading = ""
            i += 1
            continue

        if up.startswith("SCENE HEADING:") or up.startswith("Scene heading:"):
            heading = line.split(":", 1)[1].strip()
            i += 1
            continue

        if up.startswith("SCENE START:") or up.startswith("Scene start:"):
            t = _parse_mmss(line)
            if t is not None:
                ep.start = t
            i += 1
            continue

        if up.startswith("SCENE END:") or up.startswith("Scene end:"):
            t = _parse_mmss(line)
            if t is not None:
                ep.end = max(ep.end, t)
            i += 1
            continue

        if up in ("", "ACTIONS AND DIALOGUE:", "ACTIONS AND DIALOGUE"):
            i += 1
            continue

        lm = _LABEL.match(line)
        if lm:
            inner = lm.group("inner").rstrip(":").strip()
            speaker, delivery = inner, ""
            dm = re.match(r"^(?P<s>[^(]+)\((?P<d>[^)]*)\)\s*$", inner)
            if dm:
                speaker, delivery = dm.group("s").strip(), dm.group("d").strip()
            label = speaker.upper()
            kind = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx"}.get(label, "dialogue")
            # next non-empty line(s): Start/End, then text
            j = i + 1
            start = end = None
            while j < len(lines) and not lines[j].strip():
                j += 1
            tm = _TS_LINE.match(lines[j].strip()) if j < len(lines) else None
            if tm:
                start = ts_to_sec(tm.group("m"), tm.group("ms"))
                end = ts_to_sec(tm.group("e"), tm.group("es"))
                j += 1
            txt: list[str] = []
            while j < len(lines):
                l2 = lines[j].strip()
                if _LABEL.match(l2) or l2.upper().startswith(("SCENE ", "ACTIONS AND")) or re.match(r"^(SCENE (HEADING|START|END):|Start:)", l2, re.I):
                    break
                if not l2:
                    break
                txt.append(l2)
                j += 1
            if start is not None:
                ooo = start > ep.end + 2 and ep.end > 0 and start > prev_end + 30
                if end > 0 and start <= end:
                    prev_end = end
                beat = Beat(idx=len(beats), scene=scene, scene_heading=heading,
                            label=label, speaker=speaker, delivery=delivery,
                            start=start, end=end, text=" ".join(txt).strip(),
                            kind=kind, out_of_order=ooo)
                beats.append(beat)
            i = j if start is not None else i + 1
            continue

        i += 1

    ep.beats = beats
    # The beat timeline is the source of truth for promos. Anchor start/end to
    # the actual beats (a scene header's "Scene start/Scene end" is only an
    # approximation and some episodes start their first beat after 00:00).
    if beats:
        ep.start = min(b.start for b in beats)
        ep.end = max(b.end for b in beats)
    ep.beats.sort(key=lambda b: (b.start, b.end))
    return ep


def _parse_mmss(line: str) -> float | None:
    """'Scene start: 01:04.50' -> 64.5 ; None if it doesn't parse."""
    m = re.search(r"(\d{1,2}):(\d{1,2}\.\d{1,2})\s*$", line.strip())
    return ts_to_sec(m.group(1), m.group(2)) if m else None


def _grep1(prefix, text, group):
    m = re.search(rf"^{re.escape(prefix)}\s*(.+)$", text, re.M | re.I)
    return m.group(group) if m else None


def load_pack(folder: str | Path) -> list[Episode]:
    """Load every episode-*.txt in `folder` (or a nested single subfolder)."""
    folder = Path(folder)
    files = sorted(folder.glob("episode-*.txt"))
    if not files and folder.is_dir():
        sub = [d for d in folder.iterdir() if d.is_dir()]
        if len(sub) == 1:
            files = sorted(sub[0].glob("episode-*.txt"))
    if not files:
        raise FileNotFoundError(f"no episode-*.txt files found in {folder}")
    eps = [parse_episode(f) for f in files]
    eps.sort(key=lambda e: e.number)
    return eps
