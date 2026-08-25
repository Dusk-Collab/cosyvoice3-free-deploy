# -*- coding: utf-8 -*-
"""
CosyVoice3 公网部署入口（免费 GPU 平台专用：魔搭社区 Modelscope Studio / HuggingFace Spaces）

和本地 webui.py 共用同一套界面与功能，区别只在于：
  - 模型从环境变量 COSYVOICE_MODEL_DIR 读取（默认是魔搭模型库 ID，平台会自动下载，你不用下）
  - 端口从环境变量 PORT 读取（平台固定 7860）
  - 登录账号从环境变量 COSYVOICE_USER / COSYVOICE_PASS 读取（不设就不登录）
  - 默认无界面（headless），适配没有桌面的云服务器

本地照常用 webui.py + 桌面 .bat，不需要动这个文件。
"""

import os
import sys
import argparse
import numpy as np

# 关掉 Gradio 启动时的外网版本检查（免费平台上可能很慢/卡住，导致打不开）
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

# 让 app.py 能 import 到同目录的 webui.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 云端部署时， cosyvoice 需要 third_party/Matcha-TTS 子模块才能 import matcha.models
_MATCHA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'third_party', 'Matcha-TTS')
if os.path.isdir(_MATCHA_DIR):
    sys.path.insert(0, _MATCHA_DIR)

import webui  # noqa: E402

# 1) 决定模型位置：默认用魔搭模型库 ID，平台首次运行会自动下载（免费、不占你电脑空间）
MODEL_DIR = os.environ.get('COSYVOICE_MODEL_DIR', 'iic/CosyVoice-300M')

# 2) 加载模型（在免费平台上这一步由平台服务器完成，你本地无需下载任何东西）
print(f'[部署] 正在加载模型：{MODEL_DIR}（首次会因下载稍慢，之后有缓存）')
webui.args = argparse.Namespace(model_dir=MODEL_DIR)  # generate_audio 内警告信息会用到
webui.cosyvoice = webui.AutoModel(model_dir=MODEL_DIR)
webui.sft_spk = webui.cosyvoice.list_available_spks()
if len(webui.sft_spk) == 0:
    webui.sft_spk = ['']
webui.prompt_sr = 16000
webui.default_data = np.zeros(webui.cosyvoice.sample_rate)
print('[部署] 模型加载完成')

# 3) 构建界面（复用 webui.py 的全部功能：常用声音、自动识别文字、登录等）
demo = webui.build_demo()

# 4) 平台方式启动
PORT = int(os.environ.get('PORT', 7860))
auth_user = os.environ.get('COSYVOICE_USER')
auth_pass = os.environ.get('COSYVOICE_PASS')

launch_kwargs = dict(
    server_name='0.0.0.0',
    server_port=PORT,
    show_error=True,
    share=False,
)
if auth_user and auth_pass:
    launch_kwargs['auth'] = [(auth_user, auth_pass)]
    print('[登录保护] 已启用账号密码登录，未授权无法使用')

demo.launch(**launch_kwargs)
