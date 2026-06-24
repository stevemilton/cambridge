#!/usr/bin/env python3
"""Forecasting-journal dashboard — a local web UI for proving your edge.

    python3 dashboard.py        # then open http://127.0.0.1:8765

Add forecasts, resolve them with a click, and watch your Brier-vs-market edge,
calibration, and per-category breakdown update live. Stdlib only — no install.
The journal is the same forecasts.json the CLI uses, so the two interchange.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from quantloop.journal import Journal
from quantloop.webapi import dispatch
from quantloop.connectors.betfair_read import BetfairReadClient

_BETFAIR = {"client": None, "tried": False}


def _betfair_client():
    """Lazily build the read-only Betfair client from env vars (cached)."""
    if not _BETFAIR["tried"]:
        _BETFAIR["tried"] = True
        try:
            _BETFAIR["client"] = BetfairReadClient.from_env()
        except Exception:
            _BETFAIR["client"] = None
    return _BETFAIR["client"]

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "forecasts.json")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forecasting Journal</title>
<style>
  :root { --bg:#0f1115; --card:#181b22; --line:#272b35; --txt:#e8eaed; --mut:#9aa3b2;
          --grn:#3fb950; --red:#f85149; --acc:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }
  header { padding:22px 26px; border-bottom:1px solid var(--line); }
  h1 { margin:0; font-size:20px; } .sub { color:var(--mut); font-size:13px; margin-top:4px; }
  main { max-width:1000px; margin:0 auto; padding:24px; display:grid; gap:20px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.06em; color:var(--mut);
       margin:0 0 14px; }
  form { display:grid; grid-template-columns:2fr 90px 110px 110px 1fr auto; gap:10px; align-items:end; }
  label { display:block; font-size:11px; color:var(--mut); margin-bottom:4px; }
  input, select, button { background:#0d0f14; color:var(--txt); border:1px solid var(--line);
       border-radius:8px; padding:9px 10px; font-size:14px; width:100%; }
  button { cursor:pointer; }
  button.primary { background:var(--acc); color:#04101f; border:0; font-weight:600; }
  button.sm { padding:4px 9px; font-size:12px; width:auto; }
  .grn { color:var(--grn); } .red { color:var(--red); } .mut { color:var(--mut); }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th,td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }
  th { color:var(--mut); font-weight:500; font-size:12px; }
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
  .stat { background:#0d0f14; border:1px solid var(--line); border-radius:10px; padding:14px; }
  .stat .v { font-size:24px; font-weight:600; } .stat .k { color:var(--mut); font-size:12px; }
  .verdict { margin-top:14px; padding:12px 14px; border-radius:8px; background:#0d0f14;
             border:1px solid var(--line); }
  .bar { height:8px; background:#0d0f14; border-radius:5px; overflow:hidden; display:inline-block;
         width:120px; vertical-align:middle; }
  .bar > i { display:block; height:100%; background:var(--acc); }
  .tag { background:#0d0f14; border:1px solid var(--line); border-radius:20px; padding:1px 9px;
         font-size:12px; color:var(--mut); }
  .empty { color:var(--mut); padding:10px 0; }
  @media (max-width:760px){ form{grid-template-columns:1fr 1fr;} .stats{grid-template-columns:1fr 1fr;} }
</style></head>
<body>
<header><h1>Forecasting Journal</h1>
  <div class="sub">Log your probability vs the market. Beat it over ~20+ markets and you have an edge.</div>
</header>
<main>
  <div class="card">
    <h2>Import from Betfair (read-only)</h2>
    <div style="display:flex; gap:10px">
      <input id="bfq" placeholder="search markets, e.g. World Cup" style="flex:1">
      <button class="primary sm" style="width:auto" onclick="betfairSearch()">Search</button>
    </div>
    <div id="bfresults" style="margin-top:12px"></div>
    <div class="sub" style="margin-top:8px">Pulls live markets &amp; odds only — never places a bet. Click a runner to fill the form below.</div>
  </div>

  <div class="card">
    <h2>Log a forecast</h2>
    <form id="f">
      <div style="grid-column:1/2"><label>Market question</label><input id="q" placeholder="Will Brazil win the World Cup?" required></div>
      <div><label>Your %</label><input id="yp" type="number" min="0" max="100" step="1" placeholder="60" required></div>
      <div><label>Market</label><input id="mp" type="number" min="0" step="0.01" placeholder="2.10" required></div>
      <div><label>Market is…</label><select id="mode"><option value="odds">decimal odds</option><option value="pct">a %</option></select></div>
      <div><label>Category</label><input id="cat" placeholder="wc-specials"></div>
      <div><button class="primary" type="submit">Add</button></div>
    </form>
    <div id="addnote" class="sub" style="margin-top:8px"></div>
  </div>

  <div class="card">
    <h2>Your edge</h2>
    <div id="score"></div>
  </div>

  <div class="card">
    <h2>Open forecasts</h2>
    <div id="open"></div>
  </div>

  <div class="card">
    <h2>Resolved</h2>
    <div id="resolved"></div>
  </div>
</main>
<script>
const pct = x => (x*100).toFixed(0)+"%";
async function api(method, path, body){
  const r = await fetch(path,{method, headers:{"Content-Type":"application/json"},
    body: body?JSON.stringify(body):undefined});
  return r.json();
}
async function load(){
  const {forecasts} = await api("GET","/api/forecasts");
  const score = await api("GET","/api/score");
  renderOpen(forecasts.filter(f=>f.status==="open"));
  renderResolved(forecasts.filter(f=>f.status==="resolved"));
  renderScore(score);
}
function renderOpen(rows){
  const el = document.getElementById("open");
  if(!rows.length){ el.innerHTML='<div class="empty">No open forecasts. Add one above.</div>'; return; }
  el.innerHTML = `<table><tr><th>ID</th><th>Question</th><th>You</th><th>Market</th><th>Category</th><th></th></tr>`+
    rows.map(f=>`<tr><td class="mut">${f.id}</td><td>${esc(f.question)}</td><td>${pct(f.your_prob)}</td>
      <td>${pct(f.market_price)}</td><td><span class="tag">${esc(f.category||"–")}</span></td>
      <td style="white-space:nowrap">
        <button class="sm" onclick="resolve('${f.id}',1)">✓ YES</button>
        <button class="sm" onclick="resolve('${f.id}',0)">✗ NO</button>
        <button class="sm" onclick="del('${f.id}')">🗑</button></td></tr>`).join("")+`</table>`;
}
function renderResolved(rows){
  const el = document.getElementById("resolved");
  if(!rows.length){ el.innerHTML='<div class="empty">Nothing resolved yet.</div>'; return; }
  el.innerHTML = `<table><tr><th>ID</th><th>Question</th><th>You</th><th>Market</th><th>Result</th><th>Category</th></tr>`+
    rows.map(f=>`<tr><td class="mut">${f.id}</td><td>${esc(f.question)}</td><td>${pct(f.your_prob)}</td>
      <td>${pct(f.market_price)}</td><td class="${f.outcome?'grn':'red'}">${f.outcome?'YES':'NO'}</td>
      <td><span class="tag">${esc(f.category||"–")}</span></td></tr>`).join("")+`</table>`;
}
function renderScore(s){
  const el = document.getElementById("score");
  if(!s.resolved){ el.innerHTML='<div class="empty">'+esc(s.verdict||"No resolved forecasts yet.")+'</div>'; return; }
  const edge = s.edge_vs_market, ec = edge>0?'grn':'red';
  let html = `<div class="stats">
    <div class="stat"><div class="v">${s.resolved}</div><div class="k">resolved</div></div>
    <div class="stat"><div class="v">${s.your_brier}</div><div class="k">your Brier (lower=better)</div></div>
    <div class="stat"><div class="v">${s.market_brier}</div><div class="k">market Brier</div></div>
    <div class="stat"><div class="v ${ec}">${edge>0?'+':''}${edge}</div><div class="k">edge vs market</div></div>
  </div>`;
  if(s.calibration && s.calibration.length){
    html += `<h2 style="margin-top:18px">Calibration</h2><table>
      <tr><th>You said</th><th>Actually happened</th><th>n</th></tr>`+
      s.calibration.map(c=>`<tr><td>${c.bucket}</td>
        <td><span class="bar"><i style="width:${(c.actually_happened*100).toFixed(0)}%"></i></span>
        ${pct(c.actually_happened)}</td><td class="mut">${c.n}</td></tr>`).join("")+`</table>`;
  }
  const cats = Object.entries(s.by_category||{});
  if(cats.length>1){
    html += `<h2 style="margin-top:18px">By category</h2><table>
      <tr><th>Category</th><th>n</th><th>You</th><th>Market</th><th>Edge</th></tr>`+
      cats.map(([c,m])=>{const e=(m.market_brier-m.your_brier).toFixed(4);
        return `<tr><td>${esc(c)}</td><td class="mut">${m.n}</td><td>${m.your_brier}</td>
        <td>${m.market_brier}</td><td class="${e>0?'grn':'red'}">${e>0?'+':''}${e}</td></tr>`;}).join("")+`</table>`;
  }
  html += `<div class="verdict">${esc(s.verdict)}</div>`;
  el.innerHTML = html;
}
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function betfairSearch(){
  const q = document.getElementById("bfq").value.trim();
  const el = document.getElementById("bfresults");
  if(!q){ el.innerHTML=""; return; }
  el.innerHTML = '<div class="mut">searching…</div>';
  const r = await api("GET","/api/betfair/search?q="+encodeURIComponent(q));
  if(r.error){ el.innerHTML='<div class="red">'+esc(r.error)+'</div>'; return; }
  if(!r.markets || !r.markets.length){ el.innerHTML='<div class="empty">No markets found.</div>'; return; }
  el.innerHTML = r.markets.map(m=>`<div style="margin-bottom:10px">
    <div style="font-weight:600;margin-bottom:4px">${esc(m.title)}</div>
    <div>`+ m.runners.map(rn=>{
      const odds = rn.odds==null ? "n/a" : rn.odds;
      const prob = rn.prob==null ? "" : " ("+pct(rn.prob)+")";
      const dis = rn.odds==null ? "disabled" : "";
      return `<button class="sm" style="margin:2px" ${dis}
        onclick='fillFromBetfair(${JSON.stringify(m.title)},${JSON.stringify(rn.name)},${rn.odds})'>
        ${esc(rn.name)} @ ${odds}${prob}</button>`;
    }).join("") +`</div></div>`).join("");
}
function fillFromBetfair(title, runner, odds){
  document.getElementById("q").value = title + " — " + runner;
  document.getElementById("mp").value = odds;
  document.getElementById("mode").value = "odds";
  document.getElementById("yp").focus();
  document.getElementById("addnote").innerHTML = "filled from Betfair — now enter YOUR probability and Add";
}
async function resolve(id,outcome){ await api("POST",`/api/forecasts/${id}/resolve`,{outcome}); load(); }
async function del(id){ if(confirm("Delete "+id+"?")){ await api("DELETE",`/api/forecasts/${id}`); load(); } }
document.getElementById("f").addEventListener("submit", async e=>{
  e.preventDefault();
  const mode = document.getElementById("mode").value;
  const body = { question: document.getElementById("q").value,
    your_prob: document.getElementById("yp").value,
    market_price: document.getElementById("mp").value,
    odds: mode==="odds",
    category: document.getElementById("cat").value };
  const r = await api("POST","/api/forecasts",body);
  const note = document.getElementById("addnote");
  if(r.error){ note.innerHTML='<span class="red">'+esc(r.error)+'</span>'; return; }
  note.innerHTML='logged '+r.id+': you '+pct(r.your_prob)+' vs market '+pct(r.market_price);
  e.target.reset(); load();
});
load();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    journal_path = DEFAULT_PATH

    def log_message(self, *a):  # quiet
        pass

    def _send(self, status, payload, ctype="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if self.path.startswith("/api/betfair/search"):
            return self._betfair_search()
        status, result = dispatch("GET", self.path, None, Journal(self.journal_path))
        self._send(status, result)

    def _betfair_search(self):
        client = _betfair_client()
        if client is None:
            return self._send(200, {"error": "Betfair not configured. Set BETFAIR_APP_KEY, "
                                             "BETFAIR_USERNAME and BETFAIR_PASSWORD, then restart."})
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
        try:
            return self._send(200, {"markets": client.search_markets(q)})
        except Exception as exc:  # surface login/network errors to the UI, don't crash
            return self._send(200, {"error": f"Betfair: {exc}"})

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_POST(self):
        status, result = dispatch("POST", self.path, self._body(), Journal(self.journal_path))
        self._send(status, result)

    def do_DELETE(self):
        status, result = dispatch("DELETE", self.path, None, Journal(self.journal_path))
        self._send(status, result)


def main() -> None:
    ap = argparse.ArgumentParser(description="Forecasting-journal dashboard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--file", default=DEFAULT_PATH, help="journal JSON path")
    args = ap.parse_args()

    Handler.journal_path = args.file
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Forecasting dashboard → {url}   (journal: {os.path.relpath(args.file, HERE)})")
    print("Open that URL in your browser. Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
