---
name: course-study-dsh
description: DeepSeek Harness 专用的网课减负技能。静音、按平台官方菜单允许的速率把学习通/中国大学MOOC 的视频看完，用字幕原话回答弹题，章节测验先取证再按授权提交；证据不足就拒答。只在当前 harness 的 mcp-browser 通道下操作页面。
---

# 课程助手（DeepSeek Harness 版）

给 DeepSeek Harness 用的网课减负技能：**把视频看完、把弹题答对、把章节测验的证据摆出来**。不刷倍数、不伪造心跳、不碰上报接口。
Harness 的通道事实、已实测范围与调用预算在 [DSH 运行说明](references/dsh-runtime.md)；只读需要的部分，不要一次加载全部材料。

## 开始

1. 确认当前工具面：`mcp__browser__browser_*`、`pwsh`、`read/edit`。缺少受支持的浏览器通道时只做离线工作，不去找隐藏调试接口或自建 CDP 脚本。
2. 确定平台、课程、账号别名、任务类型与已有授权。续跑先读 `local/CURRENT_HANDOFF.md` 与 `local/active-session.json`，再核验平台实际状态。
3. 按任务只读所需材料：

   | 任务 | 流程 | 平台知识 |
   |---|---|---|
   | 看课、续跑、弹题、章节测验 | [网课流程](references/course-flow.md) | [学习通](references/chaoxing.md) / [中国大学MOOC](references/icourse163.md) |
   | 有无新课件/测验、截止时间 | 网课流程的列表巡检 | 先停在列表；开始测验是后续独立动作 |

4. 使用独立任务目录 `runs/<task-id>/`，记录账号别名、课程键、当前标签/执行器、已有授权、进行中的测验和证据。格式见 [状态与交接](references/state.md)。

## 速率与播放

- 进节点先探测：读 `video.playbackRate` 当前值和播放器的倍速菜单项（`span.vjs-menu-item-text`，通常是 `2x / 1.5x / 1.25x / 1x`）。
- **优先点菜单项**，那是官方动作；菜单点不动才退回 `video.playbackRate = value`，并在节点记录里注明"属性写入"而不是"菜单选择"。
- 默认取**平台允许的最高档**；`rate = 1` 可配置回保守模式（有些课倍速会判定异常）。
- 锁速课程的 `playbackRate` 恒为 1 且菜单隐藏，接受平台限制，不要用会写死 2x 的旧保活脚本。
- 观察器预算按实际速率缩放：`预算 ≈ 视频剩余秒数 / rate`，避免 2x 下多出无谓的 timeout 回合。

## 全程保留的边界

- 同一账号一次只由一个执行器操作，单标签推进；换执行器前保存断点并确认前一个已停。
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
- [列表采集](scripts/collect_task_list.js) 与 [巡检对比](scripts/inspect_tasks.py)：只读当前已加载列表；`summary`/`diff`。
- [Harness 探针](scripts/dsh_probe.py)：`--tools` 读当前工具清单，报告技能发现根、安装副本漂移和浏览器候选；只读文件系统，不联网、不打开页面。
- [打包](scripts/package_skill.py)：`export` 生成公开副本，`install` 生成安装副本；都拒绝覆盖已存在的目录。

题面与列表的采集函数不自动执行，调用契约见 [工具数据格式](references/tool-data.md)；用新批次隔离题面和字体。

## 验收与回退

交付前分别说明：平台已确认什么、文件工具验证了什么、尚有哪些内容待人工或实战核对。
安装副本与源码是否一致用 `scripts/dsh_probe.py` 核对；缺少受支持浏览器通道时写明缺口和需要启用的能力，不宣称实战通过。
需要换回旧路径时按 [回退说明](references/rollback.md) 保留现场交接，不复制覆盖对方的 `local/` 状态。
