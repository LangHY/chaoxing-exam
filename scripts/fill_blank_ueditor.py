#!/usr/bin/env python3
"""
填空题/简答题/论述题填写模板：通过 UEditor API 设置内容。

UEditor editor ID 规则（2026-06 实测）：
    ID = answerEditor{questionId}{空位编号}
    例：questionId=404896870，第1空 → editorId = answerEditor4048968701

    页面中的 textarea 和 UEditor 使用相同的 ID。
    HTML 中的 script 标签通常写：
        var answerEditor404896870_1 = UE.getEditor("answerEditor4048968701", {...});
    所以 editorId = "answerEditor" + questionId + "1"（第1空）

用法（CloakBrowser）：
    qid = "404896870"   # questionId
    blank_num = "1"      # 空位编号（第几空）
    answer_text = "50"   # 答案内容

    page.evaluate(f\"\"\"
        (() => {{
            try {{
                const editorId = 'answerEditor{qid}{blank_num}';
                const editor = UE.getEditor(editorId);
                editor.setContent('<p>{answer_text}</p>');
                editor.sync();
                return 'OK';
            }} catch(e) {{
                return 'ERR: ' + e.message;
            }}
        }})()
    \"\"\")

    # 必须点击保存按钮才能持久化到服务器
    page.evaluate(f\"\"\"
        (() => {{
            const saveBtn = document.getElementById('save_{qid}');
            if (saveBtn) saveBtn.click();
        }})()
    \"\"\")

注意：
- ⚠️ editor ID 是 `answerEditor{questionId}{空位编号}`，不是 `answer{questionId}`
- 先检查页面 HTML 中的 textarea/script 标签确认实际 ID
- HTML 内容中的单引号需要转义，换行用 <br/> 或 <p> 标签
- editor.sync() 会将 UEditor 内容同步回 textarea
- 不点击保存按钮，内容不会持久化到服务器，刷新后丢失
- 简答题和论述题使用相同的 UEditor 机制，只是内容更长
"""
