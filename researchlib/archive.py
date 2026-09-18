#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 每日结构化存档 + 日历网页。

目录结构（在用户的 Documents 下，便于自己翻看与长期备份）：

  ~/Documents/daily/
    ├── README.md              说明
    ├── index.json             所有日期的索引（网页日历读它）
    ├── site/index.html        日历回顾网页（离线可用，无外部依赖）
    ├── 2026-09-18.json        当天的结构化数据（论文/简介/简报/经典回顾）
    └── 2026-09-18.md          当天的 Markdown 版

网页是**纯静态**的：数据全部通过 fetch() 读同目录的 index.json 与 <日期>.json。
注意用 file:// 打开时浏览器可能拦截 fetch（CORS），所以 index.html 里同时内置了
「把所有数据内联进 HTML」的降级方案 —— build_site() 会把全部数据写进一个
site/data.js，网页优先读内联数据，彻底避开 file:// 的限制。
"""
import datetime as dt
import io
import json
import os

from . import config as C
from .util import log, save_json

ARCHIVE_DIR = os.path.join(C.HOME, 'Documents', 'daily')
SITE_DIR = os.path.join(ARCHIVE_DIR, 'site')
INDEX_JSON = os.path.join(ARCHIVE_DIR, 'index.json')


def _day_paths(day):
    return (os.path.join(ARCHIVE_DIR, f'{day}.json'),
            os.path.join(ARCHIVE_DIR, f'{day}.md'))


def save_day(day, brief, papers, prof, classic=None, classic_text=''):
    """把一天的结果写成结构化 json + 可读 md，并刷新索引与网页。"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    day = str(day)
    rec = {
        'date': day,
        'generated_text': brief.get('generated_text', ''),
        'window_days': brief.get('window_days'),
        'candidate_count': brief.get('candidate_count'),
        'picked_count': len(papers),
        'models': {'brief': C.MODEL_BRIEF, 'synth': C.MODEL_SYNTH},
        'agenda': brief.get('agenda', []),
        'brief_markdown': brief.get('markdown', ''),
        'classic': {
            'title': (classic or {}).get('title', ''),
            'authors': (classic or {}).get('authors', ''),
            'year': (classic or {}).get('year'),
            'venue': (classic or {}).get('venue', ''),
            'tags': (classic or {}).get('tags', []),
            'note': (classic or {}).get('note', ''),
            'review': classic_text,
        } if classic else None,
        'papers': papers,
    }
    jpath, mpath = _day_paths(day)
    save_json(jpath, rec)
    with open(mpath, 'w', encoding='utf-8') as f:
        f.write(render_md(rec))
    log(f'存档：{jpath}')
    rebuild_index()
    build_site()
    return jpath


def render_md(rec):
    L = [f"# 研究前沿日报 · {rec['date']}", '']
    if rec.get('agenda'):
        L += [f"**研究纲领**：{' · '.join(rec['agenda'])}", '']
    L += [f"候选 {rec.get('candidate_count')} 篇 → 入选 {rec.get('picked_count')} 篇"
          f"（窗口 {rec.get('window_days')} 天）", '']
    cl = rec.get('classic')
    if cl:
        L += ['---', '', f"## 📜 经典回顾：{cl['title']}", '',
              f"*{cl.get('authors','')}* — {cl.get('venue','')} ({cl.get('year','')})", '']
        if cl.get('note'):
            L += [f"> {cl['note']}", '']
        if cl.get('review'):
            L += [cl['review'], '']
    if rec.get('brief_markdown'):
        L += ['---', '', '## 📊 本周期简报', '', rec['brief_markdown'], '']
    L += ['---', '', '## 📄 论文简介', '']
    for p in rec.get('papers', []):
        L += [f"### {p.get('rank')}. {p.get('title')}", '',
              f"*{p.get('author_text','')}* — **{p.get('journal','')}** "
              f"({p.get('date','')}, 相关度 {p.get('score')})", '']
        if p.get('why'):
            L += [f"命中：{', '.join(p['why'])}", '']
        if p.get('summary'):
            L += [p['summary'], '']
        links = []
        if p.get('arxiv'):
            links.append(f"[arXiv](https://arxiv.org/abs/{p['arxiv']})")
        if p.get('doi'):
            links.append(f"[DOI](https://doi.org/{p['doi']})")
        if links:
            L += [' · '.join(links), '']
    return '\n'.join(L)


def rebuild_index():
    """扫描存档目录，重建 index.json（供网页日历读取）。"""
    days = []
    if os.path.isdir(ARCHIVE_DIR):
        for fn in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
            if not fn.endswith('.json') or fn == 'index.json':
                continue
            day = fn[:-5]
            try:
                with open(os.path.join(ARCHIVE_DIR, fn), encoding='utf-8') as f:
                    d = json.load(f)
            except Exception:
                continue
            # ISO 周标识：网页用它把同周的日期分组，标出「周刷新日」
            try:
                dt_obj = dt.date.fromisoformat(day)
                week = dt_obj.strftime('%G-W%V')
            except Exception:
                week = ''
            days.append({
                'date': day,
                'week': week,
                'picked': d.get('picked_count', 0),
                'candidates': d.get('candidate_count', 0),
                'brief': (d.get('brief_markdown') or '')[:160],
                'classic': (d.get('classic') or {}).get('title', ''),
                'classic_year': (d.get('classic') or {}).get('year'),
            })
    # 全部数据内联进 data.js，绕开 file:// 的 fetch 限制
    # 标出每周的「前沿刷新日」：同周里 picked 最多的那天
    best = {}
    for d in days:
        w = d.get('week') or ''
        if not w:
            continue
        if w not in best or (d.get('picked') or 0) > (best[w].get('picked') or 0):
            best[w] = d
    for d in days:
        w = d.get('week') or ''
        d['is_week_refresh'] = bool(w and best.get(w, {}).get('date') == d['date'])

    payload = {'index': days, 'days': {}}
    for d in days:
        try:
            with open(os.path.join(ARCHIVE_DIR, d['date'] + '.json'), encoding='utf-8') as f:
                payload['days'][d['date']] = json.load(f)
        except Exception:
            pass
    os.makedirs(SITE_DIR, exist_ok=True)
    with open(os.path.join(SITE_DIR, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.RW_DATA = ')
        json.dump(payload, f, ensure_ascii=False)
        f.write(';\n')
    save_json(INDEX_JSON, {'generated': dt.datetime.now().isoformat(timespec='seconds'),
                           'count': len(days), 'days': days})
    log(f'索引：{len(days)} 天')
    return days


def _katex_assets():
    """读取本地 KaTeX 的 css/js，并把数学字体拷进 site/katex/fonts。

    网页用 file:// 打开时浏览器会以 CORS 拒绝加载同目录的 .js/.css，
    所以样式与脚本必须**内联进 HTML**；字体走相对路径不受 CORS 限制。
    缺失时返回空串 —— 网页退回纯文本公式，不报错。
    """
    src = os.path.join(C.PKG_DIR, '_katex', 'package', 'dist')
    css = js = ''
    f = os.path.join(src, 'katex.min.css')
    if os.path.exists(f):
        css = io.open(f, encoding='utf-8').read()
    f = os.path.join(src, 'katex.min.js')
    if os.path.exists(f):
        js = io.open(f, encoding='utf-8').read()
    if not css and not js:
        log('KaTeX 缺失：网页公式按纯文本显示（python3 setup_katex.py 可补齐）')
        return '', ''
    fonts_src = os.path.join(src, 'fonts')
    fonts_dst = os.path.join(SITE_DIR, 'katex', 'fonts')
    if os.path.isdir(fonts_src):
        import shutil
        os.makedirs(fonts_dst, exist_ok=True)
        for fn in os.listdir(fonts_src):
            try:
                shutil.copy2(os.path.join(fonts_src, fn), os.path.join(fonts_dst, fn))
            except OSError:
                pass
    css = css.replace('url(fonts/', 'url(katex/fonts/')
    return css, js


def build_site():
    """生成离线日历回顾网页（KaTeX 内联，无外部网络依赖）。"""
    os.makedirs(SITE_DIR, exist_ok=True)
    kcss, kjs = _katex_assets()
    html = (_HTML.replace('__TITLE__', '研究前沿 · 日历回顾')
                 .replace('/*__KATEX_CSS__*/', kcss)
                 .replace('/*__KATEX_JS__*/', kjs))
    with open(os.path.join(SITE_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    readme = os.path.join(ARCHIVE_DIR, 'README.md')
    if not os.path.exists(readme):
        with open(readme, 'w', encoding='utf-8') as f:
            f.write(README_TEXT)
    return os.path.join(SITE_DIR, 'index.html')


README_TEXT = """# daily

由 `research_widget` 每天 06:00 自动写入，按日期结构化保存。

- `<日期>.json` — 当天的结构化数据（论文、中文简介、综合简报、经典回顾）
- `<日期>.md` — 同内容的 Markdown 版，方便直接阅读/检索
- `index.json` — 所有日期的索引
- `site/index.html` — **日历回顾网页**（双击即可离线打开）

网页没有任何外部依赖，数据内联在 `site/data.js`，可以随便拷贝/备份。
"""

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  /*__KATEX_CSS__*/
  .tex-fallback { font-family: "Noto Sans Mono", monospace; font-size: 0.94em;
                  background: rgba(127,127,127,0.14); padding: 0 4px; border-radius: 4px; }
  .tex-fallback.block { display: block; padding: 8px; margin: 8px 0; overflow-x: auto; }
  .katex-display { overflow-x: auto; overflow-y: hidden; padding: 2px 0; }
  :root {
    --bg: #14171c; --panel: #1d2129; --panel2: #232833;
    --fg: #e6e9ef; --dim: #98a1b3; --accent: #6cc7ff; --accent2: #7ee0a8;
    --line: #2e3542; --warn: #f5a623;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#f4f6fa; --panel:#fff; --panel2:#eef2f8; --fg:#1c2230;
            --dim:#5a6478; --accent:#0b6fb8; --accent2:#1a8f5a; --line:#d7deea; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font: 16px/1.7 -apple-system, "Noto Sans CJK SC", "Source Han Sans SC",
               "Microsoft YaHei", sans-serif; }
  header { padding:22px 26px 14px; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 4px; font-size:23px; }
  .sub { color:var(--dim); font-size:14px; }
  .wrap { display:grid; grid-template-columns: 320px 1fr; gap:20px;
          padding:20px 26px; align-items:start; }
  @media (max-width: 900px) { .wrap { grid-template-columns:1fr; } }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px;
          padding:16px 18px; margin-bottom:16px; }
  .cal-head { display:flex; justify-content:space-between; align-items:center;
              margin-bottom:10px; }
  .cal-head button { background:var(--panel2); color:var(--fg); border:1px solid var(--line);
              border-radius:8px; padding:4px 12px; font-size:15px; cursor:pointer; }
  .cal-head button:hover { border-color:var(--accent); color:var(--accent); }
  table.cal { width:100%; border-collapse:collapse; }
  table.cal th { color:var(--dim); font-weight:500; font-size:13px; padding:4px 0; }
  table.cal td { text-align:center; padding:3px 0; }
  .day { display:inline-flex; align-items:center; justify-content:center;
         width:34px; height:34px; border-radius:9px; cursor:default; font-size:14px;
         color:var(--dim); position:relative; }
  .day.has { cursor:pointer; color:var(--fg); background:var(--panel2);
             border:1px solid var(--line); font-weight:600; }
  .day.has:hover { border-color:var(--accent); color:var(--accent); }
  .day.sel { background:var(--accent); color:#0b0e13; border-color:var(--accent); }
  .day.today { outline:2px solid var(--accent2); outline-offset:1px; }
  .day .n { position:absolute; right:3px; bottom:1px; font-size:9px; color:var(--accent2); }
  .day.has .n { color:var(--accent2); }
  /* 周刷新日（该周跑过前沿抓取的那天）：角上标一个圆点 + 描边 */
  .day.week { border-color: var(--warn); }
  .day.week::after {
    content: ""; position: absolute; left: 3px; top: 3px;
    width: 6px; height: 6px; border-radius: 50%; background: var(--warn);
  }
  .legend { display:flex; gap:14px; font-size:12.5px; color:var(--dim);
            margin-top:10px; flex-wrap:wrap; }
  .legend i { display:inline-block; width:8px; height:8px; border-radius:50%;
              margin-right:5px; vertical-align:middle; }
  .paper { border-left:3px solid var(--accent); padding:2px 0 2px 12px; margin:14px 0; }
  .paper h3 { margin:0 0 3px; font-size:16.5px; line-height:1.45; }
  .meta { color:var(--dim); font-size:13px; margin-bottom:6px; }
  .why { color:var(--accent2); font-size:13px; margin-bottom:6px; }
  .sum { margin:6px 0; }
  .abs { color:var(--dim); font-size:13.5px; margin-top:8px; }
  details summary { cursor:pointer; color:var(--accent); font-size:13.5px; }
  a { color:var(--accent); }
  .tag { display:inline-block; background:var(--panel2); border:1px solid var(--line);
         border-radius:7px; padding:1px 8px; font-size:12.5px; color:var(--dim);
         margin-right:6px; }
  h2 { font-size:18px; margin:0 0 10px; color:var(--accent); }
  h3.sec { font-size:15.5px; color:var(--accent2); margin:18px 0 6px; }
  .brief p { margin:8px 0; }
  .classic { border-left:3px solid var(--warn); padding-left:12px; margin:14px 0; }
  .classictop { display:flex; align-items:center; gap:14px; flex-wrap:wrap;
                margin:10px 0 4px; }
  .btn { background:var(--panel2); color:var(--fg); border:1px solid var(--line);
         border-radius:8px; padding:5px 14px; font-size:14px; cursor:pointer; }
  .btn:hover { border-color:var(--accent); color:var(--accent); }
  .classic h3 { margin:0 0 3px; font-size:16.5px; }
  .empty { color:var(--dim); padding:30px 0; text-align:center; }
  ul.brief { margin:6px 0 6px 4px; padding-left:18px; }
  ul.brief li { margin:4px 0; }
</style>
</head>
<body>
<header>
  <h1>🔭 研究前沿 · 日历回顾</h1>
  <div class="sub" id="sub">加载中…</div>
</header>
<div class="wrap">
  <div>
    <div class="card">
      <div class="cal-head">
        <button id="prev">‹</button>
        <b id="ym"></b>
        <button id="next">›</button>
      </div>
      <table class="cal"><thead><tr>
        <th>一</th><th>二</th><th>三</th><th>四</th><th>五</th><th>六</th><th>日</th>
      </tr></thead><tbody id="cal"></tbody></table>
      <div class="legend">
        <span><i style="background:var(--warn)"></i>本周前沿刷新日</span>
        <span><i style="background:var(--accent2)"></i>右下角数字=入选论文数</span>
      </div>
    </div>
    <div class="card">
      <h2 style="font-size:15px">📜 当日经典回顾</h2>
      <div id="classicMini" class="sub">选择日期后显示</div>
    </div>
  </div>
  <div id="detail"><div class="empty">← 点击日历里有记录的日期</div></div>
</div>
<script src="data.js"></script>
<script>/*__KATEX_JS__*/</script>
<script>
const DATA = window.RW_DATA || {index: [], days: {}};
const byDate = {};
(DATA.index || []).forEach(d => byDate[d.date] = d);
const today = new Date();
let cur = new Date(today.getFullYear(), today.getMonth(), 1);
let sel = (DATA.index[0] || {}).date || null;

function pad(n){ return (n<10?'0':'')+n; }
function iso(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()); }

function renderCal(){
  const y = cur.getFullYear(), m = cur.getMonth();
  document.getElementById('ym').textContent = y + ' 年 ' + (m+1) + ' 月';
  const first = new Date(y, m, 1);
  let start = first.getDay(); start = (start === 0 ? 6 : start - 1);  // 周一为起始
  const days = new Date(y, m+1, 0).getDate();
  let html = '', cell = 0;
  html += '<tr>';
  for (let i=0;i<start;i++){ html += '<td></td>'; cell++; }
  for (let d=1; d<=days; d++){
    if (cell === 7){ html += '</tr><tr>'; cell = 0; }
    const key = y+'-'+pad(m+1)+'-'+pad(d);
    const has = byDate[key];
    const cls = ['day', has?'has':'', key===sel?'sel':'', key===iso(today)?'today':'',
                 (has && has.is_week_refresh) ? 'week' : ''].join(' ');
    const tip = has
      ? ((has.is_week_refresh ? '【本周前沿刷新】' : '') + has.picked + ' 篇 · ' + (has.classic||''))
      : '无记录';
    html += '<td><span class="'+cls+'" data-d="'+key+'" title="'+tip+'">'+d+
            (has ? '<span class="n">'+has.picked+'</span>' : '')+'</span></td>';
    cell++;
  }
  while (cell < 7){ html += '<td></td>'; cell++; }
  html += '</tr>';
  document.getElementById('cal').innerHTML = html;
  document.querySelectorAll('.day.has').forEach(el => {
    el.onclick = () => { sel = el.dataset.d; renderCal(); renderDetail(); };
  });
}

function esc(s){ return (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function md2html(md){
  // 极简 markdown：##/### 标题、- 列表、**粗体**、其余按段落
  // LaTeX 公式：先把 $$...$$ / $...$ / \(...\) 抽成占位符，转义之后
  // 再交回 KaTeX —— 这样公式里的 < > & \ 不会被 escape 破坏。
  const maths = [];
  let src = String(md || '');
  src = src.replace(/\$\$([^$]+?)\$\$/g, (m, e) => {
    maths.push({ tex: e.trim(), display: true }); return '@@MATH' + (maths.length - 1) + '@@';
  });
  src = src.replace(/\\\(([^)]+?)\\\)/g, (m, e) => {
    maths.push({ tex: e.trim(), display: false }); return '@@MATH' + (maths.length - 1) + '@@';
  });
  src = src.replace(/\$([^$\n]+?)\$/g, (m, e) => {
    maths.push({ tex: e.trim(), display: false }); return '@@MATH' + (maths.length - 1) + '@@';
  });
  const out = []; let inList = false;
  src.split('\n').forEach(raw => {
    const l = raw.trim();
    if (!l){ if (inList){ out.push('</ul>'); inList = false; } return; }
    if (l.startsWith('### ')){ out.push('<h3 class="sec">'+esc(l.slice(4))+'</h3>'); return; }
    if (l.startsWith('## ')){ if(inList){out.push('</ul>');inList=false;}
      out.push('<h3 class="sec">'+esc(l.slice(3))+'</h3>'); return; }
    if (l.startsWith('#')){ out.push('<h3 class="sec">'+esc(l.replace(/^#+\s*/,''))+'</h3>'); return; }
    if (/^[-*]\s+/.test(l)){
      if (!inList){ out.push('<ul class="brief">'); inList = true; }
      out.push('<li>'+bold(esc(l.replace(/^[-*]\s+/,'')))+'</li>'); return;
    }
    if (inList){ out.push('</ul>'); inList = false; }
    out.push('<p>'+bold(esc(l))+'</p>');
  });
  if (inList) out.push('</ul>');
  let html = out.join('');
  html = html.replace(/@@MATH(\d+)@@/g, (m, i) => {
    const item = maths[Number(i)];
    return item ? renderTex(item.tex, item.display) : m;
  });
  return html;
}

// KaTeX 渲染；不可用时退回等宽纯文本（file:// 下也能看）
function renderTex(tex, display){
  if (window.katex && typeof window.katex.renderToString === 'function') {
    try {
      return window.katex.renderToString(tex, { displayMode: !!display, throwOnError: false });
    } catch (e) { /* 落到降级分支 */ }
  }
  const safe = String(tex).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  return '<code class="tex-fallback' + (display ? ' block' : '') + '">' + safe + '</code>';
}

function bold(s){ return s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>'); }

function renderDetail(){
  const el = document.getElementById('detail');
  const d = sel ? DATA.days[sel] : null;
  const mini = document.getElementById('classicMini');
  if (!d){ el.innerHTML = '<div class="empty">这一天没有记录</div>';
           if (mini) mini.textContent = '选择日期后显示'; return; }
  const clList = (d.classic_list && d.classic_list.length) ? d.classic_list
               : (d.classic ? [d.classic] : []);
  const cl = clList[0];
  if (mini){
    mini.innerHTML = cl && cl.title
      ? '<b>'+esc(cl.title)+'</b><br><span class="sub">'+esc(cl.authors||'')+' · '
        +esc(cl.venue||'')+' ('+(cl.year||'')+')</span>'
        + (clList.length > 1 ? '<br><span class="sub">当天共 '+clList.length+' 篇</span>' : '')
      : '这一天没有经典回顾';
  }
  let h = '<div class="card"><h2>'+d.date+' · 入选 '+d.picked_count+' 篇'
        + (byDate[d.date] && byDate[d.date].is_week_refresh
           ? ' <span class="tag" style="color:var(--warn);border-color:var(--warn)">本周前沿刷新</span>'
           : '')
        + '</h2>';
  h += '<div class="meta">候选 '+(d.candidate_count||'-')+' 篇 · 窗口 '
     + (d.window_days||'-')+' 天 · 模型 '+(d.models?d.models.synth:'-')+'</div>';
  if (clList.length){
    // 顶部操作条：「加一篇」只有本地服务在跑时才可用
    h += '<div class="classictop"><span class="sub">📜 当天经典回顾 · 共 '
       + clList.length + ' 篇</span>';
    if (window.RF_SERVER){
      h += '<button class="btn" onclick="window.rfNewClassic()">🎲 加一篇</button>';
    } else {
      h += '<span class="sub">（用 <code>python3 server.py --open</code> 打开本页'
         + '才能「加一篇」）</span>';
    }
    h += '</div>';

    clList.forEach((c, i) => {
      h += '<div class="classic"><h3>' + (i+1) + '. ' + esc(c.title) + '</h3>';
      h += '<div class="meta">' + esc(c.authors||'') + ' — ' + esc(c.venue||'')
         + ' (' + (c.year||'') + ')';
      if (c.url){   // 只登记了真实论文页；没有就整条不显示，不拿搜索页凑数
        h += ' · <a href="' + esc(c.url) + '" target="_blank" rel="noopener">🔗 原文</a>';
      }
      h += '</div>';
      (c.tags||[]).forEach(t => h += '<span class="tag">' + esc(t) + '</span>');
      if (c.note) h += '<p class="abs">' + esc(c.note) + '</p>';
      if (c.review) h += md2html(c.review);
      h += '</div>';
    });
  }
  if (d.brief_markdown){
    h += '<h3 class="sec">📊 本周期简报</h3><div class="brief">'+md2html(d.brief_markdown)+'</div>';
  }
  h += '</div>';
  (d.papers||[]).forEach(p => {
    h += '<div class="card paper"><h3>'+p.rank+'. '+esc(p.title)+'</h3>';
    h += '<div class="meta">'+esc(p.author_text||'')+' — <b>'+esc(p.journal||'')+'</b> ('
       + esc(p.date||'')+', 相关度 '+p.score+(p.citations!=null?', 引用 '+p.citations:'')+')</div>';
    if (p.why && p.why.length) h += '<div class="why">命中：'+esc(p.why.join(' · '))+'</div>';
    if (p.summary) h += '<div class="sum">'+md2html(p.summary)+'</div>';
    const links = [];
    if (p.arxiv) links.push('<a href="https://arxiv.org/abs/'+p.arxiv+'" target="_blank">arXiv</a>');
    if (p.doi) links.push('<a href="https://doi.org/'+p.doi+'" target="_blank">DOI</a>');
    if (p.url) links.push('<a href="'+p.url+'" target="_blank">原文</a>');
    if (p.pdfurl) links.push('<a href="'+p.pdfurl+'" target="_blank">PDF</a>');
    if (links.length) h += '<div class="meta" style="margin-top:8px">'+links.join(' · ')+'</div>';
    if (p.abstract) h += '<details><summary>原文摘要</summary><div class="abs">'
                       + esc(p.abstract)+'</div></details>';
    h += '</div>';
  });
  el.innerHTML = h;
}

document.getElementById('prev').onclick = () => { cur.setMonth(cur.getMonth()-1); renderCal(); };
document.getElementById('next').onclick = () => { cur.setMonth(cur.getMonth()+1); renderCal(); };
document.getElementById('sub').textContent =
  '共 ' + (DATA.index||[]).length + ' 天记录 · 点日历中的日期查看当天论文、简报与经典回顾';
renderCal(); renderDetail();
</script>
</body>
</html>
"""
