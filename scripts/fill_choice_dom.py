#!/usr/bin/env python3
"""
选择题填写模板：通过 span.parentElement.click() 触发原生事件链。
2026-06-14 实测：40/40 全部稳定生效。

原理：click() → jQuery 事件处理器 → saveSingleSelect(this, qid) → addChoice() + submitForm()
全程由页面原生逻辑驱动，不会出现 this 上下文错误或 AJAX 挂起。

用法：
    # answers.json 格式: [{"questionId": "889029064", "answer": "B"}, ...]
    # 其中 "answer" 是 data 属性值（提交值），不是显示字母
    for answer_item in answers:
        qid = answer_item['questionId']
        target_value = answer_item['answer']  # data 属性值
        page.evaluate(f"""
            (() => {{
                const qDiv = document.getElementById('sigleQuestionDiv_{qid}');
                if (!qDiv) return 'no_div';
                const spans = qDiv.querySelectorAll('span.num_option');
                for (const span of spans) {{
                    if (span.getAttribute('data') === '{target_value}') {{
                        if (span.classList.contains('check_answer')) return 'skip';
                        span.parentElement.click();  // ← 唯一稳定方法
                        return 'clicked';
                    }}
                }}
                return 'nf';
            }})()
        """)
        page.wait_for_timeout(1500)  # 每题间隔 ≥800ms，推荐 1500ms

验证选中状态（用 data 属性值验证）：
    verify = json.loads(page.evaluate("""
        (() => {
            const r = [];
            document.querySelectorAll('div.questionLi').forEach(qDiv => {
                const qid = qDiv.getAttribute('data');
                let sel = null;
                qDiv.querySelectorAll('span.num_option').forEach(s => {
                    if (s.classList.contains('check_answer')) sel = s.getAttribute('data');
                });
                r.push({qid, sel});
            });
            return JSON.stringify(r);
        })()
    """))

⚠️ 不可靠方法（实测失败）：
- eval(optDiv.getAttribute('onclick'))：this 指向 window，AJAX 不触发
- saveSingleSelect(span, qid)：前 ~27 题正常，后续 AJAX 挂起卡死
- 纯 DOM 操作添加 check_answer class：刷新后丢失
"""
