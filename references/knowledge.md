# 知识总结：只写能考的客观知识（复习卡）

课程内容落两份文件，**不许混**：

| 文件 | 内容 | 谁写 |
|---|---|---|
| `knowledge/<course>/bank.md` / `bank.json` | 题库：题面、选项、**正确答案**；平台没给答案的题才附我的答案 | `scripts/quiz_bank.py build` |
| `knowledge/<course>/knowledge.md` | 知识总结：**能出选择题/判断题的客观知识**，一条一句 | 每节一个 agent 写 note，再由 `scripts/knowledge_doc.py build` 拼装 |

## 0. 一条知识算不算「能考」

判断标准只有一个：**把这条单独拿出来，能不能出成一道选择题或判断题**。

- **写**：定义、分类与层级、人物与著作、年代与数字、原则与规则、因果与判断标准、
  容易混的两个术语的区别。
- **不写**：老师的评价、抱怨、劝学、个人经历、比喻修辞、课堂事务。
- **举例一律删**：保留考点本身；校验拒收含「比如 / 例如 / 举例 / 譬如」的 note。
- **课程主体案例保留**：若整节以某案例为研究对象，保留能直接出题的事实链；旁支举例、修辞、评论与劝学删去。
- 改写后必须能单独构成客观判断；不要把课程叙述或写作评价当成知识点。

## 1. 格式（`notes/<course>/<section>.md`）

```markdown
**考点知识**

- 提问是整个学术研究的源头，也是后续写作目标的总源头。
- 学术论文按创新性分三类：澄清旧理论、批判旧理论、从现实中提出新问题。
- 本科论文只要求第一类：对主流问题提出反思。
- 「梓匠轮舆能与人规矩，不能使人巧」出自《孟子》。

**概念表**

- 学术论文：以提出并回答学术问题为目的的写作。
- 外部性：一方使用资源的成本由另一方承担。
```

硬性要求（`knowledge_doc.py check` 会卡）：

- 必须含 `考点知识` 与 `概念表` 两段，顺序如此。
- `考点知识` 至少 8 条，每条**一句话**，短。
- 正文至少 300 字。
- **不许带时间轴**：出现 `(00:01:17)` 这类括号直接判不合格。
- 不许出现 `本节讲什么` / `要点` / `本节结论`（旧格式），不许出现 `【单选题】` / `我的答案：` / `正确答案：`。
- 不许写「含义 / 怎么考 / 易混：」这类分行讲解——要的是知识点本身。

## 2. 调用方式（一节一个 agent，可并行）

- 原文按**节点类型**取，不是只有「字幕」一条路：
  | 节点形态 | 原文来源 |
  |---|---|
  | 有字幕的视频 | `runs/<task>/subs/<course>/<section>.srt`（功能 1/2 顺手存的） |
  | 无字幕的视频 | `scripts/asr_mimo.py --chunk-seconds 90` 转写（`[asr] enabled = true` 时） |
  | 富文本节点（`knowledge/cards` 正文 ≥ 800 字） | 直接取 `cards` 的 `innerText`，不要花钱转写 |
  | 文档型节点（`ananas/modules/pdf`） | 查看器页图（`s3.cldisk.com/.../thumb/N.png`，匿名可下）→ `scripts/quiz_ocr.py` |
  两者都没有才回节点取 `allsubtitle`——**不要为了字幕再刷一遍视频**。
  同一课程可以混用这几种节点，逐节点检查。
- 该节题目（只用于定位考点，**不许抄进产出**）：
  `python scripts/quiz_bank.py section --bank knowledge/<course>/bank.json --code <section>`。
- 产出：`runs/<task>/notes/<course>/<section>.md`，写完跑
  `python scripts/knowledge_doc.py check <note>`。

## 3. 无字幕：由 `local/private.toml` 的 `[asr]` 开关决定

| `[asr] enabled` | 行为 |
|---|---|
| `true` | 无字幕 → ASR 转写 → 按转写原文答题；无字幕节也写知识总结 |
| `false` | 旧流程：无字幕 → 学科判断（标 low-confidence）；知识总结**跳过**这些节 |

- 播放器给的是签名直链 MP4（`s2.cldisk.com/.../sd.mp4`，要 `Referer: https://mooc1.chaoxing.com/`，不要 cookie），
  **不播放也能取到**，所以可以在播放的同时并行转写：边播边转，播完直接做测验。
- CDN 每连接只给 3–10 MB 就断，脚本已做 Range 断点续传。
- **必须 90 秒分块**：600 秒分块会让模型重复同一段十几遍。
- 转写后仍逐题核对原文，不能由转写成功推断答案正确。

## 4. 拼装

```powershell
python scripts/knowledge_doc.py build --bank knowledge/<course>/bank.json `
  --notes runs/<task>/notes/<course>
```

## 5. 质量判据

1. 这条能不能出成一道选择题/判断题？不能就删。
2. 有没有出现「老师说了什么」「应该怎样学」的组织？有就删。
