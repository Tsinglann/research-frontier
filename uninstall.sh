#!/usr/bin/env bash
# 卸载研究前沿助手（保留你的工作目录与数据）
set -uo pipefail
systemctl --user disable --now research-frontier.timer 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/research-frontier."{service,timer}
systemctl --user daemon-reload 2>/dev/null || true
rm -rf "$HOME/.local/share/plasma/plasmoids/org.researchfrontier.widget"
rm -rf "$HOME/.local/share/gnome-shell/extensions/research-frontier@researchfrontier"
kbuildsycoca6 >/dev/null 2>&1 || true
echo "已卸载小组件与定时器（数据保留在你的工作目录里）"
