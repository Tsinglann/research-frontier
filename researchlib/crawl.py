#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 从 arXiv / Crossref(期刊) 抓取候选论文。

只依赖标准库 urllib + xml.etree。
"""
import collections
import datetime as dt
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

from . import config as C
from .util import clean_text, http_get, http_json, log, norm_title

ATOM = {'a': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'}


def _since(days):
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- arXiv
def _arxiv_query(q, days, max_results):
    """单次 arXiv 查询，返回窗口内的条目。"""
    out = []
    url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode({
        'search_query': q,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending',
    })
    try:
        root = ET.fromstring(http_get(url, timeout=70))
    except Exception as e:                      # noqa: BLE001
        log(f'arXiv 子查询失败：{e}')
        return out
    for e in root.findall('a:entry', ATOM):
        t = e.find('a:title', ATOM)
        s = e.find('a:summary', ATOM)
        pub = e.find('a:published', ATOM)
        upd = e.find('a:updated', ATOM)
        cat = e.find('arxiv:primary_category', ATOM)
        if t is None or pub is None:
            continue
        date = (pub.text or '')[:10]
        try:
            if (dt.date.today() - dt.date.fromisoformat(date)).days > days:
                continue
        except ValueError:
            continue
        doi_el = e.find('arxiv:doi', ATOM)
        jref = e.find('arxiv:journal_ref', ATOM)
        aid = (e.find('a:id', ATOM).text or '').rsplit('/', 1)[-1]
        out.append({
            'title': clean_text(t.text),
            'abstract': clean_text(s.text if s is not None else ''),
            'authors': [clean_text(a.find('a:name', ATOM).text)
                        for a in e.findall('a:author', ATOM)][:8],
            'date': date,
            'updated': (upd.text or '')[:10] if upd is not None else date,
            'journal': clean_text(jref.text) if jref is not None else '',
            'doi': clean_text(doi_el.text) if doi_el is not None else '',
            'arxiv': aid,
            'category': cat.get('term') if cat is not None else '',
            'url': f'https://arxiv.org/abs/{aid}',
            'pdfurl': f'https://arxiv.org/pdf/{aid}',
            'source': 'arXiv',
            'is_preprint': jref is None,
        })
    return out


def fetch_arxiv(terms, days=None, max_results=None):
    """按术语检索 arXiv 最新预印本。

    **分批检索**：把术语拆成若干小组分别查询再合并去重并重新排序。
    早期版本把 15 个术语用 OR 连成一条查询、按 submittedDate 倒序取 150 条，
    结果 latest 提交把名额占满 —— 实测 150 条里 54 条集中在最近两天，
    等于"只看见这两天的预印本"。分批后窗口覆盖明显变均匀。
    """
    days = days or C.WINDOW_DAYS
    max_results = max_results or C.ARXIV_MAX
    terms = list(terms)[:18]
    nbatch = max(1, C.ARXIV_QUERY_BATCH)
    per = max(10, C.ARXIV_PER_BATCH)
    # 交错分组：保证每组都同时含核心与外围术语
    groups = [terms[i::nbatch] for i in range(nbatch)]
    out, seen = [], set()
    for gi, g in enumerate(groups, 1):
        if not g:
            continue
        q = ' OR '.join(f'all:"{t}"' for t in g)
        part = _arxiv_query(q, days, per)
        fresh = 0
        for p in part:
            k = p['arxiv'] or p['title']
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
            fresh += 1
        log(f'  arXiv 批次 {gi}/{nbatch}（{len(g)} 术语）：取 {len(part)} 篇，新增 {fresh}')
        time.sleep(1.2)          # 对 arXiv API 友好
    if len(out) > max_results:
        out.sort(key=lambda p: p.get('date') or '', reverse=True)
        out = out[:max_results]
    return out


def _fetch_arxiv_legacy(terms, days=None, max_results=None):
    """（保留）单次大 OR 查询的旧实现，便于对照。"""
    days = days or C.WINDOW_DAYS
    max_results = max_results or C.ARXIV_MAX
    q = ' OR '.join(f'all:"{t}"' for t in terms[:18])
    url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode({
        'search_query': q,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending',
    })
    out = []
    try:
        xml = http_get(url, timeout=70)
        root = ET.fromstring(xml)
    except Exception as e:                      # noqa: BLE001
        log(f'arXiv 抓取失败：{e}')
        return out
    for e in root.findall('a:entry', ATOM):
        t = e.find('a:title', ATOM)
        s = e.find('a:summary', ATOM)
        pub = e.find('a:published', ATOM)
        upd = e.find('a:updated', ATOM)
        cat = e.find('arxiv:primary_category', ATOM)
        if t is None or pub is None:
            continue
        date = (pub.text or '')[:10]
        # 只看窗口内
        try:
            if (dt.date.today() - dt.date.fromisoformat(date)).days > days:
                continue
        except ValueError:
            continue
        doi_el = e.find('arxiv:doi', ATOM)
        jref = e.find('arxiv:journal_ref', ATOM)
        aid = (e.find('a:id', ATOM).text or '').rsplit('/', 1)[-1]
        out.append({
            'title': clean_text(t.text),
            'abstract': clean_text(s.text if s is not None else ''),
            'authors': [clean_text(a.find('a:name', ATOM).text)
                        for a in e.findall('a:author', ATOM)][:8],
            'date': date,
            'updated': (upd.text or '')[:10] if upd is not None else date,
            'journal': clean_text(jref.text) if jref is not None else '',
            'doi': clean_text(doi_el.text) if doi_el is not None else '',
            'arxiv': aid,
            'category': cat.get('term') if cat is not None else '',
            'url': f'https://arxiv.org/abs/{aid}',
            'pdfurl': f'https://arxiv.org/pdf/{aid}',
            'source': 'arXiv',
            'is_preprint': jref is None,
        })
    log(f'arXiv：{len(out)} 篇（近 {days} 天）')
    return out


# ---------------------------------------------------------------- Crossref
def fetch_crossref(journal, issn, rows=None, days=None):
    """按期刊 ISSN 抓取最近发表的论文。"""
    rows = rows or C.CROSSREF_ROWS
    days = days or C.WINDOW_DAYS
    url = 'https://api.crossref.org/works?' + urllib.parse.urlencode({
        'filter': f'issn:{issn},from-pub-date:{_since(days)}',
        'rows': rows,
        'select': 'title,DOI,abstract,author,container-title,published,type,subject,URL',
        'mailto': 'research-frontier@example.invalid',
    })
    out = []
    try:
        d = http_json(url, timeout=70)
    except Exception as e:                      # noqa: BLE001
        log(f'Crossref {journal} 失败：{e}')
        return out
    for it in d.get('message', {}).get('items', []):
        title = clean_text((it.get('title') or [''])[0])
        if not title:
            continue
        if (it.get('type') or '') not in ('journal-article', 'posted-content', 'article'):
            continue
        pub = it.get('published', {}).get('date-parts', [[None]])[0]
        date = '-'.join(f'{x:02d}' if i else str(x) for i, x in enumerate(pub) if x)
        doi = it.get('DOI') or ''
        out.append({
            'title': title,
            'abstract': clean_text(it.get('abstract') or ''),
            'authors': [clean_text(f"{a.get('given','')} {a.get('family','')}".strip())
                        for a in (it.get('author') or [])][:8],
            'date': date,
            'updated': date,
            'journal': clean_text((it.get('container-title') or [journal])[0]),
            'doi': doi,
            'arxiv': '',
            'category': '',
            'url': it.get('URL') or (f'https://doi.org/{doi}' if doi else ''),
            'pdfurl': '',
            'source': journal,
            'is_preprint': False,
        })
    if out:
        log(f'Crossref {journal}：{len(out)} 篇')
    return out


def fetch_all_journals(days=None, journals=None):
    out = []
    for name, issn, _w in (journals or C.CROSSREF_JOURNALS):
        out.extend(fetch_crossref(name, issn, days=days))
        time.sleep(0.4)          # 对 API 友好
    return out


# ---------------------------------------------------------------- 去重合并
def _key(p):
    if p.get('doi'):
        return 'doi:' + p['doi'].lower()
    if p.get('arxiv'):
        return 'ax:' + p['arxiv'].lower()
    return 'ti:' + norm_title(p['title'])


def dedupe(papers):
    """同一篇论文可能同时出现在 arXiv 与期刊源，合并字段、优先保留期刊版信息。"""
    merged = {}
    for p in papers:
        k = _key(p)
        # 标题也作为二次键，避免 DOI 缺失时重复
        tk = 'ti:' + norm_title(p['title'])
        cur = merged.get(k) or merged.get(tk)
        if cur is None:
            merged[k] = p
            merged.setdefault(tk, p)
            continue
        # 合并：补空字段；arXiv 版保留 preprint 标记与 id
        for f in ('abstract', 'doi', 'arxiv', 'journal', 'url', 'pdfurl', 'date'):
            if not cur.get(f) and p.get(f):
                cur[f] = p[f]
        if cur.get('source') == 'arXiv' and p.get('source') != 'arXiv':
            cur['source'] = p['source']
        if p.get('journal'):
            cur['is_preprint'] = False
        if len(p.get('authors') or []) > len(cur.get('authors') or []):
            cur['authors'] = p['authors']
    # 去掉别名键造成的重复对象
    uniq, seen = [], set()
    for p in merged.values():
        i = id(p)
        if i in seen:
            continue
        seen.add(i)
        uniq.append(p)
    return uniq


# ---------------------------------------------------------------- OpenAlex 引用数
def enrich_citations(papers, limit=30):
    """给前若干篇补引用数（OpenAlex 按 DOI 查询是可靠的）。"""
    done = 0
    for p in papers[:limit]:
        doi = (p.get('doi') or '').strip()
        if not doi:
            continue
        try:
            url = ('https://api.openalex.org/works/https://doi.org/' +
                   urllib.parse.quote(doi) + '?mailto=research-frontier@example.invalid')
            d = http_json(url, timeout=25, retries=2)
            p['citations'] = d.get('cited_by_count', 0)
            p['oa_url'] = ((d.get('primary_location') or {}).get('landing_page_url') or '')
            done += 1
        except Exception:
            p['citations'] = None
        time.sleep(0.25)
    log(f'OpenAlex：为 {done} 篇补上引用数')
    return papers


# ---------------------------------------------------------------- 主入口
def gather(prof, days=None):
    """按画像抓取全部候选论文并去重。"""
    days = days or C.WINDOW_DAYS
    terms = prof.get('search_terms') or C.ARXIV_TERMS
    allp = []
    allp.extend(fetch_arxiv(terms, days=days))
    allp.extend(fetch_all_journals(days=days))
    uniq = dedupe(allp)
    log(f'抓取合计：原始 {len(allp)} 篇 → 去重后 {len(uniq)} 篇')
    return uniq
