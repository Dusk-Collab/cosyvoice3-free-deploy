---
title: CosyVoice3 语音合成（免费 GPU 部署版）
emoji: 🎙️
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 5.4.0
app_file: app.py
pinned: false
hf_oauth: false
---

# CosyVoice3 语音合成 · 免费公网部署版

基于 CosyVoice-300M 的语音克隆 / 合成 Web 界面。可一键部署到
**HuggingFace Spaces（免费 GPU）** 或 **魔搭社区 Modelscope Studio（免费 GPU）**，
部署后拿到公网网址，任何设备浏览器打开即用，**无需下载那十几 G 模型**。

## 这个仓库包含什么（部署只需这几个文件）
- `app.py`：公网部署入口。模型来源 / 端口 / 登录全部走环境变量，平台按它启动会自动下载模型。
- `webui.py`：界面本体（app.py 复用它，本地 .bat 也用它）。
- `requirements.txt`：依赖清单。
- `auth.json`：可选登录配置（部署推荐改用环境变量，见下）。

> **不要**把 `pretrained_models/`、`py312/` 等十几 G 文件传上仓库——
> 平台会根据 `COSYVOICE_MODEL_DIR` 自动从模型库下载模型。

## 一键部署到 HuggingFace Spaces（免费 GPU）
1. 把本仓库推到你的 GitHub。
2. 打开 https://huggingface.co/spaces → New Space → SDK 选 **Gradio** →
   创建时选「Link to a GitHub repository」关联本仓库（或把这几个文件直接推到 Space 仓库）。
3. 在 Space 的 **Settings → Variables and secrets** 添加：
   - `COSYVOICE_MODEL_DIR` = `FunAudioLLM/CosyVoice-300M`
   - `COSYVOICE_USER` / `COSYVOICE_PASS`（可选，想加登录就填）
   - `PORT` = `7860`
4. 启动后得到 `https://你的名-空间名.hf.space` 公网网址，发给谁都能用。

## 部署到魔搭社区 Modelscope Studio（免费 GPU，国内更快）
见仓库内 `免费部署指南.md`。

## 环境变量
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COSYVOICE_MODEL_DIR` | `iic/CosyVoice-300M` | 模型库 ID，平台自动下载 |
| `PORT` | `7860` | 平台监听端口 |
| `COSYVOICE_USER` / `COSYVOICE_PASS` | 空 | 设了就启用登录保护 |
| `COSYVOICE_HEADLESS` | `1` | 云端无桌面，关闭自动开浏览器 |

## 本地使用
本地仍用 `webui.py` + 桌面 `.bat` 启动，与本仓库部署互不影响。

## ⚠️ 计费提醒（Cloud Studio / 任意按量 GPU 平台）
- 工作空间「**运行中**」就一直在烧额度/计费；只有「**关机**」才停。
- **不能靠“放着不动”自动关**：平台的“空闲自动关”是按心跳算的，开着浏览器标签页就一直算“有人用”，不会自动停。
- 最稳的保险 = 平台自带的「**定时关机**」按钮（编辑界面顶部栏），设定后到点**无条件硬关机**。每次启动都设一下（2~4 小时）。
- 仓库另附 best-effort 看门狗 `auto_shutdown.sh`（需自建腾讯云密钥才确定有效）。详见 **[CLOUD_DEPLOY.md](CLOUD_DEPLOY.md)** 的「防忘关机」一节。

## 给非技术用户的傻瓜版说明
👉 **[小白使用说明.md](小白使用说明.md)** —— 纯大白话，讲清楚"以后聊天记录没了去哪找、云端那份没了怎么重新弄"。建议收藏本仓库网址：https://github.com/Dusk-Collab/cosyvoice3-free-deploy
