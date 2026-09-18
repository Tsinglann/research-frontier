#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""zotero —— 只读访问本机 Zotero 文献库。

后端：直接读 ~/Zotero/zotero.sqlite（用 Python 内置 sqlite3，无需装任何包）。
  * 默认 immutable 模式：不打扰正在运行的 Zotero，也不受其数据库锁影响
  * --snapshot：先把库复制到 _cache/ 再读（要绝对一致性时用）
  若在 Zotero 设置里开启了「本地 API」，也可用 curl 走 http://127.0.0.1:23119/api/，
  但本工具不依赖它。

用法：
  zotero.py find <关键词> [--limit N]   搜索标题 / 作者 / 期刊 / DOI
  zotero.py recent [--limit N]          最近添加的文献
  zotero.py show <id>                   条目详情（含附件与磁盘路径）
  zotero.py pdf <id>                    打印 PDF 附件的绝对路径
  zotero.py bib <id>                    输出 BibTeX
  zotero.py audit                       附件存活审计（找出库里的死链）

<id> 可以是数字 itemID，也可以是 8 位 item key。
"""
import argparse
import os
import re
import shutil
import sqlite3
import sys
import unicodedata

HOME = os.path.expanduser('~')
ZDIR = os.path.join(HOME, 'Zotero')
DB = os.path.join(ZDIR, 'zotero.sqlite')
STORE = os.path.join(ZDIR, 'storage')
SNAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', '_cache', 'zotero_snapshot.sqlite')

FIELDS = ['title', 'publicationTitle', 'journalAbbreviation', 'date', 'volume',
          'issue', 'pages', 'DOI', 'url', 'publisher', 'ISBN', 'abstractNote',
          'extra', 'series', 'edition', 'place', 'university', 'institution']

BIB_TYPE = {'journalArticle': 'article', 'book': 'book', 'bookSection': 'incollection',
            'conferencePaper': 'inproceedings', 'preprint': 'misc',
            'thesis': 'phdthesis', 'report': 'techreport', 'computerProgram': 'misc'}

BIB_FIELD = {'title': 'title', 'publicationTitle': 'journal', 'volume': 'volume',
             'issue': 'number', 'pages': 'pages', 'DOI': 'doi',
             'publisher': 'publisher', 'ISBN': 'isbn', 'url': 'url',
             'series': 'series', 'place': 'address', 'edition': 'edition'}


# ---------------------------------------------------------------- 连接

def connect(snapshot=False):
    if not os.path.exists(DB):
        sys.exit(f'找不到 Zotero 数据库：{DB}')
    if snapshot:
        os.makedirs(os.path.dirname(SNAP), exist_ok=True)
        for suf in ('', '-journal', '-wal', '-shm'):
            if os.path.exists(DB + suf):
                shutil.copy2(DB + suf, SNAP + suf)
        return sqlite3.connect(SNAP)
    return sqlite3.connect(f'file:{DB}?immutable=1', uri=True)


def not_deleted(alias='i'):
    return (f'{alias}.itemID NOT IN (SELECT itemID FROM deletedItems) '
            f'AND {alias}.itemID NOT IN (SELECT itemID FROM deletedItems '
            f'WHERE itemID IS NULL)')


# ---------------------------------------------------------------- 取数

def resolve_id(con, ref):
    """itemID 或 item key → itemID"""
    if str(ref).isdigit():
        r = con.execute('SELECT itemID FROM items WHERE itemID=?', (int(ref),)).fetchone()
        if r:
            return r[0]
    r = con.execute('SELECT itemID FROM items WHERE key=?', (str(ref).upper(),)).fetchone()
    if r:
        return r[0]
    sys.exit(f'找不到条目：{ref}')


def fields_of(con, iid):
    rows = con.execute("""
        SELECT f.fieldName, idv.value FROM itemData id
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        JOIN fields f ON f.fieldID = id.fieldID
        WHERE id.itemID = ?""", (iid,)).fetchall()
    return {k: v for k, v in rows}


def type_of(con, iid):
    r = con.execute("""SELECT it.typeName FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE i.itemID = ?""", (iid,)).fetchone()
    return r[0] if r else '?'


def key_of(con, iid):
    r = con.execute('SELECT key FROM items WHERE itemID=?', (iid,)).fetchone()
    return r[0] if r else ''


def creators_of(con, iid):
    return con.execute("""
        SELECT c.lastName, c.firstName, ct.creatorType FROM itemCreators ic
        JOIN creators c ON c.creatorID = ic.creatorID
        LEFT JOIN creatorTypes ct ON ct.creatorTypeID = ic.creatorTypeID
        WHERE ic.itemID = ? ORDER BY ic.orderIndex""", (iid,)).fetchall()


def collections_of(con, iid):
    return [r[0] for r in con.execute("""
        SELECT co.collectionName FROM collectionItems ci
        JOIN collections co ON co.collectionID = ci.collectionID
        WHERE ci.itemID = ?""", (iid,)).fetchall()]


def attach_path(key, mode, path):
    """把 Zotero 的附件路径解析成磁盘绝对路径"""
    if not path:
        return None
    if path.startswith('storage:'):
        return os.path.join(STORE, key, os.path.basename(path[8:]))
    if path.startswith('attachments:'):
        return os.path.join(STORE, path[12:])
    if mode == 2:                       # linked_file
        return path
    return None


def attachments_of(con, iid):
    rows = con.execute("""
        SELECT i.itemID, i.key, ia.linkMode, ia.contentType, ia.path
        FROM itemAttachments ia JOIN items i ON i.itemID = ia.itemID
        WHERE ia.parentItemID = ?""", (iid,)).fetchall()
    out = []
    for aid, key, mode, ctype, path in rows:
        p = attach_path(key, mode, path)
        out.append({'itemID': aid, 'key': key, 'mode': mode,
                    'contentType': ctype, 'path': p,
                    'exists': bool(p and os.path.exists(p))})
    return out


def search(con, kw, limit):
    """搜索标题/期刊/DOI/摘要 + 作者。用 EXISTS 避免多字段命中造成的重复行。"""
    like = f'%{kw}%'
    rows = con.execute("""
        SELECT i.itemID
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND it.typeName NOT IN ('attachment', 'annotation', 'note')
          AND (
            EXISTS (SELECT 1 FROM itemData id
                    JOIN itemDataValues idv ON idv.valueID = id.valueID
                    JOIN fields f ON f.fieldID = id.fieldID
                    WHERE id.itemID = i.itemID
                      AND f.fieldName IN ('title', 'publicationTitle',
                                          'DOI', 'abstractNote')
                      AND idv.value LIKE ?)
            OR EXISTS (SELECT 1 FROM itemCreators ic
                       JOIN creators c ON c.creatorID = ic.creatorID
                       WHERE ic.itemID = i.itemID
                         AND (c.lastName LIKE ? OR c.firstName LIKE ?))
          )
        ORDER BY i.itemID DESC LIMIT ?""", (like, like, like, limit)).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------- 输出

def brief(con, iid):
    f, t = fields_of(con, iid), type_of(con, iid)
    au = creators_of(con, iid)
    who = (au[0][0] if au else '?')
    if len(au) > 1:
        who += ' 等'
    d = (f.get('date') or '')[:4]
    ttl = (f.get('title') or '(无标题)')
    if len(ttl) > 78:
        ttl = ttl[:75] + '…'
    return f'{iid:>6}  {t:<15} {who:<14} {d:<5} {ttl}'


def show(con, iid):
    f, t = fields_of(con, iid), type_of(con, iid)
    print(f'itemID : {iid}   key: {key_of(con, iid)}   类型: {t}')
    print(f'标题   : {f.get("title", "(无)")}')
    au = creators_of(con, iid)
    if au:
        print('作者   : ' + '; '.join(
            f'{l}, {fi}' if fi else l for l, fi, _ in au))
    for k in ('publicationTitle', 'volume', 'issue', 'pages', 'date',
              'publisher', 'DOI', 'ISBN', 'url'):
        if f.get(k):
            print(f'{k:<7}: {f[k]}')
    cols = collections_of(con, iid)
    if cols:
        print('分类   : ' + ' / '.join(cols))
    atts = attachments_of(con, iid)
    if atts:
        print('附件   :')
        for a in atts:
            mark = '✓' if a['exists'] else '✗ 文件缺失'
            print(f'   [{a["contentType"] or "?"}] {mark}')
            print(f'      {a["path"] or "(无路径)"}')


def bibtex(con, iid):
    f, t = fields_of(con, iid), type_of(con, iid)
    au = creators_of(con, iid)
    y = re.findall(r'\d{4}', f.get('date', ''))
    first = re.sub(r'[^A-Za-z]', '', (au[0][0] if au else 'anon')) or 'anon'
    w = re.findall(r'[A-Za-z]{3,}', f.get('title', ''))
    cite = f'{first.lower()}{y[0] if y else ""}{w[0].lower() if w else "item"}'
    lines = [f'@{BIB_TYPE.get(t, "misc")}{{{cite},']
    if au:
        names = ['{}, {}'.format(l, fi) if fi else l for l, fi, _ in au]
        lines.append('  author    = {' + ' and '.join(names) + '},')
    for k, bk in BIB_FIELD.items():
        if f.get(k):
            lines.append(f'  {bk:<9} = {{{f[k]}}},')
    if y:
        lines.append(f'  year      = {{{y[0]}}},')
    lines.append('}')
    return '\n'.join(lines)


def audit(con):
    rows = con.execute("""
        SELECT ia.parentItemID, i.key, ia.linkMode, ia.contentType, ia.path
        FROM itemAttachments ia JOIN items i ON i.itemID = ia.itemID""").fetchall()
    ok = miss = nopath = 0
    missing = []
    for parent, key, mode, ctype, path in rows:
        p = attach_path(key, mode, path)
        if p is None:
            nopath += 1
        elif os.path.exists(p):
            ok += 1
        else:
            miss += 1
            missing.append((parent, p))
    print(f'附件总数 {len(rows)}  文件存在 {ok}  文件缺失 {miss}  无路径 {nopath}')
    if missing:
        print(f'\n缺失清单（前 {min(len(missing), 30)} 条，可用 zotero.py show <parent> 查详情）：')
        for parent, p in missing[:30]:
            print(f'   parent={parent:<6} {p.replace(HOME, "~")}')
        if len(missing) > 30:
            print(f'   … 另有 {len(missing) - 30} 条')


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description='只读访问本机 Zotero 文献库')
    ap.add_argument('--snapshot', action='store_true', help='先复制快照再读')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('find', 'recent', 'show', 'pdf', 'bib'):
        p = sub.add_parser(name)
        if name == 'find':
            p.add_argument('keyword')
        if name in ('show', 'pdf', 'bib'):
            p.add_argument('ref')
        p.add_argument('--limit', type=int, default=20)
        p.add_argument('--snapshot', action='store_true')
    sub.add_parser('audit').add_argument('--snapshot', action='store_true')

    args = ap.parse_args()
    con = connect(getattr(args, 'snapshot', False))

    if args.cmd == 'find':
        ids = search(con, args.keyword, args.limit)
        if not ids:
            print('无匹配')
        for iid in ids:
            print(brief(con, iid))
        print(f'\n共 {len(ids)} 条（--limit 可调）')

    elif args.cmd == 'recent':
        rows = con.execute("""
            SELECT i.itemID FROM items i JOIN itemTypes it ON it.itemTypeID=i.itemTypeID
            WHERE it.typeName NOT IN ('attachment','annotation','note')
            ORDER BY i.dateAdded DESC LIMIT ?""", (args.limit,)).fetchall()
        for (iid,) in rows:
            print(brief(con, iid))

    elif args.cmd == 'show':
        show(con, resolve_id(con, args.ref))

    elif args.cmd == 'pdf':
        iid = resolve_id(con, args.ref)
        atts = [a for a in attachments_of(con, iid) if a['path']]
        if not atts:
            sys.exit('该条目没有附件路径')
        for a in atts:
            if not a['exists']:
                print(f'# 文件缺失: {a["path"]}', file=sys.stderr)
            print(a['path'])

    elif args.cmd == 'bib':
        print(bibtex(con, resolve_id(con, args.ref)))

    elif args.cmd == 'audit':
        audit(con)


if __name__ == '__main__':
    main()
