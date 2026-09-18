#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 通用工具（HTTP / 日志 / 状态缓存 / 文本清洗）。"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from . import config as C


# ---------------------------------------------------------------- 日志
def log(msg):
    """同时打印与落盘，方便 systemd timer 事后排查。"""
    line = time.strftime('[%Y-%m-%d %H:%M:%S] ') + str(msg)
    print(line, flush=True)
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(C.LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ---------------------------------------------------------------- HTTP
def http_get(url, timeout=60, retries=3, headers=None):
    """GET 并返回 bytes；失败重试，最后抛异常。"""
    hdr = {'User-Agent': C.USER_AGENT, 'Accept': '*/*'}
    if headers:
        hdr.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:          # noqa: BLE001 网络异常种类多，统一重试
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise last


def http_json(url, timeout=60, retries=3):
    raw = http_get(url, timeout=timeout, retries=retries)
    return json.loads(raw.decode('utf-8', 'replace'))


# ---------------------------------------------------------------- 文本
def clean_text(s):
    """压平空白、去掉控制字符。"""
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', str(s))
    s = re.sub(r'<[^>]+>', ' ', s)          # 去 HTML/JATS 标签
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def norm_title(t):
    """标题归一化，用于跨源去重。"""
    t = clean_text(t).lower()
    t = re.sub(r'[^a-z0-9\u4e00-\u9fff ]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def truncate(s, n):
    s = clean_text(s)
    return s if len(s) <= n else s[:n].rstrip() + '…'


# ---------------------------------------------------------------- 状态缓存
def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    """原子写入，避免 QML 读到半截文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''
