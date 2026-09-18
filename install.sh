#!/usr/bin/env bash
# 研究前沿助手 —— 安装脚本
#
#   bash install.sh              # 探测桌面环境 → 部署小组件 → 装定时器
#   bash install.sh --no-timer   # 只装小组件
#   bash install.sh uninstall    # 卸载（保留数据）
#
# 支持 KDE Plasma 6 与 GNOME（GNOME 用 Shell 扩展，见 gnome/）。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !\033[0m %s\n' "$*"; }

# ---------- 读配置 ----------
read_cfg() {
    "$PY" - "$SRC/config.json" "$1" <<'PY'
import json, sys, os
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    print(''); sys.exit(0)
v = d.get(sys.argv[2], '')
print(os.path.expanduser(v) if isinstance(v, str) else v)
PY
}

if [ ! -f "$SRC/config.json" ]; then
    warn "还没有配置。先跑一次向导："
    echo "    $PY $SRC/wizard.py"
    exit 1
fi
WORKDIR="$(read_cfg workdir)"
[ -z "$WORKDIR" ] && WORKDIR="$HOME/research-frontier-work"
DATA_DIR="$(read_cfg data_dir)"
[ -z "$DATA_DIR" ] && DATA_DIR="$WORKDIR/runtime"
mkdir -p "$WORKDIR" "$DATA_DIR"

# ---------- 桌面环境探测 ----------
detect_de() {
    if [ -n "${XDG_CURRENT_DESKTOP:-}" ]; then
        echo "$XDG_CURRENT_DESKTOP" | tr '[:upper:]' '[:lower:]'
    elif [ -n "${DESKTOP_SESSION:-}" ]; then
        echo "$DESKTOP_SESSION" | tr '[:upper:]' '[:lower:]'
    else
        echo unknown
    fi
}
DE="$(detect_de)"
info "检测到桌面环境：$DE"

# ---------- Plasma 小组件 ----------
install_plasma() {
    local dst="$HOME/.local/share/plasma/plasmoids/org.researchfrontier.widget"
    info "安装 Plasma 小组件 → $dst"
    rm -rf "$dst"; mkdir -p "$dst"
    cp -r "$SRC/plasmoid/." "$dst/"
    find "$dst" \( -name '*.qml' -o -name '*.sh' \) -print0 | while IFS= read -r -d '' f; do
        sed -i -e "s|@DATA_DIR@|$DATA_DIR|g" -e "s|@PROJECT_DIR@|$SRC|g" "$f"
    done
    kbuildsycoca6 >/dev/null 2>&1 || true
    ok "Plasma 小组件已安装（桌面右键 → 添加部件 → 搜索「研究前沿」）"
}

# ---------- GNOME 扩展 ----------
install_gnome() {
    local dst="$HOME/.local/share/gnome-shell/extensions/research-frontier@researchfrontier"
    info "安装 GNOME Shell 扩展 → $dst"
    rm -rf "$dst"; mkdir -p "$dst"
    cp -r "$SRC/gnome/." "$dst/"
    sed -i -e "s|@DATA_DIR@|$DATA_DIR|g" -e "s|@PROJECT_DIR@|$SRC|g" \
        "$dst/extension.js" 2>/dev/null || true
    ok "GNOME 扩展已安装"
    warn "启用：gnome-extensions enable research-frontier@researchfrontier"
    warn "Wayland 下可能需要注销重新登录一次"
}

case "$DE" in
    *kde*|*plasma*) install_plasma ;;
    *gnome*)        install_gnome ;;
    *)
        warn "未识别的桌面环境；两个都装上，你自行启用："
        install_plasma || true
        install_gnome  || true
        ;;
esac

# ---------- systemd 定时器 ----------
if [ "${1:-}" != "--no-timer" ]; then
    UNIT="$HOME/.config/systemd/user"
    mkdir -p "$UNIT"
    info "安装 systemd user timer（每天 06:00）"
    cat > "$UNIT/research-frontier.service" <<EOF
[Unit]
Description=研究前沿助手 · 数据更新
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$SRC
Environment=PYTHONUNBUFFERED=1
Environment=RESEARCH_FRONTIER_WORKDIR=$WORKDIR
ExecStart=$PY $SRC/update.py all
TimeoutStartSec=2400
Nice=10
EOF
    cat > "$UNIT/research-frontier.timer" <<EOF
[Unit]
Description=每天 06:00 更新研究前沿简报

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true
RandomizedDelaySec=180
Unit=research-frontier.service

[Install]
WantedBy=timers.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now research-frontier.timer 2>/dev/null \
        && ok "定时器已启动" \
        || warn "定时器注册失败（无 systemd 会话时正常），可手工跑 update.py"
fi

# ---------- 收尾 ----------
if [ ! -d "$SRC/_katex" ]; then
    info "获取 KaTeX（网页公式渲染，可选）"
    "$PY" "$SRC/setup_katex.py" || warn "KaTeX 下载失败，网页公式将按纯文本显示"
fi

echo
ok "安装完成"
echo "  工作目录：$WORKDIR"
echo
echo "  生成第一份简报： $PY $SRC/update.py all"
echo "  终端预览：       $PY $SRC/preview.py"
echo "  看定时器：       systemctl --user list-timers research-frontier.timer"
echo "  卸载：           bash install.sh uninstall"
