# 章节导航：如何找到新章节的考试 URL

## 问题

不能直接构造考试 URL。每个章节的 `enc` 参数不同，直接访问会 403。必须通过课程目录导航。

## 课程目录结构

```
课程主页 (mooc2-ans)
  └── iframe#frame_content-zj (课程内容)
        └── .chapter_item[onclick*="toOld"]  ← 每个学习项目
              onclick="toOld('courseid', 'chapterId', 'clazzid', 0)"
```

## 步骤

### 1. 打开课程目录 iframe

```python
IFRAME_URL = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse?courseid=260523533&clazzid=139305075&cpi=482987859&ut=s&t=1781705019044&stuenc=8bf3a7b6c9a51d48cc37ad88cb13be5e"
page.goto(IFRAME_URL, wait_until="domcontentloaded", timeout=90000)
```

### 2. 查找章节测试项

```python
# 找所有"本章单元测试"项
test_items = page.evaluate("""(() => {
    const items = document.querySelectorAll('.chapter_item[onclick*="toOld"]');
    let results = [];
    for(const item of items) {
        const text = item.textContent.trim();
        if(text.includes('本章单元测试')) {
            results.push({
                id: item.id,
                text: text.substring(0, 60),
                onclick: item.getAttribute('onclick').substring(0, 100)
            });
        }
    }
    return JSON.stringify(results);
})()""")
```

输出示例：
```json
[
  {"id": "cur1111793129", "text": "2.5 本章单元测试", "onclick": "toOld('260523533', '1111793129', '139305075',0)"},
  {"id": "cur1111793001", "text": "3.3 本章单元测试", "onclick": "toOld('260523533', '1111793001', '139305075',0)"},
  {"id": "cur1111793021", "text": "4.5 本章单元测试", "onclick": "toOld('260523533', '1111793021', '139305075',0)"}
]
```

### 3. 从 onclick 提取 chapterId

```python
import re
onclick = "toOld('260523533', '1111793001', '139305075',0)"
match = re.search(r"toOld\('(\d+)',\s*'(\d+)',\s*'(\d+)'", onclick)
courseid, chapterId, clazzid = match.groups()
# chapterId = '1111793001'
```

### 4. 打开 study page

```python
STUDY_URL = f"https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId={chapterId}&courseId={courseid}&clazzid={clazzid}&cpi=482987859&enc=8371ab71309d072441dfa55ccec106e6&mooc2=1&hidetype=0&openc=ff680bcac7a344cffd20f2cf1c5c18c1"
```

> ⚠️ `enc` 和 `openc` 参数是 course 级别的（不是 chapter 级别），同一课程的所有章节可以复用。

### 5. 等待 exam frame 加载

```python
exam_frame = None
for i in range(20):
    for frame in page.frames:
        if 'doHomeWorkNew' in frame.url:
            exam_frame = frame
            break
    if exam_frame: break
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(3)
```

### 6. 从 frame URL 提取参数

exam_frame.url 示例：
```
https://mooc1.chaoxing.com/mooc-ans/work/doHomeWorkNew?courseId=260523533&workAnswerId=55062138&workId=50493755&api=1&knowledgeid=1111793001&classId=139305075&oldWorkId=a8c638b945d9428b8416f1233fdb9ccc&jobid=work-...&enc=76e29bbd4f12a58095c47a4394907ab6&cpi=482987859&mooc2=1&...
```

关键参数：
- `workAnswerId`: 本次作答 ID（重做后会变）
- `workId`: 试卷 ID（不变）
- `enc`: 章节级认证参数（不能跨章节复用）
- `knowledgeid`: 同 chapterId

## 章节编号规律

课程目录中测试项的编号格式是 `{章节序号}.{章节内序号}`：
- 2.5 = 第2章（质点运动学）第5项 = 本章单元测试
- 3.3 = 第3章（力与牛顿运动定律）第3项 = 本章单元测试
- 4.5 = 第4章（动量守恒和能量守恒）第5项 = 本章单元测试

章节编号和 chapterId 的映射关系需要从课程目录获取，无法推算。
