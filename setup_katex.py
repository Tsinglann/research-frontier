#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 KaTeX 到包内 _katex/，供网页公式渲染（离线内联进 HTML）。

不装也无妨：网页会把公式按等宽纯文本显示。
"""
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

PKG = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(PKG, '_katex')
VER = '0.16.11'


def main():
    if os.path.exists(os.path.join(DST, 'package', 'dist', 'katex.min.js')):
        print('KaTeX 已存在，跳过。')
        return 0
    url = f'https://registry.npmjs.org/katex/-/katex-{VER}.tgz'
    print(f'下载 {url} …')
    os.makedirs(DST, exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), f'katex-{VER}.tgz')
    try:
        urllib.request.urlretrieve(url, tmp)
    except Exception as e:                      # noqa: BLE001
        print(f'下载失败：{e}\n可手工把 katex 的 dist/ 放到 {DST}/package/dist/')
        return 1
    with tarfile.open(tmp) as tf:
        tf.extractall(DST)
    print(f'✅ KaTeX 已就绪：{DST}/package/dist/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
