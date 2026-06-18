#!/usr/bin/env python3
"""
选择题填写模板：通过 span.parentElement.click() 触发原生事件链。
2026-06-14 实测：40/40 全部稳定生效。
2026-06-17 更新：适配新版页面选择器 div.singleQuesId，新增提交确认流程。

原理：click() → jQuery 事件处理器 → saveSingleSelect(this, qid) → addChoice() + submitForm()
全程由页面原生逻辑驱动，不会出现 this 上下文错误或 AJAX 挂起。

用法（CloakBrowser）：
    from cloakbrowser import launch_persistent_context
    context = launch_persistent_context(PROFILE_DIR, headless=False, humanize=True)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(EXAM_URL, wait_until="domcontentloaded", timeout=90000)

    # answers 格式: [(questionId, display_letter), ...]
    # display_letter 是页面上显示的 A/B/C/D，脚本自动匹配 textContent
    answers = [
        ("404896860", "D"),
        ("404896867", "D"),
    ]

    for qid, letter in answers:
        page.evaluate(f\"\"\"(() => {{
            const d = document.querySelector('div.singleQuesId[data="{qid}"]');
            if(!d) return;
            for(const s of d.querySelectorAll('span.num_option')){{
                if(s.textContent.trim()==='{letter}' && !s.classList.contains('check_answer')){{
                    s.parentElement.click();
                }}
            }}
        }})()\"\"\")
        time.sleep(1.5)

    # 提交流程
    page.evaluate("btnBlueSubmit()")  # 弹出确认框
    time.sleep(3)
    page.evaluate(\"\"\"(() => {
        const btn = document.getElementById('popok');
        ['mousedown','mouseup','click'].forEach(type => {
            btn.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window, clientX:0, clientY:0}));
        });
    })()\"\"\")
    time.sleep(15)

验证选中状态：
    for qid, expected in answers:
        r = page.evaluate(f\"\"\"(() => {{
            const d = document.querySelector('div.singleQuesId[data="{qid}"]');
            const s = d?.querySelector('span.num_option.check_answer');
            return s?.getAttribute('data') || 'NO_SEL';
        }})()\"\"\")

⚠️ 不可靠方法（实测失败）：
- eval(optDiv.getAttribute('onclick'))：this 指向 window，AJAX 不触发
- saveSingleSelect(span, qid)：前 ~27 题正常，后续 AJAX 挂起卡死
- 纯 DOM 操作添加 check_answer class：刷新后丢失

⚠️ 提交确认按钮 #popok：
- 无 onclick 属性，事件通过 jQuery 绑定
- 普通 .click() 和 jQuery .trigger('click') 都无法触发
- 必须用 dispatchEvent(MouseEvent) 派发真实鼠标事件
"""
