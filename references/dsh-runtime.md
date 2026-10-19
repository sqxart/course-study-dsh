# DSH 运行说明（DeepSeek Harness 专用）

版本基线：DeepSeek Harness 桌面版 0.2.1-rc.2，profile `desktop`。本文件只写本机实测或当前版本包文档能互相印证的结论；历史小节只反映对应版本快照，**不等于当前能力**。其他 harness（ZCode/Codex）的 bootstrap、CDP 名称、写权限或调用时限不适用于本技能。

## 当前通道（<运行日期>，1.0.7）

profile `desktop` 的 `cordis.patch.yml` 里有两条独立的 `mcp-client` 行：

| id | serverName | 工具前缀 | `--user-data-dir` | `--output-dir` |
|---|---|---|---|---|
| `mcp-browser` | `browser` | `mcp__browser__*` | `~/.dsh/browser/chrome-course` | `~/.dsh/browser/output` |
| `mcp-browser2` | `browser2` | `mcp__browser2__*` | `~/.dsh/browser/chrome-clean` | `~/.dsh/browser/output2` |

- 两条都是 Playwright MCP（stdio，`--browser chrome`，`toolCallTimeoutMs: 300000`），各 25 个工具；配置形状见下面「启用受支持的浏览器通道」。
- **一个账号一条通道、一个 profile、一个标签**；同一账号同一时间只有一个执行器。跨账号怎么分、什么时候必须两边都停：见 [多账号运行](multi-account.md)。
- 增删这两行会重载 MCP 并重启对应浏览器，**登录态不保证保留**；只在节点边界做，重启后先读一次 `i.chaoxing.com` 确认是不是登录页（<运行日期> 实测：`browser2` 在会话间回到 `about:blank`，再导航就落到登录页）。
- 不要新开与已有行同 id 的条目（会覆盖已有配置）；也不要让两个账号共用一个 `--user-data-dir`。

## 识别环境与资源根

- 用当前工具清单识别 harness，不凭电脑上装过什么。DeepSeek 会话可用 `cordis_inspect_query`（platform `host`、provider `Tool`）读自身工具清单。
- 技能发现（本版机制，本次已核实）：文件系统 provider 按 rank 扫描目录，目录技能为 `<root>/<name>/SKILL.md`，扁平技能为 `<root>/<name>.md`，只扫一层。

| rank | 来源 | 路径 |
|---|---|---|
| 100 | project-dsh | `<projectRoot>/.dsh/skills` |
| 200 | project-agents | `<projectRoot>/.agents/skills` |
| 300 | custom | 配置的 `customSkillDirs` |
| 400 | user-dsh | `<DSH_HOME>/skills`（默认 `~/.dsh/skills`） |
| 500 | user-agents | `<agentsHome>/skills`（默认 `~/.agents/skills`） |

`projectRoot` 是最近的含 `.git` 的祖先，没有就用会话 cwd；rank 小的先被采用。
默认用户安装位置是 `~/.agents/skills/course-study-dsh`（rank 500）；以 `skill` 返回的 base directory 核对实际加载目录。
本技能自 `course-study-v2`（DSH 适配部分）分叉而来，安装名改为 `course-study-dsh`；旧副本不由本技能同步或覆盖。
因此改源码不会自动生效：同步安装目录后，用 `python scripts/dsh_probe.py` 核对 winner 与 drift。
探针只读文件系统、不联网；`winner` 只代表文件系统层，运行期注册的同名技能仍可覆盖它。

若 `agent-instructions` 未启用，跨目录工作前显式读 `AGENTS.md` 和 `local/CURRENT_HANDOFF.md`。

## 历史快照（历史版本，接入 MCP 之前）

下面两节当时还没有浏览器通道，**已经过时**，只用来解释为什么先有一版“只能离线”的说明；当前能力以「当前通道」为准。

## 工具面（历史版本，33 项）

| 能力 | 工具 | 实测限制 |
|---|---|---|
| 文件读写 | `read` `write` `edit` `glob` `grep` | `read` 能读 `app.asar` 内的路径；`glob`/`grep` 走 ripgrep，进不了 asar，会报路径不存在 |
| 命令 | `pwsh` | 一次调用一个新进程，没有持久 shell；本机实际落在 Windows PowerShell 5.1（`PSEdition=Desktop`），PS7 语法不可用；前台命令超时后会转成后台 job 继续运行，不会被杀 |
| 后台任务 | `job_output` `job_list` `job_kill` | 后台运行没有超时上限；前台超时移交的 job 可继续读 |
| 网络 | `web_search` `web_fetch` | 单次 HTTP 取文本，不携带任何 cookie 或课程登录态，不能读需要登录的页面 |
| 技能 | `skill` | 返回 base directory 与正文；正文改动下次调用即生效，脚本改动要同步安装目录 |
| 子代理/工作流 | `workflow` `send_message` `list_agents` 等 | 只是并行委派，不提供浏览器 |
| MCP | 由 `mcp-client` 配置 | 唯一受支持的扩展通道，工具名形如 `mcp__<server>__<tool>`；每次调用默认 60 秒上限 |
| 浏览器 | `mcp__browser__*` / `mcp__browser2__*` | <运行日期> 当时没有；现在两条 Playwright MCP，见「当前通道」 |

大输出会被截断并给出完整文件路径（本次实测出现 `[output truncated; full output: …]` 与 spill 说明两处提示）；取片段用 `read` 的 offset/limit 或 `grep`。

## 浏览器能力（历史版本）

接入 MCP 之前，标签、快照、跨帧读取、点击、页面脚本、截图和下载全都是“无”，当时只能做离线工作。
现在这些能力由配置的 Playwright MCP 提供；历史矩阵不再保留，避免被误读成当前限制。
没有受支持通道时仍按“只做离线工作”处理，不要用下面这些方式补能力。

## 不要用来“补能力”的方式

- 不连隐藏调试端口。即便现在有 Chrome 进程，那也是受支持的 MCP 通道启动的，不要把它的调试端口当第二条通道。
- 不用 shell 自建 Playwright/Selenium/CDP 脚本去操作课程页；不复用 ZCode 的 browser bootstrap，不调用 Codex 的 `tab.capabilities`/CDP 接口。
- 不用 UI Automation、按键注入或窗口消息伪造点击、焦点与可见性；不改 `document.visibilityState`，不伪造心跳或学习上报。
- 不把 `web_fetch` 当登录态，不拼接或重放旧签名链接。需要登录时由用户在本机浏览器手动完成：Agent 不读取、不输出、不代填凭据，不清全站 Cookie。

## 启用受支持的浏览器通道（需要用户动作）

下面是启用通道、换机器、换账号目录或重装时的步骤。

1. 选一个提供浏览器控制的 MCP server（Playwright、Chrome DevTools 一类），用 `npx` 或本地安装启动。
2. 在 profile 的 `cordis.patch.yml` 里加一条 loader 条目。**这个版本的 `mcp-client` 每个条目只接受一个 server**（`serverName` + `command` 或 `url`），没有 `servers` 数组；多个账号/多个浏览器就写多条 id 不同的条目。先备份文件：

```yaml
- insert:
    - id: mcp-browser          # 已有条目；新增一条时换 id（例如 mcp-browser2）
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        serverName: browser    # 工具前缀 mcp__browser__ 的来源，[A-Za-z0-9_-]{1,32}
        transport: stdio
        command: npx
        args:
          - "-y"
          - "@playwright/mcp@latest"
          - "--browser"
          - "chrome"
          - "--user-data-dir"
          - "<profile-dir>"
          - "--output-dir"
          - "<output-dir>"
        failOnStartupError: false
        toolCallTimeoutMs: 300000
```

   多账号就照抄一份，只改四处：`id`、`serverName`、`--user-data-dir`、`--output-dir`。不要复用同一个 `id`（后一条会覆盖前一条），也不要让两个账号共用一个 `--user-data-dir`。改完重载或重启 harness，新工具名形如 `mcp__browser__browser_navigate`。stdio 启动失败时读 harness 日志排查，不要反复重装。
3. 用当前工具清单跑 `python scripts/dsh_probe.py --tools <工具清单.json> --require-discovered --require-winner <安装目录> --out <本次运行目录>/probe.json`。
   退出码 0 且列出候选只表示“有候选通道”；标签、跨帧、点击、页面脚本、截图、下载、登录态仍要逐项实测。`--require-discovered` 失败 exit 5，`--require-winner` 发现别的安装 exit 6。
4. 首次登录由用户在该浏览器窗口手动完成，之后按 [网课流程](../references/course-flow.md) 与 [学习通](../references/chaoxing.md) 走一个未完成节点。
5. 该 server 条目的 `toolCallTimeoutMs` 默认 60000ms；长时间等待不要压在单次调用里。

## 通道就绪后的单节点顺序

1. 探针 + 平台读：账号别名、课程、章节、附件与媒体身份、服务器保存进度。本地暂停位置只作线索，不直接当断点。
2. 静音 1x 正常播放，间隔两次读时间推进（`video.currentTime`/`duration`）。
3. 弹题：读当前题面与字体，按可见内容与真实选中态作答，只提交一次，判定后继续播放。
4. 视频到结尾 → 刷新 → 读平台完成标记。
5. 本节章节测验：读题、渲染并看图复核、真实提交、读结果页。
6. 刷新目录核对任务点，记录平台读数；不用条目数推算完成率。

任何一步结果不明，先查平台记录与已有证据，不重复提交、不重开尝试、不重放旧链接。
不扩展到全账号课程或不明计时考试。

## 等待、批量与恢复

- 单次预算由 profile 里该账号那条通道行（`mcp-browser` / `mcp-browser2`）的 `toolCallTimeoutMs` 决定（本机已从 90 秒提到 300 秒）。不要按固定 85 秒轮询：每次轮询都是一整轮模型调用，代价远高于返回的几十字节。
- 视频等待用「事件驱动观察」：一次 `frame.evaluate` 在页面里每 2 秒自检，**只在状态变化时返回**——视频结束、弹题出现、意外暂停或到预算上限。一节 20 分钟的视频通常 1–3 次调用，而不是十几次。
- 观察只读 DOM 与媒体状态，不写页面全局变量、不改播放进度；只回传 `{reason, t, duration}` 这类短状态，完整记录写本次 `runs/` 目录。
- 观察预算要比 `toolCallTimeoutMs` 小一档：本机 300 秒上限下**默认 175 秒**（`4 + ceil(视频秒数/175)` 就是按这个算的）；超时返回 `timeout` 就续一段，不算失败。只有确认通道能稳定返回时才把单次调到 270 秒。
- 一次只安排一到两个耗时动作；需要真正并行时用 `run_in_background` 加 `job_output(wait=true)`，不要把 sleep 轮询当等待。
- 观察、动作、平台完成分别验收；DOM 文本或工具返回成功都不等于平台已保存。
- 交接时写清账号别名、课程键、章节与媒体身份、已确认项、未知项和下一步；换执行器先停旧进程。

```js
// 在视频帧里等待状态变化，用一个有界循环换掉逐次轮询
const BUDGET_MS = 175000; // browser_evaluate 不传参数，预算必须写在函数里
const state = await videoFrame.evaluate(async () => {
  const v = document.querySelector('video');
  const start = performance.now();
  while (performance.now() - start < BUDGET_MS) {
    if (v.ended) return { reason: 'ended', t: v.currentTime };
    const q = document.querySelector('.ans-videoquiz');
    const r = q && q.getBoundingClientRect();
    if (r && r.width > 0 && r.height > 0 && getComputedStyle(q).display !== 'none') {
      return { reason: 'popup', t: v.currentTime };
    }
    if (v.paused) return { reason: 'paused', t: v.currentTime };
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  return { reason: 'timeout', t: v.currentTime };
});
```

- `browser_evaluate` 只把函数体交给 `page.evaluate`，**不会传参数**；写成 `async (maxMs) =>` 时 `maxMs` 是 `undefined`，循环一次都不跑、立刻返回 `timeout`（5.3 首次观察器就这样白跑一次）。预算写成函数内常量。
- 播放到约 1 分半会弹「可边看边记」笔记提示（`a.writeNote_vid_blue`「知道了」），它常与暂停同时出现；点掉提示后再 `v.play()`。观察器返回 `paused` 时带 `tip:true`，不要把它当成平台考勤而重复起播。
- 进入章节测验时可能弹「当前章节还有任务点未完成」；页面内更可信的任务点指示是左栏 `span.jobUnfinishCount` 角标（5.3 视频完成后 2→1），别把这个暂态弹窗当成视频没保存。
- `browser_take_screenshot` 的 `filename` 落在 MCP server 的 CWD（本次 `%USERPROFILE%\.dsh\profiles\desktop\`），既不是 `--output-dir` 也不是工作区；每次 `Copy-Item` 到本次 `runs/`。
- `subtitle_evidence.py find` 的多个 `--query` 是 **AND**（同一 cue 必须同时含全部词），不是 OR；查缺口要逐词单独跑，否则会误报 `NO_MATCH`。

## 字幕、取证与题面（DSH 专用）

- **取字幕原话**：进入视频小节后，在视频帧读 `performance.getEntriesByType('resource')` 里含 `allsubtitle` 的 URL——这个 URL 自带正确的 `mid`，比猜 `mid` 可靠。先在页面里 `fetch` 列表、只把 URL 回传给模型（字幕正文不进上下文），再用正式脚本落盘：

```js
// 视频帧内执行：只回传 allsubtitle 与 srt URL，不回传字幕正文
async () => {
  const entries = performance.getEntriesByType('resource').map((e) => e.name)
    .filter((url) => url.includes('allsubtitle'));
  if (!entries.length) return { allsubtitle: null, srt: [] };
  const list = await (await fetch(entries[0], { credentials: 'include' })).json();
  const srt = [];
  const walk = (node) => {
    if (typeof node === 'string') {
      if (/^https?:\/\/.*\.srt(\?|$)/i.test(node)) srt.push(node);
    } else if (node && typeof node === 'object') {
      Object.values(node).forEach(walk);
    }
  };
  walk(list);
  return { allsubtitle: entries[0], srt: [...new Set(srt)] };
}
```

```powershell
python scripts/subtitle_evidence.py fetch --url <上一步的 srt URL> --out runs/<run>/subtitle-<节点>.srt
python scripts/subtitle_evidence.py find --corpus runs/<run>/subtitle-<节点>.srt --query 蜂 --query 蝇 --window 2
python scripts/subtitle_evidence.py find --corpus runs/<run>/subtitle-<节点>.srt --query 蜂 --brief
python scripts/subtitle_evidence.py slice --corpus runs/<run>/subtitle-<节点>.srt --from 00:02:32 --to 00:03:00
```

`--brief` 每题/每条只输出一行（`gate` 末尾给 `VERDICT=`），上下文成本约为完整 JSON 的 1/10；`--out` 仍然写完整记录，两者不冲突。`slice` 按时间戳打印一段对话，用来判断引文的语气和主语，不要再用临时 peek 脚本。

`find` 返回带时间戳的引文；`fetch` 只接受显式传入的本次 URL，不读缓存、不重放旧链接。`--corpus` 也接受 `.txt` 逐行原文（讲义、自己的转写），所以「其他原文依据」同样能过闸门。从顶层页访问内层帧时记：`contentDocument` 上没有 `performance`，资源条目要用 `frame.contentWindow.performance`；写错会静默拿到空数组，看起来像“没有字幕”。

- **P0 语义取证闸门（先取证，再提交）**：任何语义题、判断题、观点题在提交前，先用字幕原话或其他原文核对，**不要按课程语境猜**。把说法拆成必须同时出现的 `terms`，写成问题文件后跑 `gate`：

```json
{"questions": [{"id": "Q3", "text": "水则就是为人民服务", "answer": "A",
                "terms": ["水则", "为人民服务"], "window": 2}]}
```

```powershell
python scripts/subtitle_evidence.py gate --corpus runs/<run>/subtitle-<节点>.srt `
  --questions runs/<run>/gate-<节点>-questions.json --out runs/<run>/gate-<节点>.json
```

退出码 **0** = 每题都 `supported`，记录里带 `evidence.text` 与时间戳，可以提交；退出码 **5** = 至少一题 `low-confidence`，`decision` 为 `do-not-submit`，`missing_terms` 指出缺哪个词、`partial` 表示只对上一部分。低置信时在节点记录里写明「低置信 + 缺什么证据」并告诉用户，再由用户决定；不要用常识或课程语境补位。4.1 Q4、4.3 Q3 就是这样丢分的。闸门只判断「有没有原文支撑」，不判断「原文能否推出选项」。

  **组合陷阱**：`terms` 必须写成「你预期的正确命题」里的词，而不是题面里的词。5.1 Q1 题面写「蜂型路线以手段为导向」，字幕里「蜂行路线」「手段」各自都出现，但属于两个不同主语的句子（蜂=目标导向，蝇=手段导向）；按题面词去查会误判为 supported。正确做法是用「蜂行路线 + 目标导向 + 管理思维」去查，查到即说明题面把主语换了，答案应为「错」。同一段文字主语一变，闸门救不了，所以闸门结论要连引文一起看。

- **多选作答预检（P1）**：多选题在提交前先跑覆盖预检，把「选中项有没有原文」「枚举题是否与并列项一致」变成可判定的结果：

```json
{"question": "三创是指", "type": "multi", "selected": ["A","C","D"],
 "options": [{"key":"A","text":"创新"},{"key":"B","text":"创造"},
             {"key":"C","text":"创优"},{"key":"D","text":"创业"}]}
```

```powershell
python scripts/option_coverage.py check --corpus runs/<run>/subtitle-<节点>.srt `
  --options runs/<run>/options-<节点>.json --brief
```

退出码 **0** = 没有阻塞项；**5** = 有阻塞项（选中项在原文里找不到，或与同一 cue 的并列项不一致），`blockers` 给出 `selected-no-evidence` / `enumeration-mismatch` / `no-selection`。并列项判定条件：同一 cue 里直接出现 3 个以上选项，或 2 个选项且该 cue 含顿号/「和、与、及」等并列符。`--out` 留完整记录，`--selected A,C` 可临时覆盖 JSON 里的选择。预检只给证据侧的事实，最终仍按内容决定；没把握时宁可少选，不要加不确定项。

  已验证与已知边界：5.3 Q2 的字幕在 00:01:09.519 同一句里列出「三驾马车 算法 算力 算料」，把「数据」加进去的错误选择被 `enumeration-mismatch` 挡住；但 12.4「三创」的字幕只提「双创→三创」，从未列出三项（「创优」全片 0 次），预检找不到并列项，**无法**发现那次 0 分——`--strict` 反而会把正确答案「创优」判成缺证据。所以缺原文默认只作警告（`warnings`），只有「原文明确并列、但与选择不一致」才阻塞；答案本身仍靠学科判断。

- **题面解码**：work 页面文本是 CXSecret 混淆字体，DOM 直读是乱码。用元素截图 + 本地 OCR 解成纯文本，截图落盘到允许的输出目录：

```powershell
python scripts/quiz_ocr.py <截图.png> --min-confidence 0.80          # 人读：置信度 + 文本
python scripts/quiz_ocr.py <截图.png> --json --out runs/<run>/ocr-<节点>.json
```

默认阈值 0.80；低于阈值的行仍会输出，但带 `low_confidence: true` 和 `!` 标记，平均置信度写在 `mean_confidence`。依赖缺失时退出码 3、引擎运行失败退出码 4，都不会静默返回空文本。OCR 只解决「读题」，不解决「答对」：语义题仍要过上面的 `gate`。

- **题区过滤与自动兜底（P2）**：整页 OCR 之后先用 `quiz_panel.py --x-min 100 --x-max 1100` 只留题区；题干只有类型标签、正文少于 8 字或带未闭合 `【` 时，用一条命令触发自动裁剪重识别：

```powershell
python scripts/ocr_guard.py <截图.png> runs/<run>/ocr-<节点>.json --dry-run   # 只看判定
python scripts/ocr_guard.py <截图.png> runs/<run>/ocr-<节点>.json --out runs/<run>/stem-<节点>.png
```

`ocr_guard.py` 取题区里第一个带题号的行做题干；判定为可疑时调用 `crop_ocr.py --auto`（按题号自动定锚点，到下一个题号或「二.判断题」这类分部标题为止）再跑一次 OCR，返回 `suspect / reasons / crop_stem / reocr`。判定规则是「去掉类型标签后的正文 < 8 字，或残留未闭合括号」，不是「整行 < 8 字」——否则每个带 `【单选题】` 的正常题干都会触发。`--dry-run` 不读图片，可在决定裁剪前先看结论。

- **章节测验选择态与提交**：题面在 cards 帧 → `ananas/modules/work` 帧 → 再一层答题帧。题目容器 `.TiMu`，选项分两种：判断/单选是 `li[role=radio]`，多选是 `li[role=checkbox]`，点击分别走 `addChoice` / `addMultipleChoice`。**选中态看 `li[aria-checked]` 与隐藏 `input[name=answer<qid>]`；多选写进隐藏框的字母来自 `span[data]`，不是显示顺序**；显示字母与内部 token 可能不同序，按索引或显示字母选择可能出错。正确做法：先读每个 `li` 的 `label`、`span[data]`、`aria-checked`，算出「该选 / 不该选」的差集，只点差集里的 `li`（按 label 重新查，别复用旧引用），每点一次等 300ms 再重读，最后核对隐藏值等于期望 `data` 的拼接。
  点 `.btnSubmit` 只弹出主页面 `#workpop`「提示 确认提交？」，再点其中 `a.jb_btn` 的「提交」才真正提交；结果页会出现「已完成 / 第1次作答 / 本次成绩」，并逐题给出「我的答案 / 得分」。一次只提交一次，提交后用 `#workId` 与 `#workAnswerId` 记档。

- 字体本身可能是内嵌 base64，也可能是 URL 加载，题面采集器的 `fonts` 会按情况标记；解码只依赖"页面已用该字体渲染"这一事实。


## 节点调用预算（历史版本）

通过合并机械操作、避免重复发现与目录往返、用 `--brief` / `slice` 控制回传体积降低调用成本。

1. `browser_click #cur<chapterId>` 进节点（目录页只当基地，进节点才离开）。
2. 一次 `evaluate`：递归找含 `<video>` 的帧 → 核对 chapterId/objectid/媒体 src → `muted=true`、`rate=1`、点 `.vjs-big-play-button` → 轮询到 `currentTime>0`。
3. 一次 `evaluate`：从所有帧的 `contentWindow.performance` 抓 `allsubtitle`，页面内 `fetch` 列表，只回传 SRT URL。
4. 一次 `pwsh`：`subtitle_evidence.py fetch` 落盘。
5. 一次 `evaluate`：事件观察器（2 秒自检，175 秒预算，弹题/结束/暂停即返回）。
6. 弹题：一次 `evaluate` 读题干与选项 → 一次 `pwsh`（`find --brief`、必要时 `slice`、`gate --brief`）→ 一次 `evaluate` 完成「选中 + 核对 + 提交一次 + 读 `#rightNum` + 点继续 + 把余额视频看完」，返回 `ended`。
7. 章节测验：一次 `evaluate` 点 `#dct2` 并轮询到答题帧可读 → 一次截图 → 一次 `pwsh`（`Copy-Item` + `quiz_ocr.py`）→ 一次 `pwsh` 批量 `find --brief` / `slice` / `gate --brief` → 一次 `evaluate` 选中、核对 `aria-checked` 与隐藏值、提交、确认 `#workpop`、读分。
8. 目录复核：一次 `evaluate` 从 `a.subBack` 的 `href` 反推出本次 `studentcourse` 地址（`stuenc` = `enc`）并 `location.href` 跳转 → 一次 `evaluate` 轮询读到「已完成任务点」。

注意：第 8 步的「反推 + 跳转」是同一个标签内的导航，不违反「不开新标签」；比先点返回、再读 iframe、再跳转少两次往返。


## v24 目录布局与倍速（历史版本）

v24 新布局与旧 mooc2 目录不同：旧的 `#cur<chapterId>` 选择器可能不存在。

- 课程入口 `v24.chaoxing.com/courselist/opencoursenewfy?...` 会跳到 `mooc2-ans/mycourse/stu`；目录在 iframe `frame_content-zj` 里，条目是 `li > generic > link`，链接文本形如 `<节号> <章节标题> <未完成任务点数>`。
- **链接末尾的数字是未完成任务点数**：看完后消失。这是最便宜的完成证据——不用 OCR，也不用等「已完成任务点」。
- 点条目 → `mooc1.chaoxing.com/mycourse/studentstudy?chapterId=...`；视频在 `mooc1.chaoxing.com/ananas/modules/video/index.html` 的嵌套帧里，帧内 `performance` 仍是取字幕的位置。
- 倍速菜单是 `span.vjs-menu-item-text`，选项 `2x / 1.5x / 1.25x / 1x`。**优先点菜单项**（官方动作）；菜单点不动才退回 `video.playbackRate = 2`，并在记录里注明"属性写入"而不是"菜单选择"。
- **属性写入会被播放器覆盖**：实测把 `playbackRate` 设成 1、读回来仍是 2——播放器按自己的菜单状态重设。所以设置后必须**读回校验**；读回不一致就记 `menu-failed`，不要声称已改速率。
- **弹题提交后可能没有判定**：v24 播放器里点提交，弹窗直接消失，`.spanHas` / `.spanNot` / `#videoquiz-continue` 全部不可见，`#rightNum` 为 null；任务点数也不变。**提交成功 ≠ 计入**，唯一可信的验收是回目录看尾部任务点数。
- **剩下的任务点通常是章节测验，不是弹题**：小节页顶部任务栏分「视频 / 章节测验」，写着「任务点已完成」说明视频那一项已经算完；任务点数还挂着 1 时，要补的是测验。
- **v24 章节测验流程（实测两节 <成绩>分）**：点「章节测验」→ 内层 iframe `mooc1.chaoxing.com/mooc-ans/work/doHomeWorkNew?workId=...` → **对 frame body 做元素截图**（视口截图只能拍到前两题）→ `quiz_ocr.py` → `quiz_panel.py` → 从 `li[role=radio]` 读 `qid` / `qtype`（单选 `span[data]` 是 A–D，判断是 `true` / `false`）→ `li[qid=X].nth(i)` 点击 → 核对 `input[name=answer<qid>]` 与 `aria-checked` → 点 `.btnSubmit` → 主页面 `#workpop` 点「提交」→ 结果帧 `selectWorkQuestionYiPiYue` 显示「已完成 / 第1次作答 / 本次成绩」。**提交后该帧就是明文**（题干 + 我的答案 + 正确答案 + 得分），可直接当复盘与题库来源。旧播放器的弹题控件要点 `input[type=radio]`，v24 测验页要点 `li[qid]`，进页先探骨架。
- 实测：381.16 s 的 1.1 以 2x 静音播完，用 187 s；回目录后 1.1 的尾部任务点数消失、1.2–1.19 仍在 → **2x 被平台正常计入**。这门课没有弹题，观察器一次跑到底，没有 282 s 空转。
- 代价：首次遇到新布局花了约 24 次调用（探索）；按上面的配方应压到 6–8 次。

## 节点级隔离与调用预算（M1）

跨节点积累上下文会放大调用成本；每节点独立会话可限制累积。

- **每节点一个新会话**（或一个独占浏览器的子 agent）。主会话只收节点结果，不再累积上下文。
- **子 agent 契约**：自己把证据写到 `runs/<节点>/evidence.json`（视频时长、实际倍率、弹题题干与引文、workId/workAnswerId、调用数），最终只回传一段紧凑 JSON；不开新标签、不碰别的课程、不提交未授权测验。
- **观察器必须有界且可续**：单次调用只跑 **175 秒**（本机 300 秒上限下）就带 `timeout` 返回，下一回合再续。**先写证据文件再返回**，即使被中断也能恢复。
- **合并调用**（一次 evaluate 内完成）：点目录项进节点 → 找 `<video>` 帧 + 静音 + 选速率 + 起播 + 抓 `allsubtitle` → 一次 `pwsh` 落盘字幕 → 观察器。
- **观察器总预算按速率缩放**：`总预算 ≈ min(剩余秒数 / rate + 60s, 1500s)`，但**单次调用仍只跑 175 秒**。把该账号通道的 `toolCallTimeoutMs` 提到 1800s 左右再跑长视频是另一条路——**会让 MCP 重载、登录态可能丢失，只在节点边界做**；默认不用。
- 验收线：**热启动**（已读过文档、已在本课程目录）单节点浏览器调用 8–10 次；冷启动（新会话从零读文档）总调用 ≤ 20、会话 token ≤ 1.5M。实际成本按本次会话和 evidence 测量，不将目标视为保证。

v24 布局下的 4 次调用配方（跨帧不能合并，所以按帧拆）：

```js
// 第 2 次调用：点倍速菜单（官方动作）+ 静音 + 起播 + 抓 allsubtitle
async () => {
  const find = (pick) => {
    const stack = [window];
    while (stack.length) {
      const w = stack.pop();
      let d; try { d = w.document; } catch (e) { continue; }
      if (!d) continue;
      const hit = pick(d);
      if (hit) return hit;
      for (let i = 0; i < w.frames.length; i++) { try { stack.push(w.frames[i]); } catch (e) {} }
    }
    return null;
  };
  // 菜单收着时先点 .vjs-playback-rate 展开
  const opener = find((d) => d.querySelector('.vjs-playback-rate'));
  if (opener) opener.click();
  await new Promise((r) => setTimeout(r, 300));
  const item = find((d) => [...d.querySelectorAll('span.vjs-menu-item-text')]
    .find((s) => s.textContent.trim() === '2x'));
  let rateSource = 'menu';
  if (item) { item.click(); await new Promise((r) => setTimeout(r, 300)); }
  const video = find((d) => d.querySelector('video'));
  if (!video) return { ok: false, reason: 'no-video' };
  if (video.playbackRate !== 2) { video.playbackRate = 2; rateSource = 'property'; }
  if (video.playbackRate !== 2) rateSource = 'rejected'; // 播放器覆盖了属性写入
  video.muted = true;
  await video.play();
  return { ok: true, rate: video.playbackRate, rateSource, duration: video.duration };
}
```

观察器随后单独一次调用（每次 175 秒，`timeout` 续）；结束回目录读尾部任务点数。**记录里必须写明 `rateSource`**：`menu` 是官方动作，`property` 是退路。

## M2 单节点验收（<运行日期> 实测）

两次由子 agent 独占浏览器、单标签跑完整节（视频 + 弹题 + 章节测验），分别量调用数、token 与任务点。

| 节点 | 视频 | 倍率 | 调用 | 会话 token | 任务点 | 测验 |
|---|---|---|---|---|---|---|
| 地球历史 1.3.3 | 454.6 s | 1x（锁速） | 10（修配方前） | 530,744 | 2 → 0 | 75 分，只提交 1 次 |
| 地球历史 1.4.1 | 389.6 s | 1x（锁速） | 8 | 491,773 | 2 → 0 | 100 分，只提交 1 次 |

- **两节都是本地 `mode=completion`（完成优先）跑的**：公开默认 `mode=evidence` 遇到无字幕测验会停在证据页，不会提交推断答案（1.3.3 的 75 分属于完成模式）。
- **量法**：调用数取该子 agent 会话的 `tool/call` 事件（`session_cost.py` 的 `tool_calls` 还包含最后一条汇报消息，节点本身减 1）；token 取同一会话的 `tokens.total`；任务点用**新加载**的目录快照跑 `toc_status.py` 前后对比（1.3.3 之后课程 244→242，1.4.1 之后 242→240，两次都复核到节行尾部数字消失）。
- **预算公式**（1x 锁速课）：`调用 ≈ 4 + ceil(视频秒数 / 175)`。4 = 进节点并起播（合并一次调用）+ OCR 一次 + 提交并回目录一次 + 写证据一次；观察器每 175 s 一次，弹题当次早退、由下一次续播。389.6 s 算出 7，1.4.1 实测 8：多出的 1 次是首次选答时按可见文字匹配（字体混淆，必然失败）导致的安全中止，不是流程必需。
- 2x 可用的课观察次数减半；这条线只对锁 1x 的课按上面的公式成立。450 s 左右 7 次，700 s 左右 8 次。**不把它写成"所有课都 ≤8"**。

这套流程在「地球历史及其生命的奥秘」上的具体事实（本课程 1.3.x/1.4.x 实测）：

- **外壳与目录**：`mooc2-ans/mycourse/stu?...&pageHeader=1`（章节详情），目录在 `frame_content-zj`，即 `studentcourse` iframe。每行是 `.chapter_item[onclick="toOld(courseId, chapterId, clazzId, 0)"]`，行文本形如 `1.4.1 早期地球的排气作用 2`，尾部数字是未完成任务点数。
- **进节点与起播可以合并**：在 `studentcourse` 帧里点 `.chapter_item`（按节号过滤），等 `ananas/modules/video/index.html` 帧出现，再静音、点倍速菜单、起播——一次 `browser_run_code_unsafe` 完成；省掉单独一次 click，也没有 ref 失效问题。导航后仍要核对 `chapterId` 与节名。
- **锁速**：这门课展开倍速菜单只有 `字幕设定/关闭字幕/公网1/公网2/高清`，没有 2x；写 `video.playbackRate=2` 会被播放器改回 1。菜单没有 2x/1.5x/1.25x 时直接记 `rateSource=locked`（预跑 1.2.1 起改用这个值，不再写属性），按 1x 播，不反复试。
- **弹题**：`li.ans-videoquiz-opt > label > span.tkRadio > input[type=radio]`，点 radio 并回读 checked；提交点用**可见的 `a.ans-videoquiz-submit`**（1.2.1 实测点 `DIV.tkTopic_oper` 不放行、视频不续播）；必要时点 `.ans-videoquiz-continue`。`.spanHas`/`.spanNot` 是静态文案（提交前就能看到「回答正确」），不是判定；弹题是否计分页面不给。
- **测验答案不要读文字**：待作答态的 DOM 文字是混淆字体（形如 `A 惉悻惆惈成敦就惃惄`），任何按可见文字匹配的选答都会失败。只认 `li[qid]` 的 DOM 顺序 + `span[data]` token：单选是 `A`–`D`，判断是整 token `true`/`false`，多选是字母拼接。核对 `input[name=answer<qid>]` 时按 **token 集合**比较——把 `true` 拆成字符再排序会得到 `ertu`，必然误报 `verify-mismatch`。
- **OCR**：截图用 `f.locator('body').screenshot()`（frame body，整页高度）。Windows 控制台先 `$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8`，否则中文乱码、只剩几行。`quiz_panel.py` 的 x 区间是宽屏页面的启发式；932 px 窄页的题面从 x≈39 开始，`100–1100` 会把题面全过滤掉。验收配方直接打印全部 OCR 行（约 25 行），不进面板过滤。
- 结果页提交后是明文（我的答案/得分），可复盘；0 分不一定点亮任务点，是否点亮只看目录尾部数字。

## 预跑：证据模式单节点（<运行日期>，1.2.1）

冷启动子 agent，只读 `mcp__browser__`、单标签、最小化，按 `local/private.toml` 的临时 `mode=evidence`（`submit=false`）跑完整节；章节测验只读不提交。

| 项 | 实测 |
|---|---|
| 视频 | 498.32 s，1x（菜单无倍速，`locked`），静音，`ended=true` |
| 弹题 | t=343.26 s；「地球作为太阳系的独立行星形成于（）亿年前」选 D（46）；无判分，`low_confidence` |
| 字幕 | `allsubtitle` 返回 HTTP 200 + `[]`；本视频**没有字幕轨**，弹题和测验都没有原文可支撑 |
| 章节测验 | workId 900001，5 题；只读打开、OCR；**0 选项点击 / 0 提交 / 未重开**；`decision=do-not-submit` |
| 任务点 | 1.2.1 行尾 `2 → 1`；课程总数 240 → 239；剩下 1 是未提交的测验 |
| 成本 | **37 次调用 / 2.29M token / 722 s**（其中浏览器 21 次） |
| 审计 | `session_cost.py --audit-submit` = clean；`check_evidence.py --require-readonly` = OK |

37 次里只有 3 次观察器 + 2 次弹题 + 1 次起播是必需动作，其余是**可避免的探索**：

1. 目录帧试探 5 次：`browser_evaluate` 读不到 `mooc2-ans` 帧（`document.domain` 隔离），改用 `browser_run_code_unsafe` 的 `page.frames()`。→ 快速配方第 1 步直接用后者。
2. 弹题 5 次：先按旧配方点 `DIV.tkTopic_oper`，浮层不动；又探候选、再点 `a.ans-videoquiz-submit` 才放行。→ 配方改成直接点 `a.ans-videoquiz-submit`，一次读题 + 一次「作答+续播」。
3. 回目录再重进 6 次：视频完先回目录核对，`page.goBack()` 又回不去，改用 `a.subBack`；再进节点开测验。→ 配方固定「视频 → 弹题 → 测验 → 最后回目录一次」。
4. 冷启动读文档/仓库 11 次：`references/quickstart.md` 就是为了把这部分压到 1–2 次。

**这次预跑证明的**：证据模式可以完整看完一节、弹题可答、测验可只读取证、不提交、平台任务点只掉视频那一项。
平台“学习记录 → 章节测验详情”（`stat2-ans`）给出的状态：1.2.1、1.2.2 都是**已查看**、无分数；1.2.3 在 23:00 时还是**未查看**，23:44 只读打开答题页后也变成了**已查看**。N/N 的“已完成”里不含这三节。这个详情页会**新开标签**，看完立即关闭，不要点“查看”重开测验；它没有作答次数列。

1.2.3 的答题页还给了隐藏字段：`#addTimes = 0`、`#limitWorkSubmitTimes = 100`、`#workAnswerId = 900002`，没有非静态的 start/answer 请求；离开后任务点仍是 2。**打开答题页本身没有消耗提交次数**（至少这个 quiz/字段语义），但会留下“已查看”。

**仍然没有证明的**：限次=1 的课是否也同样不消耗（只测了 `limitWorkSubmitTimes=100` 的 1.2.3）；弹题是否计分（页面无判定）；无字幕时测验答案的正确性（没有提交）。这些不写成结论。

复测（同日，1.2.2，409.0 s）：用 [单节点快速配方](quickstart.md) 的 6 个代码块，冷启动 **19 次调用 / 0.80M token / 浏览器 7 次 / 任务点 2→1**，`check_evidence --require-readonly` OK、`--audit-submit` clean。
比 1.2.1 少 18 次调用、少 1.49M token；少掉的正是目录帧试探、弹题按钮试错和回目录重进。剩余 11 次非浏览器调用是读配置/文档、跑校验、写证据和汇报。

## 实测结论（<运行日期>）

已核实的通道事实：技能发现与安装根；文件系统探针；`pwsh` 实际为 Windows PowerShell 5.1，前台超时转后台 job，大输出截断并给完整路径；`web_fetch` 无登录态。浏览器能力来自本机 profile 里 `insert` 的 Playwright MCP（<运行日期> 时是一条 `mcp-browser`、25 个工具；<运行日期> 起 `mcp-browser` + `mcp-browser2` 两条），不是 harness 内置浏览器。

已实战通过（<运行日期>，学习通，Chrome 与 Edge 都验证过）：3.2、3.3、3.4、4.2 四个整节点的章节测验首次 100 分；4.1 为 80 分、4.3 为 66.6 分（各有题目因缺少原文支撑答错，按规则未重开、未重交）；目录 14/84→26/84，每一步都用新加载的课程页核对。3.3、4.2、4.3 全程在 Windows 原生最小化（`IsIconic`）下完成，含播放、选项填写、弹题与章节测验提交、刷新保存。

<运行日期>，脚本化后的 5.1 节点（<时长>秒）一次跑通，目录 26→N/N：节点宏用一次 `evaluate` 完成「定位嵌套帧 + 三处身份核对 + 静音 + 点大播放键 + 确认起播」，事件观察器在同一调用里 <时长>秒自检，<时长>秒弹题早退返回，答完后 `ended` 早退；`subtitle_evidence.py fetch` 落盘 181 条字幕，`find`/`gate` 给出 00:04:16–00:04:28 与 00:08:46–00:08:54 两段原话，弹题与两道判断题全部命中，章节测验首次 <成绩>分（workId 900003）；`quiz_ocr.py` 把两道题干解到 0.95，头部 0.67–0.80 的行如标注为低置信。这一段同时修掉四个通道问题：课程卡片 href 是相对 `v24.chaoxing.com` 的，手拼 `i.chaoxing.com` 会 404，必须用 `contentDocument.baseURI` 解析出的绝对地址；`mooc2-ans` 外层 `stu` 页的 iframe 被 `document.domain` 隔离，读不到「已完成任务点」，要直接用页面自己给出的 `studentcourse` 地址加载目录；帧内资源条目要用 `contentWindow.performance`；首次出现的可见 Chrome 窗口并未最小化，`IsIconic` 复核后守卫必须补一次 `ShowWindow(SW_MINIMIZE)`。

同日 5.2（431.06 秒）按「节点调用预算」的紧凑序列只用了 **19 次调用**就走完「进节点 → 视频到尾 → 弹题 → 章节测验读完并判完」，目录 28→29/84；弹题 241.276 秒，答案由 00:02:38–00:02:59 的原文支撑。章节测验先被闸门拦住：Q2「创业思维是一种（行动导向）的方法，体现了（实用主义）的哲学思想」在本节点字幕里没有任何对应原文（5.2 字幕不含 哲学/实用/理性/前提/事先/设定）；用户明确授权「无原文时按推断作答」后按 effectuation 的学科知识补答并在记录里标 low-confidence，最终 **第1次作答 100 分**（workId 900004），目录 30/84。多选状态这一步踩了坑并修正：隐藏框字母来自 `span[data]`（乐高显示 A、data=D），按显示字母点会连续选错，改为「读 label/data/aria-checked → 只点差集 → 重读核对」后一次通过。

<运行日期> <时间>，5.3「人工智能思维」（<时长>秒，objectid `00000000000000000000000000000000`）一次跑通，目录 30→N/N：弹题 <时长>秒，答案由 00:03:49.560–00:03:56.879「人工智能算料数据它指向的是预测优化」支撑；章节测验 **第1次作答 <成绩>分（workId 900005、workAnswerId 900006）**。Q1 用 00:01:09.519–00:01:24.319「人工智能算法它高度关注因果关系」，Q2 用 00:01:05.599–00:01:15.640「人工智能三驾马车 算法 算力 算料」；Q3 在 N/N/5.2 字幕里都没有原文，按王国红等（外国经济与管理 2017, 39(4): 3-14）「嵌入创业情境中……促进团队内部知识的组织、分配与加工」答 CD，节点记录标 low-confidence。三题都把显示字母和 `span[data]` 分开核对：Q1 显示 C（因果关系）而隐藏值是 A，Q2 隐藏值 BCA、Q3 隐藏值 AC——按显示字母点会全错，单选也一样。



<运行日期>收尾：从 N/N 跑到 **N/N**，26 个节点（5.4、5.5、6.1–6.4、7.1–7.4、8.1–8.4、9.1–9.2、10.1–10.2、11.1–11.4、12.1–12.4）全部完成，其中 24 个节点章节测验首答 <成绩>分；5.5 为 83.3（多选题「少选」只得一半分），12.4 为 <成绩>分（「三创」题选了创新/创造/创业，正确答案是创新/创优/创业，已提交不可改）。按节统计：26 段视频共约 6.4 小时、26 次弹题全部答对、26 次章节测验全部提交；目录复核从 N/N 到 N/N，无待完成任务点。调用成本：单节点从最早 42 次压到 13–17 次（宏内合并字幕发现、观察器直接回传题干、提交时回读角标、每题一次 gate）。新增两个降低读题成本的小工具：`quiz_panel.py` 按题区 x 范围过滤整页 OCR（57 行压到约 20 行），`crop_ocr.py` 在题干被漏识时按 OCR 行锚点裁剪题区并 2 倍放大重识别（7.2 Q1 靠它补出题干）。新确认的坑：平台任务点计数有延迟（10.x 后目录少 <成绩>分，11.4 交卷后自补，不要回头重看视频）；「三创」是创新/创优/创业；`browser_run_code_unsafe` 只允许读 `~/.dsh` 下的两个根目录，工作区脚本加载不了。

通道形态区别：本路径是独立浏览器窗口（`--browser chrome` 或 `--browser msedge`，各自独立 `--user-data-dir`），不是 Codex/ZCode 的内置 IAB。因此 Codex 的「面板尺寸变化 / harness 最小化」清单不适用于本路径；最小化按真实 OS 窗口状态验收，尺寸只影响自身布局。**一个账号一条通道、一个浏览器、一个标签**：同一账号开两个标签/两个执行器才会触发多终端提醒；不同账号各用一条通道时怎么并发、什么时候两边都停，见 [多账号运行](multi-account.md)。换浏览器就改 `--browser` 与 `--user-data-dir` 两处。首次登录后课程列表 iframe 可能返回一次「加载失败」404，重载页面即可恢复。改这一行会让 MCP 重载并关闭浏览器，登录态不保留，所以配置改动集中在节点边界。

## 登录态与重载

- 浏览器进程一旦重启，平台的登录态不作为默认假设；每次重载后先读一次 `i.chaoxing.com`，看到登录页就处理登录，不要默认"会话已保持"。
- 登录有两种方式，按用户当次授权选择：**用户手动登录**（注重隐私时，Agent 只把窗口留到登录页）；或**用户明确给出账密时由 Agent 代输**。代输时密码只用一次、不写入任何文件、不回显；手机号、姓名、学校等 PII 放进 `local/` 的导出拦截名单，供 `package_skill.py export --denylist` 使用。
- 「记住我」或扫码登录能否跨重启由平台决定，不在本技能控制范围；不要在未确认时声称登录已保持。
- 重载后先等 10–20 秒再判断：页面可能先落登录页再跳转，别把过渡页当成会话失效。

## 窗口与前台

- 浏览器创建或重载后，**先把窗口最小化再开始操作**，不干扰用户；用 Win32 `ShowWindow(hwnd, SW_MINIMIZE)` 即可，随后用 `IsIconic` 复核。
- **不要调用 `page.bringToFront()`**：它会把浏览器窗口抬到前台。
- **不要用"点课程卡片"开新标签**：新标签同样会把窗口抬起来。改从卡片链接读出 `href`，用同一个标签 `goto` 打开（链接仍是平台本次生成的，不是手拼的旧链接）。需要回到课程列表时用页面内的「返回课程」。
- 任何可能抬窗口的动作之后（新标签、首次跨站跳转），补一次**幂等最小化守卫**：`IsIconic` 为假才 `ShowWindow(SW_MINIMIZE)`；长等待和提交前再复核一次。
- 用户要求"不要影响我"时，最小化是硬约束：宁可每次多一次守卫调用，也不要让窗口弹到前台。
- 实测最小化下静音 1x 播放速率正常，弹题、选项填写、章节测验提交和刷新核对都可在最小化下完成；元素截图在最小化下仍可读。
- 不要把"课程标签是否在前台"当成播放前提；若观察到时间推进异常，先回读 `currentTime` 再判断，别急着重新起播。

仍未验证：下载/上传、其他平台、**同一账号**的多标签并发稳定性、跨账号长视频/测验/提交并发。同一账号维持单标签；跨账号限制见 [多账号运行](multi-account.md)。
