# 题库：从已提交的结果页取数

本文件只在**节点已经提交、课程已经清零**之后使用：不提交、不重做、不点「再次答题」。
一个节点一次调用，读完立刻回目录并对比行尾——这是本阶段唯一的写盘来源。

平台事实与试点结论见 [现场笔记](field-notes.md) 的「结果页」一节；驱动的参数契约见
[工具数据格式](tool-data.md)。

## 0. 三个必须先记住的事实

1. **已提交测验点「章节测验」直接进结果页**（`mooc1.chaoxing.com/mooc-ans/work/selectWorkQuestionYiPiYue`，
   标题「查看已批阅作业」），不需要点「查看结果」，也不会出现提交按钮。实测两门课两次往返：
   `#addTimes` / `#limitWorkSubmitTimes` 字段在这张页面上**根本不存在**，目录行尾与 `jobCountDiv` 均无变化。
2. **结果页只保证给出「我的答案」**。`正确答案` 是否出现由教师设置决定；有的课程**没有开放**，页面的隐藏字段里也可能没有答案键。
   → 题库里 `correct` 只在两种情况有值：结果页明文给出，或该题满分（我的答案即正确答案）。
3. 题面与选项在**结果页是明文 DOM**（待作答页才用 `font-cxsecret` 混淆字形）。因此题库**不需要 OCR**，
   也不要再对截图跑识别。

## 1. 节点驱动（一次调用完成一个节点）

复制整段，只改开头四行常量。`SECTION` 必须与目录行文本前缀完全一致（如 `3.2.1`）。
把 `browser_run_code_unsafe` 的返回值原样写进 `runs/<task>/nodes/<course>/<section>.json`。

```js
async (page) => {
  const SECTION = '1.1';              // 目录行首的节号
  const COURSE = 'example-course';      // 课程键，仅用于回传
  const ACCOUNT = 'account-example';        // 账号别名，仅用于回传
  const CHANNEL = 'mcp__browser3';    // 本次使用的通道，仅用于回传
  const t0 = Date.now();
  const clean = (s) => (s || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n{2,}/g, '\n').trim();
  const tocFrame = () => page.frames().find((f) => f.url().includes('/mooc2-ans/mycourse/studentcourse'));
  const readRows = async () => tocFrame().locator('.chapter_item').evaluateAll((els) => els.map((e) => ({
    t: (e.innerText || '').replace(/\s+/g, ' ').trim(),
    p: [...e.querySelectorAll('span.catalog_points_yi')].map((s) => (s.innerText || '').trim())
  })));
  const rowsOf = (rows) => rows.filter((r) => /^\d+(\.\d+)*\s/.test(r.t));
  const back = async () => {
    const href = await page.evaluate(() => { const a = document.querySelector('a.subBack'); return a ? a.href : null; });
    if (!href) return { ok: false };
    await page.goto(href, { waitUntil: 'domcontentloaded' }).catch(() => null);
    await page.waitForTimeout(4000);
    for (let i = 0; i < 10 && !tocFrame(); i++) await page.waitForTimeout(700);
    return { ok: !!tocFrame() };
  };

  let toc = tocFrame();
  if (!toc) return { ok: false, reason: 'no-toc-frame', course: COURSE, section: SECTION };
  const rowsAll = await readRows();
  // Keep the unfiltered index: .nth() must address the same element list the rows came from.
  const idx = rowsAll.findIndex((r) => /^\d+(\.\d+)*\s/.test(r.t) && r.t.startsWith(SECTION + ' '));
  if (idx < 0) return { ok: false, reason: 'no-section-row', course: COURSE, section: SECTION, rows: rowsOf(rowsAll).map((r) => r.t).slice(0, 200) };
  const before = rowsAll[idx];
  const chapterRow = rowsAll.slice(0, idx).reverse().find((r) => /^\d+\s/.test(r.t));

  await toc.locator('.chapter_item').nth(idx).click();
  await page.waitForURL(/studentstudy/, { timeout: 25000 }).catch(() => null);
  await page.waitForTimeout(4000);
  const study = page.frames().find((f) => f.url().includes('studentstudy'));
  if (!study) return { ok: false, reason: 'no-studentstudy-frame', course: COURSE, section: SECTION, row: before };

  // 顺手记下播放器的字幕清单（复习文档用）；读不到就留空，绝不因此中断取题。
  let subs = { allsubtitle: null, srt: [], error: null };
  try {
    const vf = page.frames().find((f) => f.url().includes('ananas/modules/video'));
    if (vf) {
      subs = await vf.evaluate(async () => {
        const url = performance.getEntriesByType('resource').map((e) => e.name).find((u) => u.includes('allsubtitle'));
        if (!url) return { allsubtitle: null, srt: [], error: 'no-allsubtitle-request' };
        try {
          const list = await Promise.race([
            fetch(url, { credentials: 'include' }).then((r) => r.json()),
            new Promise((_, reject) => setTimeout(() => reject(new Error('subtitle-timeout')), 4000))
          ]);
          const srt = [];
          const walk = (n) => {
            if (typeof n === 'string') { if (/^https?:\/\/.*\.srt(\?|$)/i.test(n)) srt.push(n); }
            else if (n && typeof n === 'object') Object.values(n).forEach(walk);
          };
          walk(list);
          return { allsubtitle: url, srt: [...new Set(srt)], error: null };
        } catch (e) { return { allsubtitle: url, srt: [], error: String(e).slice(0, 80) }; }
      });
    }
  } catch (e) { subs = { allsubtitle: null, srt: [], error: String(e).slice(0, 80) }; }

  const tab = study.locator('li#dct2').first();
  if (await tab.count()) await tab.click().catch(() => null);
  else {
    const span = study.locator('span.spanText').filter({ hasText: '章节测验' }).first();
    if (await span.count()) await span.click().catch(() => null);
  }
  await page.waitForTimeout(4500);

  let qf = null;
  for (let i = 0; i < 24 && !qf; i++) {
    qf = page.frames().find((f) => /selectWorkQuestionYiPiYue|doHomeWorkNew/.test(f.url()));
    if (!qf) await page.waitForTimeout(500);
  }
  if (!qf) {
    const wentBack = await back();
    return { ok: false, reason: 'no-quiz-frame', course: COURSE, section: SECTION, row: before,
      frames: page.frames().map((f) => f.url().slice(0, 100)).filter(Boolean), wentBack };
  }
  const page_kind = /selectWorkQuestionYiPiYue/.test(qf.url()) ? 'selectWorkQuestionYiPiYue' : 'doHomeWorkNew';
  if (page_kind !== 'selectWorkQuestionYiPiYue') {
    const wentBack = await back();
    return { ok: false, reason: 'not-submitted-quiz', course: COURSE, section: SECTION, row: before, wentBack };
  }

  const data = await qf.evaluate(() => {
    const clean = (s) => (s || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n{2,}/g, '\n').trim();
    const body = (document.body.innerText || '');
    const meta = body.match(/题量[:：]\s*(\d+)\s*满分[:：]\s*([\d.]+)/);
    const attempt = body.match(/第(\d+)次作答\s*本次成绩([\d.]+)分/);
    const title = body.match(/已完成\s*\n([^\n]+)\n/);
    const questions = [...document.querySelectorAll('.TiMu')].map((t, i) => {
      const typeEl = t.querySelector('.newZy_TItle');
      const typeText = clean(typeEl ? typeEl.innerText : '');
      let stem = clean((t.querySelector('.qtContent') || {}).innerText || '');
      if (typeText && stem.indexOf(typeText) === 0) stem = stem.slice(typeText.length).trim();
      const options = [...t.querySelectorAll('ul.qtDetail > li')].map((li) => {
        const iEl = li.querySelector('i');
        const aEl = li.querySelector('a');
        return { key: clean(iEl ? iEl.innerText : '').replace(/[、.．]\s*$/, '').trim(), text: clean(aEl ? aEl.innerText : li.innerText) };
      });
      const answerEl = t.querySelector('.myAnswer .answerCon') || t.querySelector('.answerCon');
      const scoreEl = t.querySelector('.answerScore .scoreNum') || t.querySelector('.scoreNum');
      const markEl = t.querySelector('.answerScore .CorrectOrNot span') || t.querySelector('.CorrectOrNot span');
      const correct = (t.innerText || '').match(/正确答案[：:]\s*([^\n]+)/);
      const score = scoreEl ? parseFloat(clean(scoreEl.innerText)) : null;
      return {
        idx: i + 1,
        qid: t.getAttribute('data') || (t.id || '').replace('question', ''),
        qtype_text: typeText,
        stem,
        options,
        my_answer: clean(answerEl ? answerEl.innerText : ''),
        correct: correct ? clean(correct[1]) : null,
        score: isNaN(score) ? null : score,
        mark: markEl ? markEl.className : null
      };
    });
    return {
      meta: {
        question_count: meta ? +meta[1] : null,
        full_score: meta ? +meta[2] : null,
        attempt: attempt ? +attempt[1] : null,
        total_score: attempt ? +attempt[2] : null,
        title: title ? clean(title[1]) : null
      },
      fields: {
        add_times: (document.querySelector('#addTimes') || {}).value || null,
        limit_work_submit_times: (document.querySelector('#limitWorkSubmitTimes') || {}).value || null,
        submit_button: !!document.querySelector('.btnSubmit'),
        timu: questions.length
      },
      answer_visible: /正确答案/.test(body),
      body_head: clean(body).slice(0, 200),
      questions
    };
  });

  const url = new URL(qf.url());
  const wentBack = await back();
  const rowsAfter = tocFrame() ? await readRows() : [];
  const after = rowsOf(rowsAfter).find((r) => r.t.startsWith(SECTION + ' ')) || null;
  return {
    schema_version: 1,
    kind: 'quiz-bank-capture',
    course: COURSE,
    account: ACCOUNT,
    channel: CHANNEL,
    section: SECTION,
    section_title: before.t || data.meta.title,
    chapter: chapterRow ? chapterRow.t : null,
    page: page_kind,
    page_path: url.pathname,
    work_id: url.searchParams.get('workId'),
    work_answer_id: url.searchParams.get('workAnswerId'),
    answer_visible: data.answer_visible,
    meta: data.meta,
    fields: data.fields,
    questions: data.questions,
    pagination_suspected: !!data.meta.question_count && data.meta.question_count !== data.questions.length,
    toc: { before, after, changed: !!after && (after.t !== before.t || after.p.join() !== before.p.join()) },
    body_head: data.body_head,
    subs,
    went_back: wentBack,
    elapsed_ms: Date.now() - t0,
    captured_at: new Date().toISOString()
  };
}
```

要点：

- `ok:false` 的返回（`no-toc-frame` / `no-section-row` / `no-quiz-frame` / `not-submitted-quiz`）**不是**失败证据，
  是这一节没有可取的测验；原样落盘即可，`build` 会跳过非 capture 文件并在覆盖率里记缺失。
- `not-submitted-quiz` 是硬停手信号：说明这节测验没提交过，立即报告，不要作答、不要提交。
- `pagination_suspected: true` 表示题量对不上（分页/多页），该节要单独看，不要当整节入库。
- 一节点一次调用约 15 秒；同一标签、单执行器，节与节之间至少隔 4 秒（驱动内部已含等待）。

## 2. 归一化与合并

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/quiz_bank.py check runs/<task>/nodes/example-course/1.1.json
python scripts/quiz_bank.py build --nodes runs/<task>/nodes/example-course `
  --course example-course --title 示例课程 `
  --expected runs/<task>/expected-example-course.json
```

- `check` 只做结构自检：`kind`、结果页类型、没有提交按钮、目录行尾未变、题量与题数一致。失败返回 2。
- `build` 读目录里所有 `*.json`，跳过非 capture，写出 `knowledge/<course>/bank.json` 与 `bank.md`；
  `knowledge/` 已 gitignore（题库是课程内容，不进公开仓库）。
- `--expected` 给的是「这一门课应该有测验的节号」清单，用来在 `coverage.missing_sections` 里点名缺哪节。

## 3. 字段口径（bank.json）

| 字段 | 含义 |
|---|---|
| `correct` | 结果页明文的正确答案；或该题满分时取「我的答案」 |
| `correct_source` | `page` / `derived_from_full_score` / `null`（平台未开放，不猜） |
| `verdict` | `correct` / `wrong` / `partial` / `unknown`，取自 `.CorrectOrNot span` 的 `marking_dui` / `marking_cuo` |
| `max_score` | 按满分÷题数均分推算（`max_score_source: equal_split`），不是平台逐题分值 |
| `answer_visible` | 本节结果页是否出现「正确答案」字样 |

答题记录仍以 `runs/` 里的 evidence 为准（`work_id` / `question_count` / `score` 在那里面）；题库只补题面与选项。

## 4. 知识总结（另一份文件）

题库与知识总结是两份文件，不要混：

- `bank.json` / `bank.md`：题目、选项、我的答案、得分——由本文件的流程产出。
- `knowledge.md`：这一节**讲了什么**（概念、判断依据、示例、结论）——由字幕写成，
  一节一个 note，再由 `scripts/knowledge_doc.py` 拼装。格式、质量判据和调用方式见
  [知识总结](knowledge.md)。

字幕在这里顺手取到（播放器帧里的 `allsubtitle`），也可以事后单独下：

```powershell
python scripts/subtitle_evidence.py fetch --url "<srt URL>" --out runs/<task>/subs/<section>.srt
```

> 曾经的 `review.md`（用选项词匹配字幕、只摘几个词当「要点」）已废弃：它摘出来的是
> `[00:01:17] 那么迫切需要一种高带宽` 这种残句，复习时没有信息量。应按原文组织客观知识，不能把零散选项词当作复习卡。
