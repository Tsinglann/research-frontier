#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 用户动作 worker（部件按钮的后端）。

用法：
  action.py like <序号>          点赞：论文进入「推荐画像」，下次抓取加权
  action.py unlike <序号>        取消点赞
  action.py collect <序号>       收藏进 Zotero「研究前沿app收藏」分类
  action.py uncollect <序号>     从该分类移除
  action.py translate <序号>     走论文翻译流程（后台任务，写队列状态）
  action.py newclassic          换一篇经典论文（每天不限次数）
  action.py status               打印当前点赞数与收藏数

所有结果写进 runtime/actions.json，部件读它来显示按钮状态。
翻译是长任务，只负责**排队 + 后台启动**，进度由 translate_worker.py 写同一份状态。
"""
import datetime as dt
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from researchlib import config as C            # noqa: E402
from researchlib.util import load_json, log, save_json   # noqa: E402

ACTIONS_JSON = os.path.join(C.DATA_DIR, 'actions.json')
PAPERS_JSON = C.PAPERS_JSON
TRANSLATE_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'translate_worker.py')


def _paper(idx):
    doc = load_json(PAPERS_JSON, {'papers': []})
    papers = doc.get('papers', [])
    if not (1 <= idx <= len(papers)):
        return None
    return papers[idx - 1]


def _pkey(p):
    return (p.get('doi') or p.get('arxiv') or p.get('title') or '')[:120].lower()


def _load_actions():
    return load_json(ACTIONS_JSON, {'likes': {}, 'collected': {}, 'translations': {}})


def _save_actions(a):
    a['updated'] = int(dt.datetime.now().timestamp())
    save_json(ACTIONS_JSON, a)


def do_like(idx, on=True):
    p = _paper(idx)
    if not p:
        return f'no-paper:{idx}'
    a = _load_actions()
    k = _pkey(p)
    if on:
        a['likes'][k] = {
            'title': p.get('title'), 'journal': p.get('journal'),
            'why': p.get('why') or [], 'score': p.get('score'),
            'ts': int(dt.datetime.now().timestamp()),
        }
    else:
        a['likes'].pop(k, None)
    _save_actions(a)
    log(f'{"点赞" if on else "取消点赞"}：{p.get("title","")[:60]}（共 {len(a["likes"])} 赞）')
    return f'{"liked" if on else "unliked"}:{len(a["likes"])}'


def do_collect(idx, on=True):
    p = _paper(idx)
    if not p:
        return f'no-paper:{idx}'
    # 延迟导入：只有真要用时才碰 sqlite
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'researchlib'))
    from researchlib import zotero_write as ZW
    if not on:
        st = ZW.uncollect(p)
        a = _load_actions()
        a['collected'].pop(_pkey(p), None)
        _save_actions(a)
        log(f'取消收藏：{st}')
        return f'uncollect:{st}'
    st, item_id = ZW.collect(p)
    a = _load_actions()
    if st.startswith('created') or st.startswith('reused'):
        a['collected'][_pkey(p)] = {
            'title': p.get('title'), 'itemID': item_id,
            'ts': int(dt.datetime.now().timestamp()),
        }
        _save_actions(a)
    log(f'收藏：{st}（itemID={item_id}）')
    return f'collect:{st}'


def do_newclassic():
    """换一篇经典：递增 offset 并重新生成回顾（复用缓存，不重跑抓取）。"""
    import subprocess as sp
    r = sp.run(['/usr/bin/python3', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'classic.py'), 'new'],
               capture_output=True, text=True, timeout=600)
    out = (r.stdout or '').strip() + (' ' + (r.stderr or '').strip() if r.stderr else '')
    log(f'换经典：{out.strip()[:120]}')
    return out.strip() or 'ok'


def do_translate(idx):
    p = _paper(idx)
    if not p:
        return f'no-paper:{idx}'
    a = _load_actions()
    k = _pkey(p)
    cur = a['translations'].get(k)
    if cur and cur.get('state') in ('queued', 'running'):
        return f'busy:{cur.get("state")}'
    a['translations'][k] = {
        'title': p.get('title'), 'state': 'queued', 'progress': 0,
        'msg': '已排队', 'ts': int(dt.datetime.now().timestamp()), 'paper': p,
    }
    _save_actions(a)
    # 后台启动翻译 worker（不阻塞部件）
    try:
        subprocess.Popen(
            ['/usr/bin/python3', TRANSLATE_WORKER, str(idx)],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        log(f'翻译任务已排队：{p.get("title","")[:60]}')
        return 'translate:queued'
    except Exception as e:                      # noqa: BLE001
        a['translations'][k]['state'] = 'error'
        a['translations'][k]['msg'] = f'启动失败：{e}'
        _save_actions(a)
        return f'translate:error:{e}'


def main():
    if len(sys.argv) < 2:
        print('usage: action.py like|unlike|collect|uncollect|translate|status [序号]')
        return 2
    op = sys.argv[1]
    if op == 'status':
        a = _load_actions()
        print(f"likes={len(a.get('likes',{}))} collected={len(a.get('collected',{}))} "
              f"translations={len(a.get('translations',{}))}")
        return 0
    # newclassic 不需要序号，必须先于序号解析处理（顺序错了会 IndexError）
    if op == 'newclassic':
        try:
            print(do_newclassic())
            return 0
        except Exception as e:                      # noqa: BLE001
            log(f'换经典失败：{e}')
            print(f'error:{e}')
            return 1
    if len(sys.argv) < 3:
        print(f'{op} 需要一个论文序号')
        return 2
    try:
        idx = int(sys.argv[2])
    except ValueError:
        print('序号必须是整数')
        return 2
    fn = {'like': lambda: do_like(idx, True),
          'unlike': lambda: do_like(idx, False),
          'collect': lambda: do_collect(idx, True),
          'uncollect': lambda: do_collect(idx, False),
          'translate': lambda: do_translate(idx)}.get(op)
    if not fn:
        print(f'未知操作：{op}')
        return 2
    try:
        print(fn())
        return 0
    except Exception as e:                      # noqa: BLE001
        log(f'动作 {op} 失败：{e}')
        print(f'error:{e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
