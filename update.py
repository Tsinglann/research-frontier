#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 主入口。

用法：
  update.py all            完整跑一轮（画像 → 抓取 → 评分 → 简介 → 简报）
  update.py all --top 8    限制入选论文数
  update.py profile        只重建画像（不联网、不花钱）
  update.py crawl          只抓取 + 评分，打印候选（不调用 LLM）
  update.py brief --offline  用上次 crawl 的候选直接生成简报
  update.py status         查看上次更新时间与数据源状态
  update.py show [N]       在终端预览第 N 篇的简介

首次运行前请 copy config.example.json 到运行时目录，见 README。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from researchlib import brief as brief_mod          # noqa: E402
from researchlib import config as C                 # noqa: E402
from researchlib import crawl, llm, profile as prof_mod, zotero   # noqa: E402
from researchlib.util import load_json, log, save_json, truncate  # noqa: E402

CAND_FILE = os.path.join(C.DATA_DIR, 'candidates.json')


def cmd_profile():
    lib, colls = zotero.load_library()
    prof = prof_mod.build_profile(lib, colls)
    save_json(C.PROFILE_JSON, prof)
    print('\n=== 研究领域画像 ===')
    print('研究纲领 :', ' · '.join(prof['agenda']))
    print(f"库规模   : {prof['library']['items']} 条"
          f"（摘要 {prof['library']['with_abstract']} / PDF {prof['library']['with_pdf']}）")
    print('\n主题簇:')
    for c in prof['clusters']:
        bar = '█' * max(1, int(c['pct'] / 3))
        print(f"  {c['name']:18s} {c['count']:4d}  {bar} {c['pct']}%")
    print('\n核心术语:')
    print('  ' + '、'.join(t['term'] for t in prof['top_terms'][:16]))
    print('\n常读期刊:')
    for j in prof['journals'][:10]:
        print(f"  {j['count']:3d}  {j['name']}")
    if prof['notes']:
        print('\n跟进中的笔记:')
        for n in prof['notes'][:8]:
            print(f"  [{n['mtime_text']}] {n['name']}")
    return prof


def cmd_crawl(prof=None, quiet=False):
    prof = prof or load_json(C.PROFILE_JSON, None)
    if not prof:
        log('没有画像，先跑 profile')
        prof = cmd_profile()
    cands = crawl.gather(prof)
    scored = sorted((prof_mod.score_paper(p, prof) is not None and p or p
                     for p in cands), key=lambda p: -p['score'])
    save_json(CAND_FILE, [p for p in scored if p['score'] >= C.MIN_SCORE])
    if not quiet:
        print(f'\n=== 候选论文（相关度 ≥ {C.MIN_SCORE}，共 '
              f'{sum(1 for p in scored if p["score"] >= C.MIN_SCORE)} 篇）===')
        for i, p in enumerate([p for p in scored if p['score'] >= C.MIN_SCORE][:40], 1):
            print(f"{i:3d}. [{p['score']:5.1f}] {p['date']} {p['source'][:26]:26s} "
                  f"{truncate(p['title'], 72)}")
            if p['why']:
                print(f"        ↳ {', '.join(p['why'][:5])}")
    return scored


def cmd_synth():
    """只重新生成综合简报（复用已有论文与简介缓存，不重新抓取、不重复生成简介）。"""
    doc = load_json(C.PAPERS_JSON, None)
    prof = load_json(C.PROFILE_JSON, None)
    if not doc or not doc.get('papers'):
        log('没有论文数据，先跑 update.py all')
        return 1
    if not prof:
        log('没有画像，先跑 update.py profile')
        return 1
    papers = doc['papers']
    log(f'重生成综合简报：输入 {len(papers)} 篇（模型 {C.MODEL_SYNTH}）')
    md = llm.synthesize(prof, papers)
    if not md:
        log('综合简报返回空，放弃（原简报保留）')
        return 1
    brief = load_json(C.BRIEF_JSON, {})
    brief.update({
        'generated': int(time.time()),
        'generated_text': time.strftime('%Y-%m-%d %H:%M'),
        'markdown': md,
        'error': '',
        'model_synth': C.MODEL_SYNTH,
        'picked_count': len(papers),
        'candidate_count': brief.get('candidate_count', len(papers)),
        'window_days': brief.get('window_days', C.WINDOW_DAYS),
        'agenda': prof.get('agenda', []),
    })
    save_json(C.BRIEF_JSON, brief)
    brief_mod.write_md(prof, brief, papers)
    print('\n' + '=' * 70)
    print(md)
    print('=' * 70)
    log(f'综合简报已更新（{len(md)} 字）→ {C.BRIEF_JSON}')
    return 0


def cmd_status():
    print('数据目录 :', C.DATA_DIR)
    for name, path in (('画像', C.PROFILE_JSON), ('论文', C.PAPERS_JSON),
                       ('简报', C.BRIEF_JSON), ('日志', C.LOG_FILE)):
        if os.path.exists(path):
            st = os.stat(path)
            print(f'  {name:4s} {time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))}'
                  f'  {st.st_size/1024:.1f} KB  {path}')
        else:
            print(f'  {name:4s} （尚未生成） {path}')
    st = load_json(C.STATE_JSON, {})
    runs = st.get('runs', [])
    print(f'\n历史运行 {len(runs)} 次，缓存简介 {len(st.get("summaries", {}))} 条：')
    for r in runs[:6]:
        print(f"  {r['text']}  {r['picked']} 篇（新增 LLM {r['new']}）用时 {r['elapsed']}s")
    try:
        llm.api_key()
        print('\nDeepSeek API key : OK')
    except Exception as e:
        print(f'\nDeepSeek API key : 不可用 —— {e}')
    print('Zotero 数据库    :', 'OK' if os.path.exists(C.ZOTERO_DB) else '缺失')
    print('Obsidian 笔记库  :', 'OK' if os.path.isdir(C.OBSIDIAN_VAULT) else '缺失')


def cmd_show(n=1):
    doc = load_json(C.PAPERS_JSON, {'papers': []})
    ps = doc.get('papers', [])
    if not ps:
        print('还没有推荐论文，先跑 update.py all')
        return
    p = ps[min(n, len(ps)) - 1]
    print(f"=== {p['rank']}. {p['title']}")
    print(f"{p['author_text']} — {p['journal']} ({p['date']}) 相关度 {p['score']}")
    print(f"命中: {', '.join(p['why'])}")
    print('-' * 70)
    print(p['summary'] or '（无简介）')
    print('-' * 70)
    print('原文摘要:', truncate(p['abstract'], 900))


def main(argv=None):
    ap = argparse.ArgumentParser(description='研究前沿助手 —— 数据更新')
    ap.add_argument('stage', nargs='?', default='all',
                    choices=['all', 'profile', 'crawl', 'brief', 'synth',
                             'status', 'show'])
    ap.add_argument('--top', type=int, default=C.TOP_N, help='入选论文篇数')
    ap.add_argument('--days', type=int, default=C.WINDOW_DAYS, help='抓取窗口天数')
    ap.add_argument('--no-llm', action='store_true', help='只抓取与评分，不调用 API')
    ap.add_argument('--offline', action='store_true', help='复用上次候选，不重新抓取')
    ap.add_argument('--n', type=int, default=1, help='show 的序号')
    ap.add_argument('--force', action='store_true', help='忽略"本周已更新"，强制全量重跑')
    a = ap.parse_args(argv)

    if a.days != C.WINDOW_DAYS:
        C.WINDOW_DAYS = a.days
    if a.top != C.TOP_N:
        C.TOP_N = a.top

    t0 = time.time()
    log(f'=== research-widget 开始（stage={a.stage}）===')

    # ---- 前沿论文：每周只刷一次 ----
    # 每天 06:00 定时器仍会触发，但本周若已有前沿数据就跳过抓取+LLM，
    # 只刷新经典回顾与日历（用户要求：前沿固定每周刷新一次）。
    if a.stage in ('all', 'brief') and not a.offline:
        st = load_json(C.STATE_JSON, {})
        this_week = time.strftime('%G-W%V')
        if st.get('frontier_week') == this_week and not getattr(a, 'force', False):
            log(f'本周（{this_week}）前沿已更新过，跳过抓取；仅刷新经典/日历')
            a.offline = True          # 复用候选，只重生成经典与简报

    try:
        if a.stage == 'profile':
            cmd_profile()
        elif a.stage == 'crawl':
            cmd_crawl()
        elif a.stage == 'synth':
            return cmd_synth() or 0
        elif a.stage == 'status':
            cmd_status()
        elif a.stage == 'show':
            cmd_show(a.n)
        elif a.stage == 'brief':
            brief, papers, prof = brief_mod.build_brief(a.top, offline=a.offline)
            print('\n' + '=' * 70)
            print(brief['markdown'] or f"[综合简报失败] {brief['error']}")
            print('=' * 70)
        else:   # all
            if a.no_llm:
                cmd_crawl()
            else:
                brief, papers, prof = brief_mod.build_brief(a.top, offline=a.offline)
                print('\n' + '=' * 70)
                print(brief['markdown'] or f"[综合简报失败] {brief['error']}")
                print('=' * 70)
                print(f"\n共 {len(papers)} 篇论文简介，已写入 {C.PAPERS_JSON}")
        log(f'=== 结束，用时 {time.time()-t0:.1f}s ===')
        return 0
    except Exception as e:                      # noqa: BLE001
        import traceback
        log('运行失败：' + str(e))
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
