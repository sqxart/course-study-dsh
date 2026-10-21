---
name: course-study-dsh
description: DeepSeek Harness 专用的网课减负技能。静音、按平台官方菜单允许的速率把学习通课程的视频看完，用字幕原话回答弹题，章节测验先取证再按授权提交；证据不足就拒答。只在当前 harness 配置的 mcp-browser 通道下操作页面，一个账号一条通道。
---

# 课程助手（DeepSeek Harness 版）

给 DeepSeek Harness 用的网课减负技能：**把视频看完、把弹题答对、把章节测验的证据摆出来**。不刷倍数、不伪造心跳、不碰上报接口。
Harness 的通道事实、已实测范围与调用预算在 [DSH 运行说明](references/dsh-runtime.md)；只读需要的部分，不要一次加载全部材料。

## 开始

1. 确认当前工具面：当前账号对应的 `mcp__browser__browser_*`、`mcp__browser2__browser_*` 或 `mcp__browser3__browser_*`（一个账号只用一条）、`pwsh`、`read/edit`。缺少受支持的浏览器通道时只做离线工作，不去找隐藏调试接口或自建 CDP 脚本。
2. 先读 `local/private.toml`：没有文件就按证据模式（`mode=evidence`、`submit=false`）；有则按其 `mode` 与 `submit` 执行，并在记录里写明本次模式。然后确定平台、课程、账号别名、任务类型与已有授权；续跑先读 `local/CURRENT_HANDOFF.md` 与 `local/active-session.json`，再核验平台实际状态。
   **证据模式**下章节测验只读：打开答题页、截图/OCR、摆证据，**不点选项、不点提交、不重开**；视频和弹题照常完成。打开答题页会生成 `#workAnswerId`，平台学习记录里会标成**已查看**（无分数、不是已完成）；1.2.3 实测 `#addTimes` 仍为 0、没有消耗提交次数，但“已查看”是可见痕迹。用户明确不想留下查看记录时，停在目录并报告“测验未打开”，不要自行打开。
3. **先确认要做哪一个功能**，再只读那一条流程（详见 [四种功能](references/modes.md)）：

   | # | 功能 | 产出 | 流程 | 平台知识 |
   |---|---|---|---|---|
   | 1 | 全节点完成：视频 + 弹题 + 章节测验 | 该节点任务点全亮 | [单节点快速配方](references/quickstart.md) → [网课流程](references/course-flow.md) | [学习通](references/chaoxing.md) |
   | 2 | 单独完成视频 **或** 单独完成章节测验 | 只推进其中一个任务点 | [四种功能](references/modes.md) §2a / §2b | 同上 |
   | 3 | 形成课程题库（只读） | `knowledge/<course>/bank.json` + `bank.md` | [题库取数](references/bank.md) | 结果页明文；正确答案是否可见每课一策；`bank.md` 不写题号、正确选项打 `✓` |
   | 4 | 总结课程知识文档 | `knowledge/<course>/knowledge.md` | [知识总结](references/knowledge.md) | 只收能出选择题/判断题的客观知识；无字幕节由 `[asr]` 开关决定做不做 |

   其他参考：摸不清的现象先查 [现场笔记](references/field-notes.md)；两个账号 / 两条通道看 [多账号运行](references/multi-account.md)；
   有无新课件/测验、截止时间走网课流程的列表巡检，先停在列表，开始测验是后续独立动作。

   3、4 是**只读**功能（不点选项、不提交、不重做）；1、2 会写平台状态，必须有本次授权。同一账号、同一标签同一时间只跑一个功能。

4. 使用独立任务目录 `runs/<task-id>/`，记录账号别名、课程键、当前标签/执行器、已有授权、进行中的测验和证据。格式见 [状态与交接](references/state.md)。
   节点结束**先把 `runs/<task-id>/evidence.json` 写到盘上再汇报**（视频时长、倍率与 `rate_source`、弹题题干与证据、测验 `submitted`/`decision`、任务点前后、调用数、偏差）；写完用 `scripts/check_evidence.py --require-readonly` 自检。

## 速率与播放

- 进节点先探测：读 `video.playbackRate` 当前值和播放器的倍速菜单项（`span.vjs-menu-item-text`，通常是 `2x / 1.5x / 1.25x / 1x`）。
- **优先点菜单项**，那是官方动作；菜单点不动才退回 `video.playbackRate = value`，并在节点记录里注明"属性写入"而不是"菜单选择"。
- 默认取**平台允许的最高档**；`rate = 1` 可配置回保守模式（有些课倍速会判定异常）。
- 锁速课程的 `playbackRate` 恒为 1 且菜单隐藏，接受平台限制，不要用会写死 2x 的旧保活脚本；菜单里没有 2x/1.5x/1.25x 时记 `rate_source=locked`，不要去写属性再被改回来。
- 观察器的**总等待预算**按实际速率缩放：`总预算 ≈ 视频剩余秒数 / rate`；但**单次调用仍只跑 175 秒**并带 `timeout` 返回，避免长循环挂死唯一一次调用。

## 平台红线（从 ZCode 实战迁移，详见 [现场笔记](references/field-notes.md)）

- **导航节奏**：跳页间隔 ≥ 4 秒、每轮 ≤ 10 次跳页；永远从目录点进去，不拼 `studentstudy` / `cards` 直链。学习通曾因"拼直链 + 90 秒 27 次跳页"触发 9010 风控验证码。
- **每日上限**：`.maskDiv.jobCountDiv` 常驻 DOM 且 `display:block`，只有 `getBoundingClientRect()` 宽高大于 0 才算触发；触发即停当日视频任务，不重试。
- **任务点只看平台标记**：侧栏行尾数字、`icon_Completed`、结果页「已完成」。`video.ended`、提交动作都不算。
- **弹题不产生任务点**：答对答错都不改变任务点计数，别把弹题当成没完成的那个点。
- **测验 0 分可能不点亮任务点**：是否点亮看平台标记，不看提交成功。
- **提交三件事**：等答题帧 `.TiMu` 渲染完再作答（帧 URL 先到、内容后到）；确认框 `#workpop a.jb_btn` 的可见副本在 studentstudy 帧；多选隐藏值存 `ABC`（无逗号），不要按 `A,B,C` 比对。
- **提交后明文可读**：结果页会显示「我的答案 / 得分」，字体混淆只在待作答态；用它补题库、做复盘。
  「正确答案」是否出现由教师决定，实测两门课都没开，所以题库按 `correct: null` 记，不猜（见 [题库与复习文档](references/bank.md)）。
- **控件有两代**：旧播放器弹题要点 `input[type=radio]`（点 `li` 无效，会提交空答案）；v24 测验页要点 `li[qid]`。进页面先探骨架，别套用上一页的经验。
- 未满分的章节测验最多重做 1 次（`private.toml` 的 `redo_once`），重走完整流程，直到点亮或余量用尽。

## 全程保留的边界

- 同一账号一次只由一个执行器操作，单标签推进；换执行器前保存断点并确认前一个已停。
- 多账号：一个账号一条通道、一个 profile、一个标签；跨账号并发、停手条件和未验证范围见 [多账号运行](references/multi-account.md)。任一账号验证码/9010/多终端提醒 → 两个都停。
- 课件完成要有平台保存的完成标记；视频到尾、旧状态或本地高分都不是完成证明。
- 网课测验按本次已有作答/提交授权执行；只看题或只给参考答案不自动扩展成开始计时、填答或提交。
- 计时测验已经开始时优先完成或保存该次事务；结果不明先查平台记录，不重开尝试、不重复提交。
- 验证码、安全验证、付费或权限限制按平台与当前工具规则处理，需要用户接手时保留现场。
- 本机保留状态、材料与日志；密码不回显，登录态和私人运行数据不进入公开导出。
- 本技能只做网课；作业取题与 PDF 交付不在这里，用 `course-homework`。

## 可复用工具

先运行 `python scripts/doctor.py` 确认实际解释器、可选依赖和资源。工具不是授权来源。

- [字幕取证](scripts/subtitle_evidence.py)：`fetch/find/gate/slice`；多个 `--query` 是 **AND**（同一 cue 必须同时含全部词）。
- [截图 OCR](scripts/quiz_ocr.py)：整页识别；[题区过滤](scripts/quiz_panel.py)：按 x 范围把题区从整页里摘出来。
- [裁剪重识别](scripts/crop_ocr.py)：题干漏识时按 OCR 行锚点裁剪并放大重识别；`--auto` 按题号自动定锚点。
- [读取兜底](scripts/ocr_guard.py)：题干过短、为空或括号未闭合时自动判定并触发重识别，`--dry-run` 只看判定。
- [作答预检](scripts/option_coverage.py)：多选提交前核对每个选项的独特词是否在原文出现；枚举题找同一 cue 的并列项，缺原文只作警告。
- [目录状态](scripts/toc_status.py)：从一次目录快照读出每节的未完成任务点数，`--fail-if-unfinished` 可当验收闸门。
- [会话成本](scripts/session_cost.py)：读本次会话日志，分开报告输入 / 缓存读 / 输出与每次工具调用的体积，用来核对"每节点 ≤1.5M token"这条线；`--audit-submit` 扫描工具调用里的测验提交选择器。
- [证据检查](scripts/check_evidence.py)：按 `state.md` 的 evidence 结构核对一次节点记录；证据模式默认要求 `submitted=false`，`--require-readonly` 再加"0 选项点击 / 0 提交点击"。
- [题库归一化](scripts/quiz_bank.py)：把结果页 capture 校验、合并成 `knowledge/<course>/bank.json` + `bank.md`；`check` 单节自检，`build` 带 `--expected` 报覆盖率缺口。
- [题库计划](scripts/bank_plan.py)：从 run ledger 取「应该有测验的节号」，从 evidence 补 `work_id`/分数，产出 `expected-*.json` 与 `plan-*.json`。
- [节点驱动生成](scripts/bank_node_js.py)：把 `references/bank.md` 里的取数驱动实体化成每节一个 JS，交浏览器 `filename` 直载，免去每节点粘贴 4 KB 脚本。
- [字幕抓取](scripts/bank_subs.py)：按 capture 里记下的字幕地址批量下载 SRT，供知识总结使用。
- [无字幕转写](scripts/asr_mimo.py)：无字幕视频用 MiMo ASR 转写（签名直链 mp4 + ffmpeg + 90 秒分块），
  可在播放的同时并行转写；受 `local/private.toml` 的 `[asr] enabled` 开关控制，关掉就回退旧流程。
- [知识总结拼装](scripts/knowledge_doc.py)：校验每节 note（要点条数/时间戳/不许抄题/不许事务占位），按章拼成 `knowledge.md`；`build` 缺节会点名。
- [列表采集](scripts/collect_task_list.js) 与 [巡检对比](scripts/inspect_tasks.py)：只读当前已加载列表；`summary`/`diff`。
- [Harness 探针](scripts/dsh_probe.py)：`--tools` 读当前工具清单，报告技能发现根、安装副本漂移和浏览器候选；`--require-discovered` 扫不到安装副本时 exit 5，`--require-winner <target>` 发现的是别的安装时 exit 6；只读文件系统，不联网、不打开页面。
- [打包](scripts/package_skill.py)：`export` 生成公开副本，`install` 生成安装副本；都拒绝覆盖已存在的目录。

题面与列表的采集函数不自动执行，调用契约见 [工具数据格式](references/tool-data.md)；用新批次隔离题面和字体。

## 验收与回退

交付前分别说明：平台已确认什么、文件工具验证了什么、尚有哪些内容待人工或实战核对。
节点记录先过 `scripts/check_evidence.py`；安装副本与源码是否一致用 `scripts/dsh_probe.py` 核对；缺少受支持浏览器通道时写明缺口和需要启用的能力，不宣称实战通过。
需要换回旧路径时按 [回退说明](references/rollback.md) 保留现场交接，不复制覆盖对方的 `local/` 状态。
