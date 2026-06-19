---
name: chaoxing-exam
description: 学习通严父 — 超星学习通在线答题自动化：视觉模型提取题目文字 → 主 Agent 解题 → 自动填写答案 → 重做满分。适用于章节测试、随堂测验等非正式考试场景。两步走，零容忍，不满分不罢休。
tags: [chaoxing, exam, vision, cloakbrowser, automation, education, two-step]
---

# 学习通严父 🫡

> 视觉为眼，推理为脑。两步走，零容忍，不满分不罢休。

超星学习通（chaoxing.com）章节测试全自动化工具。

## 概述

从超星学习通考试页面自动抓取题目、视觉提取文字、主 Agent 解题并填写答案。

**两步工作流**：
1. 视觉模型 = 眼睛：看图片 → 输出文字
2. 主 Agent = 大脑：读文字 → 分析解题 → 生成答案

**支持题型**：判断题、单选题、填空题

**技术栈**：CloakBrowser（持久化登录）+ 视觉模型（图片文字提取）+ DOM 操作/UEditor API（填写答案）

## 前置条件

```bash
pip3 install cloakbrowser beautifulsoup4
python3 -m cloakbrowser install
```

> ⚠️ **使用 mimo 模型的用户不建议接入 Claude Code**：mimo 视觉模型的输出格式和 token 特性与 Claude Code 的 ACP 协议兼容性较差，可能导致子任务解析异常。建议 mimo 用户直接使用 Hermes Agent 原生能力处理解题环节。

## 完整工作流程

### 步骤 1：登录并抓取页面

使用 CloakBrowser 持久化上下文，首次需手动登录，后续自动复用。

```python
from cloakbrowser import launch_persistent_context

context = launch_persistent_context("./profile", headless=False, humanize=True)
page = context.new_page()
page.goto(EXAM_URL, wait_until="domcontentloaded", timeout=90000)
```

**关键点**：
- 登录检测：检查 URL 是否包含 `passport` 或 `login`
- 滚动加载：循环 `scrollTo(bottom)` 直到页面高度稳定
- 保存原始 HTML 和截图供后续解析

### 步骤 2：解析题目结构

用 BeautifulSoup 从 HTML 中提取结构化数据。

**HTML 结构**（2026-06 实测，新版页面）：
```
div.singleQuesId[data="questionId"]   # 每道题容器（⚠️ 不是 div.questionLi）
  div.TiMu
    div.Zy_TItle
      i                                 # 题号
      div.font-cxsecret                 # 题干（文字/图片混排）
        span.newZy_TItle                # "【单选题】"
        p / img                         # 题干文字和公式图片
    ul.Zy_ulTk
      div.clearfix                      # 每个选项
        span.num_option                 # 显示字母 A/B/C/D，data 属性存提交值
        div.answer_p                    # 选项内容
      div.blankItemDiv                  # 填空题空位（如有）
        textarea                        # 填空答案输入框
        div.edui-default                # UEditor 富文本编辑器
```

**⚠️ 关键选择器变化**（2026-06）：
- 旧版：`div.questionLi` → 新版：`div.singleQuesId`
- 先用 `page.evaluate("document.querySelectorAll('div.singleQuesId').length")` 确认题目数

### 步骤 3：视觉提取题目文字

用视觉模型把图片内容转为文字。**视觉模型只负责"看图输出文字"，不做解题判断。**

**核心原则**：视觉模型是"眼睛"，只看不判断；主 Agent 是"大脑"，负责解题。

**prompt 要点**：
- 明确说"不要分析、不要给答案"，避免视觉模型直接输出错误答案
- 要求"原样输出"，保留数学公式格式
- 选项图片单独发，让模型逐个识别

**并发策略**：
- 5 并发调用视觉 API，50 题约 2 分钟完成
- 保存到 `vision_extracted.json`，整理为 `vision_questions.md`

### 步骤 4：主 Agent 解题

主 Agent 读取 `vision_questions.md`，根据完整题目文字进行分析。

**输出格式**：生成 `chaoxing_answers.md`，包含：
- 每题的答案 + 一句话解析
- 底部答案速查表（便于快速填写）

**重要**：不要让视觉模型直接给答案，它擅长识别文字但数学推理不可靠。

### 步骤 5：填写答案

> 📖 详细答案 JSON 格式规范见 `references/answer-json-format.md`，特别是 `data` 属性值 vs 显示字母的区别。

**⚠️ 关键：选择题和填空题使用不同的机制**

#### 选择题：`span.parentElement.click()`（唯一稳定方法）

> ⚠️ **2026-06-14 实测结论**：三种方法中，只有 `click()` 全部 40 题稳定生效。

**✅ 推荐方法：按显示字母匹配 + `span.parentElement.click()`**

2026-06-17 更新：重做后选项的 `data` 属性值会随机化，**不能用 data 值匹配**。改用显示字母（textContent）匹配更可靠：

```javascript
const qDiv = document.querySelector('div.singleQuesId[data="' + qid + '"]');
const spans = qDiv.querySelectorAll('span.num_option');
for (const span of spans) {
    if (span.textContent.trim() === displayLetter) {  // 按显示字母匹配
        if (span.classList.contains('check_answer')) return;  // 已选中，跳过
        span.parentElement.click();  // 触发原生事件链
        return;
    }
}
```

**❌ 旧方法（重做后不可靠）**：用 `getAttribute('data') === targetValue` 匹配。
重做后 data 值会重新随机化，导致匹配失败（返回 NO_MATCH）。

**❌ 不可靠方法 1：`eval(optDiv.getAttribute('onclick'))`**
`this` 指向 `window`，AJAX 不触发。

**❌ 不可靠方法 2：直接调用 `saveSingleSelect(span, qid)`**
前 ~27 题正常，后续 AJAX 挂起。

**❌ 不可靠方法 3：纯 DOM 操作（添加 `check_answer` class）**
页面显示正确但不触发 AJAX 保存，刷新后丢失。

**⚠️ 点击间隔**：每题之间至少 800ms（推荐 1500ms），太快会 AJAX 冲突。

**⚠️ 点击是 toggle 操作**：点击已选中的选项会取消选中！脚本必须先检查 `span.classList.contains('check_answer')`，已正确则跳过。

#### 填空题/简答题/论述题：UEditor API + 保存按钮

不能直接写 `textarea.value` 或 `iframe.body.innerHTML`（UEditor 不认，关闭后丢失）。

**正确方法**：通过 UEditor API 设置内容并 sync，**然后点击保存按钮**：

```javascript
// editor ID：answerEditor{questionId}{空位编号}（⚠️ 不是 answer{questionId}）
const editorId = 'answerEditor' + qid + '1';  // 第1空
const editor = UE.getEditor(editorId);
editor.setContent('<p>' + answer + '</p>');     // 写入 UEditor
editor.sync();                                   // 同步回 textarea

// ⚠️ 必须点击保存按钮才能持久化！
const saveBtn = document.getElementById('save_' + qid);
if (saveBtn) saveBtn.click();
```

**UEditor editor ID 规则**：`answerEditor{questionId}{空位编号}`
- 例如 questionId=404896870，第1空 → editorId = `answerEditor4048968701`
- 先检查页面 HTML 中的 textarea/script 标签确认实际 ID

## 两步工作流原理

```
图片 ──→ 视觉模型 ──→ 文字 ──→ 主 Agent ──→ 答案
         "眼睛"              "大脑"
```

**为什么要分开**：
- 视觉模型擅长 OCR/图像理解，但数学推理不可靠（实测 50 题错 3 题）
- 主 Agent 擅长逻辑推理，但看不到图片
- 两步分开各取所长，准确率最高

## 批量章节测试自动化（2026-06-18 新增）

当用户要求"把所有章节测试都做完"时，按以下批量流程执行：

### 流程

1. **扫描所有章节**：从课程目录 iframe 获取所有 `本章单元测试` 的 chapterId
2. **逐章检查状态**：对每个 chapter，打开 study page，找到 exam frame，检查：
   - 是否有 exam frame（有些章节无 frame，跳过）
   - 状态是"待完成"（可做）还是"已完成/待批阅"（需检查重做按钮）
   - `btnBlueSubmit` 是否为 `function`（JS 是否加载）
3. **逐章执行**：对每个可做的章节，执行完整的 提取→视觉→解题→填写→提交→重做 流程
4. **汇总报告**：输出每章的成绩和状态

### 单章执行模板

```python
def do_chapter(page, chapter_id, answers):
    """单章完整流程：提取→填写→提交→检查→重做"""
    STUDY_URL = f"https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId={chapter_id}&courseId=...&clazzid=...&cpi=...&enc=...&mooc2=1&hidetype=0&openc=..."
    
    page.goto(STUDY_URL, ...)
    time.sleep(15)
    for i in range(15):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
    
    # 找 frame（两种 URL 模式都要检查）
    exam_frame = None
    for frame in page.frames:
        if 'doHomeWorkNew' in frame.url or 'selectWorkQuestion' in frame.url:
            try:
                if frame.evaluate("document.querySelectorAll('div.singleQuesId').length") > 0:
                    exam_frame = frame
                    break
            except: pass
    
    if not exam_frame: return "NO_FRAME"
    
    # 检查状态
    state = exam_frame.evaluate("document.body.innerText.substring(0, 100)")
    has_redo = exam_frame.evaluate("document.body.innerText.includes('重做')")
    has_bbs = exam_frame.evaluate("typeof btnBlueSubmit")
    
    if has_bbs != 'function': return "JS_NOT_LOADED"
    
    # 如果已完成且有重做按钮，先重做
    if ('已完成' in state or '待批阅' in state) and has_redo:
        # 点击重做 → 确认 → 等待 → 重新找 frame
        ...
    elif '已完成' in state and not has_redo:
        return "NO_REDO"
    
    # 填写答案
    for qid, letter in answers.items():
        exam_frame.evaluate(f"""...""")
        time.sleep(1.5)
    
    # 暂存 → 提交 → 确认
    exam_frame.evaluate("btnBlueSubmit()")
    time.sleep(3)
    exam_frame.locator('#popok').click(force=True, timeout=5000)
    time.sleep(15)
    
    # 获取成绩和标准答案
    final_text = exam_frame.evaluate("document.body.innerText")
    score = re.search(r'最终成绩([\d.]+)分', final_text)
    my_answers = re.findall(r'我的答案：\s*(\S+)', final_text)
    std_answers = re.findall(r'正确答案：\s*(\S+)', final_text)
    
    # 如果有错题且有重做按钮，用标准答案重做
    wrong = [i for i in range(len(my_answers)) if my_answers[i] != std_answers[i]]
    if wrong and '重做' in final_text:
        # 重做流程...
        pass
    
    return score.group(1) if score else "NO_SCORE"
```

### 批量执行注意事项

> 📖 实测批量结果和统计数据见 `references/batch-test-results.md`

1. **每章用同一个 browser context**：不需要每章重新登录，CloakBrowser 持久化 context 保持 cookies
2. **每章用 `page = context.new_page()`**：新开 tab 避免页面状态污染
3. **章节间不需要等待**：直接开新 tab 做下一章
4. **视觉提取分段**：题目超过 8 道时，截图可能太长导致视觉模型截断。分两次调用（上半部分 + 下半部分）
5. **跳过无 frame 的章节**：有些章节可能没有考试内容
6. **待批阅状态**：填空题/简答题提交后状态为"待批阅"（需人工批改），这些章节可能没有重做按钮

## 常见陷阱

1. **选择题唯一稳定方法是 `span.parentElement.click()`**：`eval(onclick)` 因 `this` 上下文错误导致 AJAX 不触发；`saveSingleSelect(span, qid)` 直接调用会在 ~27 题后卡死（AJAX 挂起）；纯 DOM 操作不持久。只有 `click()` 走原生事件链，40/40 实测稳定
2. **选择题点击间隔 ≥800ms**：太快会导致 AJAX 请求冲突或被限流，推荐 1500ms
3. **选择题点击是 toggle 操作**：点击已选中的选项会取消选中。脚本必须先用 `span.classList.contains('check_answer')` 检查当前状态，已正确则跳过
4. **`data` 属性 ≠ 显示文本，且重做后会随机化**（2026-06-17 更新）：
   - `span.num_option` 的 `textContent`（显示字母如 "A"）和 `getAttribute('data')`（提交值）**不一定相同**
   - **重做后 `data` 值会重新随机化**！同一个选项显示 "A"，重做前 data="C"，重做后可能变成 data="D"
   - **填写答案时必须用显示字母（textContent）匹配**，不能用 data 值匹配
5. **判断题的 data 值是 "true"/"false"**：不是 "A"/"B"
6. **选择器更新（2026-06）**：旧版 `div.questionLi` → 新版 `div.singleQuesId`
7. **视觉模型可能返回空结果**：部分图片（数学公式密集）视觉模型返回 0 字符。需重试或手动用 `vision_analyze` 补充
8. **视觉模型直接给答案不可靠**：必须两步分开：视觉只提文字，主 Agent 解题
9. **批量视觉提取用 asyncio 并发**：127 张图片串行 ~20 分钟，5 并发只需 ~2 分钟
10. **图片下载失败**：URL 带 `#` 片段需去掉
11. **题目未加载**：必须充分滚动页面（循环 `scrollTo(0, scrollHeight)` 直到高度稳定）
12. **登录态过期**：持久化上下文在 `~/.hermes/chaoxing_profile/`，过期需重新登录
13. **UEditor editor ID 格式**：实际为 `answerEditor{questionId}{空位编号}`（如 `answerEditor4048968701`），不是 `answer{questionId}`
14. **简答/论述题必须点击保存按钮**：UEditor 的 `setContent()` + `sync()` 不会自动保存到服务器，必须点击 `save_{questionId}` 按钮
15. **提交确认按钮 `#popok` 的点击方法取决于上下文**（2026-06-17 更新）：
    - 确认弹窗中"提交"按钮（`id="popok"`, `class="jb_btn jb_btn_92"`）**没有 onclick 属性**，事件通过 jQuery `.on('click', ...)` 绑定
    - **直接打开考试页**（URL 是 `doHomeWorkNew`）：`dispatchEvent` 有效
      ```javascript
      const btn = document.getElementById('popok');
      ['mousedown', 'mouseup', 'click'].forEach(type => {
          btn.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
      });
      ```
    - **通过 study page iframe 访问考试**：`dispatchEvent` **无效**（静默失败）。必须用 **Playwright locator force click**：
      ```python
      exam_frame.locator('#popok').click(force=True, timeout=5000)
      ```
16. **`btnBlueSubmit()` 弹出确认弹窗**：流程是 `btnBlueSubmit()` → 等3秒 → 点击 `#popok`
17. **重做流程**（2026-06-17 实测）：
    - 结果页有"重做"按钮，onclick=`redoTest()`，class=`jb_btn_bg`
    - 点击后弹出确认："之前答题内容会保留，确认重做？"→ 需点"确定"
    - **确认后页面内容变为"待完成"的答题页面，URL 不变**
    - 重做后选项的 `data` 属性值会重新随机化，必须用显示字母匹配
    - 重做后 **必须重新查找 frame 并验证 `typeof btnBlueSubmit === 'function'`**
18. **重做后 JS 可能不加载**（2026-06-18 实测）：
    - 重做后 frame URL 带 `reEdit=2` 参数，可能导致 `btnBlueSubmit` 和 `UE` 为 `undefined`
    - 症状：选择题填写 OK（纯 DOM click），但提交失败（`btnBlueSubmit is not defined`）
    - 如果 `typeof btnBlueSubmit !== 'function'`，该章重做提交会失败，应跳过
19. **frame URL 两种模式**（2026-06-18 实测）：
    - `doHomeWorkNew`：未完成/进行中的考试（`btnBlueSubmit` 通常可用）
    - `selectWorkQuestionYiPiYue`：已完成/待批阅的结果页（仍有题目 DOM）
    - 找 frame 时必须同时检查两种模式
20. **超星页面字体反爬**：`document.body.innerText` 返回乱码中文，不影响视觉截图识别
21. **超长题目页视觉提取需分段**（2026-06-18 实测）：
    - 超过 8 道题时，全页截图分辨率低，视觉模型可能截断后半部分
    - 解决：分两次调用——"请识别上半部分（第1-N题）"和"请识别下半部分（第N+1-M题）"
22. **章节测试不能直接用考试 URL**（缺 `enc` 参数会 403）：必须通过 study page → iframe 链路获取
