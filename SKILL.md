---
name: course-study-dsh
description: DeepSeek Harness 专用的课程助手（与 ZCode/Codex 版相互独立）。用于学习通、中国大学MOOC 的网课续跑、弹题与已授权章节测验、字幕取证与 OCR 读题、任务巡检，以及大学作业取题、验算、PDF 交付与存档。只在当前 harness 的 mcp-browser 通道下操作页面。
---

# 课程助手（DeepSeek Harness 版）

本技能只服务 DeepSeek Harness，与 `course-study-v2`（ZCode 与 Codex 共用的源码仓库）完全隔离：不同名、不同源目录、不同安装副本、各自维护 `local/`。
Harness 的通道事实、已实测范围与调用预算在 [DSH 运行说明](references/dsh-runtime.md)；只读它需要的部分，不要一次加载全部材料。

## 开始

1. 确认当前工具面：`mcp__browser__browser_*`、`pwsh`、`read/edit`。缺少受支持的浏览器通道时只做离线工作，不去找隐藏调试接口或自建 CDP 脚本。
2. 确定平台、课程、账号别名、任务类型与已有授权。续跑先读 `local/CURRENT_HANDOFF.md` 与 `local/active-session.json`，再核验平台实际状态；已明确的信息与授权不重复询问。
3. 按任务只读所需材料：

   | 任务 | 流程 | 平台知识 |
   |---|---|---|
   | 看课、续跑、弹题、章节测验 | [网课流程](references/course-flow.md) | [学习通](references/chaoxing.md) / [中国大学MOOC](references/icourse163.md) |
   | 作业取题、参考解答、验算、交付 | [作业流程](references/homework-flow.md) | 学习通共用同一份知识；智慧树另读 [Polymas](references/polymas.md) |
   | 有无新课件/作业/测验、截止时间 | 网课/作业流程的列表巡检 | 先停在列表；取题和开始测验是后续独立动作 |

4. 使用独立任务目录 `runs/<task-id>/`，记录账号别名、课程键、当前标签/执行器、已有授权、进行中的测验和证据。格式见 [状态与交接](references/state.md)。

## 全程保留的边界

- 同一账号一次只由一个执行器操作，单标签推进；换执行器前保存断点并确认前一个已停。
- 学习通正常播放，锁速接受 1x；不伪造心跳、学习上报或修改进度接口。静音优先，低音量回退只按学习通知识的短试流程使用。
- 课件完成要有平台保存的完成标记；视频到尾、旧状态或本地高分都不是课程完成证明。
- 网课测验按本次已有作答/提交授权执行；只看题或只给参考答案不自动扩展成开始计时、填答或提交。
- 计时测验已经开始时优先完成或保存该次事务；结果不明先查平台记录，不重开尝试、不重复提交。
- 验证码、安全验证、付费或权限限制按平台与当前工具规则处理，需要用户接手时保留现场。
- 本机保留状态、材料与日志；密码不回显，登录态和私人运行数据不进入公开导出。

## 可复用工具

先运行 `python scripts/doctor.py` 确认实际解释器、可选依赖和资源。工具不是授权来源。

- [字幕取证](scripts/subtitle_evidence.py)：`fetch/find/gate/slice`；多个 `--query` 是 **AND**（同一 cue 必须同时含全部词）。
- [截图 OCR](scripts/quiz_ocr.py)：整页识别；[题区过滤](scripts/quiz_panel.py)：按 x 范围把题区从整页里摘出来。
- [裁剪重识别](scripts/crop_ocr.py)：题干漏识时按 OCR 行锚点裁剪并放大重识别；`--auto` 按题号自动定锚点。
- [作答预检](scripts/option_coverage.py)：多选提交前核对每个选项的独特词是否在原文出现；枚举题优先找同一 cue 的并列项。
- [列表采集](scripts/collect_task_list.js) 与 [巡检对比](scripts/inspect_tasks.py)：只读当前已加载列表；`summary`/`diff`。
- [交付闸门](scripts/delivery_gate.py)：按 [交付说明](references/homework-output.md) 验证产物，不代替解题与视觉复核。
- [Harness 探针](scripts/dsh_probe.py)：`--tools` 读当前工具清单，报告技能发现根、安装副本漂移和浏览器候选；只读文件系统，不联网、不打开页面。
- [打包](scripts/package_skill.py)：`export` 生成公开副本，`install` 生成安装副本；都拒绝覆盖已存在的目录。

题面与列表的采集函数不自动执行，调用契约见 [工具数据格式](references/tool-data.md)；用新批次隔离题面和字体。

## 验收与回退

交付前分别说明：平台已确认什么、文件工具验证了什么、尚有哪些内容待人工或实战核对。
安装副本与源码是否一致用 `scripts/dsh_probe.py` 核对；缺少受支持浏览器通道时写明缺口和需要启用的能力，不宣称实战通过。

本技能与 `course-study-v2` 各自演进：改动只写本仓库，不回写共用源，也不从共用源拉取 ZCode/Codex 适配文件。
需要换回旧路径时按 [回退说明](references/rollback.md) 保留现场交接，不复制覆盖对方的 `local/` 状态。
