"""Генерация автономного HTML-экрана просмотра сети.

Один файл, открывается двойным кликом, работает офлайн: cytoscape вшит в страницу,
данные встроены как JSON. Ни сервера, ни сборки — жюри и коллегам ничего ставить не нужно.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import ROLE_RU

ASSETS = Path(__file__).parent / "assets"

# Три насыщенных тона — только для ролей, требующих действия аналитика; остальное
# нейтрально. Форма несёт роль вторым каналом, чтобы цвет не был единственным.
ROLE_STYLE = {
    "coordinator":        {"color": "#2a78d6", "shape": "diamond",         "size": 34},
    "consolidator":       {"color": "#eb6834", "shape": "ellipse",         "size": 26},
    "distributor":        {"color": "#1baf7a", "shape": "triangle",        "size": 26},
    "transit":            {"color": "#898781", "shape": "round-rectangle", "size": 18},
    "terminal":           {"color": "#c3c2b7", "shape": "ellipse",         "size": 14},
    "terminal_unverified": {"color": "#c3c2b7", "shape": "hexagon",        "size": 14},
    "peripheral":         {"color": "#e1e0d9", "shape": "ellipse",         "size": 10},
}
ROLE_RU_FULL = {**ROLE_RU, "terminal_unverified": "Сток не подтверждён (обрыв обхода)"}

NODE_FIELDS = [
    "gid", "role", "role_score", "cluster_id", "priority_score", "evidence",
    "depth", "is_seed", "in_deg", "out_deg", "in_kzt", "out_kzt",
    "pass_through", "seed_sources", "betweenness", "depth_truncated",
]


def build(features: pd.DataFrame, edges: pd.DataFrame, out_path: Path) -> Path:
    nodes = features[NODE_FIELDS].copy()
    nodes["is_seed"] = nodes.is_seed.astype(bool)
    nodes["depth_truncated"] = nodes.depth_truncated.astype(bool)
    nodes["pass_through"] = nodes.pass_through.where(nodes.pass_through.notna(), None)

    payload = {
        "nodes": nodes.to_dict("records"),
        "edges": edges[["src", "dst", "sum_kzt", "n_tx"]].to_dict("records"),
        "roleStyle": ROLE_STYLE,
        "roleRu": ROLE_RU_FULL,
    }
    html = _TEMPLATE.replace("/*__CYTOSCAPE__*/", (ASSETS / "cytoscape.min.js").read_text(encoding="utf-8"))
    html = html.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False, default=str))
    out_path.write_text(html, encoding="utf-8")
    return out_path


_TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Граф денег — схема сети</title>
<style>
  :root {
    --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
    --muted:#898781; --hair:rgba(11,11,11,.10); --accent:#2a78d6;
  }
  * { box-sizing:border-box; }
  body { margin:0; height:100vh; display:flex; flex-direction:column;
         background:var(--plane); color:var(--ink);
         font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
  header { display:flex; align-items:center; gap:16px; padding:12px 18px; flex-wrap:wrap; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  header .sub { color:var(--muted); font-size:12px; }
  .chip { background:var(--surface); border:1px solid var(--hair); border-radius:10px;
          padding:4px 10px; font-size:12px; }
  .chip b { font-variant-numeric:tabular-nums; }
  main { flex:1; display:flex; gap:12px; padding:0 18px 18px; min-height:0; }
  .panel { background:var(--surface); border:1px solid var(--hair); border-radius:14px; }
  #left { width:300px; display:flex; flex-direction:column; gap:10px; }
  #controls { padding:12px; }
  #controls label { display:block; font-size:11px; text-transform:uppercase;
                    letter-spacing:.04em; color:var(--muted); margin:10px 0 4px; }
  #controls label:first-child { margin-top:0; }
  input,select { width:100%; padding:8px 10px; border:1px solid var(--hair);
                 border-radius:9px; background:var(--plane); font:inherit; color:inherit; }
  input:focus,select:focus { outline:2px solid rgba(42,120,214,.25); }
  #toplist { flex:1; overflow:auto; padding:8px; }
  #toplist h3 { margin:4px 6px 8px; font-size:11px; text-transform:uppercase;
                letter-spacing:.04em; color:var(--muted); }
  .row { padding:7px 9px; border-radius:9px; cursor:pointer; }
  .row:hover { background:rgba(11,11,11,.04); }
  .row.on { background:rgba(42,120,214,.10); }
  .row .g { font-variant-numeric:tabular-nums; font-size:12px; font-weight:600; }
  .row .m { font-size:11px; color:var(--muted); }
  #center { flex:1; display:flex; flex-direction:column; gap:10px; min-width:0; }
  #cy { flex:1; border-radius:14px; background:var(--surface); border:1px solid var(--hair); }
  #legend { display:flex; gap:14px; flex-wrap:wrap; padding:9px 14px; font-size:12px; }
  #legend span { display:inline-flex; align-items:center; gap:6px; color:var(--ink2); }
  .dot { width:11px; height:11px; display:inline-block; }
  #right { width:330px; padding:14px; overflow:auto; }
  #right h2 { font-size:14px; margin:0 0 2px; font-variant-numeric:tabular-nums; }
  .badge { display:inline-block; padding:2px 9px; border-radius:11px; font-size:11px;
           font-weight:600; color:#fff; margin:6px 0 10px; }
  .ev { background:var(--plane); border:1px solid var(--hair); border-radius:10px;
        padding:9px 11px; font-size:12.5px; line-height:1.5; }
  table { width:100%; border-collapse:collapse; margin-top:10px; font-size:12px; }
  td { padding:4px 0; border-top:1px solid var(--hair); }
  td:last-child { text-align:right; font-variant-numeric:tabular-nums; font-weight:500; }
  .hint { color:var(--muted); font-size:12px; }
  .warn { margin-top:10px; padding:8px 10px; border-radius:9px; font-size:12px;
          background:rgba(250,178,25,.15); }
  h4 { margin:14px 0 4px; font-size:11px; text-transform:uppercase;
       letter-spacing:.04em; color:var(--muted); }
</style>
</head>
<body>
<header>
  <div>
    <h1>Граф денег — схема сети</h1>
    <div class="sub">Направление потоков, роли узлов и поиск по gid</div>
  </div>
  <span class="chip">узлов <b id="c-nodes"></b></span>
  <span class="chip">рёбер <b id="c-edges"></b></span>
  <span class="chip">кластеров <b id="c-clusters"></b></span>
  <span class="chip">на схеме <b id="c-shown"></b></span>
</header>

<main>
  <div id="left">
    <div class="panel" id="controls">
      <label for="q">Поиск по gid</label>
      <input id="q" placeholder="например 100000003684369100" autocomplete="off">
      <label for="role">Роль</label>
      <select id="role"><option value="">все роли</option></select>
      <label for="cluster">Кластер</label>
      <select id="cluster"><option value="">все кластеры</option></select>
      <label for="scope">Что показывать</label>
      <select id="scope">
        <option value="top">топ приоритета и их окружение</option>
        <option value="hops2">окружение выбранного узла, 2 колена</option>
        <option value="hops1">окружение выбранного узла, 1 колено</option>
      </select>
    </div>
    <div class="panel" id="toplist"><h3>Кого смотреть первым</h3><div id="rows"></div></div>
  </div>

  <div id="center">
    <div id="cy"></div>
    <div class="panel" id="legend"></div>
  </div>

  <div class="panel" id="right">
    <p class="hint">Выберите узел на схеме или в списке слева.</p>
  </div>
</main>

<script>/*__CYTOSCAPE__*/</script>
<script>
const DATA = /*__DATA__*/;
const byId = new Map(DATA.nodes.map(n => [String(n.gid), n]));
const adj = new Map();
for (const n of DATA.nodes) adj.set(String(n.gid), new Set());
for (const e of DATA.edges) {
  adj.get(String(e.src))?.add(String(e.dst));
  adj.get(String(e.dst))?.add(String(e.src));
}
const MAX_RENDER = 450;

const fmt = x => new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(x);
const money = x => (x >= 1e6 ? (x/1e6).toFixed(1)+' млн ₸' : fmt(x)+' ₸');

document.getElementById('c-nodes').textContent = fmt(DATA.nodes.length);
document.getElementById('c-edges').textContent = fmt(DATA.edges.length);
document.getElementById('c-clusters').textContent =
  new Set(DATA.nodes.map(n => n.cluster_id)).size;

// --- фильтры ---
const roleSel = document.getElementById('role'), clusterSel = document.getElementById('cluster');
const roleOrder = ['coordinator','consolidator','distributor','transit','terminal','terminal_unverified','peripheral'];
const present = roleOrder.filter(r => DATA.nodes.some(n => n.role === r));
for (const r of present) roleSel.add(new Option(`${DATA.roleRu[r]||r}`, r));
const clusters = [...new Set(DATA.nodes.map(n => n.cluster_id))]
  .sort((a,b) => DATA.nodes.filter(n=>n.cluster_id===b).length - DATA.nodes.filter(n=>n.cluster_id===a).length);
for (const c of clusters) clusterSel.add(new Option(`#${c} (${DATA.nodes.filter(n=>n.cluster_id===c).length} узлов)`, c));

// --- легенда ---
document.getElementById('legend').innerHTML = present.map(r => {
  const s = DATA.roleStyle[r];
  const radius = s.shape === 'ellipse' ? '50%' : (s.shape === 'diamond' ? '2px' : '2px');
  const rot = s.shape === 'diamond' ? 'transform:rotate(45deg);' : '';
  return `<span><i class="dot" style="background:${s.color};border-radius:${radius};${rot}"></i>`
       + `${DATA.roleRu[r]||r} · ${DATA.nodes.filter(n=>n.role===r).length}</span>`;
}).join('');

// --- список приоритета ---
let selected = null;
const ranked = [...DATA.nodes].sort((a,b) => b.priority_score - a.priority_score);
function renderRows(list) {
  document.getElementById('rows').innerHTML = list.slice(0,60).map((n,i) =>
    `<div class="row${String(n.gid)===selected?' on':''}" data-gid="${n.gid}">
       <div class="g">${i+1}. ${n.gid}</div>
       <div class="m">${DATA.roleRu[n.role]||n.role} · приоритет ${n.priority_score.toFixed(3)}</div>
     </div>`).join('');
  document.querySelectorAll('.row').forEach(el =>
    el.onclick = () => select(el.dataset.gid, true));
}

// --- граф ---
const cy = cytoscape({
  container: document.getElementById('cy'),
  style: [
    { selector:'node', style:{
        'background-color':'data(color)', 'shape':'data(shape)', 'width':'data(size)',
        'height':'data(size)', 'border-width':2, 'border-color':'#fcfcfb',
        'font-size':9, 'color':'#52514e', 'text-valign':'bottom', 'text-margin-y':4,
        'font-family':'system-ui, sans-serif' } },
    { selector:'node[?imp]', style:{ 'label':'data(short)' } },
    { selector:'node[?seed]', style:{ 'border-color':'#0b0b0b', 'border-width':2 } },
    { selector:'node.sel', style:{ 'border-color':'#2a78d6', 'border-width':4, 'label':'data(gid)' } },
    { selector:'edge', style:{
        'width':'data(w)', 'line-color':'#c3c2b7', 'target-arrow-color':'#c3c2b7',
        'target-arrow-shape':'triangle', 'arrow-scale':.8, 'curve-style':'bezier',
        'opacity':.75 } },
    { selector:'edge.hl', style:{ 'line-color':'#2a78d6', 'target-arrow-color':'#2a78d6',
        'opacity':1, 'width':3 } },
    { selector:'edge.hl.lbl', style:{ 'label':'data(label)', 'font-size':9, 'color':'#52514e',
        'text-background-color':'#fcfcfb', 'text-background-opacity':1,
        'text-background-padding':2 } },
  ],
  layout:{ name:'preset' }, wheelSensitivity:.25,
});

function subgraph() {
  const scope = document.getElementById('scope').value;
  const role = roleSel.value, cluster = clusterSel.value;
  let base;
  if (scope !== 'top' && selected) {
    const depth = scope === 'hops2' ? 2 : 1;
    base = new Set([selected]);
    let frontier = new Set([selected]);
    for (let d = 0; d < depth; d++) {
      const next = new Set();
      for (const id of frontier) for (const nb of (adj.get(id)||[]))
        if (!base.has(nb)) { base.add(nb); next.add(nb); }
      frontier = next;
    }
  } else {
    let pool = ranked;
    if (role) pool = pool.filter(n => n.role === role);
    if (cluster !== '') pool = pool.filter(n => String(n.cluster_id) === cluster);
    base = new Set();
    for (const n of pool) {
      if (base.size > MAX_RENDER) break;
      base.add(String(n.gid));
      for (const nb of (adj.get(String(n.gid))||[])) base.add(nb);
    }
    if (selected) base.add(selected);
  }
  return base;
}

function draw() {
  const keep = subgraph();
  const els = [];
  for (const id of keep) {
    const n = byId.get(id); if (!n) continue;
    const s = DATA.roleStyle[n.role] || DATA.roleStyle.peripheral;
    const important = ['coordinator','consolidator','distributor'].includes(n.role);
    els.push({ data:{ id, gid:n.gid, short:String(n.gid).slice(-5),
      color:s.color, shape:s.shape, size:s.size, seed:n.is_seed ? 1 : 0,
      imp: important ? 1 : 0 } });
  }
  for (const e of DATA.edges) {
    const a = String(e.src), b = String(e.dst);
    if (keep.has(a) && keep.has(b))
      els.push({ data:{ id:a+'>'+b, source:a, target:b,
        w: Math.min(1 + Math.log10(Math.max(e.sum_kzt,1))/2, 5), label: money(e.sum_kzt) } });
  }
  cy.elements().remove();
  cy.add(els);
  cy.layout({ name:'cose', animate:false, nodeRepulsion:9000, idealEdgeLength:70,
              padding:30, randomize:false }).run();
  document.getElementById('c-shown').textContent = fmt(keep.size);
  highlight();
}

function highlight() {
  cy.elements().removeClass('sel hl lbl');
  if (!selected) return;
  const node = cy.getElementById(selected);
  if (!node.length) return;
  node.addClass('sel');
  const edges = node.connectedEdges();
  edges.addClass('hl');
  // Суммы подписываем только когда связей немного — иначе веер превращается в кашу.
  if (edges.length <= 14) edges.addClass('lbl');
}

function select(gid, redraw) {
  selected = String(gid);
  const n = byId.get(selected);
  if (!n) { document.getElementById('right').innerHTML =
    '<p class="hint">Узел с таким gid не найден.</p>'; return; }
  card(n);
  if (redraw) draw(); else highlight();
  renderRows(currentList());
}

function card(n) {
  const s = DATA.roleStyle[n.role] || DATA.roleStyle.peripheral;
  const outs = DATA.edges.filter(e => String(e.src) === String(n.gid))
    .sort((a,b) => b.sum_kzt - a.sum_kzt).slice(0,6);
  const ins = DATA.edges.filter(e => String(e.dst) === String(n.gid))
    .sort((a,b) => b.sum_kzt - a.sum_kzt).slice(0,6);
  const link = e => `<div class="row" data-gid="${e}">${e}</div>`;
  document.getElementById('right').innerHTML = `
    <h2>${n.gid}</h2>
    <span class="badge" style="background:${s.color}">${DATA.roleRu[n.role]||n.role}</span>
    <div class="ev">${n.evidence}</div>
    ${n.depth_truncated ? '<div class="warn">Узел на 4-м колене: обход остановлен здесь, исходящие могли не попасть в выгрузку.</div>' : ''}
    <table>
      <tr><td>Приоритет</td><td>${n.priority_score.toFixed(3)}</td></tr>
      <tr><td>Уверенность в роли</td><td>${n.role_score.toFixed(3)}</td></tr>
      <tr><td>Колено / seed</td><td>${n.depth}${n.is_seed ? ' · seed' : ''}</td></tr>
      <tr><td>Кластер</td><td>#${n.cluster_id}</td></tr>
      <tr><td>Плательщиков → получателей</td><td>${n.in_deg} → ${n.out_deg}</td></tr>
      <tr><td>Принял</td><td>${money(n.in_kzt)}</td></tr>
      <tr><td>Отдал</td><td>${money(n.out_kzt)}</td></tr>
      <tr><td>Коэффициент пропуска</td><td>${n.pass_through==null?'—':Number(n.pass_through).toFixed(2)}</td></tr>
      <tr><td>Доходят от seed</td><td>${n.seed_sources}</td></tr>
      <tr><td>Посредничество</td><td>${Number(n.betweenness).toFixed(5)}</td></tr>
    </table>
    ${ins.length ? '<h4>Крупнейшие входящие</h4>' + ins.map(e =>
      `<div class="row" data-gid="${e.src}">${e.src} <span class="m">· ${money(e.sum_kzt)}</span></div>`).join('') : ''}
    ${outs.length ? '<h4>Крупнейшие исходящие</h4>' + outs.map(e =>
      `<div class="row" data-gid="${e.dst}">${e.dst} <span class="m">· ${money(e.sum_kzt)}</span></div>`).join('') : ''}`;
  document.querySelectorAll('#right .row').forEach(el =>
    el.onclick = () => select(el.dataset.gid, true));
}

function currentList() {
  const role = roleSel.value, cluster = clusterSel.value, q = document.getElementById('q').value.trim();
  let list = ranked;
  if (role) list = list.filter(n => n.role === role);
  if (cluster !== '') list = list.filter(n => String(n.cluster_id) === cluster);
  if (q) list = list.filter(n => String(n.gid).includes(q));
  return list;
}

cy.on('tap', 'node', evt => select(evt.target.data('gid'), false));
document.getElementById('q').oninput = e => {
  const q = e.target.value.trim();
  renderRows(currentList());
  if (byId.has(q)) {
    document.getElementById('scope').value = 'hops2';
    select(q, true);
  }
};
roleSel.onchange = clusterSel.onchange = () => { renderRows(currentList()); draw(); };
document.getElementById('scope').onchange = draw;

// Deep link для демо: viewer.html#gid=100000003684369100 открывает нужный узел сразу.
function fromHash() {
  const m = location.hash.match(/gid=(\d+)/);
  return m && byId.has(m[1]) ? m[1] : null;
}
renderRows(ranked);
const start = fromHash();
if (start) {
  document.getElementById('scope').value = 'hops2';
  document.getElementById('q').value = start;
  select(start, true);
} else {
  draw();
  select(String(ranked[0].gid), true);
}
window.addEventListener('hashchange', () => {
  const g = fromHash();
  if (g) { document.getElementById('scope').value = 'hops2'; select(g, true); }
});
</script>
</body>
</html>
"""
