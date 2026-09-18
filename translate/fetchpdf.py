#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""fetchpdf —— 用校园网订阅权限按 DOI 下载论文全文。

原理：
  1. 走 DOI 解析拿到出版社 landing page
  2. 读页面里的 <meta name="citation_pdf_url">（学术出版商通用标准）
  3. 直连下载（**显式禁用代理**——走 clash 会让出版社看到国外 IP，反而丢掉订阅权限）

实测（2026-09-18，兰州大学校园网，出口 202.201.11.203）：
  * APS / Physical Review 全系列 …… IP 认证，直接可下（x-aps-accountid 存在即已授权）
  * Springer …………………………… 直接可下
  * Nature / IOP / Wiley / Science / RSC / AIP … 需要 CARSI 机构登录，本工具会报告
    并给出替代办法（浏览器登录后由 Zotero Connector 抓取）

用法：
  fetchpdf.py <DOI 或 URL> [更多...] [-o 输出目录] [--check]

注意：仅供下载本校已订阅、且你有权访问的文献；请勿批量抓取（会被出版社封 IP）。
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

# 显式禁用代理：校园网 IP 认证要求真实源 IP
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
OPENER.addheaders = [('User-Agent', UA),
                     ('Accept', 'text/html,application/pdf,*/*')]

META_PATTERNS = [
    r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
]

# 已知出版社的 PDF URL 模板（meta 标签失效时兜底）
PUBLISHER_RULES = [
    (r'^10\.1103/', 'APS', 'https://journals.aps.org/{j}/pdf/{doi}'),
    (r'^10\.1007/', 'Springer', 'https://link.springer.com/content/pdf/{doi}.pdf'),
    (r'^10\.1140/', 'Springer', 'https://link.springer.com/content/pdf/{doi}.pdf'),
    (r'^10\.1038/', 'Nature', 'https://www.nature.com/articles/{suffix}.pdf'),
    (r'^10\.1088/', 'IOP', 'https://iopscience.iop.org/article/{doi}/pdf'),
    (r'^10\.1063/', 'AIP', 'https://pubs.aip.org/{path}'),
]

NEEDS_AUTH = {'Nature', 'IOP', 'AIP', 'Wiley', 'Science', 'RSC'}


def publisher_of(doi):
    for pat, name, _tpl in PUBLISHER_RULES:
        if re.match(pat, doi):
            return name
    return '未知'


def open_url(url, timeout=40):
    """返回 (final_url, content_type, data)"""
    with OPENER.open(url, timeout=timeout) as r:
        return r.geturl(), r.headers.get('Content-Type', ''), r.read()


def find_pdf_url(doi):
    """DOI → landing page → citation_pdf_url"""
    landing, ctype, html = None, '', b''
    try:
        landing, ctype, html = open_url(f'https://doi.org/{doi}')
    except urllib.error.HTTPError as e:
        return None, f'DOI 解析失败 HTTP {e.code}'
    except Exception as e:
        return None, f'DOI 解析失败 {e}'

    if 'pdf' in ctype.lower():
        return landing, 'landing 直接就是 PDF'

    pub = publisher_of(doi)
    text = html.decode('utf-8', 'ignore')

    # APS 专用两步法：meta 给的 http://link.aps.org/pdf/<doi> 会被跳到
    # journals.aps.org/<j>/abstract/<doi>（HTML），必须先探出期刊缩写再换 /pdf/
    if pub == 'APS':
        try:
            final, _ct, _d = open_url(f'https://link.aps.org/pdf/{doi}')
            m = re.search(r'journals\.aps\.org/([a-z]+)/(?:abstract|pdf)/', final)
            if m:
                return (f'https://journals.aps.org/{m.group(1)}/pdf/{doi}',
                        f'APS 两步法（{m.group(1)}）')
        except Exception:
            pass
        m = re.search(r'journals\.aps\.org/([a-z]+)/(?:abstract|pdf)/', landing or '')
        if m:
            return (f'https://journals.aps.org/{m.group(1)}/pdf/{doi}',
                    f'APS 规则（{m.group(1)}）')

    for pat in META_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            url = m.group(1).replace('http://', 'https://')
            return url, f'来自 citation_pdf_url（{landing}）'

    # 兜底：按出版社规则构造
    if pub == 'Springer':
        return f'https://link.springer.com/content/pdf/{doi}.pdf', '按 Springer 规则构造'
    if pub == 'Nature':
        return (f'https://www.nature.com/articles/{doi.split("/", 1)[1]}.pdf',
                '按 Nature 规则构造')
    return None, f'页面中未找到 citation_pdf_url（出版社：{pub}）'


def download(doi, outdir, check_only=False):
    pub = publisher_of(doi)
    pdf_url, how = find_pdf_url(doi)
    if not pdf_url:
        return False, f'{pub}: {how}'

    if check_only:
        try:
            with OPENER.open(pdf_url, timeout=40) as r:
                ct = r.headers.get('Content-Type', '')
                ok = 'pdf' in ct.lower()
                return ok, (f'{pub}: {"可下载" if ok else "非 PDF（"+ct+"）"}  {pdf_url}')
        except urllib.error.HTTPError as e:
            return False, f'{pub}: HTTP {e.code}  {pdf_url}'
        except Exception as e:
            return False, f'{pub}: {e}'

    try:
        final, ct, data = open_url(pdf_url)
    except urllib.error.HTTPError as e:
        hint = ('（该出版社需 CARSI 机构登录，非 IP 认证）'
                if pub in NEEDS_AUTH else '')
        return False, f'{pub}: HTTP {e.code} {hint}'
    except Exception as e:
        return False, f'{pub}: {e}'

    if not data.startswith(b'%PDF'):
        hint = ('该出版社需 CARSI 机构登录' if pub in NEEDS_AUTH
                else '返回内容不是 PDF（可能需要认证或反爬）')
        return False, f'{pub}: {hint}  final={final}'

    os.makedirs(outdir, exist_ok=True)
    name = re.sub(r'[^A-Za-z0-9._-]', '_', doi.replace('/', '_')) + '.pdf'
    path = os.path.join(outdir, name)
    with open(path, 'wb') as f:
        f.write(data)
    return True, f'{pub}: {len(data)/1e6:.2f} MB → {path}  ({how})'


def main():
    ap = argparse.ArgumentParser(description='按 DOI 用校园网权限下载全文')
    ap.add_argument('items', nargs='+', help='DOI 或 doi.org URL')
    ap.add_argument('-o', '--outdir', default='_cache/fetched')
    ap.add_argument('--check', action='store_true', help='只检查可下载性，不保存')
    args = ap.parse_args()

    ok = 0
    for raw in args.items:
        doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', raw.strip())
        good, msg = download(doi, args.outdir, args.check)
        ok += good
        print(f'[{"OK " if good else "FAIL"}] {doi}\n        {msg}')
    print(f'\n成功 {ok}/{len(args.items)}')
    return 0 if ok == len(args.items) else 1


if __name__ == '__main__':
    sys.exit(main())
