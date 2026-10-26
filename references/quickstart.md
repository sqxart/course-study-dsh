# 单节点快速配方（学习通 mooc2-ans 目录）

这是一节的**最短可执行序列**，为采用 `mooc2-ans/mycourse/stu` 目录 + `.chapter_item` 行 + 锁 1x 播放器准备。
目标：冷启动也能把浏览器调用压在 8–10 次，而不是边试边找选择器。

先读 `local/private.toml` 决定模式。**证据模式（`mode=evidence` / `submit=false`）下，章节测验只读：不点选项、不点提交、不重开**；
视频和弹题照常完成，弹题没有原文时按学科知识作答并标 `low-confidence`。
通道与更长的平台说明见 [DSH 运行说明](dsh-runtime.md)、[学习通](chaoxing.md)；本文件只给可直接粘贴的代码。

**批量跑多节时不要在主会话里逐节点驱动**：用 `workflow` 串行链、**3 节一个子 agent**
（实测 1.22 M token/节；单节点新会话 0.43–0.74 M/节；1 节/agent 反而更贵到 1.54 M/节），
驱动预生成后传 `filename`；主会话只做拆包、校验、记账。细则见 [SKILL.md](../SKILL.md) 的
「批量节点：用子 agent」。

## 0. 先决条件

- 浏览器已在课程目录页（`mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?...`），已登录，单标签。
- 只用当前账号那条通道（`mcp__browser__*` / `mcp__browser2__*` / `mcp__browser3__*` 之一，见 [多账号运行](multi-account.md)），不要跨账号混用；不要用 `browser_evaluate` 去读 `mooc2-ans` 目录帧——它被 `document.domain` 隔离，读不到。
  目录和播放器都在 `page.frames()` 里，用 `browser_run_code_unsafe` 的 `page`。
- 观察器单次 **175 秒**（本机 `toolCallTimeoutMs=300000`），返回 `timeout` 就续一段，不算失败。
  跑长视频课可以放宽，但**上限是 `toolCallTimeoutMs − 60 s`（本机 240 s）**：进节点、等帧、收尾还有 20–60 秒开销，
  280 s 会稳定撞 300 s 超时。超时后视频通常还在页面里继续播——先读状态，**不要重跑起播脚本**。
- **页签按文字点**：多数节 `1视频 / 2章节测验`，每章第一节常是 `1学习目标 / 2视频 / 3章节测验`；
  固定点 `li#dct2` 会点错，按 innerText 含「视频 / 章节测验」匹配。
- **`ended` 之后先停留 20–30 秒**再切页签或回目录：平台写观看进度有延迟，立刻切走可能这一节白看
  （本地 `ended=true`、测验满分，行尾仍剩 1 点，只能重播整段补记）。
- **别让浏览器抢你的前台。** 跳页/开新标签会把 DSH 那个浏览器窗口顶到最前，打扰用户。开工时在后台挂一次：

  ```powershell
  python scripts/browser_window.py watch --minutes 180   # 前台一露头就最小化，只动 DSH 自己的 profile
  ```

  不想挂后台就在每次跳转后跑 `python scripts/browser_window.py minimize`（幂等，只匹配 `--user-data-dir` 里带 `.dsh` 的窗口）。
  实测最小化后页面仍 `visibilityState=visible`、截图正常、新播放器继续播；**旧播放器会因失焦暂停**，那类课别最小化。
- **一节里可能有多个视频。** `ananas/modules/video` 常匹配到 **2 个 iframe**，而 `cards` 帧写明的完成条件是
  **「观看时长需 ≥ 总时长的 90%」**。只播第一个就永远拿不到那个任务点：若第一段占总时长不足 90%，只播它不能完成视频点；补播其余视频后再核对目录。
  → **遍历所有视频帧逐个播到 `ended`，不要 `.find()` 取第一个。**

## 0b. 两种节点形态，先判断走哪条

| 形态 | 判断 | 走法 |
|---|---|---|
| 视频 + 测验 | 目录行尾 > 0，且「视频」页签里 `video.currentTime` 没到末尾 | 下面 §1–§6 的完整流程 |
| **纯测验**（视频已完成） | 课程页进度显示视频点已清零，或播放器显示已完成 | 跳过 §1–§3，直接 §4 打开测验；每节约 **40–70 秒、5–8 次调用** |

纯测验模式下不要为了"确认视频"再播一遍：既浪费时间，也会让 `video.ended` 这种字段变成假证据
（本节视频不是这一轮看的，就不该声称 `ended`）。

## 0c. 无字幕视频：先起转写，再播放（`[asr] enabled = true` 时）

视频有没有字幕，进节点后看 `allsubtitle` 一眼就知道。没有字幕时不要退回学科判断，先转写：

1. 进节点（照 §1），**先别点播放**：读 `video.currentSrc` 拿到签名直链（`s2.cldisk.com/.../sd.mp4?at_=…`）。
2. 后台起 `python scripts/asr_mimo.py --source "<url>" --chunk-seconds 90 --out runs/<task>/asr/<section>.txt`，
3. 同时按 §1 正常静音起播、按平台允许的最高倍速播放。
4. 播到 `ended` 时转写一般已经完成（30 分钟视频约 40 秒转完），直接照 §4 打开章节测验，
   **对着转写原文作答**：每个数字、每个名词都在原文里能找到，和"有字幕"是同一条证据链。

- 转写墙钟 ≪ 播放时长，所以**不拖慢完成效率**；未完成节点同样适用（签名直链在页面加载时就有）。
- 开关在 `local/private.toml`：`[asr] enabled = true` 走上面这条；`false` 则回退旧流程
  （无字幕 → 学科判断并标 `low_confidence`，知识总结跳过这一节）。`asr_mimo.py` 会读这个开关，
  关掉时直接拒绝运行，除非显式 `--force`。
- 分块必须 90 秒：600 秒分块会让模型把同一段复读十几遍。
- 数据源无关：`allsubtitle` 返回 `[]` 才走这里，返回 SRT 就照旧用 `subtitle_evidence.py`。


## 1. 进节点 + 静音 + 选速 + 起播 + 拿字幕 URL（1 次调用）

把 `SECTION` 改成目标节号。返回的 `subs.srt` 为空就直接记“无字幕”，不要反复找。

```js
async (page) => {
  const SECTION = '1.2.1';
  const toc = page.frames().find(f => f.url().includes('/mooc2-ans/mycourse/studentcourse'));
  if (!toc) return { ok: false, reason: 'no-toc-frame' };
  const row = toc.locator('.chapter_item').filter({ hasText: SECTION }).first();
  if (!(await row.count())) return { ok: false, reason: 'no-row', section: SECTION };
  const rowText = (await row.innerText()).replace(/\s+/g, ' ').trim();
  await row.click();
  await page.waitForURL(/studentstudy/, { timeout: 25000 }).catch(() => null);
  await page.waitForTimeout(1500);
  let vf = null;
  for (let i = 0; i < 30 && !vf; i++) {
    vf = page.frames().find(f => f.url().includes('ananas/modules/video'));
    if (!vf) await page.waitForTimeout(500);
  }
  if (!vf) return { ok: false, reason: 'no-video-frame', rowText, url: page.url().slice(0, 120) };
  const v = vf.locator('video').first();
  await v.waitFor({ timeout: 15000 });
  let menu = [];
  const opener = vf.locator('.vjs-playback-rate').first();
  if (await opener.count()) {
    await opener.click().catch(() => null);
    await page.waitForTimeout(400);
    menu = await vf.locator('span.vjs-menu-item-text').evaluateAll(els => els.map(e => (e.innerText || '').trim()));
  }
  let rate = await v.evaluate(e => e.playbackRate);
  let rateSource = 'locked';
  const pick = ['2x', '1.5x', '1.25x'].find(x => menu.includes(x));
  if (pick) {
    const exact = new RegExp('^' + pick.replace('.', '\\.') + '$');
    await vf.locator('span.vjs-menu-item-text').filter({ hasText: exact }).first().click().catch(() => null);
    await page.waitForTimeout(500);
    rate = await v.evaluate(e => e.playbackRate);
    rateSource = rate > 1 ? 'menu' : 'menu-failed';
    if (rateSource === 'menu-failed') {
      await v.evaluate((r) => { const el = document.querySelector('video'); el.playbackRate = parseFloat(r); }, pick);
      await page.waitForTimeout(300);
      rate = await v.evaluate(e => e.playbackRate);
      rateSource = rate > 1 ? 'property' : 'rejected';
    }
  }
  await v.evaluate(e => { e.muted = true; e.volume = 0; });
  const big = vf.locator('.vjs-big-play-button').first();
  if (await big.count() && await big.isVisible().catch(() => false)) await big.click().catch(() => null);
  await v.evaluate(e => e.play().catch(() => null));
  let t = 0;
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(500);
    t = await v.evaluate(e => e.currentTime);
    if (t > 0.5) break;
  }
  const meta = await v.evaluate(e => ({ duration: e.duration, paused: e.paused, muted: e.muted, t: e.currentTime, src: (e.currentSrc || '').slice(0, 120) }));
  let subs = { allsubtitle: null, srt: [] };
  try {
    subs = await vf.evaluate(async () => {
      const url = performance.getEntriesByType('resource').map(e => e.name).find(u => u.includes('allsubtitle'));
      if (!url) return { allsubtitle: null, srt: [] };
      const list = await (await fetch(url, { credentials: 'include' })).json();
      const srt = [];
      const walk = (n) => {
        if (typeof n === 'string') { if (/^https?:\/\/.*\.srt(\?|$)/i.test(n)) srt.push(n); }
        else if (n && typeof n === 'object') Object.values(n).forEach(walk);
      };
      walk(list);
      return { allsubtitle: url, srt: [...new Set(srt)] };
    });
  } catch (e) { subs = { error: String(e).slice(0, 100) }; }
  return { ok: true, section: SECTION, rowText, url: page.url().slice(0, 100), menu, rate, rateSource, meta, subs };
}
```

> 属性写入后必须读回：读回不是 `pick` 就记 `rejected`，按实际速率播。锁速课程菜单里没有 `2x/1.5x/1.25x` 时不会进入这个分支，`rateSource` 直接是 `locked`。
>
> 下面的 `page.frames().find(...)` **只返回第一个播放器**。多视频节要把
> `page.frames().filter(f => f.url().includes('ananas/modules/video'))` 全部取出来逐个播到 `ended`；
> 其中 `duration === null` 的那个通常就是还没被激活的第二个视频（见 §0 的多视频说明）。

## 2. 观察器（每次 1 调用，175 秒）

返回 `ended` / `popup` / `paused` / `tip` / `timeout`；`timeout` 直接再发一次，不要加 sleep 轮询。

```js
async (page) => {
  const vf = page.frames().find(f => f.url().includes('ananas/modules/video'));
  if (!vf) return { reason: 'no-video-frame' };
  return await vf.evaluate(async () => {
    const BUDGET = 175000;
    const start = performance.now();
    const v = document.querySelector('video');
    if (!v) return { reason: 'no-video' };
    const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).display !== 'none'; };
    while (performance.now() - start < BUDGET) {
      if (v.ended) return { reason: 'ended', t: v.currentTime, duration: v.duration };
      if (vis(document.querySelector('.ans-videoquiz'))) return { reason: 'popup', t: v.currentTime, duration: v.duration };
      if (vis(document.querySelector('a.writeNote_vid_blue'))) return { reason: 'tip', t: v.currentTime, duration: v.duration };
      if (v.paused) return { reason: 'paused', t: v.currentTime, duration: v.duration };
      await new Promise(r => setTimeout(r, 2000));
    }
    return { reason: 'timeout', t: v.currentTime, duration: v.duration, paused: v.paused, rate: v.playbackRate };
  });
}
```

- `paused` + 页面有 `a.writeNote_vid_blue`：点「知道了」再 `play()`，不要重新进节点。
- `popup`：进入下面的弹题流程。

## 3. 弹题：先读，再答（2 次调用）

第一次只读题面和选项，带回模型；用字幕 `find`/`gate` 或学科判断决定选项下标（0 起）。

```js
async (page) => {
  const vf = page.frames().find(f => f.url().includes('ananas/modules/video'));
  if (!vf) return { ok: false, reason: 'no-video-frame' };
  return await vf.evaluate(() => {
    const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).display !== 'none'; };
    const q = document.querySelector('.ans-videoquiz');
    if (!vis(q)) return { ok: false, reason: 'no-visible-popup' };
    const lines = (q.innerText || '').replace(/[ \t]+/g, ' ').split('\n').map(s => s.trim()).filter(Boolean);
    const opts = [...q.querySelectorAll('li.ans-videoquiz-opt')].map((li, i) => ({
      i, text: (li.innerText || '').replace(/\s+/g, ' ').trim(),
      checked: (li.querySelector('input[type=radio]') || {}).checked || false
    }));
    const v = document.querySelector('video');
    return { ok: true, lines: lines.slice(0, 12), opts, paused: v.paused, t: v.currentTime };
  });
}
```

第二次：点 `input[type=radio]`、核对 checked、点**提交**（优先唯一 id `#videoquiz-submit`；只有类选择器时取 `a.ans-videoquiz-submit` 里文本为「提交」且可见的第一个，同类里还有隐藏的「提交中」），
必要时点 `.ans-videoquiz-continue`，再起播并直接续一段 175 秒观察。

```js
async (page) => {
  const IDX = 3; // 0-based
  const vf = page.frames().find(f => f.url().includes('ananas/modules/video'));
  if (!vf) return { ok: false, reason: 'no-video-frame' };
  const read = await vf.evaluate((idx) => {
    const q = document.querySelector('.ans-videoquiz');
    if (!q) return { ok: false, reason: 'no-popup' };
    const li = [...q.querySelectorAll('li.ans-videoquiz-opt')][idx];
    if (!li) return { ok: false, reason: 'no-option', idx };
    const radio = li.querySelector('input[type=radio]');
    if (radio && !radio.checked) radio.click();
    return { ok: true, checked: [...q.querySelectorAll('input[type=radio]')].map(r => r.checked) };
  }, IDX);
  if (!read.ok) return read;
  const sub = vf.locator('a.ans-videoquiz-submit').filter({ hasText: '提交' }).first();
  const subVisible = await sub.isVisible().catch(() => false);
  if (subVisible) await sub.click().catch(() => null);
  await page.waitForTimeout(1500);
  const state = await vf.evaluate(() => {
    const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).display !== 'none'; };
    return { popup: vis(document.querySelector('.ans-videoquiz')), continueVisible: vis(document.querySelector('.ans-videoquiz-continue')) };
  });
  if (state.popup && state.continueVisible) await vf.locator('.ans-videoquiz-continue').first().click().catch(() => null);
  await page.waitForTimeout(800);
  const v = vf.locator('video').first();
  await v.evaluate(e => e.play().catch(() => null));
  const obs = await v.evaluate(async () => {
    const BUDGET = 175000;
    const start = performance.now();
    const el = document.querySelector('video');
    const vis = (x) => { if (!x) return false; const r = x.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(x).display !== 'none'; };
    while (performance.now() - start < BUDGET) {
      if (el.ended) return { reason: 'ended', t: el.currentTime };
      if (vis(document.querySelector('.ans-videoquiz'))) return { reason: 'popup', t: el.currentTime };
      if (el.paused) return { reason: 'paused', t: el.currentTime };
      await new Promise(r => setTimeout(r, 2000));
    }
    return { reason: 'timeout', t: el.currentTime, duration: el.duration };
  });
  return { ok: true, read, subVisible, state, obs };
}
```

- 页面不显示弹题判分；`.spanHas` / `.spanNot` 的静态文案（如「回答正确」）**不是**判定，提交前后都可能存在，不要当成绩。
- 弹题不改变任务点；任务点只看目录行尾数字。

## 4. 章节测验：证据模式只读（1 次浏览器 + 1 次 OCR）

视频结束后**不要先回目录**。同一个 `studentstudy` 页面点「章节测验」，读完题再一次性回目录；
否则 `a.subBack` 会替换页面，你得再进一次节点（预跑里多花了 4–6 次调用）。

```js
async (page) => {
  const SHOT = 'C:/path/to/repo/runs/<task>/quiz-1.2.1.png'; // 绝对路径，改成本次 run 目录
  const fr = page.frames().find(f => f.url().includes('studentstudy'));
  if (!fr) return { ok: false, reason: 'no-studentstudy-frame' };
  const tab = fr.locator('li#dct2').first();
  if (await tab.count()) await tab.click().catch(() => null);
  else {
    const span = fr.locator('span.spanText').filter({ hasText: '章节测验' }).first();
    if (await span.count()) await span.click().catch(() => null);
  }
  let qf = null;
  for (let i = 0; i < 20 && !qf; i++) {
    qf = page.frames().find(f => /mooc-ans\/work\/doHomeWorkNew/.test(f.url()));
    if (!qf) await page.waitForTimeout(500);
  }
  if (!qf) return { ok: false, reason: 'no-quiz-frame', frames: page.frames().map(f => f.url().slice(0, 80)).filter(Boolean) };
  await qf.locator('body').screenshot({ path: SHOT, timeout: 20000 }).catch(() => null);
  const meta = await qf.evaluate(() => {
    const g = (id) => (document.querySelector(id) || {}).value || null;
    const timu = [...document.querySelectorAll('.TiMu')].map((t, i) => {
      const lis = [...t.querySelectorAll('li')].filter(li => li.getAttribute('qid'));
      return {
        idx: i + 1,
        qid: lis.length ? lis[0].getAttribute('qid') : null,
        qtype: lis.length ? lis[0].getAttribute('qtype') : null,
        data: lis.map(li => { const s = li.querySelector('span[data]'); return s ? s.getAttribute('data') : null; }),
        labels: lis.map(li => { const l = li.querySelector('label'); return l ? (l.innerText || '').trim() : null; }),
        raw: (t.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 110)
      };
    });
    return { workId: g('#workId'), workAnswerId: g('#workAnswerId'), addTimes: g('#addTimes'), limitWorkSubmitTimes: g('#limitWorkSubmitTimes'), timu, bodyH: document.body.scrollHeight, innerW: window.innerWidth };
  });
  return { ok: true, shot: SHOT, meta };
}
```

- **不点任何 `li[qid]`、不点「提交」**。证据模式只读；是否提交由 `private.toml` 的 `mode`/`submit` 决定，且必须已有授权。
- 完成模式要提交时：先等 `.TiMu` 出现再截图/作答（帧 URL 会先于内容出现，空帧上点 `.btnSubmit` 无响应）；确认框 `#workpop a.jb_btn` 的可见副本在 **studentstudy 帧**；多选隐藏 `input[name=answer<qid>]` 存 `ABC`（无逗号）。
- 打开答题页会生成 `#workAnswerId`，平台“学习记录 → 章节测验详情”里会标成**已查看**（没有分数、不是已完成）。它不等于提交，也不等于得分。
- 只读打开后应记录 `#addTimes=0`、`#limitWorkSubmitTimes=100`，核对有无提交/start 请求及任务点变化。已观察到**打开本身没有消耗提交次数**的情形。仍会留下“已查看”；限次=1 的课未单独验证。只读前先看限次说明，打开后不要重开；不想留下查看记录就别打开。
- 截图后跑 OCR（窄页面直接打印全部行）：

```powershell
$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
python scripts/quiz_ocr.py runs/<task>/quiz-1.2.1.png --json --out runs/<task>/ocr-1.2.1.json
```

## 5. 回目录 + 读任务点（1 次调用）

`page.goBack()` 实测回不到目录；用平台自己的 `a.subBack`（它的 href 是本次新生成的目录地址，不是手拼链接）。

```js
async (page) => {
  const href = await page.evaluate(() => { const a = document.querySelector('a.subBack'); return a ? a.href : null; });
  if (!href) return { ok: false, reason: 'no-subBack' };
  await page.goto(href, { waitUntil: 'domcontentloaded' }).catch(() => null);
  await page.waitForTimeout(4000);
  let f = null;
  for (let i = 0; i < 10 && !f; i++) {
    f = page.frames().find(x => x.url().includes('/mooc2-ans/mycourse/studentcourse'));
    if (!f) await page.waitForTimeout(700);
  }
  if (!f) return { ok: false, reason: 'no-toc-frame', url: page.url().slice(0, 120) };
  const rows = await f.locator('.chapter_item').evaluateAll(els => els
    .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
    .filter(t => /^\d+(\.\d+)*\s/.test(t)));
  const job = await page.evaluate(() => {
    const el = document.querySelector('.maskDiv.jobCountDiv');
    if (!el) return { present: false };
    const r = el.getBoundingClientRect();
    return { present: true, w: Math.round(r.width), h: Math.round(r.height) };
  });
  return { ok: true, url: page.url().slice(0, 120), rows, job };
}
```

`rows` 里目标节的行尾数字就是剩余任务点；要跑 `toc_status.py` 的数字口径，另存一次 aria 快照：

> **判归零只读 `span.catalog_points_yi`**（完成行整个 span 消失），不要用「行尾有没有数字」判断：
> 标题自己可能以数字结尾（`6.3.3 激光SLAM-2`），内联正则 `/(\d+)\s*$/` 会把「2」当成剩余 2 点，
> 凭空造出一个幽灵任务点。`toc_status.py` 的 `TRAILING` 要求数字前有空白，没有这个问题。


```powershell
python scripts/toc_status.py runs/<task>/toc-after.yml --prefix 1.2
```

快照落在 MCP 的输出目录（`%USERPROFILE%\.dsh\profiles\desktop` 之类），先 `Copy-Item` 到本次 `runs/`。

驱动自己落盘的 `toc-*.json`（`{"rows":[{"sec","name","pt"}]}`）不用转快照，直接当闸门：

```powershell
python scripts/toc_status.py --rows runs/<task>/toc-final.json --fail-if-unfinished
```

> 刚提交完读到的那份 `toc-after` 不算数：点数 span 可能还没渲染掉。**批末重读一次目录**，
> 目标节 `pt` 全为 `null`、`UNFINISHED_TASKS=0` 才算这批真清了。

## 6. 先写证据，再汇报

写 `runs/<task>/evidence.json`，至少包含：`mode`、`authorization`、`course`、`section`、`video`（时长/倍率/`rate_source`/`ended`/观察器次数/字幕结论）、
`popup`（题干/选择/证据）、`quiz`（题数/`submitted`/`decision`/是否点过选项）、`platform`（`toc_before`/`toc_after` 任务点）、`cost`、`deviations`。
结构见 [状态与交接](state.md) 的 evidence 段；用下面的检查器在返回前过一遍：

```powershell
python scripts/check_evidence.py runs/<task>/evidence.json --require-readonly
```

## 预算与偏差

| 动作 | 浏览器/命令调用 |
|---|---|
| 进节点 + 起播 + 字幕 | 1 |
| 观察器 | `ceil(视频秒数 / 175)` |
| 弹题（有） | 2 |
| 章节测验只读（打开 + 截图读元数据） | 1 |
| OCR + 证据检查 | 1–2 |
| 回目录 + 读任务点 | 1 |

浏览器调用应落在 **8–10 次**；冷启动会话再加读文档/写证据/汇报，总计 **≤20 次**。
这是目标，不是保证；实际成本还包含读取配置、证据检查、快照核验、写证据和汇报。超预算时先检查重复导航和探索。
