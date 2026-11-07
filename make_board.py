"""Generate a self-contained, dependency-free promo board (board.html).

    python make_board.py  [output_dir]

Reads <output_dir>/promos_all.json and inlines it into a single HTML file with
vanilla-JS search / filters. Open board.html in any browser — no server, no
npm, no Python. This is the most robust "open the link" prototype artifact:
drop the repo on GitHub Pages and it just works.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kuku Promo Finder</title>
<style>
:root{--bg:#0f1117;--card:#171a23;--line:#2a2f3a;--tx:#e6e9ef;--mut:#8a92a3;--ok:#3fb950;--rev:#d29922;--rej:#f85149;--ac:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;background:#141824;border-bottom:1px solid var(--line);padding:14px 20px;z-index:9}
h1{font-size:19px;margin:0 0 4px}header .sub{color:var(--mut);font-size:13px}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.bar input,.bar select{background:#0c0f16;border:1px solid var(--line);color:var(--tx);padding:8px 10px;border-radius:8px;font-size:14px}
.bar input{flex:1;min-width:180px}
.legend{color:var(--mut);font-size:13px;margin-top:10px}
.wrap{max-width:960px;margin:0 auto;padding:18px}
.q{color:var(--mut);font-size:13px;margin:0 0 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 12px}
.card .top{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.dot{width:10px;height:10px;border-radius:50%}.dot.ok{background:var(--ok)}.dot.review{background:var(--rev)}.dot.reject{background:var(--rej)}
.ep{font-weight:600}.ts{font-family:ui-monospace,monospace;color:var(--ac)}
.score{margin-left:auto;font-size:13px;color:var(--mut)}
.lbl{color:var(--mut);font-size:11px;letter-spacing:.04em;text-transform:uppercase;margin:8px 0 2px}
pre{background:#0c0f16;border:1px solid var(--line);border-radius:8px;padding:8px;margin:4px 0;font-size:12.5px;white-space:pre-wrap}
.cues{color:var(--mut);font-size:12.5px}
.warn{color:var(--rev);font-size:12.5px}
.copy{width:100%}
</style></head><body>
<header>
 <h1>🎬 Kuku Promo Finder</h1>
 <div class="sub">Best 20–60s promo clips, ranked & explained · raw data inlined · no dependencies</div>
 <div class="bar">
  <input id="q" placeholder="Search hook / cliff / cue…">
  <select id="ep"></select>
  <select id="verdict"><option value="">All verdicts</option><option value="ok">🟢 ok</option><option value="review">🟡 review</option><option value="reject">🔴 reject</option></select>
  <input id="min" type="number" min="0" max="100" placeholder="min score" style="max-width:110px">
 </div>
 <div class="legend" id="legend"></div>
</header>
<div class="wrap"><p class="q" id="count"></p><div id="cards"></div></div>
<script>
const DATA = __DATA__;
const P = DATA.ranked;
const epSel = document.getElementById('ep');
const eps = [...new Set(P.map(p=>p.episode))].sort((a,b)=>a-b);
epSel.innerHTML = '<option value="">All episodes</option>'+eps.map(e=>`<option>${e}</option>`).join('');
document.getElementById('legend').textContent =
  `Quality: ${DATA.quality.ok} ok · ${DATA.quality.review} review · ${DATA.quality.reject} reject  |  ${P.length} promos / ${Object.keys(DATA.per_episode).length} episodes`;
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function render(){
 const q=document.getElementById('q').value.toLowerCase();
 const ep=epSel.value, vd=document.getElementById('verdict').value, mn=+document.getElementById('min').value||0;
 const list=P.filter(p=>
   (ep===''||String(p.episode)===ep)&&
   (vd===''||(p.audit&&p.audit.verdict)===vd)&&
   (p.score||0)>=mn&&
   (!q||(JSON.stringify([p.hook,p.cliffhanger,p.why,(p.cues||[]).map(c=>c.name||c.family),p.flags||[]]).toLowerCase().includes(q)))
 );
 document.getElementById('count').textContent=`Showing ${list.length} of ${P.length}`;
 document.getElementById('cards').innerHTML=list.map(p=>{
   const v=(p.audit&&p.audit.verdict)||'ok';
   const flags=[...(p.flags||[]),...((p.audit&&p.audit.soft_flags)||[])];
   const cues=(p.cues||[]).slice(0,5).map(c=>esc(c.name||c.family)).join(' · ');
   return `<div class="card">
     <div class="top"><span class="dot ${v}"></span>
       <span class="ep">#${p.global_rank} · EP ${p.episode}</span>
       <span class="ts">${p.start} → ${p.end}</span>
       <span class="ts">${p.duration_s}s</span>
       <span class="score">score ${p.score} · hook ${p.hook_score} · cliff ${p.cliffhanger_score} · stand ${p.standalone_score}</span>
     </div>
     <div class="lbl">Hook</div><div>${esc(p.hook)}</div>
     <div class="lbl">Cliffhanger</div><div>${esc(p.cliffhanger)}</div>
     <div class="lbl">Why it works</div><div>${esc(p.why)}</div>
     <div class="lbl">Opens on / cuts on</div>
     <pre>${esc(p.hook_source)}   ⟶   ${esc(p.cliffhanger_source)}</pre>
     ${cues?`<div class="cues">cues: ${cues}</div>`:''}
     ${flags.length?`<div class="warn">⚠ ${flags.map(esc).join(' · ')}</div>`:''}
   </div>`;
 }).join('');
}
['q','ep','verdict','min'].forEach(id=>document.getElementById(id).addEventListener('input',render));
render();
</script></body></html>
"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output")
    src = out / "promos_all.json"
    if not src.exists():
        src = Path("promos_all.json")
    data = json.loads(src.read_text())
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    dst = out / "board.html"
    dst.write_text(html, encoding="utf-8")
    print(f"wrote {dst}  ({dst.stat().st_size//1024} KB, {len(data['ranked'])} promos inlined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
