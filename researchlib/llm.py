#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 调用 DSH 配置里的 DeepSeek API。

key 从 ~/.dsh/.credentials.yaml 读取（与 DSH 同一把），
也可用环境变量 DEEPSEEK_API_KEY 覆盖。
"""
import json
import os
import re
import time
import urllib.request

from . import config as C
from .util import log, truncate

_KEY_CACHE = None
_stats = {'calls': 0, 'in': 0, 'out': 0}


def stats():
    """本次进程累计的调用次数与 token 用量。"""
    return dict(_stats)


def api_key():
    global _KEY_CACHE
    if _KEY_CACHE:
        return _KEY_CACHE
    env = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if env:
        _KEY_CACHE = env
        return env
    try:
        txt = open(C.DSH_CREDENTIALS, 'r', encoding='utf-8').read()
        m = re.search(r'DEEPSEEK_API_KEY:\s*([^\s\'"]+)', txt)
        if m:
            _KEY_CACHE = m.group(1).strip()
            return _KEY_CACHE
    except OSError as e:
        log(f'读取 DSH 凭证失败：{e}')
    raise RuntimeError('找不到 DEEPSEEK_API_KEY（~/.dsh/.credentials.yaml 或环境变量）')


def chat(messages, model=None, max_tokens=1200, temperature=0.3, retries=2,
         timeout=None):
    """一次 chat completion，返回正文字符串。失败抛异常。"""
    model = model or C.MODEL_BRIEF
    body = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'stream': False,
    }
    data = json.dumps(body).encode('utf-8')
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(
                C.DEEPSEEK_BASE + '/chat/completions', data=data,
                headers={'Authorization': 'Bearer ' + api_key(),
                         'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout or C.HTTP_TIMEOUT) as r:
                d = json.loads(r.read().decode('utf-8', 'replace'))
            u = d.get('usage', {})
            reason = u.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
            log(f'  LLM {model}: in={u.get("prompt_tokens")} out={u.get("completion_tokens")} '
                f'reasoning={reason}')
            content = (d['choices'][0]['message']['content'] or '').strip()
            if not content:
                # 推理型模型会把 max_tokens 全用在 reasoning 上，导致正文为空。
                # 这种情况必须当成失败重试（并调大预算），否则会写入空简报。
                raise RuntimeError(
                    f'{model} 返回空内容（reasoning 用掉 {reason} tokens，可能 max_tokens 太小）')
            _stats['calls'] += 1
            _stats['in'] += u.get('prompt_tokens', 0) or 0
            _stats['out'] += u.get('completion_tokens', 0) or 0
            return content
        except Exception as e:                  # noqa: BLE001
            last = e
            if i < retries:
                time.sleep(2.0 * (i + 1))
    raise last


SYSTEM_PROMPT = (
    '你是理论物理文献分析助手，读得懂非平衡统计物理与随机热力学的形式化内容。'
    '用中文写作：具体、克制、不堆砌套话，不说“本文具有重要意义”这类空话。'
    '术语首次出现时给出英文原文，例如“熵产生（entropy production）”。'
)


def make_user_context(prof):
    """把画像压缩成一段简短的用户研究背景，用于每次提示。"""
    agenda = '、'.join(prof.get('agenda', [])[:4]) or '非平衡统计物理'
    terms = '、'.join(t['term'] for t in prof.get('top_terms', [])[:12])
    journals = '、'.join(j['name'] for j in prof.get('journals', [])[:6])
    notes = '、'.join(n['name'] for n in prof.get('notes', [])[:6])
    s = (f'用户的研究纲领：{agenda}。\n'
         f'高度关注的术语：{terms}。\n'
         f'常读期刊：{journals}。')
    if notes:
        s += f'\n近期在追的笔记：{notes}。'
    return s


def summarize_paper(prof, paper):
    """为一篇论文生成 3 句中文简介。"""
    ctx = make_user_context(prof)
    prompt = f"""{ctx}

请为下面这篇新论文写恰好 3 句中文简介，每句一行、不加编号以外的格式：
第1句：这篇论文做了什么（研究对象与问题）。
第2句：用了什么方法、得到什么关键结果（有具体数字/极限就写出来）。
第3句：与上述用户研究的关系——是可用的工具、可借鉴的方法、还是需要留意的新方向；如果关系较远就直说较远。

标题：{paper.get('title')}
期刊/来源：{paper.get('journal') or paper.get('source')}（{paper.get('date')}）
摘要：{truncate(paper.get('abstract') or '（原文未提供摘要，请仅依据标题谨慎推断，并明确说明这是推断）', 2200)}
"""
    # 注意：deepseek-flash 是推理型模型，reasoning 会先花掉几百到上千 token，
    # 预算给 900 时正文常被截断甚至为空，故给到 3000 并允许重试。
    txt = chat([{'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}],
               model=C.MODEL_BRIEF, max_tokens=3000, temperature=0.35, retries=3)
    if len(txt) < 20:
        raise RuntimeError('简介内容过短，视为失败：%r' % txt[:60])
    return txt


def classic_review(prof, item):
    """为一篇经典论文写简短中文回顾（3 句话）。"""
    ctx = make_user_context(prof)
    prompt = f"""{ctx}

下面是用户研究领域里的一篇经典/开山之作：

标题：{item.get('title')}
作者：{item.get('authors')}
年份：{item.get('year')}    出处：{item.get('venue')}
定位：{item.get('note')}

请写恰好 3 句中文回顾，每句一行：
第1句：这篇工作当年解决了什么问题、为什么是开山之作（讲清它之前的困境）。
第2句：核心想法是什么（用一两句话讲清机制，不要堆术语）。
第3句：它与上述用户当前研究的关系——今天还在被怎么用，或者哪个假设正在被松动。

要求：具体、克制，不要写"具有里程碑意义"这类空话；不要编造上面没给的数字或结论。
"""
    return chat([{'role': 'system', 'content': SYSTEM_PROMPT},
                 {'role': 'user', 'content': prompt}],
                model=C.MODEL_BRIEF, max_tokens=3000, temperature=0.4, retries=3)


def synthesize(prof, papers):
    """综合多篇论文写一份研究前沿简报（Markdown）。"""
    ctx = make_user_context(prof)
    lines = []
    for i, p in enumerate(papers, 1):
        lines.append(
            f"[{i}] {p.get('title')} —— {p.get('journal') or p.get('source')} "
            f"({p.get('date')}) 相关度{p.get('score')}"
            + (f" 命中术语: {', '.join(p.get('why') or [])}" if p.get('why') else '')
            + f"\n    摘要: {truncate(p.get('abstract') or '无', 700)}")
    body = '\n'.join(lines)
    prompt = f"""{ctx}

以下是本周期从 arXiv 与用户常读期刊新抓取、并按相关度排序的 {len(papers)} 篇论文：

{body}

请写一份中文研究前沿简报（Markdown，不要一级标题），包含四节：

## 一、本周期看点
3–5 条要点。每条一句话点明「谁做了什么、新在哪」，不要把摘要复述一遍。

## 二、趋势判断
2–3 段。指出这批工作里反复出现的动向（例如某个方法被反复使用、某个假设被松动），
以及它与用户纲领中哪些既有工作形成呼应或竞争。允许有判断，但必须能追溯到上面某几条。

## 三、值得深读的几篇
挑 2–3 篇，各写 2–3 句：为什么值得读、读时该盯住什么。

## 四、可切入的问题
2–4 条具体的研究问题或可做的计算/模拟。要具体到「用什么模型、算什么量、和什么比」，
不要写「可以进一步研究」这种空话。

要求：全文不超过 900 字；只依据上面给出的信息，不要编造未提供的结论或数字；
不确定的地方写明「摘要未说明」。
"""
    # deepseek-v4-pro 是推理型模型，reasoning 会吃掉大量预算；
    # 预算给小了就会出现「全部 token 用于思考、正文为空」。这里给足并允许重试。
    return chat([{'role': 'system', 'content': SYSTEM_PROMPT},
                 {'role': 'user', 'content': prompt}],
                model=C.MODEL_SYNTH, max_tokens=12000, temperature=0.4, retries=2)
