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
      # 用系统默认浏览器打开日历回顾网页（数据由 update.py 生成）
      # 用 DATA_DIR 拼路径而不是硬编码，避免路径里有空格时出问题
      # 存档固定放在 ~/Documents/daily（见 researchlib/archive.py 的 ARCHIVE_DIR）
      # 用 $HOME 直接拼，层级关系一目了然（从 SRC 往上数容易错，本喵已经错过一次）
      u="$DATA_DIR/../daily/site/index.html"
      if [ -f "$u" ]; then
          /usr/bin/xdg-open "$u" >/dev/null 2>&1 &
          echo "OPENED $u"
      else
          echo "MISSING $u"
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
