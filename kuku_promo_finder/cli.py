"""Command-line entry point.

  python -m kuku_promo_finder  /path/to/episode-folder  [-o OUTDIR]
                                   [--per-ep 3] [--top 20] [--min-score 0.32]
                                   [--llm off|auto|on] [--llm-limit 20]

Reads every episode-*.txt, runs parse -> score -> search -> copy -> audit,
and writes the raw outputs:

  OUT/promos_all.json          every ranked promo (the unedited raw output)
  OUT/promos_post_first.json   top-N global picks, one line each
  OUT/per_episode/EPxx.json    one file per episode
  OUT/failure_notes.json       where the tool flags itself as weak (self-critique)
  OUT/quality_summary.json     ok / review / reject counts + flag histogram
  OUT/digest.md                human-readable top-10 digest

Prints a terminal digest too, so `python -m kuku_promo_finder <dir>` is
useful on its own.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import audit_pack, failure_notes
from .copywriter import write_copy
from .llm import refine_many
from .parser import load_pack
from .scoring import find_windows


def _build(input_dir: Path, out_dir: Path, per_ep: int, top: int,
           min_score: float, llm: str, llm_limit: int | None) -> dict:
    eps = load_pack(input_dir)
    if not eps:
        raise SystemExit(f"no episodes found under {input_dir}")

    per_ep_map: dict[str, list] = {}
    all_ranked: list[dict] = []
    for ep in eps:
        wins = [w for w in find_windows(ep, top_per_ep=per_ep, min_score=min_score)
                if w.rank >= min_score]
        recs = []
        for rank, w in enumerate(wins, 1):
            copy = write_copy(w, ep)
            rec = w.as_record(ep, rank, copy, why=copy["why"])
            rec["episode_logline"] = ep.logline[:160]
            rec["episode_duration_s"] = round(ep.duration, 2)
            recs.append(rec)
        per_ep_map[str(ep.number)] = recs
        all_ranked.extend(recs)

    all_ranked.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(all_ranked, 1):
        r["global_rank"] = i
        r["post_first"] = i <= 10

    result = {"per_episode": per_ep_map, "ranked": all_ranked,
              "meta": {"episodes": len(eps), "per_ep": per_ep,
                        "min_score": min_score, "dedup_overlap": 0.40}}
    result = audit_pack(result, eps)

    if llm in ("on", "auto"):
        result["ranked"] = refine_many(result["ranked"],
                                       {str(e.number): e.logline for e in eps},
                                       limit=llm_limit)
    return result


def _write_outputs(result: dict, out_dir: Path, top: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "promos_all.json").write_text(json.dumps(result, indent=1))
    (out_dir / "promos_post_first.json").write_text(json.dumps(
        [{"rank": p["global_rank"], "episode": p["episode"], "start": p["start"],
          "end": p["end"], "duration_s": p["duration_s"], "hook": p["hook"],
           "cliffhanger": p["cliffhanger"], "why": p["why"]}
         for p in result["ranked"][:top]], indent=1))
    per = out_dir / "per_episode"
    per.mkdir(exist_ok=True)
    for num, recs in result["per_episode"].items():
        (per / f"EP{int(num) if num.isdigit() else num:02d}.json").write_text(
            json.dumps({"episode": num, "promos": recs}, indent=1))
    (out_dir / "failure_notes.json").write_text(json.dumps(failure_notes(result), indent=1))
    (out_dir / "quality_summary.json").write_text(json.dumps(result["quality"], indent=1))
    (out_dir / "digest.md").write_text(_digest_md(result, top))


def _digest_md(result: dict, top: int) -> str:
    q = result["quality"]
    lines = [
        "# Promo digest", "",
        f"**{q['total']} promos** across {len(result['per_episode'])} episodes -> "
        f"{q['ok']} clean, {q['review']} flagged for review, {q['reject']} rejected.", "",
        "## Post first (global top)", "",
        "| # | EP | in -> out | dur | hook | cliffhanger |",
        "|---|----|-----------|-----|------|-------------|"]
    for p in result["ranked"][:top]:
        lines.append(f"| {p['global_rank']} | {p['episode']} | {p['start']} -> {p['end']} "
                     f"| {p['duration_s']}s | {p['hook'][:60]} | {p['cliffhanger'][:60]} |")
    lines += ["", "## Quality flags", "",
              f"Soft flags: {q['soft_flag_counts']}", "",
              "See `failure_notes.json` for specific clips flagged as weak.",
              "See `promos_all.json` for every field (scores, cues, provenance)."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kuku promo finder")
    ap.add_argument("input_dir")
    ap.add_argument("-o", "--out", default="output")
    ap.add_argument("--per-ep", type=int, default=3,
                    help="max promos kept per episode after dedup (default 3)")
    ap.add_argument("--top", type=int, default=20,
                    help="how many global 'post first' to export (default 20)")
    ap.add_argument("--min-score", type=float, default=0.32,
                    help="minimum 0-1 blend score for a window to be kept")
    ap.add_argument("--llm", default="off", choices=["off", "auto", "on"],
                    help="enable the optional copy refiner (copy only)")
    ap.add_argument("--llm-limit", type=int, default=20,
                    help="max records to send to the LLM (free-tier friendly)")
    a = ap.parse_args(argv)

    result = _build(Path(a.input_dir), Path(a.out), a.per_ep, a.top,
                    a.min_score, a.llm, a.llm_limit)
    _write_outputs(result, Path(a.out), a.top)

    q = result["quality"]
    print(f"ran {len(result['per_episode'])} episodes -> {q['total']} promos "
          f"({q['ok']} ok / {q['review']} review / {q['reject']} reject)")
    print("\nPost first:")
    for p in result["ranked"][:10]:
        print(f"  {p['global_rank']:>2}. {p['episode']:<10} {p['start']}->{p['end']} "
              f"[{p['duration_s']}s]  {p['hook'][:56]}")
    print(f"\nraw outputs written to {a.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
