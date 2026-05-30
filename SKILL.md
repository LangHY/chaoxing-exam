---
name: chaoxing-exam
description: 超星学习通考试自动化：视觉模型提取题目文字 → 主 Agent 解题 → 自动填写答案。
tags: [chaoxing, exam, vision, cloakbrowser, automation, education, two-step]
---

# 超星学习通考试自动化

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

## 常见陷阱

1. **选择题点击无效**：`parent.click()` 触发 AJAX 失败。必须直接 DOM 操作 `check_answer` class
2. **填空题关闭后丢失**：直接写 textarea 不经过 UEditor。必须用 `UE.getEditor().setContent()` + `.sync()`
3. **图片下载失败**：URL 带 `#` 片段需去掉
4. **视觉模型直接给答案不可靠**：必须两步分开
5. **视觉模型返回空结果**：prompt 中明确说"不要分析不要给答案"
6. **题目未加载**：必须充分滚动页面
7. **答案需复核**：视觉模型给的答案需主 Agent 复核，实测 50 题中有 3 题需要修正
8. **Markdown LaTeX 格式错误**：视觉模型输出的 LaTeX 需清理，检查 `$` 是否配对
