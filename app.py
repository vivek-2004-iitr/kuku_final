"""Streamlit promo board (prototype UI).

Run:
    pip install streamlit
    streamlit run app.py          # (from the repo root; data in ./output)

The app reads the RAW JSON outputs the CLI produced (output/promos_all.json),
so it is a transparent viewer over real data — no hidden computation.
It lets an editor:
  * browse the ranked promo list ("post first" order)
  * filter by episode / verdict / minimum score
  * see each promo's hook, cliffhanger, why, the exact source lines the cut
    points at, and any quality flags the audit raised
  * copy the timestamps for the editor workflow
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

DATA = Path(__file__).parent / "output" / "promos_all.json"

st.set_page_config(page_title="Kuku Promo Finder", page_icon="🎬", layout="wide")
st.title("Kuku Promo Finder")
st.caption(
    "Best 20–60s promo clips in a microdrama, ranked and explained. "
    "Data source: `output/promos_all.json` (produced by the CLI — a raw, unedited run).")

if not DATA.exists():
    st.error(
        "No output/promos_all.json found. Run the pipeline first:\n\n"
        "    python -m kuku_promo_finder <episode-folder> -o output")
    st.stop()

data = json.loads(DATA.read_text())
ranked = data["ranked"]
quality = data.get("quality", {})

# ---- controls ---------------------------------------------------------
c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1.4])
episode = c1.selectbox("Episode", ["All"] + sorted({str(p["episode"]) for p in ranked}, key=int))
verdict = c2.selectbox("Audit verdict", ["All", "ok", "review", "reject"])
min_score = c3.number_input("Min score", 0.0, 100.0, 0.0, step=5.0)
search = c4.text_input("Search", "e.g. reveal, poison, black")

def visible():
    out = []
    for p in ranked:
        if episode != "All" and str(p["episode"]) != episode:
            continue
        if verdict != "All" and p.get("audit", {}).get("verdict") != verdict:
            continue
        if p.get("score", 0) < min_score:
            continue
        hay = json.dumps({k: p.get(k) for k in ("hook", "cliffhanger", "why", "cues", "flags")}).lower()
        if search.lower() and search.lower() not in hay:
            continue
        out.append(p)
    return out

shown = visible()

st.subheader(f"Ranked promos  ({len(shown)} of {len(ranked)})")
st.caption(
    f"Quality: {quality.get('ok',0)} ok · {quality.get('review',0)} review · "
    f"{quality.get('reject',0)} reject")

# ---- cards ------------------------------------------------------------
for p in shown:
    a = p.get("audit", {})
    badge = {"ok": "🟢", "review": "🟡", "reject": "🔴"}.get(a.get("verdict", ""), "⚪")
    ep = p["episode"]
    with st.container(border=True):
        st.markdown(
            f"### {badge} #{p.get('global_rank')} · Episode {ep} · {p['start']} → {p['end']} "
            f"({p['duration_s']}s) · score {p.get('score')}"
        )
        st.markdown(f"**Hook** — {p.get('hook')}")
        st.markdown(f"**Cliffhanger** — {p.get('cliffhanger')}")
        st.markdown(f"**Why it works** — {p.get('why')}")

        cols = st.columns(2)
        with cols[0]:
            st.markdown("<div style='color:#666;font-size:0.85em'>opens on →</div>",
                        unsafe_allow_html=True)
            st.code(p.get("hook_source", ""))
        with cols[1]:
            st.markdown("<div style='color:#666;font-size:0.85em'>cuts on →</div>",
                        unsafe_allow_html=True)
            st.code(p.get("cliffhanger_source", ""))

        cues = [c.get("name") or c.get("family") for c in p.get("cues", [])]
        if cues:
            st.markdown("cues: " + " · ".join(cues[:5]))
        flags = p.get("flags", []) + a.get("soft_flags", [])
        if flags:
            st.markdown("⚠ " + " · ".join(flags))

# ---- copy-all ---------------------------------------------------------
st.sidebar.header("Copy for the editor")
def ts_block():
    return "\n".join(f"{p['episode']:<6} {p['start']} -> {p['end']}   "
                     f"{p.get('hook','')[:48]}" for p in shown[:50])
if st.sidebar.button("Copy timestamps (visible)"):
    st.sidebar.code(ts_block())
st.sidebar.markdown(f"**{len(ranked)} promos** across {len(data.get('per_episode', {}))} episodes.")
