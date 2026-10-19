# course-study-dsh

给 **DeepSeek Harness** 用的网课减负技能：把视频看完、把弹题答对、把章节测验的证据摆出来。

不刷倍数、不伪造心跳、不碰上报接口。倍速优先用平台播放器菜单里给的那几档；属性写入只作退路，且必须读回。

## 它做什么

- 打开学习通课程目录，按平台允许的最高倍速静音播放，直到视频结束。
- 弹题：读字幕原文，用带时间轴的引文作答；找不到原文就标低置信，不硬猜。
- 章节测验：frame body 截图 → 本地 OCR（窄页面直接打印全部行，不套固定 x 区间）→ 按 `li[qid]` 的 DOM 顺序和 `span[data]` 选答，提交前核对隐藏值；多选题再做「选项—字幕覆盖」预检。
- 每节结束回目录核对完成标记，记录到本次 `runs/` 目录。

## 它不做什么

- 不用代码强行改出菜单没有的倍率：菜单能点才点；退路写 `playbackRate` 时读回校验，读回不一致就记 `rejected`，按平台实际速率播。
- 不提交任何没有授权的测验；公开版默认**不自动提交**章节测验。
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
| 中国大学MOOC | **未实战验证**，只有流程文档 |

## 单节点成本与预算

<运行日期>，两次用子 agent 独占浏览器、单标签跑完整节（视频 + 弹题 + 章节测验），分别量三件事：

| 节点 | 视频 | 调用 | 会话 token | 任务点 |
|---|---|---|---|---|
| 地球历史 1.4.1 | 389.6 s @1x | 8 | 0.49M | 2 → 0 |
| 地球历史 1.3.3 | 454.6 s @1x | 10 | 0.53M | 2 → 0 |

- 调用数取子 agent 会话里的 `tool/call` 事件；token 取同一会话的 total（`scripts/session_cost.py`）；任务点用新加载的目录快照跑 `scripts/toc_status.py` 前后对比（不是看视频 `ended`）。
- 1.4.1 是修好配方后的数字；1.3.3 多出的 2 次来自两个工具缺陷（判断题 token 校验、OCR 控制台编码/面板过滤），已修并复测。
- 预算公式（1x 锁速课）：`4 + ceil(视频秒数 / 175)`。4 = 进节点并起播 + OCR + 提交并回目录 + 写证据；观察器每 175 秒一次、带 timeout 返回，下一回合续。2x 可用的课观察次数减半。
- **这两个数字只覆盖这一门锁 1x 的课，不外推到所有课程。**

```powershell
# token：子 agent 自己的会话文件（调用数 = 其中的 tool/call 事件数）
python scripts/session_cost.py "<...>/<subagent-id>/session.v4.jsonl.zstd"

# 任务点：进节点前、完成后再各拍一次目录快照
python scripts/toc_status.py runs/<task>/toc-before.yml --prefix 1.4
python scripts/toc_status.py runs/<task>/toc-after.yml --prefix 1.4
```

## 安装

需要 Python 3.10+。把仓库放到 DSH 的技能根，或直接跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

默认装到 `%USERPROFILE%\.agents\skills\course-study-dsh`（DSH 的 rank 500 根）。
装完在 DSH 里跑 `python scripts/dsh_probe.py`，确认 `winner` 指向该目录、`drift` 为空。

浏览器通道要自己配：DSH 的 profile 里有一条 `mcp-browser`（Playwright MCP，独立 profile）。本项目的所有页面操作都走它。配置样例与限制见 [references/dsh-runtime.md](references/dsh-runtime.md) 的「启用受支持的浏览器通道」。

## 用法

装好后在 DSH 里把平台、课程、章节和授权说清楚，例如：

> 学习通「地球历史及其生命的奥秘」1.3.4，视频看完就好；章节测验先给我看证据，不要提交。

- 没给提交授权时，技能停在「读完题、摆出证据」这一步；`local/private.toml` 里 `submit = true` 才会提交，且只提交一次。
- 想量单个节点的成本，按「单节点成本」里的命令：子 agent 会话 → `session_cost.py`，目录快照 → `toc_status.py`。
- 没有字幕的课会标 `low_confidence`，不会假装有原文。

## 配置

`local/private.toml`（不进仓库；从仓库里的 `private.toml.example` 复制一份再改）：

```toml
[playback]
rate = 0        # 0 = 平台允许的最高档；填 1 强制保守

[quiz]
submit = false  # 公开默认；私有环境可改 true
redo_once = false
```

## 风险

1. **账号风险**：任何自动化播放都可能被平台判定异常。本项目不伪造心跳，但不保证不被风控。
2. **公开版仍可提交**：`submit` 开关写在代码里，默认关；打开后责任在使用者。
3. **实证范围有限**：一个账号、三门课（人工智能与创业智慧 84/84；示例课程10 1.1/1.2；地球历史 4 个小节）；MOOC 未验证。

## 许可证

MIT，见 [LICENSE](LICENSE)；来源与第三方声明见 [NOTICE](NOTICE)。
