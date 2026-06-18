---
name: chaoxing-exam
description: 学习通严父 — 超星学习通考试自动化：视觉模型提取题目文字 → 主 Agent 解题 → 自动填写答案 → 重做满分。两步走，零容忍，不满分不罢休。
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

**HTML 结构**：
```
div.questionLi          # 每道题容器
  h3.mark_name          # 题号 + 题型 + 分值
    span                # "(单选题, 2.0 分)"
    div > p > img       # 题干图片（多数数学公式为图片）
  form
    input[type=hidden]  # questionId, type, typeName, answer
    div.stem_answer     # 选项容器
      div.clearfix      # 每个选项
        span.num_option # 选项字母 A/B/C/D，data 属性存值
        div.answer_p    # 选项内容（文字或图片）
    div.sub_que_div     # 填空题空位
      textarea          # 填空答案输入框
      iframe            # UEditor 富文本编辑器
```

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

#### 选择题：直接 DOM 操作

不能用 `parent.click()` 或调用 `saveSingleSelect()`（会触发 AJAX，在预览模式下失败导致状态重置）。

```javascript
const qDiv = document.getElementById('sigleQuestionDiv_' + qid);
qDiv.querySelectorAll('.saveSingleSelect').forEach(s => s.classList.remove('check_answer'));
qDiv.querySelectorAll('span.num_option').forEach(span => {
    if (span.textContent.trim() === targetLetter) {
        span.classList.add('check_answer');
        const hidden = qDiv.querySelector('input[name="answer' + qid + '"]');
        if (hidden) hidden.value = span.getAttribute('data');
    }
});
```

#### 填空题：UEditor API

不能直接写 `textarea.value` 或 `iframe.body.innerHTML`（UEditor 不认，关闭后丢失）。

```javascript
const editorId = 'answerEditor' + qid + '1';  // qid + 空位编号
const editor = UE.getEditor(editorId);
editor.setContent('<p>' + answer + '</p>');
editor.sync();

// 触发保存
const div = document.getElementById('sigleQuestionDiv_' + qid);
submitForm(true, $(div), function(){});
```

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

1. **选择题点击无效**：`parent.click()` 触发 AJAX 失败。必须直接 DOM 操作 `check_answer` class
2. **填空题关闭后丢失**：直接写 textarea 不经过 UEditor。必须用 `UE.getEditor().setContent()` + `.sync()`
3. **图片下载失败**：URL 带 `#` 片段需去掉
4. **视觉模型直接给答案不可靠**：必须两步分开
5. **视觉模型返回空结果**：prompt 中明确说"不要分析不要给答案"
6. **题目未加载**：必须充分滚动页面
7. **答案需复核**：视觉模型给的答案需主 Agent 复核，实测 50 题中有 3 题需要修正
8. **Markdown LaTeX 格式错误**：视觉模型输出的 LaTeX 需清理，检查 `$` 是否配对
9. **重做按钮不是所有章节都有**（2026-06-18 新增）：
   - "待完成"状态：没有重做按钮（首次未提交）
   - "已完成"状态：有重做按钮（可重做拿满分）
   - "待批阅"状态：可能没有重做按钮（填空题/简答题需人工批改）
   - 检查方法：`exam_frame.evaluate("document.body.innerText.includes('重做')")`
10. **重做后 JS 可能不加载**（2026-06-18 新增）：
   - 重做后 frame URL 带 `reEdit=2` 参数，可能导致 `btnBlueSubmit` 和 `UE` 为 `undefined`
   - 症状：填写选择题 OK（纯 DOM click），但提交失败（`btnBlueSubmit is not defined`）
   - 检查方法：`exam_frame.evaluate("typeof btnBlueSubmit")` 应返回 `'function'`
   - 如果为 `undefined`，该章重做提交会失败，应跳过或尝试刷新 frame
11. **视觉提取超长页面需分段**（2026-06-18 新增）：
   - 超过 8-10 道题时，全页截图分辨率低，视觉模型可能截断或遗漏后半部分题目
   - 解决：分两次调用视觉模型——"请识别上半部分（第1-N题）"和"请识别下半部分（第N+1-M题）"
   - 或提高截图分辨率：`page.screenshot(path=..., full_page=True)` 后用 `vision_analyze` 逐段识别
12. **frame URL 两种模式**（2026-06-18 新增）：
   - `doHomeWorkNew`：未完成/进行中的考试
   - `selectWorkQuestionYiPiYue`：已完成/待批阅的结果页（仍显示题目和答案）
   - 两者都有 `div.singleQuesId` 元素，但 `selectWorkQuestionYiPiYue` 上 `btnBlueSubmit` 可能为 `undefined`
   - 找 frame 时必须同时检查两种模式
13. **同一个 browser context 可做多章**（2026-06-18 新增）：
   - 不需要每章重新登录，CloakBrowser 持久化 context 保持所有 cookies
   - 每章用 `page = context.new_page()` 开新 tab，避免页面状态污染
   - 上一章的 tab 可以关闭（`page.close()`）或保留
