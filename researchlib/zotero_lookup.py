#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 在 Zotero 库里找条目和全文。

翻译流程的第一步应该是「先看 Zotero 里有没有」：
用户很可能早就收藏过这篇论文（甚至已经存了全文 PDF），
那就没必要再下一遍。命中时直接复用本地 PDF，效率和一致性都更好。

只读访问（immutable），不打扰正在运行的 Zotero。
"""
import os
import re
import sqlite3

from . import config as C
from .util import log

# Zotero 附件路径的两种形式
_STORAGE_PREFIX = 'storage:'


def _connect():
    if not os.path.exists(C.ZOTERO_DB):
        return None
    con = sqlite3.connect(f'file:{C.ZOTERO_DB}?immutable=1', uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def _attach_path(con, parent_id):
    """取某个条目的 PDF 附件绝对路径（存在才算）。"""
    rows = con.execute("""SELECT ia.path, i.key
        FROM itemAttachments ia JOIN items i ON ia.itemID = i.itemID
        WHERE ia.parentItemID = ? AND ia.contentType = 'application/pdf'""",
        (parent_id,)).fetchall()
    for r in rows:
        p = r['path'] or ''
        if p.startswith(_STORAGE_PREFIX):
            full = os.path.join(C.HOME, 'Zotero', 'storage', r['key'],
                                p[len(_STORAGE_PREFIX):])
        elif p.startswith('attachments:'):
            full = os.path.join(C.HOME, 'Zotero', p[len('attachments:'):].lstrip('/'))
        elif os.path.isabs(p):
            full = p
        else:
            continue
        if os.path.exists(full) and os.path.getsize(full) > 20000:
            return full
    return None


def _by_doi(con, doi):
    return con.execute("""SELECT d.itemID FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
        WHERE f.fieldName = 'DOI' AND lower(v.value) = ?""",
        (doi.lower(),)).fetchone()


def _by_arxiv(con, arxiv):
    """arXiv id 常在 extra 或 url 字段里。"""
    base = re.sub(r'v\d+$', '', arxiv.strip())
    rows = con.execute("""SELECT d.itemID, v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
        WHERE f.fieldName IN ('extra', 'url')""").fetchall()
    for r in rows:
        val = (r['value'] or '').lower()
        if base and base.lower() in val:
            return {'itemID': r['itemID']}
    return None


def _by_title(con, title):
    norm = re.sub(r'[^a-z0-9 ]+', ' ', (title or '').lower())
    norm = re.sub(r'\s+', ' ', norm).strip()
    if len(norm) < 12:
        return None
    rows = con.execute("""SELECT d.itemID, v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
        WHERE f.fieldName = 'title'""").fetchall()
    for r in rows:
        t = re.sub(r'[^a-z0-9 ]+', ' ', (r['value'] or '').lower())
        t = re.sub(r'\s+', ' ', t).strip()
        if t and (t == norm or (len(norm) > 25 and norm[:60] in t)):
            return {'itemID': r['itemID']}
    return None


def find(paper):
    """按 DOI → arXiv → 标题 依次在 Zotero 里找。

    返回 dict：
      {'itemID': int, 'pdf': <本地PDF绝对路径或None>, 'match': 'doi|arxiv|title'}
    找不到返回 None。
    """
    con = _connect()
    if con is None:
        return None
    try:
        hit, how = None, ''
        doi = (paper.get('doi') or '').strip()
        if doi:
            r = _by_doi(con, doi)
            if r:
                hit, how = r['itemID'], 'doi'
        if hit is None and paper.get('arxiv'):
            r = _by_arxiv(con, paper['arxiv'])
            if r:
                hit, how = r['itemID'], 'arxiv'
        if hit is None and paper.get('title'):
            r = _by_title(con, paper['title'])
            if r:
                hit, how = r['itemID'], 'title'
        if hit is None:
            log('  Zotero：没有对应条目，将联网下载')
            return None
        pdf = _attach_path(con, hit)
        log(f'  Zotero：命中条目 itemID={hit}（按 {how}）'
            + (f'，已有全文 {os.path.getsize(pdf)//1024} KB' if pdf else '，但无 PDF 附件'))
        return {'itemID': hit, 'pdf': pdf, 'match': how}
    finally:
        con.close()
