#!/usr/bin/env bash
# 调星算 images API 生成图并下载（该服务返回 URL 而非 b64，官方 CLI 不兼容）
set -euo pipefail
KEY=$(cat /tmp/xk)
API=https://api.xsai5.xyz/v1/images/generations
gen() {  # gen <out.png> <model> <size> <prompt>
  local out="$1" model="$2" size="$3" prompt="$4"
  local body
  body=$(python3 -c "
import json,sys
print(json.dumps({'model':sys.argv[1],'prompt':sys.argv[2],'size':sys.argv[3],'n':1}))
" "$model" "$prompt" "$size")
  local resp url
  resp=$(curl -s -m 300 "$API" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$body")
  url=$(python3 -c "
import json,sys
d=json.loads(sys.argv[1])
if 'error' in d: print('ERR:'+json.dumps(d['error'],ensure_ascii=False)); sys.exit(0)
print(d['data'][0].get('url') or '')
" "$resp")
  if [[ "$url" == ERR:* ]]; then echo "  !! $out $url"; return 1; fi
  if [[ -z "$url" ]]; then echo "  !! $out no-url: ${resp:0:200}"; return 1; fi
  curl -s -m 300 -o "$out" "$url"
  echo "  ok $out $(stat -c%s "$out") bytes"
}
gen "$@"
