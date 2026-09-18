#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 安装向导。

依次询问：工作目录 / Zotero 目录与读取授权 / Obsidian 库 / MATLAB 与 LaTeX 目录，
然后**只读**扫描 Zotero 库自动生成你的研究领域画像（terms.json），最后写 config.json。

设计原则：
  * 只读 Zotero（immutable 模式打开 sqlite，不干扰正在运行的 Zotero）
  * 写 Zotero 需要单独授权（--allow-write）；本向导只给出提示，不擅自开启
  * 不采集、不上传任何数据；所有产物都在你选的工作目录里

用法：
  python3 wizard.py            # 交互式
  python3 wizard.py --yes      # 全部用默认值（CI / 非交互）
"""
import argparse
import json
import os
import re
import sqlite3
import sys

PKG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PKG)

DEFAULT_WORKDIR = os.path.join(os.path.expanduser('~'), 'research-frontier-work')


def ask(prompt, default=''):
    if not sys.stdin.isatty():
        return default
    tip = f' [{default}]' if default else ''
    try:
        ans = input(f'{prompt}{tip}: ').strip()
    except EOFError:
        return default
    return ans or default


def confirm(prompt, default=True):
    if not sys.stdin.isatty():
        return default
    d = 'Y/n' if default else 'y/N'
    try:
        ans = input(f'{prompt} [{d}]: ').strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans.startswith('y')


# ---------------------------------------------------------------- Zotero 只读扫描
STOP = set("""the a an of in on for and or to with by from at as is are was were be been
being it its this that these those we our us they their them he she his her you your
new novel study studies using used use via can could may might will would shall should
under over between among into than then also such more most less least very much many
two three one first second approach approaches method methods result results show shows
shown find found here there when where which who whom whose what how why all any both
each few other some only own same so no nor not now do does did doing have has had
about after before during while because if but just like cannot""".split())

NOISE = set("""pdf fulltext full text file article download attachment supplement
supplementary supporting appendix manuscript accepted version copy preprint""".split())


def scan_zotero(db_path, limit=800):
    """只读扫描 Zotero：返回 (条目列表, 分类列表)。绝不修改库。"""
    if not os.path.exists(db_path):
        return [], []
    con = sqlite3.connect(f'file:{db_path}?immutable=1', uri=True, timeout=20)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        rows = cur.execute("""
            SELECT i.itemID AS id, t.typeName AS type, i.key AS key
              FROM items i JOIN itemTypes t ON i.itemTypeID = t.itemTypeID
             WHERE t.typeName NOT IN ('attachment','note','annotation')
             LIMIT ?""", (limit,)).fetchall()
        ids = [r['id'] for r in rows]
        if not ids:
            return [], []
        qs = ','.join('?' * len(ids))
        fields = {}
        for r in cur.execute(f"""
                SELECT d.itemID AS iid, f.fieldName AS fn, v.value AS val
                  FROM itemData d
                  JOIN itemDataValues v ON d.valueID = v.valueID
                  JOIN fields f ON d.fieldID = f.fieldID
                 WHERE d.itemID IN ({qs})
                   AND f.fieldName IN ('title','publicationTitle','date','abstractNote')""",
                ids):
            fields.setdefault(r['iid'], {})[r['fn']] = r['val']
        items = []
        for r in rows:
            f = fields.get(r['id'], {})
            title = (f.get('title') or '').strip()
            if not title or title.lower() in NOISE:
                continue
            ym = re.search(r'(19|20)\d{2}', str(f.get('date') or ''))
            items.append({
                'title': title,
                'journal': (f.get('publicationTitle') or '').strip(),
                'year': int(ym.group(0)) if ym else None,
                'abstract': (f.get('abstractNote') or '')[:1200],
            })
        colls = [(x['name'], x['n']) for x in cur.execute("""
            SELECT c.collectionName AS name, COUNT(ci.itemID) AS n
              FROM collections c LEFT JOIN collectionItems ci
                ON c.collectionID = ci.collectionID
             GROUP BY c.collectionID ORDER BY n DESC LIMIT 20""")]
        return items, colls
    finally:
        con.close()


def build_terms(items):
    """从 Zotero 条目提取关键词与主题簇（纯本地统计，不联网）。"""
    from collections import Counter
    word = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")

    def toks(text):
        return [w.lower() for w in word.findall(text or '')
                if w.lower() not in STOP and w.lower() not in NOISE and len(w) > 2]

    freq = Counter()
    for it in items:
        for w in set(toks(it['title'])):
            freq[w] += 3
        for w in set(toks(it['abstract'])):
            freq[w] += 1

    # 双词组（bigram）更能代表方向，例如 "entropy production"
    bigram = Counter()
    for it in items:
        ws = toks(it['title'])
        for a, b in zip(ws, ws[1:]):
            bigram[f'{a} {b}'] += 4

    core = [w for w, _ in bigram.most_common(24)]
    secondary = [w for w, _ in freq.most_common(40) if w not in core][:30]
    weak = [w for w, _ in freq.most_common(120) if w not in core and w not in secondary][:40]

    # 主题簇：按双词组前缀粗分（用户可手改 terms.json）
    clusters = {}
    for t in core[:12]:
        clusters.setdefault('方向 · ' + t, [t])
    for t in secondary[:8]:
        clusters.setdefault('相关 · ' + t, [t])
    jour = Counter(it['journal'] for it in items if it['journal'])
    return {
        'core': core or ['review'],
        'secondary': secondary,
        'weak': weak,
        'clusters': clusters or {'未分类': core or ['review']},
        'journals': [{'name': j, 'count': n} for j, n in jour.most_common(20)],
        '_note': '由 wizard.py 从你的 Zotero 库自动生成。可手工编辑：core 权重 3、'
                 'secondary 2、weak 1；clusters 用于画像分组。',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', action='store_true', help='全部用默认值')
    a = ap.parse_args()

    print('=' * 68)
    print(' 研究前沿助手 · 安装向导')
    print('=' * 68)
    print('本向导只读取你本机的 Zotero 库来生成研究领域画像；')
    print('不会上传任何数据，也不会修改你的 Zotero 库。\n')

    workdir = os.path.expanduser(
        a.yes and DEFAULT_WORKDIR or ask('① 工作目录（数据/存档/翻译项目都放这里）',
                                         DEFAULT_WORKDIR))
    zotero_dir = os.path.expanduser(
        a.yes and '~/Zotero' or ask('② Zotero 数据目录（含 zotero.sqlite）', '~/Zotero'))
    db = os.path.join(zotero_dir, 'zotero.sqlite')
    print(f'   检查 {db} …', '存在' if os.path.exists(db) else '**不存在**')

    items, colls = scan_zotero(db)
    print(f'   只读扫描到 {len(items)} 条文献'
          + (f'，{len(colls)} 个分类' if colls else ''))

    if items and confirm('③ 用这个库自动生成研究领域画像（terms.json）？', True):
        terms = build_terms(items)
        os.makedirs(workdir, exist_ok=True)
        with open(os.path.join(workdir, 'terms.json'), 'w', encoding='utf-8') as f:
            json.dump(terms, f, ensure_ascii=False, indent=1)
        print(f'   ✅ 画像已写入 {workdir}/terms.json（核心词 {len(terms["core"])} 个）')
    else:
        print('   跳过画像生成（稍后可手工写 terms.json，或重跑本向导）')

    obsidian = os.path.expanduser(
        ask('④（可选）Obsidian 库路径，直接回车跳过', '~/Documents/Obsidian'))
    if obsidian and not os.path.isdir(obsidian):
        print('   该目录不存在，已忽略')
        obsidian = ''
    matlab = os.path.expanduser(ask('⑤（可选）MATLAB 程序目录，回车跳过', ''))
    if matlab and not os.path.isdir(matlab):
        print('   该目录不存在，已忽略')
        matlab = ''
    latex = os.path.expanduser(
        ask('⑥（可选）LaTeX / Markdown 工作目录，回车跳过', '~/Documents'))

    api_key = ask('⑦ DeepSeek API Key（回车则读环境变量 DEEPSEEK_API_KEY）', '')

    cfg = json.load(open(os.path.join(PKG, 'templates', 'config.example.json'),
                        encoding='utf-8'))
    cfg = {k: v for k, v in cfg.items() if not k.startswith('_')}
    cfg.update({
        'workdir': workdir,
        'zotero_dir': zotero_dir,
        'obsidian_vault': obsidian,
        'matlab_dir': matlab,
        'latex_dirs': [latex] if latex and os.path.isdir(latex) else [],
    })
    os.makedirs(workdir, exist_ok=True)
    with open(os.path.join(PKG, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    with open(os.path.join(workdir, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f'\n✅ 配置已写入：\n   {os.path.join(PKG, "config.json")}'
          f'\n   {os.path.join(workdir, "config.json")}')

    if api_key:
        envf = os.path.join(PKG, '.env')
        with open(envf, 'w', encoding='utf-8') as f:
            f.write(f'DEEPSEEK_API_KEY={api_key}\n')
        os.chmod(envf, 0o600)
        print(f'   API Key 已写入 {envf}（权限 600）')
    else:
        print('   提示：请 export DEEPSEEK_API_KEY=sk-... 后再运行 update.py')

    print('\n下一步：bash install.sh          # 部署小组件到 Plasma 或 GNOME')
    print('       python3 update.py all     # 生成第一份简报')
    return 0


if __name__ == '__main__':
    sys.exit(main())
