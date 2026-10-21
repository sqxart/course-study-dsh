# 知识总结：只写考点知识与概念（复习卡）

课程内容落两份文件，**不许混**：

| 文件 | 内容 | 谁写 |
|---|---|---|
| `knowledge/<course>/bank.md` / `bank.json` | 题库：题面、选项、**正确答案**；平台没给答案的题才附我的答案 | `scripts/quiz_bank.py build` |
| `knowledge/<course>/knowledge.md` | 知识总结：这一节涉及的**知识与概念**，一条一句 | 每节一个 agent 写 note，再由 `scripts/knowledge_doc.py build` 拼装 |

## 0. 写什么、不写什么

- **写**：定义、分类、判断依据、因果关系、结论性判断、易混术语的区别。
- **不写**：本节讲什么 / 要点 1..N / 本节结论 这类总结；不要「含义 / 怎么考 / 易混」分行讲道理；
  不要写学习方法、考试技巧、老师个人经历、课堂事务。
- **不写**题目原文和答案。这里写的是"支撑这些题的知识"。
- 只写字幕里讲过的；字幕没讲的原理、数据、结论一律不补。

## 1. 一节 note 的格式（`notes/<course>/<section>.md`）

```markdown
**考点知识**

- 提问是学术研究的源头，也是后续写作目标的总源头（00:00:20–00:00:45）
- 学习与学术要分开：学术论文按创新性分三类——澄清旧理论、批判旧理论、从现实中发现新问题
- 本科论文要求的是第一类，能对主流问题提出反思即可
- 外部性指一方使用资源、成本由另一方承担

**概念表**

- 学术论文：以提出并回答学术问题为目的的写作。
- 外部性：一方使用资源的成本由另一方承担。
```

硬性要求（`knowledge_doc.py check` 会卡）：

- 必须含 `考点知识` 与 `概念表` 两段（顺序如此）。
- `考点知识` 至少 6 条，每条**一句话**，短。
- 每条尽量带时间戳（单点或区间）；若该节只有 ASR 转写、没有字幕，note 顶部写一行 `来源：ASR 转写`，
  校验会放行。
- 正文至少 200 字。
- **不许**出现 `本节讲什么` / `要点` / `本节结论`；**不许**出现 `【单选题】` / `我的答案：` / `正确答案：`。
- 不许写「怎么考 / 含义 / 易混：」这类分行讲解——用户要的是知识点本身。

## 2. 调用方式（一节一个 agent，可并行）

给 agent 的输入：

- 字幕：`runs/bank/subs/<course>/<section>.srt`；没有字幕的节用 ASR 转写
  （`scripts/asr_mimo.py`，见下）。
- 该节题目（只用于定位考点，**不许抄进产出**）：
  `python scripts/quiz_bank.py section --bank knowledge/<course>/bank.json --code <section>`。
- 产出：`runs/bank/notes/<course>/<section>.md`，写完自己跑
  `python scripts/knowledge_doc.py check <note>`。

## 3. 没有字幕的节：MiMo ASR

播放器给的是签名直链 MP4（`s2.cldisk.com/.../sd.mp4`，CDN 要 `Referer: https://mooc1.chaoxing.com/`，
不需要 cookie）。一次调用完成下载 → ffmpeg 转 16k 单声道 mp3 → 分块 → MiMo ASR：

```powershell
python scripts/asr_mimo.py --source "<signed mp4 url>" --out runs/bank/asr/<section>.txt
```

- 端点 `https://api.xiaomimimo.com/v1/chat/completions`，`model=mimo-v2.5-asr`，`api-key` 头；
  key 放 `local/mimo.key`（gitignore）或 `$MIMO_API_KEY`。
- 实测：14.7 分钟视频 38.7 MB → 转写 **<时长>秒**，计费 <时长>秒（约 0.12 元），中文与专名准确。
- ASR 输出没有时间轴，所以这类 note 不强制时间戳。

## 4. 拼装

```powershell
python scripts/quiz_bank.py build --nodes runs/bank/nodes/paper-writing --course paper-writing `
  --title 示例课程11 --expected runs/bank/expected-paper-writing.json
python scripts/knowledge_doc.py build --bank knowledge/<course>/bank.json `
  --notes runs/<task>/notes/<course>
```

## 5. 质量判据

1. 看完「考点知识」能不能直接答这一节的题。
2. 每条是不是**一句话就能读完**；读完有没有"在复习而不是在上课"的感觉。
