# 学习通严父 🫡

> 视觉为眼，推理为脑。两步走，零容忍，不满分不罢休。

超星学习通（chaoxing.com）在线答题自动化 Agent Skill，适用于章节测试、随堂测验等非正式考试场景。从打开页面到满分收工，全程无需人工介入：

1. **导航**：从课程目录页自动找到章节测试入口，通过 iframe 链路穿透到考试页面（处理 enc 鉴权、frame 嵌套、JS 懒加载）
2. **提取**：保存考试页 HTML 解析题目结构（questionId、题型、选项 data 映射），同时全页截图送入视觉模型识别题干和选项中的数学公式，转为 LaTeX 文字
3. **解题**：主 Agent 读取完整题目文字，逐题推理生成答案（选择题输出显示字母，填空题输出数值/表达式）
4. **填写**：按显示字母匹配选项并触发原生点击事件（间隔 1.5s 防限流），填空题通过 UEditor API 写入并 sync
5. **提交**：调用 `btnBlueSubmit()` 弹出确认框，用 Playwright force click 点击 `#popok` 确认（jQuery 绑定的按钮，普通 click 无效）
6. **重做**：读取系统给出的标准答案，点击重做按钮，用正确答案重新填写并再次提交，直到满分

实测覆盖大学物理B课程全部 10 个章节测试，**9/10 章满分通过**。

---

## 设计思路

### 为什么要"两步走"？

```
截图 ──→ 视觉模型（眼睛）──→ 纯文字题目 ──→ 主 Agent（大脑）──→ 答案
         擅长 OCR / 识图              擅长逻辑推理 / 计算
         不擅长数学推理                看不到图片
```

单一模型直接看图答题，实测 50 题错 3 题。拆成"看"和"想"两步，各取所长，准确率显著提升。

- **视觉模型**的 prompt 明确要求：「不要分析、不要给答案，只输出文字」
- **主 Agent** 拿到完整文字后自由推理，不受 OCR 噪声干扰

### 为什么需要"重做"机制？

首次答题正确率约 65-75%（取决于题目难度）。但超星系统提交后会显示标准答案，所以：

1. 先提交一次（即使有错题）
2. 读取系统给出的标准答案
3. 用标准答案重做，直接拿满分

这就是"严父"的核心逻辑：**不指望一次全对，但保证最终满分**。

---

## 前置条件

| 组件 | 用途 | 安装方式 |
|------|------|----------|
| **Hermes Agent** | 主 Agent 框架（或任意支持 tool calling 的 LLM Agent） | [hermes-agent](https://hermes-agent.nousresearch.com) |
| **CloakBrowser** | 持久化浏览器上下文，保持登录态，绕过反爬 | `pip install cloakbrowser && python -m cloakbrowser install` |
| **Playwright** | 浏览器自动化（CloakBrowser 底层依赖） | 随 CloakBrowser 安装 |
| **BeautifulSoup4** | HTML 解析，提取题目结构 | `pip install beautifulsoup4` |
| **视觉子模型** | 图片 OCR，将公式截图转为 LaTeX 文字 | 在 Agent config 中配置 `vision` 模型 |

### 视觉模型配置

在 Hermes Agent 的 `~/.hermes/config.yaml` 中：

```yaml
custom_providers:
  - name: Hermes
    base_url: https://token-plan-cn.xiaomimimo.com/v1
    api_key: tp-xxx
    model: mimo-v2.5          # 支持图片输入

vision:
  provider: Hermes
  model: mimo-v2.5
```

> ⚠️ `mimo-v2.5-pro` 不支持图片输入，只能用 `mimo-v2.5` 或其他视觉模型（GPT-4o、Claude Vision 等）。

### 环境要求

- **操作系统**：macOS / Linux
- **Python**：3.9+
- **浏览器**：CloakBrowser 自带 Chromium，无需额外安装
- **网络**：需能访问 `mooc1.chaoxing.com` 和 `mooc2-ans.chaoxing.com`

---

## 完整运行流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                     学习通严父 · 完整 Loop                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ① 导航 ──────────────────────────────────────────────────────────   │
│  │  课程目录 → 找到章节 chapterId (解析 toOld onclick)                │
│  │  → Study Page → 滚动触发 iframe → exam frame 加载完成              │
│  │  → 验证 btnBlueSubmit 函数存在（JS 是否加载完毕）                   │
│  │                                                                    │
│  ② 提取 ──────────────────────────────────────────────────────────   │
│  │  保存 HTML → BeautifulSoup 解析题目结构                            │
│  │    ├─ questionId (div.singleQuesId[data])                          │
│  │    ├─ 题型（单选/填空/简答）                                        │
│  │    └─ 选项 data 属性映射（A→data值, B→data值, ...）                 │
│  │  全页截图 → 视觉模型识别                                            │
│  │    └─ prompt: "不要分析不要给答案，只输出文字"                       │
│  │  输出 vision_questions.md（完整题目 + LaTeX 公式）                  │
│  │                                                                    │
│  ③ 解题 ──────────────────────────────────────────────────────────   │
│  │  主 Agent 读取 vision_questions.md                                  │
│  │  逐题推理 → 生成答案 dict: {questionId: 显示字母}                   │
│  │                                                                    │
│  ④ 填写 + 提交 ───────────────────────────────────────────────────   │
│  │  for each question:                                                │
│  │    span.parentElement.click()  ← 按显示字母匹配，间隔 1.5s          │
│  │  暂存 → btnBlueSubmit() → Playwright force click #popok            │
│  │  等待 15 秒 → 读取成绩                                             │
│  │                                                                    │
│  ⑤ 重做满分 ──────────────────────────────────────────────────────   │
│  │  读取系统标准答案（正确答案字段）                                    │
│  │  点击"重做" → 确认弹窗 → 用标准答案重新填写                         │
│  │  再次提交 → 验证 100 分                                            │
│  │                                                                    │
│  ⑥ 循环 ──────────────────────────────────────────────────────────   │
│     下一章 → 回到 ①                                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 核心技术细节

### 1. iframe 链路（章节测试的关键）

章节测试不能直接打开考试 URL（缺少 `enc` 参数会返回 403）。必须通过嵌套 iframe 链路：

```
Study Page
  └─ iframe#iframe → Knowledge Cards
       └─ iframe(work) → doHomeWorkNew (考试页面)
```

```python
# 等待 exam frame 加载（需要滚动触发）
exam_frame = None
for i in range(20):
    for frame in page.frames:
        if 'doHomeWorkNew' in frame.url or 'selectWorkQuestion' in frame.url:
            exam_frame = frame
            break
    if exam_frame:
        break
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(3)

# 验证 JS 加载完毕
has_bbs = exam_frame.evaluate("typeof btnBlueSubmit")  # 应为 'function'
```

**所有操作必须在 `exam_frame` 上下文执行**，不能用 `page`，也不能直接打开考试 URL。

> 详见 `SKILL.md` 中"章节测试自动化完整流程"章节。

### 2. 选择题填写（唯一稳定方法）

```javascript
// ✅ 正确：按显示字母匹配 + parentElement.click()
const qDiv = document.querySelector('div.singleQuesId[data="' + qid + '"]');
const spans = qDiv.querySelectorAll('span.num_option');
for (const span of spans) {
    if (span.textContent.trim() === displayLetter) {   // ← 用 textContent，不用 data！
        if (span.classList.contains('check_answer')) return;  // toggle 保护
        span.parentElement.click();  // 触发原生事件链
        return;
    }
}
```

**为什么用 `textContent` 而不是 `data` 属性？**

重做后选项的 `data` 值会随机化。同一个选项显示 "A"，重做前 `data="C"`，重做后可能变成 `data="D"`。但 `textContent`（显示字母）始终不变。

**为什么用 `parentElement.click()`？**

| 方法 | 结果 |
|------|------|
| `eval(onclick)` | ❌ `this` 指向 `window`，AJAX 不触发 |
| `saveSingleSelect(span, qid)` | ❌ 前 27 题正常，之后 AJAX 挂起 |
| 纯 DOM 操作（改 class） | ❌ 页面显示对了但没保存 |
| `span.parentElement.click()` | ✅ 走原生事件链，40/40 稳定 |

**点击间隔**：每题 ≥ 1.5 秒，否则 AJAX 冲突。

### 3. 提交确认弹窗（#popok 的坑）

提交按钮的 onclick 是 `btnBlueSubmit()`，弹出确认弹窗。弹窗中的"提交"按钮（`#popok`）**没有 onclick 属性**，事件通过 jQuery `.on('click')` 绑定。

**直接访问考试 URL 时**，`dispatchEvent` 可以触发：

```javascript
const btn = document.getElementById('popok');
['mousedown', 'mouseup', 'click'].forEach(type => {
    btn.dispatchEvent(new MouseEvent(type, {
        bubbles: true, cancelable: true, view: window
    }));
});
```

**通过 iframe 访问时**，`dispatchEvent` 静默失败。必须用 Playwright force click：

```python
exam_frame.locator('#popok').click(force=True, timeout=5000)
```

### 4. 填空题填写（UEditor API）

不能直接写 `textarea.value`（UEditor 不认，关闭后丢失）。

```javascript
// editor ID 格式：answerEditor{questionId}{空位编号}
const editor = UE.getEditor('answerEditor' + qid + '1');
editor.setContent('<p>' + answer + '</p>');
editor.sync();  // 必须 sync 回 textarea
```

### 5. 重做流程

```python
# 1. 点击重做按钮
exam_frame.evaluate("""(() => {
    const a = document.querySelector('a[onclick*="redoTest"]');
    if(a) a.click();
})()""")

# 2. 确认弹窗（"之前答题内容会保留，确认重做？"）
# 弹窗可能在 page 或 frame 上，两个都要试
for target in [page, exam_frame]:
    target.evaluate("""(() => {
        for(const b of document.querySelectorAll('a,button')){
            if(b.textContent.trim()==='确定' && b.offsetParent!==null)
                { b.click(); return; }
        }
    })()""")

# 3. 重新查找 frame（重做后 frame URL 可能变化）
# 4. 用标准答案重新填写
# 5. 再次提交
```

### 6. HTML 选择器（2026-06 版本）

```
div.singleQuesId[data="questionId"]   ← 每道题容器（不是旧版的 div.questionLi）
  span.num_option                      ← 选项（textContent=显示字母, data=提交值）
  span.num_option.check_answer         ← 已选中的选项
  .newZy_TItle                         ← 题型标签（【单选题】等）
```

### 7. 超星反爬措施

- **字体反爬**：页面用 `font-cxsecret` 自定义字体替换中文，`innerText` 返回乱码。不影响视觉截图识别。
- **AJAX 限流**：选择题点击间隔 < 800ms 会导致请求冲突。
- **enc 参数**：每个章节的考试 URL 需要特定的 `enc` 参数，直接构造 URL 会 403。

---

## 实测数据

大学物理B课程，10 个章节测试：

| 章节 | 主题 | 题数 | 首次分数 | 重做后 |
|------|------|------|----------|--------|
| 2.5 | 质点运动学 | 11 | 72.8 | **100** ✅ |
| 3.3 | 力与牛顿运动定律 | 10 | 70 | **100** ✅ |
| 4.5 | 动量守恒和能量守恒 | 13 | 待批阅 | — ⚠️ |
| 6.4 | 角动量/振动 | 10 | 70 | **100** ✅ |
| 7.8 | 机械波 | 10 | 70 | **100** ✅ |
| 8.7 | 静电学 | 15 | 53.3 | **100** ✅ |
| 9.5 | 静电学（续） | 3 | 66.7 | **100** ✅ |
| 10.5 | 磁场 | 10 | 80 | **100** ✅ |
| 11.4 | 电磁感应 | 8 | 25 | **100** ✅ |
| NEW | 狭义相对论 | 7 | 85.7 | **100** ✅ |

**总结**：首次平均正确率 65-75%，重做后 9/10 章满分。唯一未满分的 4.5 处于"待批阅"状态（系统不提供重做按钮）。

---

## 已知问题

1. **重做后 JS 加载失败**：部分章节重做后 `btnBlueSubmit` 和 `UE` 为 `undefined`，导致提交失败。可能与 `reEdit=2` URL 参数有关。
2. **"待批阅"状态无法重做**：含填空题的章节提交后进入"待批阅"，系统不显示重做按钮。
3. **frame URL 两种模式**：`doHomeWorkNew`（进行中）和 `selectWorkQuestionYiPiYue`（已完成），两者都有题目 DOM 但 JS 状态不同。
4. **填空题答案格式**：系统可能要求特定格式（如 "50" vs "50 m/s"），不同题目不一致。

---

## 适用场景

- ✅ 超星学习通章节测试 / 在线考试
- ✅ 题目含数学公式图片（物理、高数、线代等）
- ✅ 单选题、多选题、判断题、填空题
- ✅ 自动重做拿满分
- ⚠️ 简答题/论述题可填写，答案质量取决于主 Agent
- ❌ 不支持视频题、实操题、上传文件题

## 注意事项

- ⚠️ **使用 mimo 模型的用户不建议接入 Claude Code**：mimo 视觉模型的输出格式和 token 特性与 Claude Code 的 ACP 协议兼容性较差，可能导致子任务解析异常。建议 mimo 用户直接使用 Hermes Agent 原生能力处理解题环节。

---

## 项目结构

```
chaoxing-exam/
├── README.md                       # 本文件
├── SKILL.md                        # Agent Skill 定义（完整技术细节 + 22 条陷阱）
├── references/
│   ├── answer-json-format.md       # 答案 JSON 格式规范
│   └── chapter-navigation.md       # 课程目录导航流程
└── scripts/
    ├── fill_choice_click.py        # 选择题 click() 方法模板
    ├── fill_choice_dom.py          # 选择题 DOM 操作模板（旧版）
    └── fill_blank_ueditor.py       # 填空题 UEditor API 模板
```

## License

MIT
