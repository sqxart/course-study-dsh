# 外部验收清单（5 步）

给另一台机器或另一个人用：只照 [README](README.md) 和本清单，验证 1.0.11 能装、能探、能跑一节，并回报三个数字。
不要把本机的 `local/`、`runs/`、浏览器 profile 复制过去。

## 前置

- **步骤 1–3 不需要浏览器和课程账号**：Windows + Python 3.10+ + Node/npx；`pip install` 需要网络（zstandard 必需，OCR 可选）。
- **步骤 4–5 才需要**：一个能登录学习通的 DSH 浏览器 profile（`mcp-browser` 通道已配置并能打开课程页），以及一个可以跑的小节。
- 公开默认证据模式**不提交**章节测验。打开答题页会生成 `#workAnswerId`，它不等于提交；已观察到打开后 `#addTimes=0`、`#limitWorkSubmitTimes=100`、没有消耗提交次数的情形，但会留下“已查看”。限次=1 的课未单独验证；先看限次说明，打开后不要重开。

## 五步

1. **安装到 DSH 能发现的位置**（默认目标；目标必须不存在或为空，或加 `-Force` 升级）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   # 已有安装就升级（保留 local/）：
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
   ```
   默认目标 `%USERPROFILE%\.agents\skills\course-study-dsh`（设了 `DSH_AGENTS_HOME` 则是 `$env:DSH_AGENTS_HOME\skills\course-study-dsh`）。
   确认 `<target>\local\private.toml` 存在，且 `mode = "evidence"`、`submit = false`；版本看 `<target>\package-manifest.json` 的 `version`（应为 `1.0.11`）或 `doctor.py` 的 `version`；**重启/重载 DSH 会话**让技能目录刷新。
   装依赖（至少 zstandard；OCR 可选）：
   ```powershell
   pip install -r requirements.txt
   pip install -r requirements-ocr.txt   # 可选
   ```
   只验证打包、不打算让 DSH 加载时，才用 `-Target C:\path\to\course-study-dsh`；最后一级目录名必须正好是 `course-study-dsh`，那种装法要另配发现根，不算本清单的通过路径。

2. **探针**：回到**源码仓库根目录**（`install.ps1` 所在目录），把当前工具名写成 JSON 数组（例如 `["read", "mcp__browser__browser_click"]`）存成当前目录的 `tools.json`，跑：
   ```powershell
   python .\scripts\dsh_probe.py --tools tools.json --agents-home <agents home> --require-discovered --require-winner <target>
   ```
   `<agents home>` 是 `%USERPROFILE%\.agents` 或 `$env:DSH_AGENTS_HOME`，**必须和步骤 1 安装时的环境一致**；新 shell 丢了变量会找到 0 份或旧安装。`--tools` 的相对路径按当前工作目录解析。从仓库跑时 `--source` 默认是仓库，`manifest_drift_files` 才是“安装 vs 源码”。`--require-winner` 把“`winner` 必须指向本次安装”变成 exit code，不再靠人眼看。期望：
   - `tools.verdict: "candidate"`、exit 0；
   - `copies >= 1`，且 `winner.skill_file` 指向你刚装的 `<target>\SKILL.md`；
   - `source_is_installed_copy: false`、`manifest_drift_files: 0`。
   把 `--require-winner` 指向一个错误目录时，应 **exit 6**、stderr 带 `winner-mismatch`；`--require-discovered` 找不到副本时 **exit 5**、`not-discovered`。两者不再混用同一个 exit code。
   如果在安装目录里跑探针，`source_is_installed_copy` 会是 true，drift 变成“安装 vs manifest 哈希”的自检；能查篡改，但不能证明和源码一致。探针只读文件系统、不查询运行期 catalog；`copies >= 1` 只证明文件在发现根里，重启后仍以 DSH 的技能列表/实际调用为准。再**不带** `--tools` 跑一次（两个 require 参数保留）：
   ```powershell
   python .\scripts\dsh_probe.py --agents-home <agents home> --require-discovered --require-winner <target>
   ```
   期望 `tools.verdict: "unknown"`、exit 0（unknown 不等于没有浏览器）。

3. **环境**：
   ```powershell
   python <target>\scripts\doctor.py
   ```
   期望 `verdict: "resources-ready"`、exit 0；记录 `dependencies.ocr_ready`（false **不是**失败：装 `requirements-ocr.txt` 或改用截图读题）、`dependencies.browser_ready`（固定 `unknown`）和 `dependencies.core.zstandard`（步骤 5 需要 true）。
   `doctor.py` 只检查文件和依赖，不打开浏览器。

4. **跑一节（证据模式，不提交）**：让技能打开一个未完成小节，把视频看完；章节测验只读题、摆证据、不提交。确认：
   - `runs/<task>/evidence.json` 已生成（先写证据再返回），并且：
     ```powershell
     python <target>\scripts\check_evidence.py runs\<task>\evidence.json --require-readonly
     ```
     返回 `OK`、exit 0；记录里写明 `do-not-submit`/证据不足；
   - 回目录后这一节的任务点**只掉视频那一项**（常见是 `2 → 1`，剩下的 1 是未提交的测验）；若 `2 → 0`，说明测验被提交或平台点亮了它，必须查清，不能当作通过；
   - 没有对章节测验点过选项或提交；打开过就记下 `workAnswerId`、`#addTimes`、`#limitWorkSubmitTimes`，不重开。记录本次的次数与任务点是否变化。
   - 可选核对：课程页“学习记录 → 章节测验详情”里这一节应显示**已查看**、没有分数、不是“已完成”。这个详情页可能新开标签，看完立即关掉；不要点“查看”重开测验。

5. **量成本**：子 agent 的 id 就是 `%USERPROFILE%\.dsh\sessions\<workspace-key>\<agent-id>\session.v4.jsonl.zstd` 的目录名（从 `list_agents` 取）：
   ```powershell
   python <target>\scripts\session_cost.py <该子 agent 的 session.v4.jsonl.zstd> --audit-submit
   ```
   `--audit-submit` 期望 `submit audit: clean`、exit 0；若报 suspect，说明浏览器调用里出现了测验提交选择器，先查清再报。
   任务点快照：目录页用 `browser_snapshot` 存成文件（MCP 的 `filename` 只能落在它的输出目录，本机是 `%USERPROFILE%\.dsh\profiles\desktop`），再 `Copy-Item` 到 `runs/<task>/toc-after.yml`：
   ```powershell
   python <target>\scripts\toc_status.py runs\<task>\toc-after.yml --prefix <章号>
   ```
   回报：调用数、会话 token、任务点前后、`submit audit`。

## 同机替代（没有第二台机器时）

步骤 1–3 可以在这台机器上用**临时 `DSH_AGENTS_HOME`** 走一遍，不碰真实安装：

1. `$env:DSH_AGENTS_HOME = "$env:TEMP\same-machine-agents"`，按步骤 1 默认安装（不用 `-Target`）；安装和探针必须在同一个 shell，`--require-winner <target>` 防止探针回落到真实安装。
2. 按步骤 2/3 在同一环境跑探针与 `doctor.py`；期望 `copies >= 1`、`winner` 是临时 target、`source_is_installed_copy: false`、`manifest_drift_files: 0`、`resources-ready`。
3. 步骤 4–5 用一次**证据模式**节点（可以是另一门课的小节，不提交测验），按步骤 4/5 留 `evidence.json`、`session_cost --audit-submit` 和任务点快照。

这只证明“打包、文档、本机环境、证据模式节点”能走通，**不是外部验收**：另一台机器的登录/网络/权限差异、测验只读是否占作答次数、以及“陌生人”对文档的理解仍未被真正独立验证。报告里写“同机替代”，不要写成另一台机器的通过。

## 通过标准

- 步骤 1–3 与期望一致：装到发现根、`copies >= 1`、`winner` 指向 `<target>`、`source_is_installed_copy: false`、`manifest_drift_files: 0`、doctor `resources-ready`；`ocr_ready` 只记录，不是硬性通过项；
- 步骤 4 有 `evidence.json`，`check_evidence.py --require-readonly` 通过，且公开默认下**没有提交**；
- 步骤 5 的数字能复现，`submit audit` 为 clean；
- 调用数按执行方式判断，不直接判失败：
  - **热启动**（已在本课程目录、已读过技能文档）浏览器调用 8–10 次；
  - **冷启动**（新会话从零开始）总调用目标 ≤20 次；
  - 明显超出时先查异常（目录帧试探、弹题按钮、回目录重进、重复读文档），不要为了凑数字少做验收。
  - 参考公式（1x 锁速课，热启动）：`4 + ceil(视频秒数 / 175)`。
  - **一个子 agent 只跑一个节点**：<运行日期> 丝绸之路 10 节按“3 节点一批”跑，实测 1.73–2.16M token/节点，超过 1.5M 预算；单节点新会话是 0.49–0.80M。批处理只省了子 agent 启动，不省 token。

## 停手条件

任一情况出现即停，保留现场并回报，不重试：验证码、9010、多终端登录提醒、每日上限（`.maskDiv.jobCountDiv` 几何尺寸大于 0）、登录页跳转。
章节测验一旦发现已经提交或开始计时，不重开、不重复提交，先查平台记录。

## 回报模板

```text
环境: Windows / Python x.y / Node x.y / DSH 版本
安装: <target>，mode=evidence，submit=false
探针: --tools=candidate exit 0；copies=... winner=... source_is_installed_copy=false drift=...；无 tools=unknown exit 0
doctor: verdict=resources-ready exit 0，ocr_ready=... browser_ready=unknown
一节: <课程>/<节>，evidence.json=是/否，check_evidence=OK/FAIL，提交=否，任务点前→后
成本: calls=... tokens=...（视频秒数=...），submit audit=clean/review
异常: 无 / ...
```
