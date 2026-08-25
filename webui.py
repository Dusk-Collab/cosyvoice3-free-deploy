# Copyright (c) 2024 Alibaba Inc (authors: Xiang Lyu, Liu Yue)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
import argparse
import glob
import shutil
import numpy as np
import torch
import torchaudio
import random
import librosa
import time
import gradio as gr
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 懒加载本地 SenseVoice 模型，用于自动识别参考音频里念的文字
_sensevoice_model = None

def get_sensevoice_model():
    global _sensevoice_model
    if _sensevoice_model is None:
        from funasr import AutoModel
        logging.info('正在加载 SenseVoice 语音识别模型（首次启动需几秒钟）...')
        # disable_update 避免每次检查 funasr 更新弹提示
        _sensevoice_model = AutoModel(
            model='iic/SenseVoiceSmall',
            disable_update=True,
            disable_pbar=True,
        )
    return _sensevoice_model


def clean_sensevoice_text(raw):
    """去掉 SenseVoice 输出里的 <|zh|><|NEUTRAL|><|Speech|> 这类标记。"""
    import re
    text = re.sub(r'<\|[^|]+\|>', '', raw)
    return text.strip()


def transcribe_audio(path):
    """识别音频里的文字，失败返回空字符串。"""
    if not path or not os.path.isfile(path):
        return ''
    try:
        model = get_sensevoice_model()
        result = model.generate(input=path)
        # result 形如 [{'key': 'xxx', 'text': '<|zh|><|NEUTRAL|><|Speech|>识别文字'}]
        text = ''
        if result and isinstance(result, list) and 'text' in result[0]:
            text = clean_sensevoice_text(result[0]['text'])
        if text:
            gr.Info('已自动识别参考音频文字：' + text[:40] + ('...' if len(text) > 40 else ''))
        return text
    except Exception as e:
        gr.Warning('参考音频文字识别失败：' + str(e))
        return ''
sys.path.append('{}/third_party/Matcha-TTS'.format(ROOT_DIR))

# 让 pydub/gradio 转码音频时能找到自带的 ffmpeg/ffprobe，
# 否则生成成功但浏览器播放前转码失败会报红“错误”
_ffmpeg_bin = os.path.join(ROOT_DIR, 'py312', 'ffmpeg', 'bin')
if os.path.isdir(_ffmpeg_bin):
    if _ffmpeg_bin not in os.environ.get('PATH', ''):
        os.environ['PATH'] = _ffmpeg_bin + os.pathsep + os.environ.get('PATH', '')
    try:
        import pydub
        _ff = os.path.join(_ffmpeg_bin, 'ffmpeg.exe')
        _fp = os.path.join(_ffmpeg_bin, 'ffprobe.exe')
        if os.path.isfile(_ff):
            pydub.AudioSegment.converter = _ff
        if os.path.isfile(_fp):
            pydub.AudioSegment.ffprobe = _fp
    except Exception:
        pass
from cosyvoice.cli.cosyvoice import AutoModel
from cosyvoice.utils.file_utils import logging
from cosyvoice.utils.common import set_all_random_seed


inference_mode_list = ['预训练音色', '3s极速复刻', '跨语种复刻', '自然语言控制']
instruct_dict = {
    '预训练音色': '最简单：① 在右侧选一个音色 → ② 在「输入要念的文字」里打字 → ③ 点【生成音频】。不用传任何参考声音。',
    '3s极速复刻': '让声音模仿某个参考音频：\n① 在上方「常用参考声音」里直接选一个（或上传/录制），不超过30秒\n② 在「参考音频里念的文字」填上那段音频念的文字\n③ 在「输入要念的文字」填你想生成的话\n④ 点【生成音频】',
    '跨语种复刻': '用参考音频的声音，念另一种语言的文字：\n① 上传或录制一段参考音频，不超过30秒\n② 在「输入要念的文字」填和参考音频不同语言的文字\n③ 点【生成音频】',
    '自然语言控制': '用文字描述想要的效果：\n① 选一个预训练音色\n② 在「想要的效果」里写，例如：用四川话说 / 语速慢一点 / 开心地念\n③ 点【生成音频】'
}
stream_mode_list = ['否', '是']
max_val = 0.8


def generate_seed():
    seed = random.randint(1, 100000000)
    return {
        "__type__": "update",
        "value": seed
    }


def change_instruction(mode_checkbox_group):
    return instruct_dict[mode_checkbox_group]


def generate_audio(tts_text, mode_checkbox_group, sft_dropdown, prompt_text, prompt_wav_upload, prompt_wav_record, instruct_text,
                   seed, stream, speed):
    # Gradio 5.4.0 对 Radio value=False 构建 API schema 会报错，云端用字符串接收再转 bool
    stream = (stream == '是')
    if prompt_wav_upload is not None:
        prompt_wav = prompt_wav_upload
    elif prompt_wav_record is not None:
        prompt_wav = prompt_wav_record
    else:
        prompt_wav = None
    # if instruct mode, please make sure that model is iic/CosyVoice-300M-Instruct and not cross_lingual mode
    if mode_checkbox_group in ['自然语言控制']:
        if cosyvoice.instruct is False:
            gr.Warning('您正在使用自然语言控制模式, {}模型不支持此模式, 请使用iic/CosyVoice-300M-Instruct模型'.format(args.model_dir))
            yield (cosyvoice.sample_rate, default_data)
            return
        if instruct_text == '':
            gr.Warning('您正在使用自然语言控制模式, 请输入instruct文本')
            yield (cosyvoice.sample_rate, default_data)
            return
        if prompt_wav is not None or prompt_text != '':
            gr.Info('您正在使用自然语言控制模式, prompt音频/prompt文本会被忽略')
    # if cross_lingual mode, please make sure that model is iic/CosyVoice-300M and tts_text prompt_text are different language
    if mode_checkbox_group in ['跨语种复刻']:
        if cosyvoice.instruct is True:
            gr.Warning('您正在使用跨语种复刻模式, {}模型不支持此模式, 请使用iic/CosyVoice-300M模型'.format(args.model_dir))
            yield (cosyvoice.sample_rate, default_data)
            return
        if instruct_text != '':
            gr.Info('您正在使用跨语种复刻模式, instruct文本会被忽略')
        if prompt_wav is None:
            gr.Warning('您正在使用跨语种复刻模式, 请提供prompt音频')
            yield (cosyvoice.sample_rate, default_data)
            return
        gr.Info('您正在使用跨语种复刻模式, 请确保合成文本和prompt文本为不同语言')
    # if in zero_shot cross_lingual, please make sure that prompt_text and prompt_wav meets requirements
    if mode_checkbox_group in ['3s极速复刻', '跨语种复刻']:
        if prompt_wav is None:
            gr.Warning('prompt音频为空，您是否忘记选择或上传prompt音频？')
            yield (cosyvoice.sample_rate, default_data)
            return
        if torchaudio.info(prompt_wav).sample_rate < prompt_sr:
            gr.Warning('prompt音频采样率{}低于{}'.format(torchaudio.info(prompt_wav).sample_rate, prompt_sr))
            yield (cosyvoice.sample_rate, default_data)
            return
    # sft mode only use sft_dropdown
    if mode_checkbox_group in ['预训练音色']:
        if instruct_text != '' or prompt_wav is not None or prompt_text != '':
            gr.Info('您正在使用预训练音色模式，prompt文本/prompt音频/instruct文本会被忽略！')
        if sft_dropdown == '':
            gr.Warning('没有可用的预训练音色！')
            yield (cosyvoice.sample_rate, default_data)
            return
    # zero_shot mode only use prompt_wav prompt text
    if mode_checkbox_group in ['3s极速复刻']:
        if prompt_text == '':
            gr.Warning('prompt文本为空，您是否忘记输入prompt文本？')
            yield (cosyvoice.sample_rate, default_data)
            return
        if instruct_text != '':
            gr.Info('您正在使用3s极速复刻模式，预训练音色/instruct文本会被忽略！')

    if mode_checkbox_group == '预训练音色':
        logging.info('get sft inference request')
        set_all_random_seed(seed)
        for i in cosyvoice.inference_sft(tts_text, sft_dropdown, stream=stream, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())
    elif mode_checkbox_group == '3s极速复刻':
        logging.info('get zero_shot inference request')
        set_all_random_seed(seed)
        for i in cosyvoice.inference_zero_shot(tts_text, prompt_text, prompt_wav, stream=stream, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())
    elif mode_checkbox_group == '跨语种复刻':
        logging.info('get cross_lingual inference request')
        set_all_random_seed(seed)
        for i in cosyvoice.inference_cross_lingual(tts_text, prompt_wav, stream=stream, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())
    else:
        logging.info('get instruct inference request')
        set_all_random_seed(seed)
        for i in cosyvoice.inference_instruct(tts_text, sft_dropdown, instruct_text, stream=stream, speed=speed):
            yield (cosyvoice.sample_rate, i['tts_speech'].numpy().flatten())


def list_saved_ref_audio():
    """扫描 参考音频 文件夹，返回 [(显示名, 完整路径), ...] 供列表使用。
    用户把音频保存到该文件夹即永久出现，删除文件则消失。"""
    ref_dir = os.path.join(ROOT_DIR, '参考音频')
    if not os.path.isdir(ref_dir):
        return []
    seen = set()
    files = []
    for ext in ('*.wav', '*.WAV', '*.mp3', '*.MP3', '*.flac', '*.FLAC', '*.m4a', '*.M4A'):
        for f in glob.glob(os.path.join(ref_dir, ext)):
            # Windows 不区分大小写，同一文件可能因 .wav/.WAV 被扫两次，用真实路径去重
            key = os.path.normcase(os.path.realpath(f))
            if key not in seen:
                seen.add(key)
                files.append(f)
    files = sorted(files)
    return [(os.path.basename(f), f) for f in files]


def save_favorite_audio(filepath, name):
    """用户把一段音频保存为常用：复制到 参考音频 文件夹，返回新时间戳触发列表重渲染。"""
    if filepath is None or filepath == '':
        gr.Warning('请先上传一段要保存的音频')
        return time.time()
    ref_dir = os.path.join(ROOT_DIR, '参考音频')
    os.makedirs(ref_dir, exist_ok=True)
    ext = os.path.splitext(filepath)[1] or '.wav'
    if name and name.strip():
        # 去掉 Windows 文件名不允许的字符
        safe = ''.join(c for c in name.strip() if c not in '\\/:*?"<>|')
        dest_name = safe + ext
    else:
        dest_name = os.path.basename(filepath)
    dest = os.path.join(ref_dir, dest_name)
    try:
        shutil.copy2(filepath, dest)
        gr.Info('已保存为常用参考声音：' + dest_name)
    except Exception as e:
        gr.Warning('保存失败：' + str(e))
    return time.time()


def delete_one(path):
    """删除常用参考声音文件，返回新时间戳触发列表重渲染。"""
    if not path:
        return time.time()
    ref_dir = os.path.join(ROOT_DIR, '参考音频')
    real_ref = os.path.realpath(ref_dir)
    real_sel = os.path.realpath(path)
    # 安全检查：只允许删除 参考音频 文件夹内的文件
    if not (real_sel == real_ref or real_sel.startswith(real_ref + os.sep)):
        gr.Warning('只能删除参考音频文件夹里的文件')
        return time.time()
    try:
        os.remove(path)
        gr.Info('已删除：' + os.path.basename(path))
    except Exception as e:
        gr.Warning('删除失败：' + str(e))
    return time.time()


def build_demo():
    default_mode = '3s极速复刻'
    with gr.Blocks() as demo:
        gr.Markdown("### 代码库 [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) \
                    预训练模型 [CosyVoice-300M](https://www.modelscope.cn/models/iic/CosyVoice-300M) \
                    [CosyVoice-300M-Instruct](https://www.modelscope.cn/models/iic/CosyVoice-300M-Instruct) \
                    [CosyVoice-300M-SFT](https://www.modelscope.cn/models/iic/CosyVoice-300M-SFT)")
        gr.Markdown("#### 想让电脑替你念什么，就在这里生成语音。先选「用法」，按右侧步骤操作即可。")

        tts_text = gr.Textbox(label="输入要念的文字", lines=2, value='')
        with gr.Row():
            mode_checkbox_group = gr.Radio(choices=inference_mode_list, label='选择用法（怎么生成）', value=default_mode)
            instruction_text = gr.Text(label="操作步骤（跟着做就行）", value=instruct_dict[default_mode], scale=0.5)
            sft_dropdown = gr.Dropdown(choices=sft_spk, label='选择音色', value=sft_spk[0], scale=0.25)
            stream = gr.Radio(choices=stream_mode_list, label='是否边生成边播放', value='否')
            speed = gr.Number(value=1, label="语速(0.5慢~2.0快)", minimum=0.5, maximum=2.0, step=0.1)
            with gr.Column(scale=0.25):
                seed_button = gr.Button(value="\U0001F3B2")
                seed = gr.Number(value=0, label="随机推理种子")

        with gr.Row():
            prompt_wav_upload = gr.Audio(sources='upload', type='filepath', label='上传参考音频（不超过30秒）', editable=True)
            prompt_wav_record = gr.Audio(sources='microphone', type='filepath', label='录制参考音频', editable=True)

        gr.Markdown("#### 📁 常用参考声音（点击名字使用，点击 × 删除）")
        with gr.Accordion("已保存的音频（点击展开/收起）", open=True):
            render_trigger = gr.State(0)

            @gr.render(inputs=[render_trigger])
            def render_favorites(trigger):
                items = list_saved_ref_audio()
                if not items:
                    gr.Markdown("暂无常用参考声音，上传后点“保存为常用”即可出现。")
                    return
                for name, path in items:
                    with gr.Row():
                        name_btn = gr.Button(name, variant='secondary', scale=5)
                        del_btn = gr.Button("×", variant='stop', size='sm', scale=0)
                        name_btn.click(
                            lambda p=path: [
                                gr.update(value=p),
                                gr.update(value=transcribe_audio(p))
                            ],
                            inputs=[], outputs=[prompt_wav_upload, prompt_text]
                        )
                        del_btn.click(delete_one, inputs=[gr.State(path)], outputs=[render_trigger])

        with gr.Row():
            favorite_upload = gr.Audio(sources='upload', type='filepath', label='上传要存为常用的音频')
            fav_name_input = gr.Textbox(label='给这段声音起个名字（可选）', placeholder='例如：我的声音、客服播报')
            save_fav_button = gr.Button('💾 保存为常用', variant='secondary')
            refresh_fav_button = gr.Button('🔄 刷新常用列表', variant='secondary')

        prompt_text = gr.Textbox(label="参考音频里念的文字", lines=1, placeholder="把上面选的参考音频里念的文字打在这里（复刻模式需要）", value='')
        instruct_text = gr.Textbox(label="想要的效果（如：用开心的语气说）", lines=1, placeholder="例如：用四川话说 / 语速慢一点", value='')

        generate_button = gr.Button("▶ 生成音频", variant="primary")

        audio_output = gr.Audio(label="生成结果（可播放/下载）", autoplay=True, streaming=True)

        def on_reference_audio_changed(path):
            """上传/录制/选中参考音频后，自动识别文字并填入 prompt_text。"""
            if path:
                return gr.update(value=transcribe_audio(path))
            return gr.update(value='')

        seed_button.click(generate_seed, inputs=[], outputs=seed)
        save_fav_button.click(save_favorite_audio, inputs=[favorite_upload, fav_name_input], outputs=[render_trigger])
        favorite_upload.upload(save_favorite_audio, inputs=[favorite_upload, fav_name_input], outputs=[render_trigger])
        refresh_fav_button.click(fn=lambda: time.time(), inputs=[], outputs=[render_trigger])
        prompt_wav_upload.change(on_reference_audio_changed, inputs=[prompt_wav_upload], outputs=[prompt_text])
        prompt_wav_record.change(on_reference_audio_changed, inputs=[prompt_wav_record], outputs=[prompt_text])
        generate_button.click(generate_audio,
                              inputs=[tts_text, mode_checkbox_group, sft_dropdown, prompt_text, prompt_wav_upload, prompt_wav_record, instruct_text,
                                      seed, stream, speed],
                              outputs=[audio_output])
        mode_checkbox_group.change(fn=change_instruction, inputs=[mode_checkbox_group], outputs=[instruction_text])
    demo.queue(max_size=4, default_concurrency_limit=2)
    return demo


def main():
    """本地入口：构建界面并启动（供 webui.py 直接运行 / .bat 调用）。"""
    demo = build_demo()
    auth = load_auth()
    launch_kwargs = dict(server_name='0.0.0.0', server_port=args.port,
                         inbrowser=not os.environ.get('COSYVOICE_HEADLESS'),
                         show_error=True)
    if auth is not None:
        launch_kwargs['auth'] = auth
        print('[登录保护] 已启用账号密码登录，未授权无法使用')
    demo.launch(**launch_kwargs)


def load_auth():
    """读取 auth.json 启用登录保护。返回 Gradio 的 auth 参数或 None。
    文件不存在 / enabled=false / 没有用户 → 返回 None（不启用登录，本地用）。
    auth.json 示例：
    {
      "enabled": true,
      "users": {"admin": "改成你自己的密码", "guest": "123456"}
    }
    """
    auth_path = os.path.join(ROOT_DIR, 'auth.json')
    if not os.path.isfile(auth_path):
        return None
    try:
        import json
        with open(auth_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if not cfg.get('enabled', False):
            return None
        users = cfg.get('users', {})
        if not users:
            return None
        return [(u, p) for u, p in users.items()]
    except Exception as e:
        print('[登录保护] 读取 auth.json 失败，未启用登录：', e)
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',
                        type=int,
                        default=8000)
    parser.add_argument('--model_dir',
                        type=str,
                        default='pretrained_models/CosyVoice3-0.5B',
                        help='local path or modelscope repo id')
    args = parser.parse_args()
    cosyvoice = AutoModel(model_dir=args.model_dir)

    sft_spk = cosyvoice.list_available_spks()
    if len(sft_spk) == 0:
        sft_spk = ['']
    prompt_sr = 16000
    default_data = np.zeros(cosyvoice.sample_rate)
    main()
