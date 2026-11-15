#!/bin/bash
# 在 fnOS 宿主机上安装 Torrent115 宿主机脚本代理（aria2/Transmission 移动文件用）
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 755 "$DIR/agent/t115-host-agent.py" /usr/local/sbin/t115-host-agent.py
install -m 644 "$DIR/agent/t115-host-agent.service" /etc/systemd/system/
install -m 644 "$DIR/agent/t115-host-agent.timer" /etc/systemd/system/
mkdir -p /vol1/@appdata/torrent115/data/hooks/pending /vol1/@appdata/torrent115/data/hooks/done
systemctl daemon-reload
systemctl enable --now t115-host-agent.timer
systemctl status t115-host-agent.timer --no-pager | head -5
