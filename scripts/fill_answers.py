#!/usr/bin/env python3
"""步骤 5：自动填写答案。选择题用 DOM 操作，填空题用 UEditor API。
读取 answers.json，通过 CloakBrowser 填写到考试页面。
"""
import json
import time
import argparse
from pathlib import Path
from cloakbrowser import launch_persistent_context

def main():
    parser = argparse.ArgumentParser(description="自动填写考试答案")
    parser.add_argument("--url", required=True, help="考试页面 URL")
    parser.add_argument("--answers", default="./output/answers.json", help="答案 JSON 文件")
    parser.add_argument("--questions", default="./output/questions.json", help="题目 JSON 文件")
    parser.add_argument("--profile", default="./chaoxing_profile")
    args = parser.parse_args()

    with open(args.answers, "r") as f:
        answers_data = json.load(f)
    with open(args.questions, "r") as f:
        questions = json.load(f)

    choice_answers = {int(k): v for k, v in answers_data["choice_answers"].items()}
    fill_answers = {int(k): v for k, v in answers_data["fill_answers"].items()}
    qid_map = {q["number"]: q["id"] for q in questions}

    context = launch_persistent_context(
        args.profile, headless=False, humanize=True,
        args=["--window-size=1280,900", "--disable-blink-features=AutomationControlled"]
    )
    page = context.new_page()

    try:
        page.goto(args.url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(6000)

        # 滚动加载
        prev_h = 0
        for i in range(30):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)
            h = page.evaluate("document.body.scrollHeight")
            if h == prev_h and i > 3:
                break
            prev_h = h
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # === 选择题：DOM 操作 ===
        print("=== 填写选择题 ===")
        for num in sorted(choice_answers.keys()):
            qid = qid_map[num]
            letter = choice_answers[num]
            page.evaluate(f"""
                (() => {{
                    const qDiv = document.getElementById('sigleQuestionDiv_{qid}');
                    if (!qDiv) return;
                    qDiv.querySelectorAll('.saveSingleSelect').forEach(s => s.classList.remove('check_answer'));
                    qDiv.querySelectorAll('span.num_option').forEach(span => {{
                        if (span.textContent.trim() === '{letter}') {{
                            span.classList.add('check_answer');
                            const hidden = qDiv.querySelector('input[name="answer{qid}"]');
                            if (hidden) hidden.value = span.getAttribute('data');
                        }}
                    }});
                }})()
            """)
        print(f"  选择题 {len(choice_answers)} 题已填写 ✅")

        # === 填空题：UEditor API ===
        print("\n=== 填写填空题 ===")
        for num in sorted(fill_answers.keys()):
            answer = fill_answers[num]
            if answer == "?":
                continue
            qid = qid_map[num]
            page.evaluate(f"document.getElementById('sigleQuestionDiv_{qid}').scrollIntoView({{block:'center'}})")
            page.wait_for_timeout(300)
            result = page.evaluate(f"""
                (() => {{
                    const editorId = 'answerEditor{qid}1';
                    try {{
                        const editor = UE.getEditor(editorId);
                        editor.setContent('<p>{answer}</p>');
                        editor.sync();
                        const div = document.getElementById('sigleQuestionDiv_{qid}');
                        submitForm(true, $(div), function(){{}});
                        return 'ok';
                    }} catch(e) {{ return 'err:' + e.message; }}
                }})()
            """)
            print(f"  第{num}题: {answer} -> {result}")
            time.sleep(1)

        print("\n✅ 全部完成！")

    except Exception as e:
        print(f"错误: {e}")
    finally:
        context.close()

if __name__ == "__main__":
    main()
