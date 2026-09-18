#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 只读读取本机 Zotero 文献库。

用 immutable 模式打开 sqlite，不打扰正在运行的 Zotero，也不受其锁影响。
"""
import os
import re
import sqlite3

from . import config as C
from .util import clean_text, norm_title, log

# 不算「文献」的条目类型
NON_ITEM_TYPES = ('attachment', 'note', 'annotation')

# 从 Zotero extra 字段里抠 arXiv id
ARXIV_RE = re.compile(r'arxiv[:\s]*([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/\d{7})', re.I)
DOI_RE = re.compile(r'10\.\d{4,9}/[^\s"<>]+')


def _connect():
    if not os.path.exists(C.ZOTERO_DB):
        raise FileNotFoundError(f'找不到 Zotero 数据库：{C.ZOTERO_DB}')
    con = sqlite3.connect(f'file:{C.ZOTERO_DB}?immutable=1', uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def _items(con, typ):
    """取某个 itemType 的条目，返回 dict。"""
    sql = """
      SELECT i.itemID AS id, t.typeName AS type, i.key AS key
        FROM items i
        JOIN itemTypes t ON i.itemTypeID = t.itemTypeID
       WHERE t.typeName = ?
    """
    return [dict(r) for r in con.execute(sql, (typ,))]


def _field_map(con, item_ids, field_names):
    """一次性取多个 item 的若干字段 → {itemID: {field: value}}。"""
    if not item_ids:
        return {}
    qs = ','.join('?' * len(item_ids))
    fs = ','.join('?' * len(field_names))
    sql = f"""
      SELECT d.itemID AS iid, f.fieldName AS fn, v.value AS val
        FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
       WHERE d.itemID IN ({qs}) AND f.fieldName IN ({fs})
    """
    out = {}
    for row in con.execute(sql, list(item_ids) + list(field_names)):
        out.setdefault(row['iid'], {})[row['fn']] = row['val']
    return out


def _creators(con, item_ids):
    """取作者（按 orderIndex 排序）。"""
    if not item_ids:
        return {}
    qs = ','.join('?' * len(item_ids))
    sql = f"""
      SELECT ic.itemID AS iid, c.lastName AS last, c.firstName AS first, ic.orderIndex AS ord
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
       WHERE ic.itemID IN ({qs})
       ORDER BY ic.itemID, ic.orderIndex
    """
    out = {}
    for row in con.execute(sql, list(item_ids)):
        out.setdefault(row['iid'], []).append((row['first'] or '', row['last'] or ''))
    return out


def _storage_paths(con, item_ids):
    """附件 → 磁盘绝对路径；只保留实际存在的 PDF。返回 {parentItemID: [path]}。"""
    if not item_ids:
        return {}
    qs = ','.join('?' * len(item_ids))
    sql = f"""
      SELECT ia.parentItemID AS pid, ia.contentType AS ctype, ia.path AS path,
             i.key AS akey
        FROM itemAttachments ia
        JOIN items i ON ia.itemID = i.itemID
       WHERE ia.parentItemID IN ({qs})
    """
    out = {}
    for row in con.execute(sql, list(item_ids)):
        if row['ctype'] != 'application/pdf':
            continue
        p = row['path'] or ''
        if p.startswith('storage:'):
            fn = p[len('storage:'):]
            full = os.path.join(C.HOME, 'Zotero', 'storage', row['akey'], fn)
        elif p.startswith('attachments:'):
            full = os.path.join(C.HOME, 'Zotero', p[len('attachments:'):].lstrip('/'))
        elif os.path.isabs(p):
            full = p
        else:
            continue
        if os.path.exists(full):
            out.setdefault(row['pid'], []).append(full)
    return out


def collection_counts(con):
    """分类 → 条目数。"""
    sql = """
      SELECT c.collectionName AS name, COUNT(ca.itemID) AS n
        FROM collections c
        LEFT JOIN collectionItems ca ON c.collectionID = ca.collectionID
       GROUP BY c.collectionID ORDER BY n DESC
    """
    return [(r['name'], r['n']) for r in con.execute(sql)]


def load_library(max_items=600):
    """读取整个文献库（期刊论文/书籍/预印本等），返回统一结构的列表。"""
    con = _connect()
    try:
        rows = []
        for typ in ('journalArticle', 'preprint', 'book', 'bookSection',
                    'conferencePaper', 'document', 'report', 'thesis'):
            rows.extend(_items(con, typ))
        # 去重（同一条目可能被多个类型查询命中）
        seen = set()
        rows = [r for r in rows if not (r['id'] in seen or seen.add(r['id']))]

        ids = [r['id'] for r in rows]
        fields = _field_map(con, ids, ['title', 'publicationTitle', 'date', 'DOI',
                                       'abstractNote', 'extra', 'url', 'volume',
                                       'pages', 'journalAbbreviation'])
        creators = _creators(con, ids)
        pdfs = _storage_paths(con, ids)
        colls = collection_counts(con)

        lib = []
        for r in rows:
            f = fields.get(r['id'], {})
            title = clean_text(f.get('title'))
            if not title:
                continue
            # 剔除 Zotero 里常见的附件泄漏条目
            if title.lower().strip() in ('full text pdf', 'pdf', 'snapshot', 'full text'):
                continue
            extra = f.get('extra') or ''
            arx = ARXIV_RE.search(extra) or ARXIV_RE.search(f.get('url') or '')
            doi = (f.get('DOI') or '').strip()
            if not doi:
                m = DOI_RE.search(extra)
                doi = m.group(0).rstrip('.') if m else ''
            date = str(f.get('date') or '')
            ym = re.search(r'(19|20)\d{2}', date)
            lib.append({
                'id': r['id'],
                'key': r['key'],
                'type': r['type'],
                'title': title,
                'journal': clean_text(f.get('publicationTitle') or
                                      f.get('journalAbbreviation') or ''),
                'year': int(ym.group(0)) if ym else None,
                'doi': doi,
                'arxiv': arx.group(1) if arx else '',
                'abstract': clean_text(f.get('abstractNote') or ''),
                'authors': [' '.join(x for x in a if x).strip() for a in creators.get(r['id'], [])],
                'pdf': (pdfs.get(r['id']) or [''])[0],
                'norm': norm_title(title),
            })
        log(f'Zotero：载入 {len(lib)} 条文献，分类 {len(colls)} 个')
        return lib, colls
    finally:
        con.close()
