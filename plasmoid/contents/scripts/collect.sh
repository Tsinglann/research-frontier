#!/usr/bin/env bash
# 研究前沿助手 —— 把运行数据喂给 QML 部件（以及手动触发更新）
#
# 为什么不用 XMLHttpRequest 读 file://：Plasma 的 QML 安全策略会静默拒绝，
# 表现为界面空白但 journal 里没有任何报错（本喵踩过）。
# 因此统一走 P5S.DataSource(engine=executable) + 本脚本输出 JSON。
#
#   collect.sh profile|papers|brief   输出对应 JSON（QML 每次轮询都调）
#   collect.sh update                 手动触发一次完整更新
set -u
STAGE="${1:-}"
DATA_DIR="@DATA_DIR@"
SRC="@PROJECT_DIR@"
PY=/usr/bin/python3

case "$STAGE" in
  profile|papers|brief)
      f="$DATA_DIR/$STAGE.json"
      if [ ! -s "$f" ]; then
          # 文件还没生成：输出空对象，QML 侧会安全忽略
          echo "{}"
          exit 0
      fi
      # 输出必须是**单行压缩 JSON**：本部件实测发现 P5S.DataSource 的
      # executable 引擎对多行输出处理不可靠（44KB 的多行 JSON 只拿到了开头的
      # "{" 之类残缺内容），而 researchfrontier 那种单行 JSON 一直很稳。
      # 所以这里统一用 python 把 JSON 压成一行再吐出去。
      "$PY" -c 'import json,sys,io
try:
    d=json.load(io.open(sys.argv[1],encoding="utf-8"))
except Exception:
    print("{}"); sys.exit(0)
sys.stdout.write(json.dumps(d,ensure_ascii=False,separators=(",",":")))
' "$f"
      ;;
  open)
      # 用系统默认浏览器打开日历回顾网页（数据由 update.py 生成）。
      # ⚠️ 必须让浏览器进程脱离 plasmashell：原来直接 `xdg-open "$u" &` 仍是它的
      # 子进程，plasmashell 回收子进程时这次启动就断了 ——
      # 表现为「第一次能打开，关掉之后再点就没反应」。
      # 所以用 setsid + nohup 起一个独立会话，再 disown。
      u="$HOME/Documents/daily/site/index.html"
      if [ ! -f "$u" ]; then
          echo "MISSING $u"
      else
          launched=""
          # 优先用户自己的浏览器包装脚本（可能带代理参数），再回退通用名字
          for b in "$HOME/.local/bin/chrome" "$HOME/.local/bin/chromium" \
                   "$HOME/.local/bin/firefox" google-chrome chrome chromium firefox; do
              if command -v "$b" >/dev/null 2>&1; then
                  setsid nohup "$b" "$u" >/dev/null 2>&1 &
                  disown 2>/dev/null || true
                  launched="$b"
                  break
              fi
          done
          if [ -z "$launched" ] && command -v xdg-open >/dev/null 2>&1; then
              setsid nohup xdg-open "$u" >/dev/null 2>&1 &
              disown 2>/dev/null || true
              launched="xdg-open"
          fi
          if [ -n "$launched" ]; then
              echo "OPENED $u via $launched"
          else
              echo "NO-BROWSER $u"
          fi
      fi
      ;;
  update)
      mkdir -p "$DATA_DIR"
      {
        echo "[collect] $(date '+%F %T') 手动更新"
        "$PY" "$SRC/update.py" all
        echo "[collect] $(date '+%F %T') rc=$?"
      } >> "$DATA_DIR/update.log" 2>&1
      echo "OK"
      ;;
  *)
      echo "usage: collect.sh profile|papers|brief|update|open" >&2
      exit 2
      ;;
esac
