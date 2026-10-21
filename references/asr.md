# ASR：默认关闭，别人装了不一定能用

这门技能的主链路（看视频、答弹题、交章节测验、取题库、写复习卡）**不需要 ASR**。
只有一种情况会用到它：**这节课没有字幕**，而你还想按老师原话答题或写复习卡。

## 0. 先看这里：三件东西缺一不可

| 需要 | 缺了会怎样 | 怎么补 |
|---|---|---|
| `ffmpeg` + `ffprobe` 在 PATH 上 | `asr_mimo.py` 直接 `ffmpeg not found` 退出 | Windows：`winget install Gyan.FFmpeg`；macOS：`brew install ffmpeg`；Linux：包管理器装 `ffmpeg` |
| 一个 ASR 服务的 API key | 只会提示 `no API key`；不影响其它功能 | 见下面 §2 |
| `local/private.toml` 里 `[asr] enabled = true` | 脚本拒绝运行（`ASR is switched off`） | 见 §1；这是**安全默认**，防止误花钱 |

没有字幕又没有 ASR 时，技能会退回老行为：弹题按学科知识猜并标 `low_confidence`，复习卡**跳过这一节**，
并在报告里写明「本节无字幕、未转写」。**不会静默失败，也不会假装有原文。**

## 1. 打开开关

安装器会把 `private.toml.example` 复制成 `local/private.toml`（`local/` 已被 gitignore，不会外传）。
把 `[asr]` 段改成：

```toml
[asr]
enabled = true
chunk_seconds = 90        # 实测值；600 秒分块会让模型把同一段复读十几遍
# 下面这些不填就走 MiMo 默认值
# endpoint   = "https://api.xiaomimimo.com/v1/chat/completions"
# model      = "mimo-v2.5-asr"
# auth_style = "api-key"  # MiMo 用 api-key 头；多数 OpenAI 兼容服务用 bearer
# key_file   = "local/mimo.key"
```

key 的读取顺序：`--api-key` → 环境变量（`MIMO_API_KEY`、`ASR_API_KEY`、`--provider-key-env` 指定的那个）→ `key_file`。
`local/mimo.key` 只放一行 key，**不要提交、不要贴进 issue**。

## 2. 选一个 ASR 服务

### 2.1 MiMo（脚本默认，实测过的就是它）

- 模型 `mimo-v2.5-asr`，OpenAI 兼容的 chat-completions，音频走 base64 `input_audio`。
- 注册送体验金（**2026-10 核实仍在有效**），够跑几十小时课程音频（实测 30 分钟视频约 <时长>秒转完）：

> 我在用 MiMo 开放平台，体验小米顶尖模型 MiMo V2.6 等。通过我的邀请码注册：双方各得 ¥10 API 体验金 + 首单 9 折。
> 邀请码：**KQDN7K**。注册：<https://platform.xiaomimimo.com?ref=KQDN7K>（注册后自动填入 · 体验金 40 天有效）

  （这是本项目作者的邀请链接；不想用可以自己搜官网注册，脚本不绑定邀请关系。）
- 拿到 key 后：`echo <key> > local/mimo.key`，或设 `MIMO_API_KEY`。

### 2.2 其它 OpenAI 兼容的 ASR

只要对方接受同样的 `input_audio` chat 负载，就能直接换：

```powershell
python scripts/asr_mimo.py --source "<签名 mp4>" --out runs/asr/2.1.txt `
  --endpoint https://api.groq.com/openai/v1/chat/completions `
  --model whisper-large-v3-turbo --auth-style bearer --provider-key-env GROQ_API_KEY
```

常见的免费/低价路线（额度与政策各家会变，以官网为准，**本项目没有逐家实测**）：

| 路线 | 说明 | 代价 |
|---|---|---|
| Groq | 有免费额度，`whisper-large-v3-turbo` 速度极快 | 需 `--auth-style bearer`；免费档有速率限制 |
| SiliconFlow 等国内聚合 | 提供 `SenseVoice`/`Whisper` 类模型，常有免费额度 | 需确认它支持 `input_audio` 这种 chat 负载 |
| 阿里云 / 腾讯云 / 讯飞 | 商用 ASR，中文效果好 | 按量计费，通常要实名 |

**不支持 `input_audio` 的服务（只有独立 `/audio/transcriptions` 接口）不能直接用本脚本**：
本项目没有为每家写适配器，遇到这种就用下面的本地路线。

### 2.3 完全本地、免费：faster-whisper / whisper.cpp

不想联网、不想办 key，就用本地模型转写，再把结果放进 `runs/<task>/asr/<节>.txt`，技能会直接用它写复习卡：

```powershell
pip install faster-whisper
# 自己下 mp4（播放器里的签名直链），转 16k 单声道 wav：
ffmpeg -i lesson.mp4 -ar 16000 -ac 1 lesson.wav
python -c "from faster_whisper import WhisperModel as W; m=W('small', device='cpu', compute_type='int8'); segs,_=m.transcribe('lesson.wav', language='zh'); open('2.1.txt','w',encoding='utf-8').write('\n'.join(s.text for s in segs))"
```

- 优点是零成本、离线；缺点是慢（CPU 上 small 模型大约 1 小时音频要十几分钟），中文标点不如云端。
- `scripts/media_keep.py` 只认 `asr/<节>.txt` 这个**结果文件**，不关心它是谁转的，所以本地路线可以直接混用。

## 3. 成本与体积

- 实测：30 分钟视频 ≈ <时长>秒转完、约 0.5 元/小时音频（MiMo，2026-10 的价格，可能变）。
- 音频不落盘：脚本在临时目录转码、分块、base64 后即删；`--keep-audio` 才保留（调试用）。
- 一节课的转写 ≈ 30–60 KB 文本，建议放在 `runs/`（已 gitignore），不要提交。

## 4. 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `ffmpeg not found on PATH` | 没装 ffmpeg | 装完重开终端 |
| `ASR is switched off` | `[asr] enabled` 是 false 或缺文件 | 改配置，或临时 `--force` |
| `no API key` | 三个来源都没有 key | 写 `local/mimo.key` 或设环境变量 |
| 403 / 401 | key 错、或服务商要 `bearer` 而不是 `api-key` | 加 `--auth-style bearer` |
| 转写整段重复 | 分块太大 | `--chunk-seconds 90` |
| 下载 403 | 签名 mp4 需要 `Referer: https://mooc1.chaoxing.com/` | 脚本已带；直链过期就重新进节点取一次 |
