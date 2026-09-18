#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 翻译任务 worker（后台跑）。

用法：translate_worker.py <论文序号>

流程（严格对齐 translatepaper/_TRANSLATION_SPEC.md）：

  1. **先查 Zotero**：按 DOI → arXiv → 标题找条目；
     命中且**已有全文 PDF** 就直接复用它（不重复下载）
  2. 没有则联网取：arXiv 直链 → 代理兜底 → 项目里已验证的 fetchpdf.py（按 DOI）
  3. 在 translatepaper 下按 SOP 建项目目录 <一作姓>_<年>_<短标题>/
  4. SOP 要求的数据准备：
       pdftotext source.txt
       pdftohtml -xml -i fonts.xml
       fonts_linear.py fonts.xml pages/   ← 按页字体标注（公式校对的唯一依据）
  5. 写 meta.json / README.md / session_note.txt，状态标为「等待 LLM 翻译」
  6. 进度写回 runtime/actions.json，部件据此显示

**为什么后段交给会话**：逐节产出 LaTeX 译文需要 LLM 逐段判断，
塞进无人值守脚本里既不可控也容易烧 token。worker 把可机械化的部分做扎实，
之后在会话里说「翻译 <项目名>」即按 SOP 继续。
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from researchlib import config as C                       # noqa: E402
from researchlib import zotero_lookup                     # noqa: E402
from researchlib.util import load_json, log, save_json    # noqa: E402

ACTIONS_JSON = os.path.join(C.DATA_DIR, 'actions.json')
PAPERS_JSON = C.PAPERS_JSON
# 翻译工具与 SOP 随包携带在 translate/ 目录
TOOLS = os.path.join(C.PKG_DIR, 'translate')
SPEC = os.path.join(C.PKG_DIR, 'translate', 'TRANSLATION_SPEC.md')


def _run(cmd, cwd=None, timeout=900, desc=''):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '') + (r.stderr or '')
        if r.returncode != 0:
            log(f'  [{desc}] rc={r.returncode}: {out.strip()[:260]}')
        return r.returncode == 0, out
    except Exception as e:                                  # noqa: BLE001
        log(f'  [{desc}] 执行失败：{e}')
        return False, str(e)


def _slug(paper):
    authors = paper.get('authors') or []
    first = ''
    if authors:
        parts = str(authors[0]).split()
        first = parts[-1] if parts else ''
    first = re.sub(r'[^A-Za-z]', '', first)[:12] or 'Unknown'
    m = re.search(r'(19|20)\d{2}', str(paper.get('date') or ''))
    year = m.group(0) if m else ''
    words = re.findall(r'[A-Za-z]{3,}', paper.get('title') or '')[:3]
    short = ''.join(w.capitalize() for w in words)[:24] or 'Paper'
    return f'{first}_{year}_{short}'


def _update_state(key, **kw):
    a = load_json(ACTIONS_JSON, {'likes': {}, 'collected': {}, 'translations': {}})
    t = a.setdefault('translations', {}).setdefault(key, {})
    t.update(kw)
    t['updated'] = int(dt.datetime.now().timestamp())
    save_json(ACTIONS_JSON, a)


def main():
    if len(sys.argv) < 2:
        print('usage: translate_worker.py <序号>')
        return 2
    idx = int(sys.argv[1])
    papers = load_json(PAPERS_JSON, {'papers': []}).get('papers', [])
    if not (1 <= idx <= len(papers)):
        print(f'序号超出范围：{idx}')
        return 2
    paper = papers[idx - 1]
    key = (paper.get('doi') or paper.get('arxiv') or paper.get('title') or '')[:120].lower()
    title = paper.get('title') or ''

    def fail(msg):
        log(f'翻译任务失败：{msg}')
        _update_state(key, state='error', msg=msg)
        print(f'error:{msg}')
        return 1

    # ---------- 1) 先查 Zotero ----------
    _update_state(key, state='running', progress=8, msg='检查 Zotero 是否已有条目与全文')
    zot = zotero_lookup.find(paper)

    name = _slug(paper)
    proj = os.path.join(C.TRANSLATE_ROOT, name)
    os.makedirs(os.path.join(proj, 'sections'), exist_ok=True)
    os.makedirs(os.path.join(proj, 'pages'), exist_ok=True)
    pdf = os.path.join(proj, 'source.pdf')
    src_from = ''

    # ---------- 2) 取全文：Zotero 优先，否则联网 ----------
    if zot and zot.get('pdf') and os.path.exists(zot['pdf']):
        _update_state(key, progress=25, msg='复用 Zotero 里的全文')
        try:
            if os.path.abspath(zot['pdf']) != os.path.abspath(pdf):
                import shutil
                shutil.copy2(zot['pdf'], pdf)
            src_from = f"Zotero 条目 {zot['itemID']}（按 {zot['match']} 命中）"
        except Exception as e:                              # noqa: BLE001
            log(f'  复制 Zotero 全文失败：{e}')
    if not (os.path.exists(pdf) and os.path.getsize(pdf) > 20000):
        _update_state(key, progress=35, msg='联网下载原文 PDF')
        ok = False
        arx = (paper.get('arxiv') or '').strip()
        if arx:
            url = f'https://arxiv.org/pdf/{arx}'
            _run(['curl', '-sL', '--max-time', '240', '-o', pdf, url], desc='arXiv 直连')
            ok = os.path.exists(pdf) and os.path.getsize(pdf) > 20000
            if not ok:
                _run(['curl', '-sL', '--max-time', '240', '-x', 'http://127.0.0.1:7890',
                      '-o', pdf, url], desc='arXiv 走代理')
                ok = os.path.exists(pdf) and os.path.getsize(pdf) > 20000
        if not ok and paper.get('doi'):
            fp = os.path.join(TOOLS, 'fetchpdf.py')
            if os.path.exists(fp):
                _run(['/usr/bin/python3', fp, paper['doi'], '-o', pdf], desc='fetchpdf')
                ok = os.path.exists(pdf) and os.path.getsize(pdf) > 20000
        if not ok:
            if not getattr(C, 'ENABLE_AUTO_FETCH', False):
                return fail('未找到全文，且发行版默认关闭自动下载（见 config.json 的 enable_auto_fetch）')
            return fail('取全文失败：Zotero 无条目、arXiv 无直链、DOI 下载也未成功')
        src_from = src_from or '联网下载'
    log(f'  原文 PDF：{os.path.getsize(pdf)//1024} KB（来源：{src_from}）')

    # ---------- 3) SOP 数据准备 ----------
    _update_state(key, progress=55, msg='提取文本与字体信息（SOP 数据准备）')
    _run(['pdftotext', pdf, os.path.join(proj, 'source.txt')], desc='pdftotext')
    _run(['pdftohtml', '-xml', '-i', pdf, os.path.join(proj, 'fonts.xml')], desc='pdftohtml')
    fl = os.path.join(TOOLS, 'fonts_linear.py')
    pages_dir = os.path.join(proj, 'pages')
    if os.path.exists(fl):
        _run(['/usr/bin/python3', fl, os.path.join(proj, 'fonts.xml'), pages_dir + '/'],
             desc='fonts_linear')
    # 逐页纯文本（SOP 也要求，用于定位段落）
    ok, out = _run(['pdfinfo', pdf], desc='pdfinfo')
    pages = 0
    if ok:
        m = re.search(r'^Pages:\s*(\d+)', out, re.M)
        pages = int(m.group(1)) if m else 0
    for pno in range(1, pages + 1):
        _run(['pdftotext', '-layout', '-f', str(pno), '-l', str(pno), pdf,
              os.path.join(pages_dir, f'p{pno:03d}.txt')], desc=f'pdftotext p{pno}')
    n_font = len([f for f in os.listdir(pages_dir) if f.startswith('fonts_p')]) \
        if os.path.isdir(pages_dir) else 0
    if n_font == 0:
        log('  ⚠ fonts_linear.py 未产出 pages/fonts_pNNN.txt（公式校对会缺依据）')

    # ---------- 4) 项目说明 ----------
    _update_state(key, progress=85, msg='写项目说明，等待 LLM 翻译')
    info = {
        'title': title, 'authors': paper.get('authors') or [],
        'journal': paper.get('journal'), 'date': paper.get('date'),
        'doi': paper.get('doi'), 'arxiv': paper.get('arxiv'), 'url': paper.get('url'),
        'pages': pages, 'score': paper.get('score'), 'why': paper.get('why') or [],
        'summary': paper.get('summary') or '', 'zotero_item': (zot or {}).get('itemID'),
        'pdf_source': src_from, 'fonts_pages': n_font,
        'created': dt.datetime.now().isoformat(timespec='seconds'),
    }
    save_json(os.path.join(proj, 'meta.json'), info)
    with io_open(os.path.join(proj, 'session_note.txt')) as f:
        f.write(f"""项目：{name}
标题：{title}
作者：{', '.join(info['authors'][:6])}
出处：{info['journal']} ({info['date']})  DOI: {info['doi'] or '-'}  arXiv: {info['arxiv'] or '-'}
页数：{pages}    字体标注文件：{n_font} 个
全文来源：{src_from}
Zotero 条目：{info['zotero_item'] or '（未命中）'}
建立时间：{info['created']}

【状态】数据准备完成，**等待 LLM 翻译**。

【下一步（在 DSH 会话里说这句即可）】
    翻译 {name}

【流程依据】{SPEC}
  - 正文/摘要/图注/表注/章节标题 → 中文（标题后括注英文原题）
  - 作者/机构/DOI/卷期页码等元数据 → 保留英文；参考文献完全保留英文原样
  - 公式不翻译；图片只放占位框；公式以 pages/fonts_pNNN.txt 的字体标注为准
  - 编译验证：xelatex 跑两遍（ctex + Fandol 已就绪）
  - 收尾：译稿 PDF 归档回 Zotero（SOP 第 97 行起）

【数据文件】
  source.pdf     原文
  source.txt     纯文本（公式必乱，只用于定位段落）
  fonts.xml      字体信息
  pages/         fonts_pNNN.txt 字体标注 + pNNN.txt 逐页文本
  meta.json      元数据
  sections/      译文分节 .tex
""")
    with io_open(os.path.join(proj, 'README.md')) as f:
        f.write(f"""# {title}

{', '.join(info['authors'][:6])}

**{info['journal']}** ({info['date']}) · {pages} 页

- DOI: {info['doi'] or '—'} · arXiv: {info['arxiv'] or '—'}
- 全文来源：{src_from}

## 为什么收进来

相关度 {info['score']}，命中方向：{', '.join(info['why'])}

{info['summary']}

## 状态

数据准备完成，**等待 LLM 翻译**（见 session_note.txt）。
""")
    _update_state(key, state='ready', progress=100, project=proj, pages=pages,
                  msg=f'准备完成（{pages} 页），会话里说「翻译 {name}」继续')
    log(f'翻译准备完成：{proj}（{pages} 页，来源 {src_from}）')
    print(f'ready:{name}')
    return 0


def io_open(path, mode='w'):
    """小包装：统一 utf-8。"""
    return open(path, mode, encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
