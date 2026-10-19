# 本地状态与交接

新版任务目录由调用方明确选择，例如 `runs/<task-id>/`；脚本使用绝对路径或相对输入文件的位置，
不把当前shell目录当成技能资源根。旧目录不移动、不清理、不覆盖。

一个任务目录可包含 `state.json`、课程配置、列表快照、读题批次、验算脚本、产物清单和脱敏摘要。
密码保留在用户选择的本地凭据位置或本次进程环境中，不写进状态和输出日志。

```json
{
  "schema_version": 1,
  "task_id": "local-task",
  "platform": "chaoxing",
  "mode": "course",
  "account_alias": "account-a",
  "course_key": "course-a",
  "authorization": {"read": true, "answer": false, "submit": false},
  "active_attempt": null,
  "current": {"section": "section-a", "media_key": null},
  "confirmed": [],
  "pause_reason": null,
  "next_action": "reload-list-and-verify",
  "updated_at": "2026-01-01T00:00:00+08:00"
}
```

这是记录格式，不授予动作权限；authorization 来自当前用户与同一任务已有授权。
`confirmed` 每项应包含对象身份、平台证据、读取时间和使用方法；没有证据的旧done不能直接计入。

## 节点证据（`runs/<task>/evidence.json`）

每个节点**先写这个文件再汇报**；`scripts/check_evidence.py` 按下面的结构检查，证据模式默认要求 `submitted=false`，`--require-readonly` 再加“0 选项点击 / 0 提交 / 未重开”。

```json
{
  "schema_version": 1,
  "kind": "node-evidence",
  "mode": "evidence",
  "authorization": {"source": "local/private.toml", "submit": false, "redo_once": false},
  "course": {"title": "课程名", "course_id": 0, "clazz_id": 0},
  "section": {"code": "1.2.1", "title": "节名", "chapter_id": ""},
  "video": {
    "duration_seconds": 498.32, "rate": 1, "rate_source": "locked",
    "muted": true, "ended": true, "observer_calls": 3,
    "subtitles": {"allsubtitle": null, "srt": [], "srt_urls": 0}
  },
  "popup": {"question": "题干", "selected": "D", "evidence_status": "insufficient-evidence", "low_confidence": true},
  "quiz": {
    "work_id": "0", "work_answer_id": null, "question_count": 5,
    "submitted": false, "decision": "do-not-submit", "platform_status": "已查看",
    "add_times": 0, "limit_work_submit_times": 100,
    "options_clicked": 0, "submit_clicked": 0, "reopened": false
  },
  "platform": {"toc_before": {"task_points": 2}, "toc_after": {"task_points": 1}},
  "cost": {"tool_calls": 12},
  "deviations": ["无字幕，测验只读"]
}
```

- `mode` 是 `evidence` 或 `completion`；`rate_source` 是 `menu` / `property` / `rejected` / `locked`。
- `quiz.decision` 在证据模式固定写 `do-not-submit`；完成模式提交后写实际结果页读数。
- `quiz.platform_status` 写平台学习记录里的读数：证据模式打开过是 `已查看`，没打开是 `未查看`；它不是分数，也不能替代任务点。
- `quiz.add_times` / `quiz.limit_work_submit_times` 读答题页隐藏字段。1.2.3 只读打开后 `add_times` 仍是 0、`limit_work_submit_times` 100，没有提交/start 请求：打开本身没有消耗提交次数，但会留下“已查看”。限次=1 的课未单独验证。
- `check_evidence.py` 会检查这三个字段：证据模式打开过测验（有 `work_answer_id`）却没写 `platform_status` 时给 warning；`platform_status` 只接受 `已查看` / `未查看` / `已完成`；`add_times` 必须是 ≥0 的整数，`limit_work_submit_times` 必须是 ≥1 的整数。
- `platform.toc_after.task_points` 只能小于等于 before；没下降写 warning，不能写成“已完成”。
- `deviations` 写清可复现的偏差（按钮不放行、无字幕、回目录方式），空数组也要有。
- `cost.tool_calls` 写本次会话 `tool/call` 事件数（含最后一条汇报）；节点动作数 = 这个数减 1。用 `session_cost.py` 核对。

进行中测验另记录 attempt标识、是否已开始、剩余时间/截止、已保存答案清单和提交结果。
保存时避免密码、cookie和签名链接；题目、答案与真实课程资料可以保留在本机任务目录。

更新小型JSON文件用“临时文件→同目录替换”，避免中断产生半份状态。切换执行器先停旧进程。
旧版可能用字符串 paused 或布尔 paused+pauseReason；读取时记录原格式并解释，不原地改写旧文件。

交接应说明：任务与账号别名、授权范围、当前执行器/标签、进行中的尝试、已确认项、未知项、
最近错误、状态文件位置和下一步。恢复先读盘面再核对平台，不以历史聊天中的完成声明替代。
