#!/usr/bin/env bash
# ============================================================
# CosyVoice 云端 GPU 一键部署脚本
# 适用：腾讯云 Cloud Studio / 魔搭 Studio / 任意 Linux GPU 工作区
# 用法：把本脚本放到工作区，终端执行  bash cloud_deploy.sh
# 特点：不用时平台自动休眠/关机 → 不计费、不计时间
# ============================================================
set -e
echo "===== CosyVoice 云端部署开始 ====="

# 1) 代码：克隆我们已推到 GitHub 的仓库（含 app.py / webui.py / requirements.txt）
REPO_DIR="${HOME}/cosyvoice-deploy"
if [ ! -d "$REPO_DIR" ]; then
  git clone https://github.com/Dusk-Collab/cosyvoice3-free-deploy.git "$REPO_DIR"
fi
cd "$REPO_DIR"

# 2) Python：云端 GPU 镜像通常已预装 torch+cuda；检测不到再补装
PY=python3
if ! $PY -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  echo "[提示] 未检测到 CUDA，尝试安装 torch(GPU)…"
  $PY -m pip install --break-system-packages torch torchaudio \
    --index-url https://download.pytorch.org/whl/cu121 || true
fi

# 3) 安装依赖（requirements 已排除 torch，避免装成 CPU 版）
$PY -m pip install --break-system-packages -r requirements.txt

# 4) 模型与端口（按需改）：
#    - 想用 CosyVoice3 新模型，把下面改成 FunAudioLLM/Fun-CosyVoice3-0.5B-2512
#    - 登录保护：取消注释下面两行并改成你的账号密码（防止别人白嫖你的额度）
export COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-iic/CosyVoice-300M}"
export PORT="${PORT:-7860}"
# export COSYVOICE_USER=boss
# export COSYVOICE_PASS=123456

# 5) 启动（平台会把 7860 端口自动暴露成公网网址）
echo "[部署] 启动 CosyVoice，监听 0.0.0.0:$PORT"
nohup $PY app.py > deploy.log 2>&1 &
echo "[部署] 已后台启动，日志见 deploy.log"
sleep 10
echo "===== 启动日志（最后 20 行）====="
tail -n 20 deploy.log
echo "===== 完成后在平台点“访问 / 公开链接”即可拿到公网网址 ====="
