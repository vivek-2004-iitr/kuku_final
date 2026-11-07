"""Optional LLM refiner (swappable model layer).

The brief: "if a paid API would help, tell us how you'd use it and build a
smaller version for free" + "a solution where the model is easy to swap will
shine". So the CORE pipeline is pure rules (offline, zero cost). This module
adds a copy refiner that, when an endpoint is configured, rewords the
human-facing strings (hook / cliffhanger / why) to be punchier and on-brand.

Hard invariants (checked, not trusted):
  * The LLM NEVER edits timestamps, scores, or cue lists. It returns ONLY the
    three copy strings; we re-attach them to the rule-computed record.
  * Runs on any OpenAI-compatible chat endpoint. Free options:
      - Ollama local:   KUKU_LLM_BASE_URL=http://localhost:11434/v1  KUKU_LLM_MODEL=qwen2.5:7b
      - OpenRouter :free models: KUKU_LLM_BASE_URL=https://openrouter.ai/api/v1  KUKU_LLM_API_KEY=...
      - A Kuku-provided API in the interview: set KUKU_LLM_BASE_URL/_MODEL/_API_KEY
  * KUKU_USE_LLM=on|auto|off (default off). 'auto' turns on when a key is set.
  * No key / no endpoint / any error -> rule copy is kept; nothing is corrupted.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

_SYSTEM = (
    "You rewrite marketing copy for microdrama promo clips. Given a clip's "
    "opening beat, closing beat, and detected cues, write three tight lines:\n"
    "hook: the scroll-stopping moment (<= 12 words)\n"
    "cliffhanger: the unresolved cut that makes viewers press play (<= 14 words)\n"
    "why: one sentence on why this works on its own (<= 22 words).\n"
    "Be concrete; make no claim the footage wouldn't support. Return JSON only."
)


def _cfg() -> tuple[str, str, str, bool]:
    key = os.environ.get("KUKU_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("KUKU_LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("KUKU_LLM_MODEL", "gpt-4o-mini")
    use = os.environ.get("KUKU_USE_LLM", "off").lower()
    if use == "auto":
        use = bool(key)
    return base, model, key, use in ("on", "1", "true") or use == "auto" and bool(key)


def _refine_one(rec: dict, logline: str, base: str, model: str, key: str) -> dict | None:
    prompt = {"episode": rec.get("episode"), "logline": logline,
              "opens_on": rec.get("hook_source", rec.get("hook", "")),
              "cuts_on": rec.get("cliffhanger_source", rec.get("cliffhanger", "")),
              "cues": [c.get("name") for c in rec.get("cues", [])][:5]}
    body = {"model": model,
            "messages": [{"role": "system", "content": _SYSTEM},
                         {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            "temperature": 0.4}
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        out = json.loads(m.group(0) if m else text)
    except Exception as e:  # noqa: BLE001
        rec["llm_error"] = f"{type(e).__name__}: {e}"
        return None
    for k in ("hook", "cliffhanger", "why"):
        if isinstance(out.get(k), str) and out[k].strip():
            rec[k] = out[k].strip()
    rec["copy_engine"] = f"llm:{model}"
    return rec


def refine_many(records: list[dict], loglines: dict | None = None, limit: int | None = None) -> list[dict]:
    """Refine up to `limit` records (bounded to stay free-tier friendly).
    `limit=None` means all; a large run should pass a small number."""
    base, model, key, enabled = _cfg()
    loglines = loglines or {}
    if not enabled or not key:
        return records
    out, n = [], 0
    for rec in records:
        if limit is not None and n >= limit:
            out.append(rec); continue
        out.append(_refine_one(rec, loglines.get(str(rec.get("episode")), ""), base, model, key) or rec)
        n += 1
    return out
