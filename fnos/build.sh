#!/usr/bin/env bash
# 在 fnOS NAS 上构建 Torrent115 的离线 FPK。
# 用法：bash fnos/build.sh [版本号] [镜像名]
#   bash fnos/build.sh 0.1.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FNOS_DIR="$ROOT/fnos"
VERSION="${1:-0.1.0}"
IMAGE="${2:-torrent115:latest}"
TAG="torrent115:$VERSION"
OUT_DIR="$ROOT/artifacts/release"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

command -v fnpack >/dev/null 2>&1 || { echo "缺少 fnpack" >&2; exit 1; }

cp -R "$FNOS_DIR/." "$STAGE/"
rm -rf "$STAGE/agent" "$STAGE/install-agent.sh"
find "$STAGE" -name '._*' -delete
sed -i "s/__T115_VERSION__/$VERSION/g" "$STAGE/manifest"
sed -i "s/__T115_TAG__/$VERSION/g" "$STAGE/app/docker/docker-compose.yaml"
sed -i "/^    image:/a\\    pull_policy: never" "$STAGE/app/docker/docker-compose.yaml"

echo "导出镜像 $IMAGE -> $TAG"
docker tag "$IMAGE" "$TAG"
docker save "$TAG" | gzip -1 > "$STAGE/app/docker/torrent115-image.tar.gz"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$TAG")"
IMAGE_ARCH="$(docker image inspect --format '{{.Architecture}}' "$TAG")"
SHA="$(sha256sum "$STAGE/app/docker/torrent115-image.tar.gz" | awk '{print $1}')"

cat > "$STAGE/cmd/offline-image.env" <<META
IMAGE_TAG=$TAG
IMAGE_ARCH=$IMAGE_ARCH
IMAGE_ID=$IMAGE_ID
IMAGE_ARCHIVE_SHA256=$SHA
META
cp "$STAGE/cmd/offline-image.env" "$STAGE/app/docker/offline-image.env"

mkdir -p "$OUT_DIR"
(cd "$STAGE" && fnpack build)
FPK="$(find "$STAGE" -maxdepth 1 -name '*.fpk' | head -n 1)"
[ -n "$FPK" ] || { echo "未找到 fpk 产物" >&2; exit 1; }
mv "$FPK" "$OUT_DIR/Torrent115-$VERSION.fpk"
echo "已生成: $OUT_DIR/Torrent115-$VERSION.fpk"
