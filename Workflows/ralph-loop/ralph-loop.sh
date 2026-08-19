#!/bin/bash
# Ralph Loop：每轮以全新 context 启动一个 agent CLI，靠磁盘文件（计划清单）接力。
#
# 通用版：不绑定具体 CLI。约定 agent 命令接收"单个 prompt 字符串"作为最后参数，
# 例如：
#   AGENT_CMD='kimi -p'        ./ralph-loop.sh 8
#   AGENT_CMD='claude -p'      ./ralph-loop.sh 8
#   AGENT_CMD='codex exec'     ./ralph-loop.sh 8
#
# 环境变量：
#   AGENT_CMD    （必填）调用 agent CLI 的命令前缀
#   PROMPT_FILE  每轮注入的指令文件，默认 PROMPT.md
#   PLAN_FILE    任务清单（'- [ ]' 格式），默认 plan.md
#   LOG_DIR      每轮输出日志目录，默认 .ralph
#
# 参数：
#   $1           最大轮数，默认 8（防失控兜底，务必设置）
set -u
cd "$(dirname "$0")"

: "${AGENT_CMD:?请设置 AGENT_CMD，例如 AGENT_CMD='kimi -p'}"
PROMPT_FILE=${PROMPT_FILE:-PROMPT.md}
PLAN_FILE=${PLAN_FILE:-plan.md}
LOG_DIR=${LOG_DIR:-.ralph}
MAX_LOOPS=${1:-8}

mkdir -p "$LOG_DIR"

for i in $(seq 1 "$MAX_LOOPS"); do
  echo "===== Loop $i / $MAX_LOOPS 开始 $(date +%H:%M:%S) ====="
  # 故意不加引号：AGENT_CMD 允许携带参数（如 'kimi -p'）
  # shellcheck disable=SC2086
  output=$($AGENT_CMD "$(cat "$PROMPT_FILE")" 2>&1)
  echo "$output" | tee "$LOG_DIR/loop-$i.log" | tail -5

  # 双重完成判定：agent 显式报告 + 清单中确实没有未完成项
  # 缺一不可——只信信号会被幻觉欺骗，只信清单会在 agent 忘记勾掉时误判
  if echo "$output" | grep -q "EXIT_SIGNAL: true" && ! grep -q '^- \[ \]' "$PLAN_FILE"; then
    echo "===== 全部任务完成，循环收敛于第 $i 轮 ====="
    exit 0
  fi
done

echo "===== 达到上限 $MAX_LOOPS 轮仍未收敛，人工介入 ====="
exit 1
