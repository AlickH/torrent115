#!/bin/bash
# 本地升级 FPK：备份数据 -> 卸载 -> 安装新包 -> 恢复数据 -> 启动。
# 用法：bash fnos/upgrade.sh artifacts/release/Torrent115-0.2.0.fpk
set -euo pipefail

APP="torrent115"
FPK="${1:?用法: bash fnos/upgrade.sh <fpk>}"
DATA_DIR="/vol1/@appdata/${APP}/data"
BACKUP="$(mktemp -d)"
trap 'rm -rf "$BACKUP"' EXIT

command -v appcenter-cli >/dev/null 2>&1 || { echo "缺少 appcenter-cli" >&2; exit 1; }
[ -f "$FPK" ] || { echo "找不到 fpk: $FPK" >&2; exit 1; }

if [ -d "$DATA_DIR" ]; then
  cp -a "$DATA_DIR/." "$BACKUP/"
  echo "已备份数据: $DATA_DIR -> $BACKUP"
fi

appcenter-cli stop "$APP" >/dev/null 2>&1 || true
appcenter-cli uninstall "$APP" >/dev/null 2>&1 || true
appcenter-cli install-fpk "$FPK"

mkdir -p "$DATA_DIR"
if [ -n "$(ls -A "$BACKUP" 2>/dev/null)" ]; then
  cp -a "$BACKUP/." "$DATA_DIR/"
  echo "已恢复数据到 $DATA_DIR"
fi

appcenter-cli start "$APP" >/dev/null 2>&1 || true
appcenter-cli status "$APP"
