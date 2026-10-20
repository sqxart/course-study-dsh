# course-study-dsh

给 **DeepSeek Harness** 用的网课减负技能：把视频看完、把弹题答对、把章节测验的证据摆出来。

不刷倍数、不伪造心跳、不碰上报接口。倍速优先用平台播放器菜单里给的那几档；属性写入只作退路，且必须读回。

## 它做什么

- 打开学习通课程目录，按平台允许的最高倍速静音播放，直到视频结束。
- 弹题：读字幕原文，用带时间轴的引文作答；找不到原文就标低置信，不硬猜。
- 章节测验：frame body 截图 → 本地 OCR（窄页面直接打印全部行，不套固定 x 区间）→ 按 `li[qid]` 的 DOM 顺序和 `span[data]` 选答；有提交授权时才在提交前核对隐藏值，多选题再做「选项—字幕覆盖」预检。
- 每节结束回目录核对完成标记，记录到本次 `runs/` 目录。

## 它不做什么

- 不用代码强行改出菜单没有的倍率：菜单能点才点；退路写 `playbackRate` 时读回校验，读回不一致就记 `rejected`，按平台实际速率播。
- 不提交任何没有授权的测验；公开版默认**证据模式 + 不提交**——找不到原文就停在证据页。
- 不做作业代写、不做 PDF 交付（那是 `course-homework` 的事）。
- 不绕过验证码、付费墙或权限限制。

## 与其他项目的区别

网课自动化不缺实现：[OCSJS](https://github.com/ocsjs/ocsjs)（3.8k★）覆盖四平台、自带题库；`Samueli924/chaoxing`（3.6k★）走接口直报。这个项目只做一件它们没做的事：

**把视频字幕当成证据源。** 弹题和测验答案要能在字幕里找到原文和时间轴，找不到就标低置信；不做题库、不靠视觉模型硬猜、不"先交了再看答案重做"。没有字幕的课不假装有：地球历史 1.3.3 的多选题无从查原文，就标 `low_confidence` 并接受丢了 25 分。

## 功能与验证范围

| 项 | 行为与限制 |
|---|---|
| 学习通 · 人工智能与创业智慧 | 84/84 任务点，26 个节点，24 个满分 |
| 5.5 多选题 | 83.3（少选，部分给分） |
| 12.4 「三创」题 | 0 分（答案不在字幕里，已提交不可改） |
| 学习通 · 示例课程10 1.1 | 381 s 视频，2x 静音 187 s 看完，平台正常计入 |
| 学习通 · 地球历史 1.3.3 | 454.6 s 视频（锁 1x）+ 1 道弹题 + 测验 75 分；任务点 2→0 |
| 学习通 · 地球历史 1.4.1 | 389.6 s 视频（锁 1x）+ 1 道弹题 + 测验 100 分；任务点 2→0 |
| 学习通 · 地球历史 1.2.1（预跑） | 498.3 s 视频（锁 1x）+ 1 道弹题；**证据模式只读测验、未提交**；任务点 2→1 |
| 学习通 · 地球历史 1.2.2（复测） | 409.0 s 视频（锁 1x）+ 1 道弹题；证据模式只读、未提交；任务点 2→1；19 次 / 0.80M token |
| 学习通 · 示例课程10 1.3（A）+ 1.1（B）并发 | 234.6 s + 381.2 s @2x；两段播放重叠 124.6 s；任务点都 1→0；A 13 次 / 0.53M，B 18 次 / 0.74M |
| 学习通 · 丝绸之路上的民族（10 节，A） | 10 节视频（合计 6985.7 s @1x）+ 10 次弹题 + 10 次章节测验；9 节 100 分、3.4 50 分；任务点都 2→0；7 节有 SRT |
| 学习通 · 丝绸之路 4.3（A）+ 无人驾驶车辆 1.1（C）并发 | 834.1 s @1x + 503.5 s @2x；真实重叠 251.9 s；A 任务点 2→1，C 1→1（2x 视频 ended 但未清）；A 24 次 / 1.08M，C 25 次 / 1.28M；无验证码/多终端 |

- 1.2.1/1.2.2 的只读测验在平台“学习记录 → 章节测验详情”里显示 **已查看**、无分数、不是“已完成”。
- <运行日期> 用 1.2.3 做只读实测：打开答题页后 `#addTimes=0`、`#limitWorkSubmitTimes=100`，没有提交/start 请求，任务点仍 2；**打开本身没有消耗提交次数**（至少这门课/这个字段语义）。仍会留下“已查看”痕迹；限次=1 的课未单独验证。
- 账号 B（独立 profile，browser2）：完成课「示例课程13」1.1 只读打开，SRT 230 条、`gate` supported；倍速菜单在 DOM 里但不可见，属性写 2 读回 2 后还原 1x/暂停/静音。没有打开测验，没有进度变化。
- <运行日期> 两账号有界并发：A「示例课程10」1.3 + B「示例课程10」1.1，2x 菜单、播放重叠 **124.6 s**、都 `ended`、任务点都 1→0；A 13 次 / 0.53M token，B 18 次 / 0.74M，`--audit-submit` 都 clean；无验证码、无多终端提醒。长视频、测验/提交并发未验证。
- <运行日期> A+C 三通道有界并发（只做视频、不提交）：A「丝绸之路」4.3（834.1 s @1x）+ C「无人驾驶车辆」1.1（503.5 s @2x），**真实重叠 251.9 s**；A 任务点 2→1，C 视频 `ended` 但 1.1 行尾仍 1（2x 是否计入未判定，也可能是该 1 分本就是测验）；A 24 次 / 1.08M token，C 25 次 / 1.28M；两边 `--audit-submit` clean、日上限 0×0、无验证码/多终端。C 的 2x 归因待 1x 复测。
- <运行日期>「欧洲文明概论」1.1（B，视频已完成、只差章节自测）只读打开：5 题，`#addTimes=0`、`#limitWorkSubmitTimes=100`，0 选择 / 0 保存 / 0 提交，任务点仍 1。限次=1 的课仍未遇到。
- <运行日期>「丝绸之路上的民族」连续 10 节（A，completion）：视频合计 6985.7 s @1x、弹题 10 次、章节测验 10 次各提交一次；**9 节 100 分、3.4 50 分**，10 节任务点都 2→0。1.1/1.2/3.2/3.3/3.4/4.1/4.2 有 SRT（143–272 条），2.1/2.2/3.1 的 `allsubtitle` 返回 `[]`，只能按学科知识作答并标 `low_confidence`。
- 3.4 的 50 分是**真实局限**：Q1 多选「亚历山大帝国把()全部连接起来」的引文同时提到地中海/印度河/咸海/波斯湾，gate 判全 supported，但题库答案是这四个区域的真子集，ABCD 全选判 0。已提交一次、未重做（`redo_once=false`）。gate 只证明词在原文，不证明集合；「全部连接/全部包括」类题不要全选。

## 单节点成本与预算

<运行日期>，两次用子 agent 独占浏览器、单标签跑完整节（视频 + 弹题 + 章节测验），分别量三件事：

| 节点 | 视频 | 调用 | 会话 token | 任务点 |
|---|---|---|---|---|
| 地球历史 1.4.1 | 389.6 s @1x | 8 | 0.49M | 2 → 0 |
| 地球历史 1.3.3 | 454.6 s @1x | 10 | 0.53M | 2 → 0 |

- 调用数取子 agent 会话里的 `tool/call` 事件；token 取同一会话的 total（`scripts/session_cost.py`）；任务点用新加载的目录快照跑 `scripts/toc_status.py` 前后对比（不是看视频 `ended`）。
- 1.4.1 是修好配方后的数字；1.3.3 多出的 2 次来自两个工具缺陷（判断题 token 校验、OCR 控制台编码/面板过滤），已修并复测。
- 预算公式（1x 锁速课）：`4 + ceil(视频秒数 / 175)`。4 = 进节点并起播 + OCR + 提交并回目录 + 写证据；观察器每 175 秒一次、带 timeout 返回，下一回合续。2x 可用的课观察次数减半。
- 两节都在本地 `mode=completion` 下跑；公开默认 `mode=evidence` 遇到无字幕的测验会停在证据页，不会提交 1.3.3 那种推断答案。
- **这两个数字只覆盖这一门锁 1x 的课，不外推到所有课程。**
- **不要把多个节点塞进同一个子 agent**：<运行日期> 丝绸之路 10 节用「3 节点一批」跑了三批，分别是 75 次 / 6.47M、82 次 / 5.18M、81 次 / 5.21M，折合约 **1.73–2.16M token/节点**，超过 1.5M 预算；而单节点新会话是 1.4.1 = 0.49M、1.2.2 = 0.80M。原因是上下文跨节点累积。一个子 agent 只跑一个节点（或最多 2 个）。

<运行日期> 又跑了一次**证据模式预跑**（地球历史 1.2.1，冷启动子 agent，测验只读不提交）：498.3 s 视频，**37 次调用 / 2.29M token / 任务点 2→1**。
37 次不是流程必需：其中 21 次浏览器调用，约 16 次花在目录帧试探、弹题按钮试错、回目录重进和冷启动读文档上。
这些已固化成 [单节点快速配方](references/quickstart.md)（含可粘贴代码）。同一天用 1.2.2 复测（409.0 s，仍然冷启动、证据模式、只读不提交）：
**19 次调用 / 0.80M token / 浏览器 7 次 / 任务点 2→1**——比 1.2.1 少 18 次调用、少 1.49M token，浏览器调用在 8–10 目标内。
`scripts/check_evidence.py` 与 `session_cost.py --audit-submit` 是这次预跑补的可测量闸门。
`--audit-submit` 的 `clean` 是**证据模式**的要求：completion 模式本来就会点 `.btnSubmit`，报 `review` 是正常的；证据模式报 suspect 才需要先查清。

```powershell
# token：子 agent 自己的会话文件（调用数 = 其中的 tool/call 事件数）
# 子 agent id 就是 %USERPROFILE%\.dsh\sessions\<workspace-key>\<id>\ 的目录名
python scripts/session_cost.py "<...>/<subagent-id>/session.v4.jsonl.zstd" --audit-submit

# 证据：证据模式下应为 OK，且 submitted=false、0 次点击/提交
python scripts/check_evidence.py runs/<task>/evidence.json --require-readonly

# 任务点：进节点前、完成后再各拍一次目录快照
python scripts/toc_status.py runs/<task>/toc-before.yml --prefix 1.4
python scripts/toc_status.py runs/<task>/toc-after.yml --prefix 1.4
```

## 安装

需要 Python 3.10+（本机实测 3.14.7）和 Node/npx（浏览器通道用）。装到 DSH 能发现的位置：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
# 已有安装就地升级（保留 local/ 配置）：
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
```

默认装到 `%USERPROFILE%\.agents\skills\course-study-dsh`；设了 `DSH_AGENTS_HOME` 就装到 `$env:DSH_AGENTS_HOME\skills\course-study-dsh`。
装完**重启或重载 DSH 会话**，技能目录才会刷新；探针本身不需要重载。

只想验证打包、或装到别的目录（DSH 不会自动发现，除非把它加进发现根）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target C:\path\to\course-study-dsh
```

`-Target` 的最后一级目录名必须正好是 `course-study-dsh`；父目录不必预先建；目标必须不存在或为空，`-Force` 就地升级。安装脚本把 `private.toml.example` 种成 `<安装目录>\local\private.toml`（默认 evidence / 不提交），已有 `local/private.toml` 不会被覆盖。输出里的 `uploaded: false` 是固定值：脚本不上传任何文件。

装完在**源码仓库根目录**跑探针（这样 `--source` 默认是仓库，能把安装副本和源码比对）：

```powershell
# <agents home> = %USERPROFILE%\.agents，或你设置的 $env:DSH_AGENTS_HOME
python .\scripts\dsh_probe.py --tools tools.json --agents-home <agents home> --require-discovered --require-winner <target>
```

如果只能用安装副本里的探针（例如只有安装包），它默认 `--source` 就是自己，`manifest_drift_files` 会走“安装副本 vs 安装时记录在 `package-manifest.json` 的哈希”的自检；这能查篡改，但不能证明和源码一致。输出里 `source_is_installed_copy: true` 就是这种自比。

**安装和探针必须在同一个 shell/环境变量下**：`DSH_AGENTS_HOME` 同时决定安装目标和探针的发现根。新 shell 丢了变量时，探针可能找到旧安装或 0 份，exit 仍是 0。要显式指：

- `--agents-home <...\agents>`：agents home，里面是 `skills\course-study-dsh`；
- `--custom-root <...\skills>`：技能根，里面直接是 `course-study-dsh`；
- `--require-discovered`：扫不到任何安装副本时 exit 5；
- `--require-winner <target>`：`winner` 不是这个安装目录时 exit 6（stderr 带 `winner-mismatch`），防止环境变量丢了却找到旧安装；`--require-discovered` 仍是 exit 5（`not-discovered`）。

`--tools` 的相对路径按**当前工作目录**解析；把 `tools.json` 放在当前目录，或写绝对路径。清单就是工具名 JSON 数组，让 Agent 把当前工具列表写成 `["read", "mcp__browser__browser_click", ...]` 即可。单技能不用加 `--name`。

看输出里的这些字段，不要只看 exit 0：

- `tools.verdict`：`candidate`（有浏览器形状的工具，仍未验证）/ `none`（没有）/ `unknown`（没给清单）。没有时 exit 1，`capability.live_course_work` 才是 `blocked`。
- `copies` / `winner`：文件系统发现了几份安装、哪一份 rank 最小。**`candidate` 只证明工具面，不证明你刚装的副本会被加载**；`copies: 0` 说明安装目录不在发现根里——改装到默认根，或用上面的参数指过去再跑（`--require-discovered` 会让这种情况 exit 5）。
- `manifest_drift_files` / `drift`：与 `package-manifest.json` 比对的差异；0 = 没有差异。`source_is_installed_copy: true` 表示比的是“安装副本 vs manifest 哈希”，false 表示比的是“安装 vs 源码”。
- 不带 `--tools`：只证明文件系统发现，`tools.verdict: unknown`、exit 0——不会把“没提供清单”说成“没有浏览器”。

依赖：

```powershell
pip install -r requirements.txt       # zstandard：session_cost.py 读会话日志
pip install -r requirements-ocr.txt   # 可选：本地 OCR 读题；不装也能用截图 + 模型读图
```

浏览器通道**默认没有**：需要 Node/npx，并在 DSH profile 的 `cordis.patch.yml` 加一条 `mcp-browser`（Playwright MCP，独立 profile；多账号再加一条 id 不同、`--user-data-dir` 不同的），重载后登录。配置样例与限制见 [references/dsh-runtime.md](references/dsh-runtime.md) 的「启用受支持的浏览器通道」。没有它只能做离线工作。

另一个机器或另一个人只照 README 验收时，用 [ACCEPTANCE.md](ACCEPTANCE.md) 的 5 步清单（安装 → 探针 → doctor → 一节不提交 → 量成本）。

## 用法

装好后在 DSH 里把平台、课程、章节和授权说清楚，例如：

> 学习通「地球历史及其生命的奥秘」1.3.4，视频看完就好；章节测验先给我看证据，不要提交。

- 没给提交授权时，技能停在「读完题、摆出证据」这一步；`submit = true` 且 `mode = "completion"` 才会提交推断答案，且只提交一次。
- 证据模式下章节测验**只读**：打开答题页、截图/OCR、逐题写证据，不点选项、不点提交、不重开。打开答题页会生成 `#workAnswerId`，它不等于提交；已观察到 `addTimes` 仍为 0、没有消耗提交次数的情形，但会在平台留下“已查看”。
- 想量单个节点的成本，按「单节点成本」里的命令：子 agent 会话 → `session_cost.py`，目录快照 → `toc_status.py`。
- 没有字幕的课会标 `low_confidence`，不会假装有原文。
- 三个账号（B 已退役）：每个账号一条独立 profile 的 `mcp-browser` 系通道，单标签、单执行器；跨账号做过两次有界视频并发（A+B 重叠 124.6 s、A+C 重叠 251.9 s），长视频/测验/提交并发未验证；A+C 里 C 的 2x 视频任务点未清，原因待 1x 复测。规则和停手条件见 [多账号运行](references/multi-account.md)。
- 单节的固定动作（进节点/起播、175 秒观察器、弹题、测验只读、回目录）有可粘贴代码：[references/quickstart.md](references/quickstart.md)。

## 配置

`local/private.toml`（不进仓库；安装脚本会在安装目录生成一份，内容来自 `private.toml.example`）：

```toml
mode = "evidence"   # evidence（默认）| completion（私用）

[playback]
rate = 0            # 0 = 平台允许的最高档；填 1 强制保守

[quiz]
submit = false      # 动作开关：false 时连证据答案也不提交
redo_once = false

[limits]
max_calls_per_node = 30   # 建议预算，不是代码门禁；超限写进 evidence.deviations
```

- `mode = "evidence"`：只允许提交有字幕/原文支撑的答案；`submit=false` 时连有支撑的答案也不提交，停在证据页写 `do-not-submit`。
- `mode = "completion"`：允许按学科知识推断并提交，记录里标 `low_confidence=true`，只建议在本人账号上用。
- 技能开始前读这个文件来决定本次模式；它是流程约定，不是内核强制——绕过它的责任在使用者。
- `max_calls_per_node` 是建议预算，没有代码会因超限而停；超了要写进 `evidence.deviations`，并用 `session_cost.py` 复核。
- 公开包默认 `evidence` + `submit=false`；本机要完成优先，就自己改成 `completion` + `submit=true`。

## 风险

1. **账号风险**：任何自动化播放都可能被平台判定异常。本项目不伪造心跳，但不保证不被风控。
2. **配置不是内核门禁**：`submit` 与 `mode` 由技能开始时读取，没有代码强制；默认关，打开后责任在使用者。
3. **实证范围有限**：三个账号（B 已退役）、七门课（示例账号：人工智能与创业智慧 N/N、示例课程10 1.1–1.3、地球历史 6 个小节、丝绸之路上的民族 10 节；示例账号：示例课程13 1.1 只读取字幕和倍速，欧洲文明概论 1.1 只读测验；示例账号：无人驾驶车辆 1.1 只做视频，2x 任务点未清）。地球历史 1.2.1/1.2.2 只跑到证据模式、未提交测验。
4. **证据模式仍会打开答题页**：会生成 `#workAnswerId`，平台“学习记录 → 章节测验”里会标成**已查看**（没有分数、不是已完成）。1.2.3 实测 `#addTimes` 仍为 0、没有提交请求、任务点不变，因此打开本身没有消耗提交次数；但“已查看”是可见痕迹，不想留痕就在指令里明确“不要打开测验”。限次=1 的课未单独验证。

## 许可证

MIT，见 [LICENSE](LICENSE)；来源与第三方声明见 [NOTICE](NOTICE)。
