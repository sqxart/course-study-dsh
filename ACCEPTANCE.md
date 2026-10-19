# 外部验收清单（5 步）

给另一台机器或另一个人用：只照 [README](README.md) 和本清单，验证 1.0.0 能装、能探、能跑一节，并回报三个数字。
不要把本机的 `local/`、`runs/`、浏览器 profile 复制过去。

## 前置

- Windows + Python 3.10+ + Node/npx。
- 一个能登录学习通的 DSH 浏览器 profile（`mcp-browser` 通道已配置并能打开课程页）。
- 一个可以跑的小节；公开默认证据模式**不提交**章节测验，所以不会消耗提交次数。

## 五步

1. **安装**（目标目录必须不存在或为空，或加 `-Force` 升级）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target C:\path\to\skills\course-study-dsh
   ```
   确认 `<target>\local\private.toml` 存在，且 `mode = "evidence"`、`submit = false`。

2. **探针**：把当前工具名写成 JSON 数组（例如 `["read", "mcp__browser__browser_click"]`），跑：
   ```powershell
   python C:\path\to\skills\course-study-dsh\scripts\dsh_probe.py --tools tools.json
   ```
   期望 `verdict: "candidate"`、exit 0。再**不带** `--tools` 跑一次，期望 `verdict: "unknown"`、exit 0（unknown 不等于没有浏览器）。

3. **环境**：
   ```powershell
   python C:\path\to\skills\course-study-dsh\scripts\doctor.py
   ```
   记录 `verdict`、`dependencies.ocr_ready`、`browser_ready`（后者固定 `unknown`，不是失败）。

4. **跑一节（证据模式，不提交）**：让技能打开一个未完成小节，把视频看完；章节测验只读题、摆证据、不提交。确认：
   - `runs/<task>/evidence.json` 已生成（先写证据再返回）；
   - 记录里写明 `do-not-submit` 或证据不足；
   - 回目录后任务点数字没有因为这个动作下降（视频那一项可能已点亮，测验那一项应保持不变）。

5. **量成本**：
   ```powershell
   python C:\path\to\skills\course-study-dsh\scripts\session_cost.py <该子 agent 的 session.v4.jsonl.zstd>
   python C:\path\to\skills\course-study-dsh\scripts\toc_status.py <目录快照> --prefix <章号>
   ```
   回报：调用数、会话 token、任务点前后。

## 通过标准

- 步骤 1–3 与期望一致；
- 步骤 4 有 `evidence.json`，且公开默认下**没有提交**；
- 步骤 5 的数字能复现；不要求 ≤8，按公式 `4 + ceil(视频秒数/175)` 判断是否异常（超出先查异常，不直接判失败）。

## 停手条件

任一情况出现即停，保留现场并回报，不重试：验证码、9010、多终端登录提醒、每日上限（`.maskDiv.jobCountDiv` 几何尺寸大于 0）、登录页跳转。

## 回报模板

```text
环境: Windows / Python x.y / Node x.y / DSH 版本
安装: <target>，mode=evidence，submit=false
探针: --tools=candidate exit 0；无 tools=unknown exit 0
doctor: verdict=... ocr_ready=... browser_ready=unknown
一节: <课程>/<节>，evidence.json=是/否，提交=否，任务点前→后
成本: calls=... tokens=...（视频秒数=...）
异常: 无 / ...
```
