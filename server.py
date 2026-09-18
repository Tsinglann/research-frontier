#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 本地预览服务（给日历网页提供「加一篇」按钮的后端）。

为什么需要它：网页是用 `file://` 打开的，此时浏览器会拦截页面发起的
POST 请求（CORS），所以「加一篇」这种要写数据的按钮在纯静态页面上做不了。
本服务用 Python 标准库起一个**只监听 127.0.0.1** 的小 HTTP 服务，
让网页既能显示数据、也能触发「加一篇经典」。

用法：
  server.py [--port 8765] [--open]     # --open 启动后自动开浏览器

设计：
  * 只绑定 127.0.0.1，不对外暴露
  * GET  /             → 日历回顾网页（数据实时读 daily/ 与 runtime/）
  * GET  /site/*       → 静态文件（data.js 等）
  * GET  /api/state    → 当前简报 + 经典列表
  * POST /api/classic/new → 追加一篇经典，返回新的经典列表
"""
import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from researchlib import archive, config as C            # noqa: E402
from researchlib.util import load_json                  # noqa: E402


def _render_page():
    """返回网页 HTML（带实时数据 + 注入「加一篇」能力）。"""
    archive.build_site()
    html_path = os.path.join(archive.SITE_DIR, 'index.html')
    try:
        html = io.open(html_path, encoding='utf-8').read()
    except OSError:
        return '<h1>还没有数据。先运行 python3 update.py all</h1>'
    # 注入：告诉前端「有后端可用」，据此显示「加一篇」按钮
    inject = '''<script>
window.RF_SERVER = true;
window.rfNewClassic = async function () {
  try {
    const r = await fetch('/api/classic/new', { method: 'POST' });
    const d = await r.json();
    if (d.ok) { location.reload(); }
    else { alert('加一篇失败：' + (d.error || '未知错误')); }
  } catch (e) { alert('请求失败：' + e); }
};
</script>'''
    return html.replace('</body>', inject + '\n</body>')


class Handler(BaseHTTPRequestHandler):
    server_version = 'research-frontier/1.0'

    def log_message(self, fmt, *args):      # 安静点，别刷屏
        pass

    def _send(self, code, body, ctype='text/html; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), 'application/json; charset=utf-8')

    # -------------------------------------------------- GET
    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            return self._send(200, _render_page())
        if path == '/api/state':
            brief = load_json(C.BRIEF_JSON, {})
            st = load_json(C.STATE_JSON, {})
            return self._json({
                'ok': True,
                'generated': brief.get('generated_text'),
                'classic_list': st.get('classic_list') or (
                    [brief['classic']] if brief.get('classic') else []),
            })
        if path == '/api/classic/new':
            return self._json({'ok': False, 'error': '请用 POST'}, 405)
        # 静态文件
        rel = path.lstrip('/')
        full = os.path.normpath(os.path.join(archive.SITE_DIR, rel))
        if full.startswith(os.path.abspath(archive.SITE_DIR)) and os.path.isfile(full):
            ctype = ('application/javascript' if full.endswith('.js')
                     else 'text/css' if full.endswith('.css')
                     else 'font/woff2' if full.endswith('.woff2')
                     else 'application/octet-stream')
            with open(full, 'rb') as f:
                return self._send(200, f.read(), ctype)
        return self._send(404, 'not found', 'text/plain; charset=utf-8')

    # -------------------------------------------------- POST
    def do_POST(self):
        path = self.path.split('?')[0]
        try:
            ln = int(self.headers.get('Content-Length') or 0)
            if ln:
                self.rfile.read(ln)
        except Exception:
            pass
        if path == '/api/classic/new':
            try:
                r = subprocess.run(['/usr/bin/python3',
                                    os.path.join(HERE, 'classic.py'), 'new'],
                                   cwd=HERE, capture_output=True, text=True, timeout=600)
                out = (r.stdout or '').strip()
                st = load_json(C.STATE_JSON, {})
                lst = st.get('classic_list') or []
                if r.returncode != 0 and not lst:
                    return self._json({'ok': False,
                                       'error': (r.stderr or out or 'classic.py 失败')[:200]})
                return self._json({'ok': True, 'count': len(lst), 'raw': out[:120]})
            except Exception as e:                          # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)[:200]})
        return self._json({'ok': False, 'error': 'not found'}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--open', action='store_true', help='启动后自动打开浏览器')
    a = ap.parse_args()

    os.makedirs(archive.SITE_DIR, exist_ok=True)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'研究前沿 · 日历回顾服务已启动：{url}')
    print('（只监听 127.0.0.1，仅在你自己机器上可访问；Ctrl+C 退出）')
    if a.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已退出')
    finally:
        srv.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
