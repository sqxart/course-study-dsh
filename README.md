# course-study-dsh

给 **DeepSeek Harness** 用的网课减负技能：把视频看完、把弹题答对、把章节测验的证据摆出来。

不刷倍数、不伪造心跳、不碰上报接口。倍速优先用平台播放器菜单里给的那几档；属性写入只作退路，且必须读回。

## 装上之后：能直接用吗？

**主链路不需要任何 API key。** 但有几项能力是「作者本机刚好有、别人不一定有」的，缺了不会崩，只会降级——
先看这张表，能省掉大半「为什么我这里不对」：

| 能力 | 需要什么 | 缺了会怎样 | 是否必需 |
|---|---|---|---|
| 打开课程、看视频、答弹题、交测验 | DeepSeek Harness + 一条 `mcp-browser*` 通道 + 你自己的学习通登录态 | 什么都做不了 | **必需** |
| 取题库、写复习卡、拼文档 | Python 3.10+（标准库即可） | 跑不了脚本 | **必需** |
| 截图 OCR 读题（`quiz_ocr.py`） | `pip install -r requirements-ocr.txt`（Pillow / fonttools / rapidocr / onnxruntime） | 改用模型读保存下来的截图，或走 DOM 明文 | 可选 |
| 无字幕转写（`asr_mimo.py`） | `ffmpeg` + `ffprobe` + 一个 ASR 服务 key + `[asr] enabled = true` | 无字幕课退回「学科判断 + low_confidence」，复习卡跳过该节 | 可选，**默认关闭** |
| 外部题库比对（`bank_crosscheck.py`） | `pip install pymupdf` | 跳过比对，题库只用平台原文 | 可选 |
| 会话成本报告（`session_cost.py`） | `pip install -r requirements.txt`（zstandard） | 只是没有成本报表 | 可选 |
| 测试（`pytest tests`） | Node.js（`node --check` 校验文档里的 JS 片段） | 相关用例 skip，其余照跑 | 可选 |

装完先自检：

```powershell
python scripts/doctor.py                     # Python/Node/OCR/字体 一次看清
powershell -ExecutionPolicy Bypass -File .\install.ps1   # 装到 ~/.agents/skills/course-study-dsh
```

`install.ps1` 会把 `private.toml.example` 复制成 `local/private.toml`——**公开默认是证据模式、不提交**；
`local/`、`runs/`、`knowledge/` 都在 `.gitignore` 里，不随仓库走。

## 两个开关：自动提交 与 ASR（默认都关，选择权在你）

先说清楚：**这个技能有自动作答并提交章节测验的能力，也有自动转写无字幕视频的能力，但默认全关。**
默认的「证据模式」只读题、只摆证据——不点选项、不点提交、不重做，最安全，代价是你拿不到分。
如果你（账号本人、有权处理这门课的人）需要它真的把测验做掉，请自己打开下面这些开关；我们不会替你开。

| 开关 | 位置 | 打开后会发生什么 | 风险 |
|---|---|---|---|
| `mode = "completion"` | `local/private.toml` | 允许用学科知识推断答案（标 `low_confidence`），不再要求字幕原文 | 推断可能错；错答案进了成绩不可撤回 |
| `[quiz] submit = true` | 同上 | 章节测验会**真的点选项并提交** | 提交消耗作答次数、分数入档；0 分可能不点亮任务点；能否重做由平台决定 |
| `redo_once = true` | 同上 | 未满分时自动重做 1 次（仍受平台剩余次数限制） | 重做是新事务，次数用尽就没有了 |
| `[asr] enabled = true` | 同上 | 无字幕课先转写，再按转写原文答题 / 写复习卡 | 需要 key + ffmpeg，按音频时长计费（见下一节） |

打开方式（按需删掉注释、只改你确实需要的行）：

```toml
mode = "completion"        # 允许推断；只读用户保持默认 "evidence"

[quiz]
submit = true              # 真的提交；没有授权就别开
redo_once = false          # 未满分自动重做一次；确认平台还有次数再开

[asr]
enabled = true             # 无字幕课转写
```

**打开之前请自己权衡**（这些是真实后果，不是免责套话）：

- 自动提交 = 把「作答 + 提交」交给模型。答错就进档案，**多数课程不能撤销**；有的课提交后才给正确答案，有的连答案都不给。
- 部分课程提交后学习记录里会出现作答痕迹（`#workAnswerId`、「已查看」）；只读模式也会留下「已查看」，但不会有分数。
- 自动答题依赖字幕/转写质量：没有原文时模型会猜，猜错的分收不回来。想要稳妥就只开视频、不开测验。
- 平台若对自动化行为有判定，后果由使用者承担；请只在自己的账号、自己有权处理的课程上使用。
- 本技能不绕过验证码、付费墙、权限限制，也不改上报字段——这些边界不会因为打开开关而放宽。

怎么确认现在是什么模式：`python scripts/doctor.py` 或看 `local/private.toml` 的 `mode` / `submit`，安装器装完也会打印一行。
想只做一部分，就按 [四种功能](references/modes.md) 挑：只视频、只测验、只题库、只知识总结都支持。

## ASR（无字幕转写）：默认关闭，按需开启

只有「这节课没有字幕、你又想按老师原话答题/写复习卡」时才需要它。三个条件缺一不可：
`ffmpeg` 在 PATH、有 ASR 服务的 key、`local/private.toml` 里 `[asr] enabled = true`。

**它替你做什么**：进节点时读播放器里的字幕清单；没有字幕就取签名直链 mp4，切 90 秒分块转写，
把文本存到 `runs/<task>/asr/<节>.txt`，再把这段原文用于弹题作答和复习卡；有字幕的课直接存 SRT，不花这笔钱。
不想用、没配 key、或者中途关掉 `enabled`，都会**自动退回**「不转写」的老流程，不会卡住主链路。

默认走 MiMo（`mimo-v2.5-asr`，OpenAI 兼容的 `input_audio` 负载）；作者实测 30 分钟视频约 <时长>秒转完、约 0.5 元/小时音频。
**邀请活动目前仍有效**（2026-10 核实）：

> 我在用 MiMo 开放平台，体验小米顶尖模型 MiMo V2.6 等。通过我的邀请码注册：双方各得 ¥10 API 体验金 + 首单 9 折。
> 邀请码：**KQDN7K**。注册：<https://platform.xiaomimimo.com?ref=KQDN7K>（注册后自动填入 · 体验金 40 天有效）

（邀请码是作者的分成链接；不想用可以直接搜官网自己注册，脚本不绑定任何邀请关系，拿别家的 key 一样能跑。）

> 我在用 MiMo 开放平台，体验小米顶尖模型 MiMo V2.6 等。通过我的邀请码注册：双方各得 ¥10 API 体验金 + 首单 9 折。
> 邀请码：**KQDN7K**。注册：<https://platform.xiaomimimo.com?ref=KQDN7K>（注册后自动填入 · 体验金 40 天有效）

（邀请码是作者的分成链接；不想用可以直接搜官网自己注册，脚本不绑定任何邀请关系。）

**不锁定这家**：脚本接受任何同形态的 OpenAI 兼容端点，换服务只是几个参数的事——

```powershell
python scripts/asr_mimo.py --source "<签名 mp4>" --out runs/asr/2.1.txt `
  --endpoint https://api.groq.com/openai/v1/chat/completions `
  --model whisper-large-v3-turbo --auth-style bearer --provider-key-env GROQ_API_KEY
```

不想联网就在本地转写（faster-whisper / whisper.cpp），结果丢进 `runs/<task>/asr/<节>.txt`，技能照样认。
常见免费路线、成本、排错表与本地做法见 [ASR 说明](references/asr.md)。

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

**把视频字幕当成证据源。** 弹题和测验答案要能在字幕里找到原文和时间轴，找不到就标低置信；不靠视觉模型硬猜、不"先交了再看答案重做"。没有字幕的课不假装有：无字幕课的多选题无从查原文，就标 `low_confidence` 并接受丢了 25 分。
事后的题库与复习文档也只吃平台原文：题面与「我的答案」来自提交后的结果页，**平台不给正确答案就留空**，不用学科知识补。

## 功能与验证范围

公开文档保留能力、方法和限制；逐账号、逐节点的原始运行记录留在本地 `runs/`。

| 项 | 行为与限制 |
|---|---|
| 节点执行 | 视频、弹题、章节测验与纯测验节点按授权模式处理，完成以平台任务点为准 |
| 题库 | 从已提交结果页提取题面、选项、我的答案与得分；正解只取平台开放内容或满足条件的满分反推 |
| 知识总结 | 有字幕用字幕，无字幕按 ASR 开关转写，富文本和文档页图使用对应取数通道 |
| 多账号 | 独立通道、profile、标签和执行器；仅有限范围有界验证，长视频/测验/提交并发未充分验证 |

- 只读打开测验可能留下「已查看」；限次=1 的课未单独验证，打开前读规则，不重开。
- 多视频节点按总时长要求播放所有视频；锁速课接受 1x，速率菜单优先并读回确认。
- 平台未公布弹题正解时记 `revealed_correct: null`，不猜。
- 无字幕且 ASR 关闭时，证据模式不能提交缺乏原文支撑的测验答案。

## 单节点成本与预算

每节点独立子 agent、单标签，分别量调用数、token 和平台任务点，避免跨节点上下文累积。

- 调用数取会话 `tool/call`，token 用 `scripts/session_cost.py`；任务点用新加载目录快照跑 `scripts/toc_status.py`。
- 1x 锁速课预算公式：`4 + ceil(视频秒数 / 175)`；4 是进节点起播、OCR、提交回目录和写证据。观察器每 175 秒返回，timeout 下一回合续；可用 2x 时观察次数相应减少。
- 热启动浏览器调用目标 8–10 次；冷启动总调用目标 ≤20、会话 token 目标 ≤1.5M。这是预算，实际成本按本次运行核对。
- 一个子 agent 只跑一个节点（或最多 2 个），减少重复探索；[快速配方](references/quickstart.md) 提供可粘贴代码。
- 公开默认 `mode=evidence`；无字幕测验停在证据页。`--audit-submit` 的 clean 是证据模式要求，completion 提交后报 review 需按实际模式解释。

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

## 从 GitHub 安装（把你的链接 + 下面这段一起发给 DSH）

这个技能不是"点一下自动装"的插件：DSH 的技能发现是读 `<agentsHome>/skills/<name>/SKILL.md`，
所以安装动作是 **clone → 跑安装脚本 → 重载会话**。把仓库链接和下面这段一起发给你 DSH 里的 agent 即可：

```text
帮我装一个 DeepSeek Harness 技能，仓库：<在这里粘贴 GitHub 链接>

按顺序做，每步报告结果：
0. 先自查，再动手：我的工具清单里有没有 mcp__browser__* / mcp__browser2__* / mcp__browser3__* 这类浏览器通道？
   没有就先别装，先告诉我怎么加一条 Playwright 的 mcp-client —— 这是能不能真跑课的前提，装完没通道只能离线用。
1. git clone 到临时目录（如 %TEMP%\course-study-dsh），cd 进去；
2. 确认 python >= 3.10；
3. 运行 powershell -ExecutionPolicy Bypass -File .\install.ps1
   （默认装到 %USERPROFILE%\.agents\skills\course-study-dsh）；
4. 运行 pip install -r requirements.txt；
5. 在仓库根目录验证，期望 exit 0 且 copies: 1、source_is_installed_copy: false、manifest_drift_files: 0：
   python .\scripts\dsh_probe.py --agents-home %USERPROFILE%\.agents --require-discovered --require-winner %USERPROFILE%\.agents\skills\course-study-dsh
6. 重启/重载 DSH 会话，让技能目录刷新；
7. 汇报：装到哪、探针三个数字、通道结论（有/没有），以及我下一步该怎么配。

装好后我打算用它跑学习通课程。默认是证据模式、不提交测验；需要提交时我会另外明确授权。
```

两点前提，装之前值得先确认：

- **需要一个浏览器通道**（Playwright MCP 的 `mcp-client` 行，工具前缀 `mcp__browser__*` 之类）。
  没有通道时本技能**只做离线工作**（读文档、跑脚本、做证据校验），不会去连页面——这是设计上的边界，不是 bug。
  通道怎么配见 [DSH 运行说明](references/dsh-runtime.md) 的「启用受支持的浏览器通道」。
- **安装脚本是 PowerShell**（Windows）。仓库里没有 macOS/Linux 的安装器；其他平台只能手工把
  `SKILL.md`、`references/`、`scripts/`、`tests/` 复制到 `<agentsHome>/skills/course-study-dsh/`。

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

> 学习通「某门课」某节，视频看完就好；章节测验先给我看证据，不要提交。

- 没给提交授权时，技能停在「读完题、摆出证据」这一步；`submit = true` 且 `mode = "completion"` 才会提交推断答案，且只提交一次。
- 证据模式下章节测验**只读**：打开答题页、截图/OCR、逐题写证据，不点选项、不点提交、不重开。打开答题页会生成 `#workAnswerId`，它不等于提交；已观察到 `addTimes` 仍为 0、没有消耗提交次数的情形，但会在平台留下“已查看”。
- 想量单个节点的成本，按「单节点成本」里的命令：子 agent 会话 → `session_cost.py`，目录快照 → `toc_status.py`。
- 没有字幕的课会标 `low_confidence`，不会假装有原文。
- 多账号各用独立 profile 的通道、单标签、单执行器；授权、停止和恢复规则见 [多账号运行](references/multi-account.md)。
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
3. **实证范围有限**：已覆盖视频、测验、题库与知识总结的部分场景；限次=1、付费/权限受限内容、其他平台以及长视频/测验/提交并发未充分验证。逐账号、逐节点记录留在本地 `runs/`。
4. **证据模式仍会打开答题页**：会生成 `#workAnswerId`，平台“学习记录 → 章节测验”里会标成**已查看**（没有分数、不是已完成）。
   实测 `#addTimes` 仍为 0、没有提交请求、任务点不变，因此打开本身没有消耗提交次数；但“已查看”是可见痕迹，
   不想留痕就在指令里明确“不要打开测验”。限次=1 的课未单独验证。

## 许可证

MIT，见 [LICENSE](LICENSE)；来源与第三方声明见 [NOTICE](NOTICE)。
