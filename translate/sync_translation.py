#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""sync_translation.py —— 把 translatepaper 里译好的 PDF 同步到 Zotero 对应条目。

**这是 translatepaper 的标准收尾步骤**：一篇论文译完、编译通过后，
自动把 `main.pdf` 作为「中文译文」附件挂到 Zotero 里那篇原文的条目上。

匹配策略（依次尝试，命中即止）：
  1. 项目目录 `source.pdf` 的 PDF 元数据标题
  2. `main.tex` 里 `\itshape{...}` / `\large{...}` 的英文原标题
  3. 项目名里的 DOI 片段（若目录名含 DOI）
  4. 与 Zotero 标题的关键词交集

用法：
  sync_translation.py                      # 扫 translatepaper 下所有项目（预演）
  sync_translation.py EdwardsJammed        # 只处理一个项目
  sync_translation.py --apply              # 真正写入（**需先关闭 Zotero**）
  sync_translation.py --apply --all        # 批量处理所有项目

注意：写库前必须关闭 Zotero，否则会撞锁 / 被 Zotero 覆盖。
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DB = os.path.expanduser('~/Zotero/zotero.sqlite')
STORE = os.path.expanduser('~/Zotero/storage')
BAKDIR = os.path.join(ROOT, '_cache', 'zotero_backup')
KEYCHARS = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'
ATTACH_TITLE = '中文译文'


def zotero_running():
    """看 23119 是否在监听（Zotero 的本地端口）"""
    try:
        out = subprocess.run(['ss', '-ltn'], capture_output=True, text=True).stdout
        return '23119' in out
    except Exception:
        return False


def project_title(d):
    """尽力从项目目录里挖出英文原标题"""
    # 1) source.pdf 的元数据标题
    sp = os.path.join(d, 'source.pdf')
    if os.path.exists(sp):
        try:
            out = subprocess.run(['pdfinfo', sp], capture_output=True, text=True).stdout
            m = re.search(r'^Title:[ \t]*(.+)$', out, re.M)
            if m and m.group(1).strip() and len(m.group(1).strip()) > 8:
                return m.group(1).strip(), 'source.pdf 元数据'
        except Exception:
            pass
    # 2) main.tex 里的英文副标题
    mt = os.path.join(d, 'main.tex')
    if os.path.exists(mt):
        s = open(mt, encoding='utf-8', errors='ignore').read()
        for pat in (r'\\itshape\s+([^}]{10,180})\}', r'\\large\s+([^}\\\\]{10,180})'):
            m = re.search(pat, s)
            if m:
                t = re.sub(r'\s+', ' ', m.group(1)).strip()
                if len(t) > 10:
                    return t, 'main.tex 标题'
    return None, None


def match(cur, title):
    """标题 → Zotero itemID"""
    if not title:
        return None, '无标题可用'
    norm = ' '.join(title.lower().split())
    norm = re.sub(r'[^a-z0-9 ]', ' ', norm)
    norm = ' '.join(norm.split())
    best = None
    for iid, t in cur.execute("""SELECT i.itemID, idv.value FROM items i
            JOIN itemTypes it ON it.itemTypeID=i.itemTypeID
            JOIN itemData id ON id.itemID=i.itemID
            JOIN itemDataValues idv ON idv.valueID=id.valueID
            JOIN fields f ON f.fieldID=id.fieldID
            WHERE f.fieldName='title'
              AND it.typeName NOT IN ('attachment','note','annotation')
              AND i.itemID NOT IN (SELECT itemID FROM deletedItems)"""):
        tn = re.sub(r'[^a-z0-9 ]', ' ', ' '.join(t.lower().split()))
        tn = ' '.join(tn.split())
        if tn == norm:
            return iid, f'标题精确匹配：{t[:50]}'
        # 关键词交集
        w1 = {w for w in norm.split() if len(w) > 4}
        w2 = {w for w in tn.split() if len(w) > 4}
        if w1 and w2:
            j = len(w1 & w2) / min(len(w1), len(w2))
            if j >= 0.75 and (best is None or j > best[0]):
                best = (j, iid, t)
    if best:
        return best[1], f'标题关键词 {best[0]:.0%}：{best[2][:50]}'
    return None, '未匹配到条目'


def new_key(cur):
    import random
    while True:
        k = ''.join(random.choice(KEYCHARS) for _ in range(8))
        if not cur.execute('SELECT 1 FROM items WHERE key=?', (k,)).fetchone():
            return k


def already_attached(cur, itemID, src):
    """避免重复挂同一个译稿（按文件名判断）"""
    fn = os.path.basename(src)
    for (path,) in cur.execute("""SELECT ia.path FROM itemAttachments ia
            WHERE ia.parentItemID=?""", (itemID,)):
        if path and path.endswith(fn):
            return True
    return False


def attach(cur, itemID, src, title=ATTACH_TITLE):
    key = new_key(cur)
    fn = os.path.basename(src)
    d = os.path.join(STORE, key)
    os.makedirs(d, exist_ok=True)
    shutil.copy2(src, os.path.join(d, fn))
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""INSERT INTO items (itemTypeID,dateAdded,dateModified,
                   clientDateModified,libraryID,key,version,synced)
                   VALUES (3,?,?,?,1,?,0,0)""", (now, now, now, key))
    aid = cur.lastrowid
    cur.execute("""INSERT INTO itemAttachments (itemID,parentItemID,linkMode,
                   contentType,path,syncState)
                   VALUES (?,?,0,'application/pdf',?,0)""",
                (aid, itemID, f'storage:{fn}'))
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


def projects(only=None, all_=False):
    out = []
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d) or name.startswith(('_', '.')):
            continue
        if not os.path.exists(os.path.join(d, 'main.pdf')):
            continue
        if not os.path.exists(os.path.join(d, 'main.tex')):
            continue
        if only and not any(name == o or name.startswith(o) for o in only):
            continue
        out.append((name, d))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('projects', nargs='*', help='项目目录名（可多个；缺省=全部预演）')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    if args.apply and zotero_running():
        sys.exit('⚠️ Zotero 正在运行 —— 写库会撞锁或被覆盖。\n'
                 '   请先完全退出 Zotero（Ctrl+Q），再跑本命令。')

    ps = projects(args.projects or None, args.all)
    if not ps:
        sys.exit('没有找到可同步的项目（需同时有 main.tex 与 main.pdf）')

    con = sqlite3.connect(DB if args.apply else f'file:{DB}?immutable=1',
                          uri=not args.apply)
    cur = con.cursor()
    if args.apply:
        os.makedirs(BAKDIR, exist_ok=True)
        bk = os.path.join(BAKDIR, f'zotero_presync_{time.strftime("%Y%m%d_%H%M%S")}.sqlite')
        con.close()
        shutil.copy2(DB, bk)
        con = sqlite3.connect(DB)
        cur = con.cursor()
        print(f'[备份] {bk}\n')

    ok = skip = fail = 0
    for name, d in ps:
        title, how = project_title(d)
        pdf = os.path.join(d, 'main.pdf')
        sz = os.path.getsize(pdf) / 1e6
        if not title:
            print(f'  [?] {name:<42} 提取不到英文标题 → 跳过')
            fail += 1
            continue
        iid, m = match(cur, title)
        if iid is None:
            print(f'  [?] {name:<42} {m}')
            print(f'        标题: {title[:66]}')
            fail += 1
            continue
        if already_attached(cur, iid, pdf):
            print(f'  [=] {name:<42} 条目 {iid} 已有同名附件 → 跳过')
            skip += 1
            continue
        print(f'  [✓] {name:<42} → 条目 {iid}（{m}）  {sz:.2f}MB')
        if args.apply:
            key, aid = attach(cur, iid, pdf)
            print(f'        已附加 key={key} attachID={aid}')
        ok += 1

    if args.apply:
        con.commit()
        print(f'\n[已提交] 新增 {ok}，跳过 {skip}，未匹配 {fail}')
        print('打开 Zotero 后：先确认附件，再手动同步；若提示冲突选「保留本地」。')
    else:
        print(f'\n预演：可同步 {ok}，跳过 {skip}，未匹配 {fail}')
        print('加 --apply 执行（需先关闭 Zotero）。')
    con.close()


if __name__ == '__main__':
    main()
