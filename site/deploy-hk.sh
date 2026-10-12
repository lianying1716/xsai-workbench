#!/usr/bin/env bash
# 星采 Stargather 官网 → 香港服务器（cai.xsai5.xyz）
#
# 用法：./deploy-hk.sh
# 作用：把 site/ 目录整体同步到 HK 的 /var/www/cai，并校验线上可用。
#
# 前置：本机 ~/.ssh/config 里已有 deploy-host（203.0.113.10）。
# 站点是纯静态页面，不需要重启任何服务；nginx 直接发文件。
set -euo pipefail

HOST="${HOST:-deploy-host}"
REMOTE_DIR="${REMOTE_DIR:-/var/www/cai}"
DOMAIN="${DOMAIN:-https://cai.xsai5.xyz}"
SRC="$(cd "$(dirname "$0")" && pwd)"

echo "==> 打包 $SRC"
TARBALL="$(mktemp /tmp/cai-site-XXXXXX.tar.gz)"
trap 'rm -f "$TARBALL"' EXIT
tar czf "$TARBALL" -C "$SRC" \
  --exclude='./tools' --exclude='./output' --exclude='./deploy-hk.sh' \
  --exclude='./.git' --exclude='./*.sh' \
  .

echo "==> 上传到 $HOST:$REMOTE_DIR"
scp -q "$TARBALL" "$HOST:/tmp/cai-site.tar.gz"
ssh "$HOST" "set -e
  mkdir -p '$REMOTE_DIR'
  # 保留旧版本一份，便于回滚
  if [ -d '$REMOTE_DIR' ] && [ -n \"\$(ls -A '$REMOTE_DIR' 2>/dev/null)\" ]; then
    rm -rf '${REMOTE_DIR}.prev'
    cp -a '$REMOTE_DIR' '${REMOTE_DIR}.prev'
  fi
  tar xzf /tmp/cai-site.tar.gz -C '$REMOTE_DIR'
  rm -f /tmp/cai-site.tar.gz
  chown -R www-data:www-data '$REMOTE_DIR'
  nginx -t
  systemctl reload nginx
"

echo "==> 校验 $DOMAIN"
for path in / /mobile.html /assets/vendor/gsap.min.js /assets/art/orbit-knowledge.webp; do
  code=$(curl -sS -m 20 -o /dev/null -w '%{http_code}' "$DOMAIN$path")
  printf '  %-40s %s\n' "$path" "$code"
  [ "$code" = "200" ] || { echo "!! $path 返回 $code"; exit 1; }
done

echo "==> 完成。上一版本备份在 $REMOTE_DIR.prev"
