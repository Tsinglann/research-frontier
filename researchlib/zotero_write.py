#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 把论文收藏进 Zotero（写入库）。

⚠️ 直接改 `~/Zotero/zotero.sqlite`。Zotero 运行时会锁库，也会用内存状态覆盖
我们的写入，所以：
  * 检测到 23119 在监听（Zotero 在跑）→ **拒绝写入**并明确提示先退出 Zotero
  * 写库前自动备份到 `_cache/zotero_backup_<时间>.sqlite`
  * 写完后把 items.synced 置 0，让 Zotero 下次同步时上传

条目建到根分类「研究前沿app收藏」下（不存在则创建）。
Schema 处理照搬项目里已验证的 `_tools/zotero_attach.py` / `zotero_ingest.py`。
"""
import datetime as dt
import os
import random
import re
import shutil
import socket
import sqlite3
import string

from . import config as C
from .util import log

COLLECTION_NAME = '研究前沿app收藏'
ZOTERO_STORAGE = os.path.join(C.HOME, 'Zotero', 'storage')
BACKUP_DIR = os.path.join(C.PKG_DIR, '_cache')


def zotero_running():
    """23119 有监听 = Zotero 在运行（它自己起的本地服务端口）。"""
    for host in ('127.0.0.1', '::1'):
        s = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET,
                          socket.SOCK_STREAM)
        s.settimeout(0.6)
        try:
            if s.connect_ex((host, 23119)) == 0:
                return True
        except OSError:
            pass
        finally:
            s.close()
    return False


def _new_key(cur, n=8):
    alpha = string.ascii_uppercase + string.digits
    while True:
        k = ''.join(random.choice(alpha) for _ in range(n))
        if not cur.execute('SELECT 1 FROM items WHERE key=?', (k,)).fetchone():
            return k


def _set_field(cur, item_id, field, value):
    if value in (None, ''):
        return
    row = cur.execute('SELECT fieldID FROM fields WHERE fieldName=?', (field,)).fetchone()
    if not row:
        return
    fid = row[0]
    row = cur.execute('SELECT valueID FROM itemDataValues WHERE value=?', (str(value),)).fetchone()
    vid = row[0] if row else cur.execute(
        'INSERT INTO itemDataValues (value) VALUES (?)', (str(value),)).lastrowid
    cur.execute('INSERT OR REPLACE INTO itemData (itemID,fieldID,valueID) VALUES (?,?,?)',
                (item_id, fid, vid))


def _get_field(cur, item_id, field):
    row = cur.execute("""SELECT v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID=v.valueID
        JOIN fields f ON d.fieldID=f.fieldID
        WHERE d.itemID=? AND f.fieldName=?""", (item_id, field)).fetchone()
    return row[0] if row else ''


def _find_item(cur, doi='', title=''):
    if doi:
        r = cur.execute("""SELECT d.itemID FROM itemData d
            JOIN itemDataValues v ON d.valueID=v.valueID
            JOIN fields f ON d.fieldID=f.fieldID
            WHERE f.fieldName='DOI' AND lower(v.value)=?""", (doi.lower(),)).fetchone()
        if r:
            return r[0]
    if title:
        r = cur.execute("""SELECT d.itemID FROM itemData d
            JOIN itemDataValues v ON d.valueID=v.valueID
            JOIN fields f ON d.fieldID=f.fieldID
            WHERE f.fieldName='title' AND lower(v.value)=?""", (title.lower(),)).fetchone()
        if r:
            return r[0]
    return None


def _ensure_collection(cur, name):
    r = cur.execute('SELECT collectionID FROM collections WHERE collectionName=?', (name,)).fetchone()
    if r:
        return r[0]
    lib = cur.execute('SELECT libraryID FROM libraries ORDER BY libraryID LIMIT 1').fetchone()
    libid = lib[0] if lib else 1
    parent = cur.execute("SELECT collectionID FROM collections WHERE collectionName='Library'"
                         ).fetchone()
    now = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 注意：collections 表**没有** dateAdded / dateModified，只有 clientDateModified
    cid = cur.execute("""INSERT INTO collections
        (collectionName, parentCollectionID, clientDateModified, libraryID, key,
         version, synced)
        VALUES (?,?,?,?,?,0,0)""",
        (name, parent[0] if parent else None, now, libid, _new_key(cur))).lastrowid
    log(f'  新建分类：{name}（collectionID={cid}）')
    return cid


def _in_collection(cur, coll_id, item_id):
    return bool(cur.execute('SELECT 1 FROM collectionItems WHERE collectionID=? AND itemID=?',
                            (coll_id, item_id)).fetchone())


def collect(paper, dry_run=False):
    """把一篇论文收藏进 Zotero。返回 (状态字符串, itemID 或 None)。"""
    doi = (paper.get('doi') or '').strip()
    title = (paper.get('title') or '').strip()
    if not doi and not title:
        return 'no-identifier', None
    if not os.path.exists(C.ZOTERO_DB):
        return 'no-db', None
    if zotero_running() and not dry_run:
        return 'zotero-running', None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not dry_run:
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(C.ZOTERO_DB, os.path.join(BACKUP_DIR, f'zotero_backup_{stamp}.sqlite'))

    con = sqlite3.connect(C.ZOTERO_DB, timeout=20)
    try:
        cur = con.cursor()
        coll = _ensure_collection(cur, COLLECTION_NAME)
        item_id = _find_item(cur, doi, title)
        state = 'reused'
        if item_id is None:
            now = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            tid = cur.execute("SELECT itemTypeID FROM itemTypes WHERE typeName='journalArticle'"
                              ).fetchone()
            if not tid:
                return 'no-itemtype', None
            item_id = cur.execute("""INSERT INTO items
                (itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key,
                 version, synced)
                VALUES (?,?,?,?,1,?,0,0)""",
                (tid[0], now, now, now, _new_key(cur))).lastrowid
            _set_field(cur, item_id, 'title', title)
            _set_field(cur, item_id, 'DOI', doi)
            _set_field(cur, item_id, 'publicationTitle', paper.get('journal') or '')
            _set_field(cur, item_id, 'date', paper.get('date') or '')
            _set_field(cur, item_id, 'url', paper.get('url') or paper.get('pdfurl') or '')
            _set_field(cur, item_id, 'abstractNote', paper.get('abstract') or '')
            # 作者（firstCreator 由 Zotero 生成，这里只写入 creators 表）
            authors = paper.get('authors') or []
            for idx, name in enumerate(authors[:20]):
                name = (name or '').strip()
                if not name:
                    continue
                parts = name.split()
                last = parts[-1] if parts else name
                first = ' '.join(parts[:-1]) if len(parts) > 1 else ''
                row = cur.execute('SELECT creatorID FROM creators WHERE lastName=? AND firstName=?',
                                  (last, first)).fetchone()
                cid = row[0] if row else cur.execute(
                    'INSERT INTO creators (firstName,lastName) VALUES (?,?)',
                    (first, last)).lastrowid
                ct = cur.execute("SELECT creatorTypeID FROM creatorTypes WHERE creatorType='author'"
                                 ).fetchone()
                cur.execute("""INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex)
                               VALUES (?,?,?,?)""", (item_id, cid, ct[0] if ct else 1, idx))
            state = 'created'
        if not _in_collection(cur, coll, item_id):
            nxt = (cur.execute('SELECT COALESCE(MAX(orderIndex),0)+1 FROM collectionItems '
                               'WHERE collectionID=?', (coll,)).fetchone() or [1])[0]
            cur.execute('INSERT INTO collectionItems (collectionID,itemID,orderIndex) VALUES (?,?,?)',
                        (coll, item_id, nxt))
        else:
            state = state + '+already' if state == 'reused' else state
        cur.execute('UPDATE items SET synced=0, dateModified=? WHERE itemID=?',
                    (dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), item_id))
        if dry_run:
            con.rollback()
            return f'dry-{state}', item_id
        con.commit()
        return state, item_id
    finally:
        con.close()


def uncollect(paper):
    """从收藏分类里移除（不移除条目本身）。"""
    if zotero_running():
        return 'zotero-running'
    doi = (paper.get('doi') or '').strip()
    title = (paper.get('title') or '').strip()
    con = sqlite3.connect(C.ZOTERO_DB, timeout=20)
    try:
        cur = con.cursor()
        r = cur.execute('SELECT collectionID FROM collections WHERE collectionName=?',
                        (COLLECTION_NAME,)).fetchone()
        if not r:
            return 'no-collection'
        item_id = _find_item(cur, doi, title)
        if not item_id:
            return 'not-found'
        cur.execute('DELETE FROM collectionItems WHERE collectionID=? AND itemID=?',
                    (r[0], item_id))
        con.commit()
        return 'removed'
    finally:
        con.close()


def collection_count():
    """收藏分类里现有多少条（给部件显示）。"""
    try:
        con = sqlite3.connect(f'file:{C.ZOTERO_DB}?immutable=1', uri=True)
        cur = con.cursor()
        r = cur.execute("""SELECT COUNT(*) FROM collectionItems ci
            JOIN collections c ON ci.collectionID=c.collectionID
            WHERE c.collectionName=?""", (COLLECTION_NAME,)).fetchone()
        con.close()
        return r[0] if r else 0
    except Exception:
        return 0
