#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""zotero_attach.py —— 给 Zotero 已有条目附加一个 PDF 文件（需先关闭 Zotero）。

做三件事：
  1. 把文件复制到 ~/Zotero/storage/<新key>/
  2. 在 items 表插入一条 attachment 条目（itemTypeID=3）
  3. 在 itemAttachments 表插入关联（linkMode=0 = imported_file）

用法：
  zotero_attach.py --item <itemID|key> --file <pdf> [--title <显示名>] [--apply]
  zotero_attach.py --batch <json>            # [{item, file, title}, ...]
"""
import argparse
import json
import os
import random
import shutil
import sqlite3
import sys
import time

DB = os.path.expanduser('~/Zotero/zotero.sqlite')
STORE = os.path.expanduser('~/Zotero/storage')
BAKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                      '_cache', 'zotero_backup')
KEYCHARS = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'      # Zotero 的 8 位 key 字符集


def new_key(cur):
    while True:
        k = ''.join(random.choice(KEYCHARS) for _ in range(8))
        if not cur.execute('SELECT 1 FROM items WHERE key=?', (k,)).fetchone():
            return k


def resolve(cur, ref):
    if str(ref).isdigit():
        r = cur.execute('SELECT itemID FROM items WHERE itemID=?', (int(ref),)).fetchone()
        if r:
            return r[0]
    r = cur.execute('SELECT itemID FROM items WHERE key=?', (str(ref).upper(),)).fetchone()
    return r[0] if r else None


def add_one(cur, itemID, src, title, apply_):
    if not os.path.exists(src):
        return False, f'源文件不存在: {src}'
    key = new_key(cur)
    fname = os.path.basename(src)
    dest_dir = os.path.join(STORE, key)
    if apply_:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src, os.path.join(dest_dir, fname))
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("""INSERT INTO items (itemTypeID, dateAdded, dateModified,
                       clientDateModified, libraryID, key, version, synced)
                       VALUES (3, ?, ?, ?, 1, ?, 0, 0)""", (now, now, now, key))
        aid = cur.lastrowid
        cur.execute("""INSERT INTO itemAttachments (itemID, parentItemID, linkMode,
                       contentType, path, syncState)
                       VALUES (?, ?, 0, 'application/pdf', ?, 0)""",
                    (aid, itemID, f'storage:{fname}'))
        # 附件显示名
        fid = cur.execute("SELECT fieldID FROM fields WHERE fieldName='title'").fetchone()
        if fid and title:
            vid = cur.execute('SELECT valueID FROM itemDataValues WHERE value=?',
                              (title,)).fetchone()
            if not vid:
                cur.execute('INSERT INTO itemDataValues (value) VALUES (?)', (title,))
                vid = (cur.lastrowid,)
            cur.execute('INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?,?,?)',
                        (aid, fid[0], vid[0]))
        # 父条目标记待同步
        cur.execute('UPDATE items SET synced=0, dateModified=? WHERE itemID=?',
                    (now, itemID))
        return True, f'item {itemID} ← {fname}  (key={key}, attachID={aid})'
    return True, f'[预演] item {itemID} ← {src}  (将用新 key)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--item')
    ap.add_argument('--file')
    ap.add_argument('--title', default='')
    ap.add_argument('--batch', help='JSON 文件：[{item,file,title},...]')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(DB):
        sys.exit(f'找不到 {DB}')
    con = sqlite3.connect(DB)
    cur = con.cursor()

    jobs = []
    if args.batch:
        jobs = json.load(open(args.batch, encoding='utf-8'))
    else:
        if not (args.item and args.file):
            sys.exit('需要 --item 和 --file，或用 --batch')
        jobs = [{'item': args.item, 'file': args.file, 'title': args.title}]

    if args.apply:
        os.makedirs(BAKDIR, exist_ok=True)
        b = os.path.join(BAKDIR, f'zotero_preattach_{time.strftime("%Y%m%d_%H%M%S")}.sqlite')
        con.close()
        shutil.copy2(DB, b)
        con = sqlite3.connect(DB)
        cur = con.cursor()
        print(f'[备份] {b}\n')

    ok = 0
    for j in jobs:
        iid = resolve(cur, j['item'])
        if iid is None:
            print(f'[FAIL] 找不到条目 {j["item"]}'); continue
        good, msg = add_one(cur, iid, j['file'], j.get('title', ''), args.apply)
        ok += good
        print(f'[{"OK " if good else "FAIL"}] {msg}')

    if args.apply:
        con.commit()
        print(f'\n[已提交] 成功 {ok}/{len(jobs)}；打开 Zotero 后会看到新附件。')
    else:
        print(f'\n预演结束（未写库）。成功 {ok}/{len(jobs)}，加 --apply 执行。')
    con.close()


if __name__ == '__main__':
    main()
