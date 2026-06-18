# answers.json 格式规范

## 格式

```json
[
  {"questionId": "888683258", "type": "single", "answer": "true"},
  {"questionId": "888683264", "type": "single", "answer": "false"},
  {"questionId": "888683278", "type": "single", "answer": "B"},
  {"questionId": "889029195", "type": "blank", "answer": "答案文本"}
]
```

**注意**：判断题的 `answer` 值是 `"true"` 或 `"false"`（对应 `data` 属性），不是 `"A"` / `"B"`。

## 关键：`answer` 字段的含义

对于选择题，`answer` 存储的是 `span.num_option` 的 **`data` 属性值**（提交值），**不是**显示的字母。

### 为什么？

超星页面的选项结构：
```html
<span data="A" class="num_option">A</span>  <!-- data 和显示一致 -->
<span data="D" class="num_option">B</span>  <!-- data 和显示不一致！ -->
<span data="B" class="num_option">C</span>  <!-- data 和显示不一致！ -->
<span data="C" class="num_option">D</span>  <!-- data 和显示不一致！ -->
```

页面随机打乱 `data` 属性值和显示字母的对应关系。`data` 属性值是实际提交到服务器的答案。

### 从 chaoxing_parse.py 的输出推导

解析脚本为每个选项存储：
- `letter`: 显示字母（如 "A"、"B"、"C"、"D"）
- `value`: data 属性值（如 "A"、"D"、"B"、"C"）

主 Agent 看到的题目选项按显示字母排列，选择后需要查找对应的 `value`：

```python
# 示例：主 Agent 选择 "C. 康拉德・费德勒"
# 在题目 JSON 中找到 letter="C" 的选项，取其 value
for opt in question['options']:
    if opt['letter'] == 'C':
        answer_value = opt['value']  # 可能是 "B"
        break
```

### 生成 answers.json 的正确代码

```python
answers = []
for q in questions:
    qid = q['id']
    answer_letter = answers_map[q['number']]  # 主 Agent 选择的显示字母
    for opt in q.get('options', []):
        if opt['letter'] == answer_letter:
            answers.append({
                'questionId': qid,
                'type': 'single',
                'answer': opt['value']  # 用 value，不用 letter！
            })
            break
```

## 验证时的匹配

填写脚本用 `span.getAttribute('data') === targetValue` 匹配。
验证脚本也用 `span.getAttribute('data')` 读取选中值，与 answers.json 比较。
**不要用 `span.textContent.trim()`**，那是显示字母，不一定等于提交值。
