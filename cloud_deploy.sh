#!/usr/bin/env bash
# ============================================================
# CosyVoice 云端 GPU 一键部署脚本
# 适用：腾讯云 Cloud Studio / 魔搭 Studio / 任意 Linux GPU 工作区
# 用法：把本脚本放到工作区，终端执行  bash cloud_deploy.sh
# 特点：不用时平台自动休眠/关机 → 不计费、不计时间
# ============================================================
set -e
echo "===== CosyVoice 云端部署开始 ====="

# 1) 代码：克隆/更新我们已推到 GitHub 的仓库（含 app.py / webui.py / requirements.txt）
REPO_DIR="${HOME}/cosyvoice-deploy"
if [ ! -d "$REPO_DIR/.git" ]; then
  rm -rf "$REPO_DIR"
  git clone https://github.com/Dusk-Collab/cosyvoice3-free-deploy.git "$REPO_DIR"
else
  echo "[更新] 拉取最新代码..."
  git -C "$REPO_DIR" pull origin main
fi
cd "$REPO_DIR"

# 让 Cloud Studio 打开工作空间时自动启动 CosyVoice（复制到工作空间根 .vscode）
mkdir -p "$HOME/.vscode"
if [ -f "$REPO_DIR/.vscode/preview.yml" ]; then
  cp -f "$REPO_DIR/.vscode/preview.yml" "$HOME/.vscode/preview.yml"
fi

# 2) 模型缓存放到工作空间“持久盘”（stop/start 后仍在，避免重复下载5GB）
#    Cloud Studio 工作空间磁盘是持久化的，关机/休眠后文件保留；
#    只有“手动重置工作空间”或“免费高性能版闲置>30天被回收”才会清空。
#    把缓存写死在这个路径，确保每次部署都复用同一份模型，不重复下载。
export MODELSCOPE_CACHE="${REPO_DIR}/.modelscope_cache"
export HF_HOME="${REPO_DIR}/.hf_cache"

# 3) Python：云端 GPU 镜像通常已预装 torch+cuda；检测不到再补装
PY=python3
if ! $PY -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  echo "[提示] 未检测到 CUDA，尝试安装 torch(GPU)…"
  $PY -m pip install --break-system-packages torch torchaudio \
    --index-url https://download.pytorch.org/whl/cu121 || true
fi

# 3) 安装依赖（requirements 已排除 torch，避免装成 CPU 版）
$PY -m pip install --break-system-packages -r requirements.txt

# 4) cosyvoice 需要 third_party/Matcha-TTS。仓库若已含源码（我们已上传）直接复用，
#    仅在缺失时才运行时 clone 兜底（网络可能不稳定，不要覆盖已上传版本）。
mkdir -p third_party
if [ -d "third_party/Matcha-TTS/matcha" ]; then
  echo "[部署] 检测到仓库自带 Matcha-TTS 源码，直接复用（跳过下载）"
else
  echo "[部署] 仓库缺 Matcha-TTS，运行时下载..."
  rm -rf third_party/Matcha-TTS
  git clone --depth 1 https://gitcode.com/gh_mirrors/cos/Matcha-TTS.git third_party/Matcha-TTS || \
    git clone --depth 1 https://github.com/FunAudioLLM/Matcha-TTS.git third_party/Matcha-TTS
fi

# 5) 模型与端口（按需改）：
#    - 想用 CosyVoice3 新模型，把下面改成 FunAudioLLM/Fun-CosyVoice3-0.5B-2512
#    - 登录保护：取消注释下面两行并改成你的账号密码（防止别人白嫖你的额度）
export COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-iic/CosyVoice-300M}"
export PORT="${PORT:-7860}"
# export COSYVOICE_USER=boss
# export COSYVOICE_PASS=123456

# 6) 启动（平台会把 7860 端口自动暴露成公网网址）
echo "[部署] 启动 CosyVoice，监听 0.0.0.0:$PORT"
nohup $PY app.py > deploy.log 2>&1 &
echo "[部署] 已后台启动，日志见 deploy.log"
sleep 10
echo "===== 启动日志（最后 20 行）====="
tail -n 20 deploy.log
echo "===== 完成后在平台点“访问 / 公开链接”即可拿到公网网址 ====="
