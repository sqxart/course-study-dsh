# course-study-dsh workspace (DeepSeek Harness only)

本仓库是 DeepSeek Harness 专用课程技能的源码，<运行日期> 从 `C:/publicworkspace/course-study-v2`（提交 `46c4ea8`）分叉而来。
两份仓库此后各自演进：这里不保留 ZCode/Codex 适配文件，也不把改动回写到共用源。

## Current work

先读 `local/CURRENT_HANDOFF.md` 与 `local/active-session.json`；通道事实与已实测范围见 `references/dsh-runtime.md`。
Harness 的技能发现按 rank 扫描目录（`<root>/<name>/SKILL.md`，只扫一层）。DSH 的 user-agents 根是
`~/.agents/skills`（rank 500），因此 `~/.agents/skills/course-study-dsh` 才是实际加载副本：改源码不会自动生效，同步后要用
`python scripts/dsh_probe.py` 核对 winner 与 drift。

## Collaboration

- 单执行器、单标签；同一账号同一时间只有一个执行器在操作课程。
- 改动流程：本仓库改 → 验证（`python -m pytest tests -q`）→ 提交 → 同步安装副本（先备份，再按哈希核对）。
- 不修改 `course-study-v2` 的安装副本，也不让两个技能的 `local/` 状态互相覆盖。
- 浏览器只用当前 profile 里的 `mcp-browser` 系通道（`mcp-browser` / `mcp-browser2`，一个账号一条）；不复制其他 harness 的 bootstrap、CDP 或写权限。

## Local records and Git

`local/`、`runs/`、`profiles/`、`_validation/`、`dist/` 都被忽略，保留其本地内容。
凭据、cookie、个人身份与签名链接只放在明确选择的私有位置，永不入库。
这是本地仓库，没有远端；推送或公开发布是另一次用户动作，导出前必须人工复核身份与密钥。
