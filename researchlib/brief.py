#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 简报生成与产物落盘。

产物（QML 部件读这里）：
  profile.json  研究领域画像
  papers.json   本轮推荐论文（含中文简介）
  brief.json    综合简报（结构化）
  brief.md      综合简报（纯文本，便于外部阅读）
  state.json    已生成简介的缓存（避免重复调用 API）
"""
import os
import time

from . import config as C
from . import archive, classics, crawl, llm, profile as prof_mod, zotero
from .util import load_json, log, save_json, truncate


CAND_FILE = os.path.join(C.DATA_DIR, 'candidates.json')

# 小部件只显示要点，完整内容交给浏览器网页（用户要求"部件内更简短"）
WIDGET_CHARS = 150


def _compact_summary(text, limit=WIDGET_CHARS):
    """把 3 句简介压成小部件用的短版（约 limit 字，保留前两句重点）。"""
    t = (text or '').strip()
    if not t:
        return ''
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if not lines:
        return ''
    short = lines[0]
    if len(short) < limit and len(lines) > 1:
        short = short + ' ' + lines[1]
    if len(short) > limit:
        short = short[:limit].rstrip() + '…'
    return short


def _compact_brief(md, limit=260):
    """从完整简报里抽出最适合小部件看的几行（跳过趋势分析等长段落）。"""
    md = (md or '').strip()
    if not md:
        return ''
    import re as _re
    secs = _re.split(r'\n(?=##\s)', md)
    out = []
    for sec in secs:
        head = sec.strip().splitlines()[0] if sec.strip() else ''
        if any(k in head for k in ('看点', '可切入', '值得深读')):
            out.append(sec.strip())
    picked = '\n\n'.join(out) if out else secs[0].strip()
    if len(picked) > limit:
        picked = picked[:limit].rstrip() + '…'
    return picked


def _pick(scored, top_n):
    """按相关度挑选，同一来源最多 MAX_PER_SOURCE 篇，避免单一期刊霸榜。"""
    picked, per_src = [], {}
    for p in scored:
        j = (p.get('journal') or p.get('source') or 'other').lower()
        if per_src.get(j, 0) >= C.MAX_PER_SOURCE:
            continue
        per_src[j] = per_src.get(j, 0) + 1
        picked.append(p)
        if len(picked) >= top_n:
            break
    return picked


def build_brief(top_n=None, offline=False):
    """跑一轮完整流水线：画像 → 抓取 → 评分 → LLM 简介 → 综合简报。

    offline=True 时复用上次 crawl 存下的候选（runtime/candidates.json），
    跳过联网抓取，只做评分/简介/简报 —— 调试与手动重生成时很有用。
    """
    top_n = top_n or C.TOP_N
    t0 = time.time()

    # 1) 画像
    lib, colls = zotero.load_library()
    if not lib:
        raise RuntimeError('Zotero 库为空，无法构建画像')
    prof = prof_mod.build_profile(lib, colls)
    save_json(C.PROFILE_JSON, prof)

    # 2) 抓取（或复用上次候选）
    if offline:
        cands = load_json(CAND_FILE, [])
        if not cands:
            log('offline 模式但没有候选缓存，改为联网抓取')
            offline = False
    if not offline:
        cands = crawl.gather(prof)

    # 3) 评分排序
    scored = []
    for p in cands:
        s = prof_mod.score_paper(p, prof)
        if s >= C.MIN_SCORE:
            scored.append(p)
    scored.sort(key=lambda p: (-p['score'], p.get('date') or ''))
    picked = _pick(scored, top_n)
    log(f'评分：{len(cands)} 篇候选（{"离线缓存" if offline else "联网抓取"}）中 '
        f'{len(scored)} 篇过门槛，取 {len(picked)} 篇')

    # 4) 补引用数（只对最终入选的做，省额度）
    crawl.enrich_citations(picked, limit=len(picked))

    # 5) LLM 简介（带缓存：摘要没变就不重复花钱）
    state = load_json(C.STATE_JSON, {'summaries': {}, 'runs': []})
    cache = state.get('summaries', {})
    new_calls = 0
    for p in picked:
        key = (p.get('doi') or p.get('arxiv') or p.get('title') or '')[:80].lower()
        p['cache_key'] = key
        hit = cache.get(key)
        if hit and hit.get('summary') and hit.get('abstract_hash') == hash(p.get('abstract') or ''):
            p['summary'] = hit['summary']
            p['summary_model'] = hit.get('model', C.MODEL_BRIEF)
            p['summary_cached'] = True
            continue
        try:
            txt = llm.summarize_paper(prof, p)
            p['summary'] = txt
            p['summary_model'] = C.MODEL_BRIEF
            p['summary_cached'] = False
            cache[key] = {'summary': txt, 'model': C.MODEL_BRIEF,
                          'abstract_hash': hash(p.get('abstract') or ''),
                          'title': p.get('title'), 'ts': int(time.time())}
            new_calls += 1
        except Exception as e:                  # noqa: BLE001
            log(f'  简介生成失败（{p.get("title","")[:50]}）：{e}')
            p['summary'] = ''
            p['summary_model'] = ''
            # 失败不进缓存，下次运行会自动重试这一篇
    log(f'简介：新增 {new_calls} 次 API 调用，命中缓存 {len(picked) - new_calls} 篇')

    # 6) 综合简报
    synth_md, synth_err = '', ''
    try:
        synth_md = llm.synthesize(prof, picked)
    except Exception as e:                      # noqa: BLE001
        synth_err = str(e)
        log(f'综合简报生成失败：{e}')

    # 6.5) 经典论文回顾（每天一篇，按日期稳定选取，结果按 key 缓存）
    # offset 让「换一篇」按钮能取到典籍库里的下一篇
    offset = int(load_json(C.STATE_JSON, {}).get('classic_offset', 0) or 0)
    classic = classics.pick(offset=offset)
    ckey = 'classic:' + classic['key']
    centry = cache.get(ckey)
    classic_text = ''
    if centry and centry.get('summary'):
        classic_text = centry['summary']
        classic['cached'] = True
    else:
        try:
            classic_text = llm.classic_review(prof, classic)
            cache[ckey] = {'summary': classic_text, 'model': C.MODEL_BRIEF,
                           'title': classic['title'], 'ts': int(time.time())}
            classic['cached'] = False
        except Exception as e:                  # noqa: BLE001
            log(f'经典回顾生成失败：{e}')
    classic['review'] = classic_text
    log(f'经典回顾：{classic["year"]} {classic["title"][:52]}'
        + ('（缓存）' if classic.get('cached') else ''))

    elapsed = round(time.time() - t0, 1)
    brief = {
        'generated': int(time.time()),
        'generated_text': time.strftime('%Y-%m-%d %H:%M'),
        'elapsed_sec': elapsed,
        'window_days': C.WINDOW_DAYS,
        'model_synth': C.MODEL_SYNTH,
        'model_brief': C.MODEL_BRIEF,
        'new_count': new_calls,
        'candidate_count': len(cands),
        'picked_count': len(picked),
        'agenda': prof.get('agenda', []),
        'markdown': synth_md,
        'markdown_short': _compact_brief(synth_md),
        'error': synth_err,
        'classic': classic,
    }

    # 7) papers.json —— 只保留部件需要的字段
    papers_out = []
    for i, p in enumerate(picked, 1):
        papers_out.append({
            'rank': i,
            'title': p.get('title'),
            'authors': (p.get('authors') or [])[:4],
            'author_text': ', '.join((p.get('authors') or [])[:3]) +
                           (' 等' if len(p.get('authors') or []) > 3 else ''),
            'journal': p.get('journal') or p.get('source'),
            'date': p.get('date'),
            'doi': p.get('doi'),
            'arxiv': p.get('arxiv'),
            'url': p.get('url'),
            'pdfurl': p.get('pdfurl'),
            'citations': p.get('citations'),
            'category': p.get('category'),
            'score': p.get('score'),
            'why': p.get('why') or [],
            'is_preprint': p.get('is_preprint', False),
            'abstract': truncate(p.get('abstract') or '', 1800),
            'summary': p.get('summary') or '',
            # 小部件只显示这两项（更短）；完整内容在浏览器网页与每日存档里
            'summary_short': _compact_summary(p.get('summary') or ''),
            'abstract_short': truncate(p.get('abstract') or '', 220),
            'summary_cached': p.get('summary_cached', False),
            'cached': p.get('summary_cached', False),
            'summary_model': p.get('summary_model') or '',
        })
    papers_doc = {
        'generated': brief['generated'],
        'generated_text': brief['generated_text'],
        'window_days': C.WINDOW_DAYS,
        'count': len(papers_out),
        'papers': papers_out,
    }

    # 8) 落盘
    save_json(C.PAPERS_JSON, papers_doc)
    save_json(C.BRIEF_JSON, brief)
    write_md(prof, brief, papers_out)

    # 9) 每日结构化存档（<workdir>/daily/）+ 刷新日历网页
    try:
        archive.save_day(brief.get('generated_text', '')[:10] or
                         time.strftime('%Y-%m-%d'),
                         brief, papers_out, prof, classic, classic_text)
    except Exception as e:                      # noqa: BLE001
        log(f'存档失败（不影响小部件）：{e}')

    # 记录这是哪一周生成的前沿数据（update.py 据此判断本周是否已刷过）
    state['frontier_week'] = time.strftime('%G-W%V')
    state['summaries'] = cache
    state['runs'] = ([{'ts': brief['generated'], 'text': brief['generated_text'],
                       'picked': len(papers_out), 'new': new_calls,
                       'elapsed': elapsed}] + state.get('runs', []))[:20]
    save_json(C.STATE_JSON, state)

    log(f'完成：{len(papers_out)} 篇推荐 + 综合简报，用时 {elapsed}s')
    return brief, papers_out, prof


def write_md(prof, brief, papers):
    """写一份可读的 Markdown 简报（桌面部件之外也能看）。"""
    L = []
    L.append(f'# 研究前沿简报 · {brief["generated_text"]}')
    L.append('')
    L.append(f'> 数据源：Zotero 文献库（{prof["library"]["items"]} 条）+ arXiv + '
             f'{len(C.CROSSREF_JOURNALS)} 种常读期刊 · 窗口 {C.WINDOW_DAYS} 天 · '
             f'候选 {brief["candidate_count"]} 篇 → 入选 {brief["picked_count"]} 篇')
    L.append('')
    if prof.get('agenda'):
        L.append(f'**研究纲领**：{" · ".join(prof["agenda"])}')
        L.append('')
    if brief.get('markdown'):
        L.append(brief['markdown'].strip())
        L.append('')
    elif brief.get('error'):
        L.append(f'（综合简报生成失败：{brief["error"]}）')
        L.append('')
    L.append('---')
    L.append('')
    L.append('## 论文简介')
    L.append('')
    for p in papers:
        flag = '预印本' if p['is_preprint'] else '已发表'
        cite = f'{p["citations"]} 次引用' if p.get('citations') is not None else '引用数未知'
        L.append(f'### {p["rank"]}. {p["title"]}')
        L.append('')
        L.append(f'*{p["author_text"]}* — **{p["journal"] or p["source"]}** ({p["date"]}, '
                 f'{flag}, 相关度 {p["score"]}, {cite})')
        L.append('')
        if p.get('why'):
            L.append(f'命中方向：{", ".join(p["why"])}')
            L.append('')
        if p.get('summary'):
            for line in p['summary'].splitlines():
                if line.strip():
                    L.append(line.strip())
        else:
            L.append('（中文简介生成失败，见下方摘要）')
        L.append('')
        L.append(f'<details><summary>原文摘要</summary>\n\n{p["abstract"]}\n\n</details>')
        L.append('')
        links = []
        if p.get('arxiv'):
            links.append(f'[arXiv:{p["arxiv"]}](https://arxiv.org/abs/{p["arxiv"]})')
        if p.get('doi'):
            links.append(f'[DOI](https://doi.org/{p["doi"]})')
        if p.get('url'):
            links.append(f'[原文链接]({p["url"]})')
        if p.get('pdfurl'):
            links.append(f'[PDF]({p["pdfurl"]})')
        if links:
            L.append(' · '.join(links))
            L.append('')
    text = '\n'.join(L)
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = C.BRIEF_MD + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, C.BRIEF_MD)
    return text
