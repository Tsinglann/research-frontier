#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 研究领域画像 + 论文相关度评分。

画像来源：Zotero 文献库（权威，代表用户已读/已收藏）
         + 你配置的 Obsidian 库 / LaTeX 工作目录（代表正在跟进的活方向）
"""
import collections
import os
import re
import time

from . import config as C
from . import zotero
from .util import clean_text, load_json, log, norm_title

# 标题/摘要分词用
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")
STOP = set('the a an of in on for and or to with by from at as is are was were be been being it its this that these those we our us they their them he she his her you your new novel study studies using used use via can could may might will would shall should under over between among into than then also such more most less least very much many two three one first second approach approaches method methods result results show shows shown find found here there when where which who whom whose what how why all any both each few other some only own same so no nor not now do does did doing have has had about after before during while because if but just like cannot'.split())


def _tokens(text):
    return [w for w in (m.group(0).lower() for m in WORD_RE.finditer(text or ''))
            if w not in STOP and w not in C.NOISE_WORDS and len(w) > 2]


def _term_hits(text, terms):
    """返回命中的术语列表（大小写不敏感，词边界宽松）。"""
    low = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    hits = []
    for t in terms:
        if t in low:
            hits.append(t)
    return hits


def _soft_hits(text, term):
    """软匹配：把连字符空格差异也算命中（Brownian-motor ↔ Brownian motor）。

    用 :func:`norm_title` 归一化后做子串匹配，比纯字面匹配多召回一些变体。
    """
    if not text or not term:
        return False
    nt = norm_title(text)
    nterm = norm_title(term)
    return bool(nterm) and nterm in nt


def term_hits_weighted(text):
    """按 TERM_WEIGHTS 给一段文本打分，返回 (总分, 命中术语列表)。

    先做字面匹配（快），再对未命中的术语做一次软匹配（容错）。
    这样即使摘要里写作 "Brownian-motor" 或 "Fokker Planck" 也能命中。
    """
    low = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    score, hits = 0.0, []
    for term, w in C.TERM_WEIGHTS.items():
        if term in low:
            score += w
            hits.append(term)
        elif w >= 2.0 and _soft_hits(text, term):
            score += w * 0.5          # 软匹配只给一半分
            hits.append(term)
    return score, hits


def domain_penalty(paper):
    """无关领域惩罚。

    天文/高能/宇宙学的论文经常大量使用统计物理与热力学词汇，
    纯术语打分会把它们排到最前面（实测：一篇虫洞随机热力学拿到 25.1 分）。
    这里按标题与摘要命中无关领域词的程度做乘性惩罚。
    """
    title = (paper.get('title') or '').lower()
    abstract = (paper.get('abstract') or '').lower()
    cat = (paper.get('category') or '').lower()
    hits = 0
    for t in C.OFF_TOPIC_TERMS:
        if t in title:
            hits += 3          # 标题命中权重高
        elif t in abstract:
            hits += 1
    if cat.startswith(('astro-ph', 'hep-', 'gr-qc')):
        hits += 3
    if hits == 0:
        return 1.0
    return C.OFF_TOPIC_PENALTY ** min(hits, 3)


def journal_bonus(journal):
    """按期刊影响力给的乘性加成（用户 Zotero 里的主流期刊应更容易入选）。"""
    j = (journal or '').lower()
    for name, factor in C.JOURNAL_BONUS:
        if name in j:
            return factor
    return 1.0


# ---------------------------------------------------------------- 画像
def build_profile(lib, colls):
    """从文献库构建画像 dict。"""
    now = int(time.time())
    # 只看带年份的、近 12 年的活跃兴趣（老论文多为经典奠基作，另计）
    recent = [p for p in lib if p.get('year') and p['year'] >= 2014]

    # --- 主题簇统计 ---
    cluster_stat = {}
    for name, terms in C.TOPIC_CLUSTERS.items():
        n = 0
        for p in lib:
            blob = p['title'] + ' ' + (p['abstract'] or '')
            if _term_hits(blob, terms) or _soft_hits(p['title'], terms[0]):
                n += 1
        cluster_stat[name] = n
    total_hits = sum(cluster_stat.values()) or 1
    clusters = sorted(
        ({'name': k, 'count': v, 'pct': round(100.0 * v / total_hits, 1)}
         for k, v in cluster_stat.items()),
        key=lambda d: -d['count'])

    # --- 关键词频次（标题权重 3，摘要权重 1）---
    freq = collections.Counter()
    for p in lib:
        for w in set(_tokens(p['title'])):
            freq[w] += 3
        for w in set(_tokens(p['abstract'] or '')):
            freq[w] += 1
    top_words = [{'word': w, 'weight': n} for w, n in freq.most_common(80)]

    # --- 术语命中（权威：按词典算）---
    term_score = collections.Counter()
    for p in lib:
        blob = p['title'] + ' ' + (p['abstract'] or '')
        _, hits = term_hits_weighted(blob)
        for t in hits:
            term_score[t] += C.TERM_WEIGHTS.get(t, 1)
    top_terms = [{'term': t, 'score': s} for t, s in term_score.most_common(30)]

    # --- 期刊分布 ---
    jc = collections.Counter(p['journal'] for p in lib if p['journal'])
    journals = [{'name': k, 'count': v} for k, v in jc.most_common(18)]

    # --- 年份分布 ---
    yc = collections.Counter(p['year'] for p in lib if p['year'])
    years = [{'year': y, 'count': yc[y]} for y in sorted(yc)]

    # --- 最近入库的研究兴趣（近 3 年）---
    newest = sorted([p for p in lib if p.get('year') and p['year'] >= 2023],
                    key=lambda p: (-(p['year'] or 0), p['title']))
    recent_titles = [p['title'] for p in newest[:40]]

    # --- Obsidian / LaTeX 笔记跟进 ---
    notes = _scan_notes()

    # --- 判定研究纲领（一句话画像）---
    agenda = [c['name'] for c in clusters[:4] if c['count'] > 0]

    prof = {
        'generated': now,
        'generated_text': time.strftime('%Y-%m-%d %H:%M'),
        'library': {
            'items': len(lib),
            'with_abstract': sum(1 for p in lib if p['abstract']),
            'with_pdf': sum(1 for p in lib if p['pdf']),
            'with_doi': sum(1 for p in lib if p['doi']),
            'recent_12y': len(recent),
            'collections': [{'name': n, 'count': c} for n, c in colls[:20]],
        },
        'agenda': agenda,
        'clusters': clusters,
        'top_terms': top_terms,
        'top_words': top_words,
        'journals': journals,
        'years': years,
        'recent_titles': recent_titles,
        'notes': notes,
        # 搜索用的术语池：核心术语优先
        'search_terms': [t['term'] for t in top_terms[:18]] or C.ARXIV_TERMS,
    }
    log(f'画像：纲领={agenda}，核心术语 {len(prof["search_terms"])} 个，笔记 {len(notes)} 篇')
    return prof


def _scan_notes(limit=400, recent_days=180):
    """扫用户配置的 Obsidian 库中的 md 笔记，挑出与研究方向相关的。"""
    roots = [p for p in (C.OBSIDIAN_VAULT,) if p]
    hits = []
    if not os.path.isdir(C.OBSIDIAN_VAULT):
        return hits
    cutoff = time.time() - recent_days * 86400
    all_terms = C.TERMS_CORE + C.TERMS_SECONDARY
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ('.obsidian', '.trash', 'attachments')]
            for fn in filenames:
                if not fn.endswith('.md'):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                name = fn[:-3]
                hit_terms = _term_hits(name, all_terms)
                # 文件名没命中时，看内容（只读前 4KB，控制开销）
                if not hit_terms:
                    try:
                        with open(full, 'r', encoding='utf-8', errors='replace') as f:
                            head = f.read(4096)
                        hit_terms = _term_hits(head, all_terms)
                    except OSError:
                        continue
                if not hit_terms:
                    continue
                hits.append({
                    'name': name,
                    'path': full,
                    'rel': os.path.relpath(full, root),
                    'mtime': int(st.st_mtime),
                    'mtime_text': time.strftime('%Y-%m-%d', time.localtime(st.st_mtime)),
                    'recent': st.st_mtime >= cutoff,
                    'terms': hit_terms[:5],
                    'score': 3 * len([t for t in hit_terms if t in C.TERMS_CORE]) +
                             2 * len([t for t in hit_terms if t in C.TERMS_SECONDARY]),
                })
    hits.sort(key=lambda h: (-h['score'], -h['mtime']))
    return hits[:limit]


# ---------------------------------------------------------------- 点赞反馈
_LIKES_CACHE = {'ts': 0, 'data': {}}


def load_likes(max_age=60):
    """读用户在部件上点赞过的论文（runtime/actions.json），带 60 秒缓存。

    点赞 = 「这类工作我感兴趣」，是对抓取最直接的反馈信号，
    比任何关键词词典都准，所以只用于加权、不改变硬门槛。
    """
    now = time.time()
    if now - _LIKES_CACHE['ts'] < max_age:
        return _LIKES_CACHE['data']
    # 用 util.load_json（读失败返回默认值），不直接 import json
    data = load_json(os.path.join(C.DATA_DIR, 'actions.json'), {}) or {}
    data = data.get('likes', {}) or {}
    _LIKES_CACHE.update({'ts': now, 'data': data})
    return data


def _like_boost(paper, likes):
    """按点赞记录算加成倍率与原因。

    两个信号：
      * 同一期刊（+15%/次，上限 +30%）—— 说明你在意这个刊的工作
      * 标题命中点赞论文的命中术语（+0.8/个，上限 +4.0）—— 说明你在意这个话题
    """
    if not likes:
        return 1.0, []
    jr = (paper.get('journal') or paper.get('source') or '').lower()
    title_low = (paper.get('title') or '').lower()
    bonus, reasons, journal_hit = 0.0, [], 0
    for info in likes.values():
        lj = (info.get('journal') or '').lower()
        if jr and lj and (lj in jr or jr in lj):
            journal_hit += 1
        for term in (info.get('why') or []):
            if term and term.lower() in title_low:
                bonus += 0.8
                reasons.append(term)
    if journal_hit:
        bonus += min(0.30, 0.15 * journal_hit)
        reasons.append('点赞期刊')
    return 1.0 + min(1.0, bonus), sorted(set(reasons))[:3]


# ---------------------------------------------------------------- 评分
def score_paper(paper, prof):
    """给一篇候选论文打相关度分（0 起）。

    构成：
      1. 术语命中（核心 3 / 次级 2 / 外围 1，软匹配减半）
      2. 画像高频词命中标题（+0.8/个）
      3. 期刊加成（PRL / Nature Physics 等顶刊 ×1.2–1.45）
      4. **点赞反馈加成**（同刊 / 同话题，最多 ×2.0）—— 用户在部件上的显式反馈

    注：早期版本没有第 3 项，导致摘要写得长的 PRE 文章挤掉 PRL 的实质好文
    （用户 Zotero 里 PRL 占 15%，而 PRL 摘要普遍偏短）。
    另外 arXiv 预印本常在投稿后才更新摘要，这里对缺失摘要的条目只按标题评分，
    不做惩罚——否则会系统性漏掉最新预印本。
    """
    title = paper.get('title') or ''
    abstract = paper.get('abstract') or ''
    blob = title + ' ' + abstract

    s, hits = term_hits_weighted(blob)
    if not abstract:
        # 没有摘要：术语分打个折（信息量少），但仍保留排序能力
        s *= 0.75
        s += term_hits_weighted(title)[0] * 0.5

    # 画像里出现过的自由关键词，命中标题额外加分
    title_low = title.lower()
    prof_words = {w['word'] for w in prof.get('top_words', [])[:60]}
    for w in prof_words:
        if w and w in title_low:
            s += 0.8

    s *= journal_bonus(paper.get('journal') or paper.get('source') or '')
    s *= domain_penalty(paper)

    # 点赞反馈（用户显式兴趣）
    boost, why_like = _like_boost(paper, load_likes())
    s *= boost

    # 展示用的命中说明：只留较长的术语（短的像 "granular" 说明性差）
    paper['score'] = round(s, 2)
    paper['liked_boost'] = round(boost, 3)
    paper['why'] = sorted({h for h in hits if len(h) >= 5},
                          key=lambda x: -len(x))[:6] or sorted(set(hits), key=lambda x: -len(x))[:4]
    if why_like:
        paper['why'] = list(paper['why']) + [f'👍{w}' for w in why_like[:2]]
    return paper['score']
