#!/usr/bin/env bash
# ============================================================
# auto_shutdown.sh —— CosyVoice 云端“忘关机”看门狗（可选，best-effort）
#
# 作用：监测 Gradio(7860) 一段时间无人访问后，尽量把整个工作空间关掉，
#       避免一直“运行中”烧免费额度 / 后付费。
#
# 重要认知（务必先看）：
#   工作空间的“计费 / 计时”生命周期由 Cloud Studio 平台控制，
#   容器内部【无法保证】一定能停掉计费。本脚本只能“尽力”关停：
#     1) 若设置了腾讯云 API 凭据（TENCENT_SECRET_ID / TENCENT_SECRET_KEY）
#        且提供了工作空间 ID（CS_WORKSPACE_ID），调用
#          tccli cloudstudio StopWorkspace --workspace-id <id>
#        这是唯一【确定能】从内部真正关停工作空间的方式（需要你自己的密钥，可选）。
#     2) 否则尝试  shutdown -h now / poweroff（部分工作空间可用，best-effort）。
#     3) 都不行时只写日志告警，请你手动点「关机」或用平台“定时关机”。
#
# 真正“万无一失”的保险是 Cloud Studio 自带的【定时关机】按钮
# （编辑界面顶部栏「设置定时关机」），设定后到点无条件硬关机，比本脚本更可靠。
# 本脚本只是补充，二选一或双保险都行。
#
# 启用方式（在 cloud_deploy.sh 顶部或环境变量里设）：
#   export AUTO_SHUTDOWN_IDLE_MINUTES=120   # 空闲 120 分钟后尝试关停
# ============================================================
set +e

PORT="${PORT:-7860}"
IDLE_MINUTES="${AUTO_SHUTDOWN_IDLE_MINUTES:-0}"
LOG="deploy.log"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "${IDLE_MINUTES:-0}" -le 0 ] 2>/dev/null; then
  echo "[看门狗] 未启用（AUTO_SHUTDOWN_IDLE_MINUTES 未设置或 <=0），退出"
  exit 0
fi

echo "[看门狗] 已启用：Gradio(:${PORT}) 连续 ${IDLE_MINUTES} 分钟无新访问则尝试关停工作空间"

# ---- 准备 tccli（仅在用户显式提供腾讯云 API 密钥时）----
TC_AVAILABLE=0
if [ -n "$TENCENT_SECRET_ID" ] && [ -n "$TENCENT_SECRET_KEY" ] && [ -n "$CS_WORKSPACE_ID" ]; then
  if ! command -v tccli >/dev/null 2>&1; then
    pip install --break-system-packages tccli >/dev/null 2>&1 || pip install tccli >/dev/null 2>&1 || true
  fi
  if command -v tccli >/dev/null 2>&1; then
    export TENCENTCLOUD_SECRET_ID="$TENCENT_SECRET_ID"
    export TENCENTCLOUD_SECRET_KEY="$TENCENT_SECRET_KEY"
    TC_AVAILABLE=1
    echo "[看门狗] 检测到腾讯云密钥 + 工作空间ID，将用 tccli StopWorkspace 真正关停"
  fi
else
  echo "[看门狗] 未配置腾讯云密钥(可选)。若无密钥，本脚本只能 best-effort 尝试 shutdown；"
  echo "[看门狗] 最可靠做法仍是平台『定时关机』按钮。当前仅作兜底。"
fi

last_activity=$(date +%s)
while true; do
  sleep 60
  now=$(date +%s)

  had_conn=0
  # 方式A：端口有 ESTABLISHED 连接（有人正在用）
  if command -v ss >/dev/null 2>&1; then
    if ss -tan 2>/dev/null | grep -q ":${PORT}.*ESTAB"; then had_conn=1; fi
  fi
  # 方式B：日志最近 1 分钟有变动且含请求（Gradio 会打 /gradio_api 等）
  if [ -f "$LOG" ]; then
    if find "$LOG" -mmin -1 2>/dev/null | grep -q .; then
      if tail -n 80 "$LOG" 2>/dev/null | grep -q "gradio_api\|/api/\|POST \|GET \|/queue"; then
        had_conn=1
      fi
    fi
  fi

  if [ "$had_conn" = "1" ]; then
    last_activity=$now
    continue
  fi

  idle=$(( (now - last_activity) / 60 ))
  if [ "$idle" -ge "$IDLE_MINUTES" ]; then
    echo "[看门狗] 已空闲 ${idle} 分钟，尝试关停工作空间（$(date)）" | tee -a "$LOG"
    stopped=0
    if [ "$TC_AVAILABLE" = "1" ]; then
      tccli cloudstudio StopWorkspace --workspace-id "$CS_WORKSPACE_ID" >> "$LOG" 2>&1 && stopped=1
    fi
    if [ "$stopped" = "0" ]; then
      shutdown -h now >> "$LOG" 2>&1 || poweroff >> "$LOG" 2>&1 || true
    fi
    # 无论成败都退出循环，避免反复执行
    break
  fi
done
