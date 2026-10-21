# 四种功能：先选一个，再读对应流程

这个技能只做四件事。**开工前先用一句话确认用户要哪一件**；一句话里有两件就按「1 → 2 → 3/4」的顺序排，不要默认全做。
平台事实、通道与调用预算在 [DSH 运行说明](dsh-runtime.md)；本文件只讲四种功能各自的最短路径、判据和边界。

| # | 功能 | 用户会怎么说 | 产出 | 会写平台状态吗 |
|---|---|---|---|---|
| 1 | 全节点完成：视频 + 弹题 + 章节测验 | 把课跑完、任务点清零、刷课 | 该节点任务点全亮 | 会 |
| 2 | 单独完成视频 **或** 单独完成章节测验 | 只把视频看完 / 只做这一节测验 | 只推进其中一个任务点 | 会（只动这一件） |
| 3 | 形成课程题库（只读） | 出题库、取题目、要答案 | `knowledge/<course>/bank.json` + `bank.md` | **不会** |
| 4 | 总结课程知识文档 | 复习卡、知识点总结、课程总结 | `knowledge/<course>/knowledge.md` | **不会** |

- 3 和 4 是**只读**功能：只进结果页、只读字幕，不点选项、不提交、不重做。
- 1 和 2 会改平台状态，必须已经有本次授权；证据模式（`mode=evidence`）下连 2 的测验部分也只能读到证据为止。
- **开工前把选择权交给用户**：告诉他技能支持自动作答并提交（`mode=completion` + `submit=true`）和无字幕 ASR 转写，
  两者默认关闭；讲清风险（分数不可撤回、次数会消耗、推断可能错），由用户决定改不改配置。没明确要求就按只读跑。
- 同一账号、同一标签、同一时间只跑一个功能；换功能前先回目录、确认上一个功能已收尾。
- **窗口别抢前台**：跳转会把 DSH 的浏览器顶到前面。开工挂 `python scripts/browser_window.py watch --minutes 180`
  （后台守候）或每次跳转后 `minimize`；它只动 `--user-data-dir` 带 `.dsh` 的窗口，用户自己的浏览器不受影响。
  最小化后截图与 DOM 操作照常；旧播放器会因失焦暂停，那类课不要最小化。

## 1. 全节点完成（视频 + 弹题 + 章节测验）

流程：[单节点快速配方](quickstart.md) → [网课流程](course-flow.md)。要点：

- 一个节点**只进一次**：视频 → 弹题 → 章节测验 → 最后回目录核任务点数。
- 倍速优先点播放器菜单；菜单点不动才写 `video.playbackRate`，并记 `rate_source=property`。
- **顺手留下文本**：进节点时播放器帧的 `allsubtitle`（含 srt 地址）与签名 `mp4` 一起记进 `evidence.json`
  （`subs` / `media` 字段），节点结束后跑 `scripts/media_keep.py keep --evidence …`：
  有 SRT 存 `subs/<course>/<节>.srt`，没有才按 `[asr] enabled` 用 90 秒分块转写成 `asr/<course>/<节>.txt`。
  知识总结直接用这份文本，不再为同一节课重复取字幕或重复付费转写。
- 完成判据只看平台标记（目录行尾剩余点数、`icon_Completed`、结果页「已完成」）。
- 节点结束先写 `runs/<task>/evidence.json`，再过 `scripts/check_evidence.py`。

## 2a. 只完成视频

1. 从目录进节点，**不点「章节测验」(dct2)**——打开待作答页会在平台留下「已查看」痕迹，只做视频就不要碰它。
2. 探测倍速并起播，观察器按 `总预算 ≈ 剩余秒数 / rate` 续，单次调用 ≤175 秒。
3. `ended` 后立刻回目录，读这一行的剩余任务点数。
4. `evidence.json` 里把测验段写成 `"quiz": {"opened": false, "decision": "skipped"}`，`video.ended` 只作本地状态，不作完成证明。
5. 字幕同样顺手留下：`subs`（`allsubtitle` 与 srt 列表）与 `media.mp4` 写进 `evidence.json`，回目录前跑
   `scripts/media_keep.py keep --evidence <该节点>`。只做视频的节点往往就是以后要写复习卡的节点，此时不存等于白看。

判据：回目录后该行点数减少（或整行数字消失）。数字没变就是没录上，按 [现场笔记](field-notes.md) 排查，不要重复刷。

## 2b. 只完成章节测验

1. 从目录进节点，**不播放视频**（只测验时不要起播，省时间也少一层状态）。
2. 点 `dct2`／「章节测验」，等 `.TiMu` 渲染完再作答（帧 URL 先到、内容后到）。
3. 证据模式：只截图/OCR，**不点选项、不点提交**，报告「测验未打开或仅查看」。
   完成模式：按 [单节点快速配方](quickstart.md) 的作答与提交段执行，提交确认在 studentstudy 帧的 `#workpop a.jb_btn`。
4. 回目录核这一节的任务点是否点亮（0 分可能不点亮，看平台标记不看提交成功）。

`evidence.json` 里 `video` 段写 `{"played": false}`，`quiz` 段记 `opened` / `submitted` / `decision` / `work_id` / 分数。

## 3. 形成课程题库（只读）

流程：[题库取数](bank.md)。要点：

- 输入必须是**已提交**的节点：点「章节测验」直接进结果页 `selectWorkQuestionYiPiYue`；出现 `doHomeWorkNew` 就是没提交，**停手报告**，不要替用户先交。
- 一节点一 agent、一节点一次调用，按节号从目录点进去；每节点落一份 capture 到 `runs/<task>/nodes/<course>/<节>.json`，跑 `scripts/quiz_bank.py check`。
- `bank.md` 排版：**不写题号**；单选/多选在正确选项行末尾打 `✓`；「正确答案：…（来源）」行保留。
- 收口：`scripts/quiz_bank.py build --expected …`，覆盖率里缺节必须是 0。

## 4. 总结课程知识文档

流程：[知识总结](knowledge.md)。要点：

- 输入是这一节的字幕（无字幕且 `[asr] enabled = true` 才用 `scripts/asr_mimo.py --chunk-seconds 90` 转写）。
  **先看 `runs/<task>/subs/<course>/` 与 `runs/<task>/asr/<course>/` 里有没有现成文件**——功能 1/2 已经顺手存过，
  有就直接用；没有再回放节点取 `allsubtitle`，别为了字幕再刷一遍视频。
- 一节一个 note，只写**能出选择题/判断题**的客观知识：定义、分类、人物与著作、年代数字、原则、因果、易混区别。
- 不写时间轴、删掉举例（课程主体案例保留）、不写老师评价/劝学/课堂事务、不抄题目。
- 每份 note 先过 `scripts/knowledge_doc.py check` 到 `ok`，再 `knowledge_doc.py build` 拼成 `knowledge.md`，缺节必须为 0。

## 组合与顺序

| 用户要的 | 正确顺序 |
|---|---|
| 先把课跑完，再要题库和总结 | 1（或 2）做完并回目录确认 → 3（只读取数）→ 4（字幕写卡） |
| 只要题库 | 直接 3；发现没提交就停在报告，不要顺手提交 |
| 只要知识总结 | 直接 4；字幕缺就按 `[asr]` 开关处理，不为了总结去刷视频 |
| 只要视频 / 只要测验 | 直接 2a / 2b，别把另一个功能带进来 |

## 验收清单（按功能）

- 1 / 2：平台侧任务点标记有变化；`evidence.json` 通过 `scripts/check_evidence.py`（证据模式加 `--require-readonly`）。
- 3：每节 `quiz_bank.py check` 通过；`build` 的 `missing_sections` 为空；`bank.md` 无「题号」行、正确选项带 `✓`。
- 4：每节 `knowledge_doc.py check` 为 `ok`；`build` 报 `MISSING=0`；`knowledge.md` 无时间码、无举例标记。
