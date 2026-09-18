#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— **加一篇**经典论文（部件/网页「加一篇」按钮的后端）。

用法：classic.py new        再添加一篇经典（每天不限次数，累积而不是替换）
      classic.py show       打印当前已累积的经典

与旧版的区别：旧版是「换一篇」（替换当天那篇），现在改成**追加** ——
每点一次就在列表末尾加一篇新的，当天可以一直加。

设计：
  * offset 存在 runtime/state.json 的 classic_offset，每次 +1 在典籍库里顺延
  * 回顾文本按典籍 key 缓存（同一篇重复遇到不再花钱）
  * 只重写 brief.json / brief.md / 当日存档，**不重跑抓取**
"""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from researchlib import archive, brief as brief_mod, classics, config as C, llm  # noqa: E402
from researchlib.util import load_json, log, save_json                            # noqa: E402


def current():
    """当天已累积的经典列表。"""
    st = load_json(C.STATE_JSON, {})
    lst = st.get('classic_list') or []
    if lst:
        return lst
    return [classics.pick(offset=st.get('classic_offset', 0))]


def make_new(bump=True):
    """再添加一篇经典：offset +1 取下一篇，**追加**到当天列表。"""
    st = load_json(C.STATE_JSON, {})
    off = int(st.get('classic_offset', 0) or 0)
    if bump:
        off += 1
    classic = classics.pick_by_index(off)
    brief = load_json(C.BRIEF_JSON, {})
    prof = load_json(C.PROFILE_JSON, {})
    if not brief or not prof:
        log('还没有简报/画像，先跑一次 update.py all')
        print('error:no-brief')
        return 1

    cache = st.get('summaries', {})
    ckey = 'classic:' + classic['key']
    hit = cache.get(ckey)
    if hit and hit.get('summary'):
        text = hit['summary']
        classic['cached'] = True
    else:
        try:
            text = llm.classic_review(prof, classic)
            cache[ckey] = {'summary': text, 'model': C.MODEL_BRIEF,
                           'title': classic['title'], 'ts': int(dt.datetime.now().timestamp())}
            classic['cached'] = False
        except Exception as e:                                  # noqa: BLE001
            log(f'经典回顾生成失败：{e}')
            print(f'error:{e}')
            return 1
    classic['review'] = text
    classic['url'] = classics.link_of(classic)

    # 追加到当天列表（若已在列表里则不重复加）
    cur_list = list(st.get('classic_list') or [])
    if not cur_list and brief.get('classic'):
        cur_list = [brief['classic']]          # 首次点击时把当天原篇纳入
    if not any(x.get('key') == classic.get('key') for x in cur_list):
        cur_list.append(classic)
    brief['classic_list'] = cur_list
    brief['classic'] = cur_list[0] if cur_list else classic   # 兼容旧字段
    brief['generated_text'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    save_json(C.BRIEF_JSON, brief)
    st['classic_offset'] = off
    st['classic_list'] = cur_list
    st['summaries'] = cache
    save_json(C.STATE_JSON, st)

    # 同步当天存档（便于网页日历看到最新经典）
    papers = load_json(C.PAPERS_JSON, {'papers': []}).get('papers', [])
    try:
        archive.save_day(brief.get('generated_text', '')[:10], brief, papers, prof,
                         classic, text)
    except Exception as e:                                      # noqa: BLE001
        log(f'存档更新失败（不影响部件）：{e}')

    log(f'经典已加：{classic["year"]} {classic["title"][:52]}'
        + ('（缓存）' if classic.get('cached') else '')
        + f'；当天累计 {len(cur_list)} 篇')
    print(f'ok:{classic["year"]}:{len(cur_list)}')
    return 0


def main():
    op = sys.argv[1] if len(sys.argv) > 1 else 'new'
    if op == 'show':
        lst = current()
        print(f'当天已累积 {len(lst)} 篇：')
        for i, c in enumerate(lst, 1):
            print(f"  {i}. {c['year']} {c['title'][:60]}")
            print(f"     {c.get('authors','')} — {c.get('venue','')}")
            print(f"     {c.get('url') or classics.link_of(c)}")
        return 0
    return make_new(bump=(op == 'new'))


if __name__ == '__main__':
    sys.exit(main())
