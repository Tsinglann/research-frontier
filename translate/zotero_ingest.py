#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""zotero_ingest.py —— 把浏览器下载的 PDF 自动识别、归档并挂到 Zotero 对应条目。

用途：需 CARSI 登录才能拿的文献（Nature / IOP / Wiley / RSC / Science …），
由你在浏览器里下载到某个目录，本工具负责剩下的脏活：
  识别 DOI/标题 → 匹配 Zotero 已有条目 → 复制进 storage → 挂成附件
  → 匹配不到的列出来（可用 --new-in 新建条目并放进指定分类）

与「手工拖进 Zotero」相比，它**不会产生重复条目**。

用法（需先关闭 Zotero）：
  zotero_ingest.py ~/Downloads                       # 预演，只报告
  zotero_ingest.py ~/Downloads --apply               # 归档并挂附件
  zotero_ingest.py ~/Downloads --apply --new-in 30   # 匹配不到的新建到 collection 30
"""
import argparse
import collections
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf as fitz                                   # noqa: E402

DB = os.path.expanduser('~/Zotero/zotero.sqlite')
STORE = os.path.expanduser('~/Zotero/storage')
BAKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                      '_cache', 'zotero_backup')
KEYCHARS = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'
DOI_RE = re.compile(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+')


def doi_from_filename(path):
    """文件名形如 10.1103_PhysRevE.59.6448.pdf（批量下载工具的命名）→ 还原 DOI"""
    b = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r'^(10\.\d{4,9})_(.+)$', b)
    return f'{m.group(1)}/{m.group(2)}' if m else None


def pdf_meta(path):
    """返回 (doi, title)：DOI 从前两页正文抽，抽不到就用文件名兜底；标题优先用 PDF 元数据"""
    doi = None
    title = None
    try:
        out = subprocess.run(['pdfinfo', path], capture_output=True, text=True).stdout
        m = re.search(r'^Title:[ \t]*(.+)$', out, re.M)
        if m and m.group(1).strip():
            title = m.group(1).strip()
    except Exception:
        pass
    try:
        d = fitz.open(path)
        txt = ''.join(d[i].get_text() for i in range(min(2, d.page_count)))
        d.close()
        for m in DOI_RE.finditer(txt):
            cand = m.group(0).rstrip('.,;)' + "'")
            if len(cand) > 8:
                doi = cand
                break
    except Exception:
        pass
    if not doi:
        doi = doi_from_filename(path)      # 文件名兜底（批量下载工具按 DOI 命名）
    return doi, title


def new_key(cur):
    import random
    while True:
        k = ''.join(random.choice(KEYCHARS) for _ in range(8))
        if not cur.execute('SELECT 1 FROM items WHERE key=?', (k,)).fetchone():
            return k


def match(cur, doi, title):
    """返回 (itemID, 依据) 或 (None, 原因)"""
    if doi:
        r = cur.execute("""SELECT i.itemID FROM items i
            JOIN itemData id ON id.itemID=i.itemID
            JOIN itemDataValues idv ON idv.valueID=id.valueID
            JOIN fields f ON f.fieldID=id.fieldID
            WHERE f.fieldName='DOI' AND lower(idv.value)=?
              AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
            LIMIT 1""", (doi.lower(),)).fetchone()
        if r:
            return r[0], f'DOI {doi}'
    if title:
        norm = ' '.join(title.lower().split())
        for iid, t in cur.execute("""SELECT i.itemID, idv.value FROM items i
                JOIN itemTypes it ON it.itemTypeID=i.itemTypeID
                JOIN itemData id ON id.itemID=i.itemID
                JOIN itemDataValues idv ON idv.valueID=id.valueID
                JOIN fields f ON f.fieldID=id.fieldID
                WHERE f.fieldName='title'
                  AND it.typeName NOT IN ('attachment','note','annotation')
                  AND i.itemID NOT IN (SELECT itemID FROM deletedItems)"""):
            if ' '.join(t.lower().split()) == norm:
                return iid, '标题精确匹配'
        key_words = [w for w in re.findall(r'[A-Za-z][A-Za-z-]{4,}', title)
                     if w.lower() not in ('the', 'and', 'for', 'with', 'from')][:4]
        if key_words:
            sql = """SELECT i.itemID FROM items i
                JOIN itemTypes it ON it.itemTypeID=i.itemTypeID
                JOIN itemData id ON id.itemID=i.itemID
                JOIN itemDataValues idv ON idv.valueID=id.valueID
                JOIN fields f ON f.fieldID=id.fieldID
                WHERE f.fieldName='title'
                  AND it.typeName NOT IN ('attachment','note','annotation')
                  AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
                  AND %s LIMIT 1""" % ' AND '.join(['idv.value LIKE ?'] * len(key_words))
            r = cur.execute(sql, tuple('%' + w + '%' for w in key_words)).fetchone()
            if r:
                return r[0], f'标题关键词 {key_words}'
    return None, '未匹配到已有条目'


def attach(cur, itemID, src, title='全文 PDF'):
    fname = os.path.basename(src)
    # 防重复：同父条目下已有同名附件就跳过（回滚 2026-09-18 见过的重复问题）
    for (path,) in cur.execute('SELECT path FROM itemAttachments WHERE parentItemID=?',
                               (itemID,)).fetchall():
        if path and os.path.basename(path.replace('storage:', '')) == fname:
            return None, None
    key = new_key(cur)
    d = os.path.join(STORE, key)
    os.makedirs(d, exist_ok=True)
    shutil.copy2(src, os.path.join(d, fname))
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""INSERT INTO items (itemTypeID,dateAdded,dateModified,
                   clientDateModified,libraryID,key,version,synced)
                   VALUES (3,?,?,?,1,?,0,0)""", (now, now, now, key))
    aid = cur.lastrowid
    cur.execute("""INSERT INTO itemAttachments (itemID,parentItemID,linkMode,
                   contentType,path,syncState)
                   VALUES (?,?,0,'application/pdf',?,0)""",
                (aid, itemID, f'storage:{fname}'))
    fid = cur.execute("SELECT fieldID FROM fields WHERE fieldName='title'").fetchone()
    if fid and title:
        vid = cur.execute('SELECT valueID FROM itemDataValues WHERE value=?',
                          (title,)).fetchone()
        if not vid:
            cur.execute('INSERT INTO itemDataValues (value) VALUES (?)', (title,))
            vid = (cur.lastrowid,)
        cur.execute('INSERT INTO itemData (itemID,fieldID,valueID) VALUES (?,?,?)',
                    (aid, fid[0], vid[0]))
    cur.execute('UPDATE items SET synced=0, dateModified=? WHERE itemID=?', (now, itemID))
    return key, aid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--new-in', type=int, default=None,
                    help='匹配不到时，新建条目并放进该 collectionID')
    ap.add_argument('--move', action='store_true', help='归档后删除源文件')
    args = ap.parse_args()

    pdfs = []
    for d in args.dirs:
        d = os.path.expanduser(d)
        if os.path.isfile(d) and d.lower().endswith('.pdf'):
            pdfs.append(d)
        else:
            for root, _dn, fn in os.walk(d):
                pdfs += [os.path.join(root, f) for f in fn if f.lower().endswith('.pdf')]
    if not pdfs:
        sys.exit('没找到 PDF')

    if args.apply:
        con = sqlite3.connect(DB)
        cur = con.cursor()
        os.makedirs(BAKDIR, exist_ok=True)
        bk = os.path.join(BAKDIR, f'zotero_preingest_{time.strftime("%Y%m%d_%H%M%S")}.sqlite')
        con.close()
        shutil.copy2(DB, bk)
        con = sqlite3.connect(DB)
        cur = con.cursor()
        print(f'[备份] {bk}\n')
    else:
        # 只读预演用 immutable：无需 journal，只读文件系统下也能跑
        con = sqlite3.connect(f'file:{DB}?immutable=1', uri=True)
        cur = con.cursor()

    stat = collections.Counter()
    unmatched = []
    for p in pdfs:
        doi, title = pdf_meta(p)
        iid, how = match(cur, doi, title)
        name = os.path.basename(p)[:56]
        if iid is None:
            stat['未匹配'] += 1
            unmatched.append((p, doi, title))
            print(f'  [?] {name}')
            print(f'      DOI={doi or "-"}  标题={(title or "-")[:52]}')
            if args.apply and args.new_in is not None:
                # 新建最简条目（journalArticle）并归入指定分类
                key = new_key(cur)
                now = time.strftime('%Y-%m-%d %H:%M:%S')
                cur.execute("""INSERT INTO items (itemTypeID,dateAdded,dateModified,
                               clientDateModified,libraryID,key,version,synced)
                               VALUES (22,?,?,?,1,?,0,0)""", (now, now, now, key))
                newid = cur.lastrowid
                for fname_, val in (('title', title), ('DOI', doi)):
                    if not val:
                        continue
                    fid = cur.execute('SELECT fieldID FROM fields WHERE fieldName=?',
                                      (fname_,)).fetchone()
                    if not fid:
                        continue
                    vid = cur.execute('SELECT valueID FROM itemDataValues WHERE value=?',
                                      (val,)).fetchone()
                    if not vid:
                        cur.execute('INSERT INTO itemDataValues (value) VALUES (?)', (val,))
                        vid = (cur.lastrowid,)
                    cur.execute('INSERT INTO itemData (itemID,fieldID,valueID) VALUES (?,?,?)',
                                (newid, fid[0], vid[0]))
                cur.execute('INSERT INTO collectionItems (collectionID,itemID,orderIndex) '
                            'VALUES (?,?,0)', (args.new_in, newid))
                attach(cur, newid, p)
                print(f'      → 已新建条目 {newid} 并归入 collection {args.new_in}')
                stat['新建条目'] += 1
            continue
        exists = cur.execute("""SELECT COUNT(*) FROM itemAttachments ia
            WHERE ia.parentItemID=?""", (iid,)).fetchone()[0]
        print(f'  [✓] {name}')
        print(f'      → 条目 {iid}（{how}），该条目现有 {exists} 个附件')
        if args.apply:
            key, aid = attach(cur, iid, p)
            if key is None:
                print('      → 该条目已有同名附件，跳过（不重复）')
                stat['重复跳过'] += 1
                continue
            if args.move:
                os.remove(p)
            print(f'      → 已附加 key={key} attachID={aid}')
            stat['已附加'] += 1

    if args.apply:
        con.commit()
        print(f'\n统计: {dict(stat)}')
        print('[已提交] 打开 Zotero 检查；匹配不到的可加 --new-in <collectionID> 重跑。')
    else:
        print(f'\n预演结束。共 {len(pdfs)} 个 PDF，未匹配 {len(unmatched)} 个。')
        print('加 --apply 执行。')
    con.close()


if __name__ == '__main__':
    main()
