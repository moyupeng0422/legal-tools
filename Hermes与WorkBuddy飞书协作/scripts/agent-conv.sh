#!/usr/bin/env bash
# agent-conv.sh — 飞书多 agent conv 文件读写引擎 v1.0 (2026-11-22)
# 契约：protocol-multiagent.md §4 + collab-directory-spec.md §2
# 子命令:
#   read <conv路径>                       读（编码 fallback 内建）
#   append <conv路径> --type r1|r2|r3|state --content-file <f> [--task-id X] [--pair P] [--topic T]
#   list [--pair hermes-badi] [--state open|closed|all]
#   init <pair目录>                       初始化 pair 目录结构
set -euo pipefail
die() { echo "$1"; exit 2; }

CMD="${1:-}"; shift || true
case "$CMD" in
  read)   [[ $# -lt 1 ]] && die "用法: agent-conv.sh read <conv路径>"; exec python3 "$HOME/.hermes/scripts/_conv_impl.py" read "$@";;
  append) [[ $# -lt 3 ]] && die "用法: agent-conv.sh append <conv路径> --type TYPE --content-file F"; exec python3 "$HOME/.hermes/scripts/_conv_impl.py" append "$@";;
  list)   exec python3 "$HOME/.hermes/scripts/_conv_impl.py" list "$@";;
  init)   [[ $# -lt 1 ]] && die "用法: agent-conv.sh init <pair目录>"; exec python3 "$HOME/.hermes/scripts/_conv_impl.py" init "$@";;
  *) die "用法: agent-conv.sh read|append|list|init ...";;
esac
