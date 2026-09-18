#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 终端预览（不开桌面也能看简报）。

用法：
  preview.py            打印当前简报（综合 + 前 5 篇简介）
  preview.py 12         打印第 12 篇的完整内容
  preview.py --all      打印全部论文简介
  preview.py --md       打印 brief.md 原文
  preview.py --profile  打印研究画像摘要
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from researchlib import config as C            # noqa: E402
from researchlib.util import load_json, truncate   # noqa: E402


def hr(ch='─', n=76):
    print(ch * n)


def show_brief(top=5, show_all=False):
    brief = load_json(C.BRIEF_JSON, None)
    doc = load_json(C.PAPERS_JSON, {'papers': []})
    papers = doc.get('papers', [])
    if not brief and not papers:
        print('还没有数据。先运行：')
        print(f'  python3 {os.path.join(C.PKG_DIR, "update.py")} all')
        return 1
    if brief:
        hr('═')
        print(f"研究前沿简报 · {brief.get('generated_text')}   "
              f"窗口 {brief.get('window_days')} 天 · 候选 {brief.get('candidate_count')} 篇 → "
              f"入选 {brief.get('picked_count')} 篇 · 用时 {brief.get('elapsed_sec')}s")
        print(f"模型：简介 {brief.get('model_brief')} / 综合 {brief.get('model_synth')}")
        hr('═')
        if brief.get('markdown'):
            print(brief['markdown'].strip())
        elif brief.get('error'):
            print('（综合简报生成失败：%s）' % brief['error'])
        print()
    n = len(papers) if show_all else min(top, len(papers))
    for p in papers[:n]:
        hr()
        flag = '预印本' if p.get('is_preprint') else '已发表'
        cit = p.get('citations')
        print(f"{p['rank']}. {p['title']}")
        print(f"   {p.get('author_text','')} — {p.get('journal','')} ({p.get('date')}, {flag}"
              + (f", {cit} 引用" if cit is not None else "") + f", 相关度 {p.get('score')})")
        if p.get('why'):
            print(f"   命中: {', '.join(p['why'])}")
        for line in (p.get('summary') or '（无中文简介）').splitlines():
            if line.strip():
                print('   ' + line.strip())
        links = []
        if p.get('arxiv'):
            links.append('https://arxiv.org/abs/' + p['arxiv'])
        if p.get('doi'):
            links.append('https://doi.org/' + p['doi'])
        if links:
            print('   ' + '  '.join(links))
    hr()
    print(f"（共 {len(papers)} 篇；完整 Markdown 见 {C.BRIEF_MD}）")
    return 0


def show_one(idx):
    doc = load_json(C.PAPERS_JSON, {'papers': []})
    papers = doc.get('papers', [])
    if not papers:
        print('还没有论文数据')
        return 1
    p = papers[max(0, min(idx, len(papers)) - 1)]
    hr('═')
    print(f"{p['rank']}. {p['title']}")
    hr('═')
    print(f"作者   : {', '.join(p.get('authors') or []) or '—'}")
    print(f"来源   : {p.get('journal')} ({p.get('date')}) "
          f"{'预印本' if p.get('is_preprint') else '已发表'}")
    print(f"相关度 : {p.get('score')}   命中: {', '.join(p.get('why') or [])}")
    if p.get('citations') is not None:
        print(f"引用数 : {p.get('citations')}")
    if p.get('doi'):
        print(f"DOI    : https://doi.org/{p['doi']}")
    if p.get('arxiv'):
        print(f"arXiv  : https://arxiv.org/abs/{p['arxiv']}")
    hr()
    print('【中文简介】')
    print(p.get('summary') or '（生成失败）')
    hr()
    print('【原文摘要】')
    print(p.get('abstract') or '（无）')
    return 0


def show_profile():
    prof = load_json(C.PROFILE_JSON, None)
    if not prof:
        print('还没有画像，先跑 update.py profile')
        return 1
    print('研究纲领 :', ' · '.join(prof.get('agenda', [])))
    lib = prof.get('library', {})
    print(f"文献库   : {lib.get('items')} 条（摘要 {lib.get('with_abstract')}，"
          f"PDF {lib.get('with_pdf')}，近 12 年 {lib.get('recent_12y')}）")
    print('\n主题簇:')
    for c in prof.get('clusters', []):
        print(f"  {c['name']:16s} {c['count']:4d}  {c['pct']:5.1f}%")
    print('\n核心术语:', '、'.join(t['term'] for t in prof.get('top_terms', [])[:16]))
    print('\n常读期刊:')
    for j in prof.get('journals', [])[:10]:
        print(f"  {j['count']:3d}  {j['name']}")
    print('\n跟进中的笔记:')
    for n in prof.get('notes', [])[:10]:
        print(f"  [{n['mtime_text']}] {n['name']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description='研究前沿助手 · 终端预览')
    ap.add_argument('n', nargs='?', type=int, default=None, help='看第 n 篇')
    ap.add_argument('--all', action='store_true', help='列出全部论文简介')
    ap.add_argument('--md', action='store_true', help='打印 brief.md 原文')
    ap.add_argument('--profile', action='store_true', help='打印研究画像')
    ap.add_argument('--top', type=int, default=5, help='简报后附几篇简介')
    a = ap.parse_args()
    if a.md:
        print(open(C.BRIEF_MD, encoding='utf-8').read() if os.path.exists(C.BRIEF_MD)
              else '还没有 brief.md')
        return 0
    if a.profile:
        return show_profile()
    if a.n:
        return show_one(a.n)
    return show_brief(top=a.top, show_all=a.all)


if __name__ == '__main__':
    sys.exit(main())
