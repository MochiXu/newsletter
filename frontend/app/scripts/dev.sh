#!/bin/bash
# 预览/开发包装脚本:预览运行环境不会加载 nvm,这里显式把 node 目录放进 PATH,
# 再跑 copy-data + vite。供 .claude/launch.json 调用。
set -e
export PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH"
cd "$(dirname "$0")/.."
node scripts/copy-data.mjs || true
exec node node_modules/vite/bin/vite.js --port 5179 --strictPort
