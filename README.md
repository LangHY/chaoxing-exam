# 学习通严父 🫡

> 视觉为眼，推理为脑。两步走，零容忍，不满分不罢休。

超星学习通（chaoxing.com）章节测试全自动化：**视觉模型提取题目 → Agent 解题 → 自动填写 → 提交 → 重做满分**。

## 工作原理

```
图片 ──→ 视觉模型 ──→ 文字 ──→ 主 Agent ──→ 答案 ──→ 自动填写
         "眼睛"              "大脑"              "手"
```

**为什么要分两步？**
- 视觉模型擅长看图识字，但数学推理不可靠（实测 50 题错 3 题）
- 主 Agent 擅长逻辑推理，但看不到图片
- 分开各取所长，准确率最高

## 快速开始

### 1. 安装依赖

```bash
pip install cloakbrowser beautifulsoup4
python -m cloakbrowser install
```

### 2. 配置视觉模型

在 `config.yaml` 中配置支持视觉的模型（如 mimo-v2-omni、GPT-4o 等）：

```yaml
custom_providers:
  - name: vision-provider
    base_url: https://your-api-endpoint/v1
    api_key: your-api-key
    model: your-vision-model
```

### 3. 运行

```bash
# 步骤 1: 登录并抓取页面（首次需手动登录，后续自动复用）
python scripts/extract_page.py --url "YOUR_EXAM_URL"

# 步骤 2: 解析题目结构
python scripts/parse_questions.py

# 步骤 3: 视觉提取题目文字（并发调用视觉模型）
python scripts/vision_extract.py

# 步骤 4: 主 Agent 解题（读取 vision_questions.md，生成 answers.json）

# 步骤 5: 自动填写答案
python scripts/fill_answers.py
```

## 详细工作流

### 步骤 1：登录并抓取页面

使用 CloakBrowser 持久化上下文保持登录态：

```python
from cloakbrowser import launch_persistent_context

context = launch_persistent_context("./profile", headless=False, humanize=True)
page = context.new_page()
page.goto(EXAM_URL, wait_until="domcontentloaded", timeout=90000)
```

### 步骤 2：解析题目结构

从 HTML 中提取题号、题型、题干（文字/图片 URL）、选项。

### 步骤 3：视觉提取

用视觉模型把图片内容转为文字。**关键 prompt**：

```
请完整识别其中的文字和数学公式，原样输出，不要分析、不要给答案。
```

- 并发调用（5 线程），50 题约 2 分钟
- 输出 `vision_questions.md` 供主 Agent 阅读

### 步骤 4：主 Agent 解题

主 Agent 读取 `vision_questions.md`，逐题分析，输出 `chaoxing_answers.md`（含解析 + 速查表）。

### 步骤 5：自动填写

**选择题**：直接 DOM 操作（不能用 click，会触发 AJAX 失败）

```javascript
qDiv.querySelectorAll('.saveSingleSelect').forEach(s => s.classList.remove('check_answer'));
targetSpan.classList.add('check_answer');
```

**填空题**：通过 UEditor API（不能直接写 textarea，关闭后丢失）

```javascript
UE.getEditor(editorId).setContent('<p>答案</p>');
UE.getEditor(editorId).sync();
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 选择题点击无效 | `click()` 触发 AJAX，预览模式失败 | 用 DOM 操作 `check_answer` class |
| 填空题关闭后丢失 | 直接写 textarea 不经过 UEditor | 用 `UE.getEditor().setContent()` + `.sync()` |
| 视觉模型直接给答案错 | 数学推理能力弱 | prompt 加"不要分析不要给答案" |
| 图片下载失败 | URL 带 `#` 片段 | 去掉 `#` 后的内容 |
| 题目未加载 | 页面没滚动完 | 循环 `scrollTo(bottom)` 直到高度稳定 |
| 登录态过期 | profile cookie 失效 | 删除 profile 目录重新登录 |

## 项目结构

```
chaoxing-exam/
├── README.md                   # 本文件
├── SKILL.md                    # Agent skill 定义（完整技术细节）
├── scripts/
│   ├── extract_page.py         # 登录 + 抓取页面
│   ├── parse_questions.py      # 解析题目结构
│   ├── vision_extract.py       # 视觉模型提取文字
│   ├── fill_choice_dom.py      # 选择题填写（DOM 操作）
│   └── fill_blank_ueditor.py   # 填空题填写（UEditor API）
└── examples/
    └── sample_output.md        # 示例输出
```

## 适用场景

- 超星学习通在线考试 / 整卷预览
- 题目含数学公式图片（线性代数、高等数学等）
- 支持判断题、单选题、填空题

## 注意事项

- ⚠️ **使用 mimo 模型的用户不建议接入 Claude Code**：mimo 视觉模型的输出格式和 token 特性与 Claude Code 的 ACP 协议兼容性较差，可能导致子任务解析异常。建议 mimo 用户直接使用 Hermes Agent 原生能力处理解题环节。

## License

MIT
