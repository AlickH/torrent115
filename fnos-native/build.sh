#!/usr/bin/env bash
# 构建 Torrent115 Native FPK。
# 用法：bash fnos-native/build.sh [版本] [x86|arm]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/fnos-native"
VERSION="${1:-0.12.0}"
ARCH="${2:-x86}"
case "$ARCH" in
  x86) PLATFORM="x86" ;;
  arm) PLATFORM="arm" ;;
  *) echo "arch 仅支持 x86/arm" >&2; exit 1 ;;
esac
WH="$SRC/wheelhouse/$ARCH"
[ -d "$WH" ] || { echo "缺少 wheelhouse: $WH" >&2; exit 1; }
command -v fnpack >/dev/null || { echo "缺少 fnpack" >&2; exit 1; }
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$SRC/." "$STAGE/"
rm -rf "$STAGE/wheelhouse"
sed -i "s/__T115_VERSION__/$VERSION/g" "$STAGE/manifest"
sed -i "s/^platform=x86$/platform=$PLATFORM/" "$STAGE/manifest"
SERVER="$STAGE/app/server"
mkdir -p "$SERVER"
cp "$ROOT"/*.py "$ROOT/wsgi.py" "$ROOT/requirements-native.txt" "$SERVER/"
rm -f "$SERVER/localtorrent.py.orig" 2>/dev/null || true
cp -R "$ROOT/static" "$SERVER/static"
cp -R "$WH" "$SERVER/wheelhouse"
find "$STAGE" -name '._*' -delete
mkdir -p "$ROOT/artifacts/release"
(cd "$STAGE" && fnpack build)
FPK="$(find "$STAGE" -maxdepth 1 -name '*.fpk' | head -n1)"
[ -n "$FPK" ] || { echo "未找到 fpk" >&2; exit 1; }
mv "$FPK" "$ROOT/artifacts/release/Torrent115-native-$VERSION-$ARCH.fpk"
echo "已生成: $ROOT/artifacts/release/Torrent115-native-$VERSION-$ARCH.fpk"
