#!/usr/bin/env python3
"""步骤 2：从 HTML 中解析题目结构，提取题号、题型、题干图片 URL、选项。"""
import json
import re
import argparse
from pathlib import Path
from bs4 import BeautifulSoup

def parse_questions(html_path, output_dir):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    questions = []
    for q in soup.find_all("div", class_="questionLi"):
        question = {}
        qid = q.get("data", "")
        question["id"] = qid

        h3 = q.find("h3", class_="mark_name")
        if not h3:
            continue

        # 题号
        num_match = re.search(r"(\d+)", h3.contents[0].strip() if h3.contents else "")
        question["number"] = int(num_match.group(1)) if num_match else 0

        # 题型和分值
        type_span = h3.find("span")
        if type_span:
            m = re.search(r"\((.*?)\)", type_span.get_text(strip=True))
            if m:
                parts = m.group(1).split(",")
                question["type"] = parts[0].strip()
                if len(parts) > 1:
                    score_m = re.search(r"([\d.]+)", parts[1])
                    question["score"] = float(score_m.group(1)) if score_m else 0

        # 题干（图片或文字）
        question["stem_text"] = ""
        question["stem_images"] = []
        stem_div = h3.find("div", style=True)
        if stem_div:
            imgs = stem_div.find_all("img")
            if imgs:
                for img in imgs:
                    url = img.get("data-original") or img.get("src", "")
                    question["stem_images"].append({"url": url, "alt": img.get("alt", "")})
            else:
                p = stem_div.find("p")
                if p:
                    question["stem_text"] = p.get_text(strip=True)

        # 选项
        question["options"] = []
        form = q.find("form")
        if form:
            for opt_div in form.find_all("div", class_="clearfix"):
                option = {}
                letter_span = opt_div.find("span", class_="num_option")
                if letter_span:
                    option["letter"] = letter_span.get_text(strip=True)
                    option["value"] = letter_span.get("data", "")
                answer_p = opt_div.find("div", class_="answer_p")
                if answer_p:
                    opt_imgs = answer_p.find_all("img")
                    if opt_imgs:
                        option["images"] = [{"url": i.get("data-original") or i.get("src", "")} for i in opt_imgs]
                    else:
                        p = answer_p.find("p")
                        if p:
                            option["text"] = p.get_text(strip=True)
                if "letter" in option:
                    question["options"].append(option)

        # 填空
        question["blanks"] = []
        if form:
            for i, bd in enumerate(form.find_all("div", class_="sub_que_div")):
                question["blanks"].append({"index": i + 1})

        questions.append(question)

    # 保存
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with open(output / "questions.json", "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"解析完成: {len(questions)} 题 -> {output / 'questions.json'}")

    # 统计
    from collections import Counter
    types = Counter(q["type"] for q in questions)
    for t, c in types.items():
        print(f"  {t}: {c} 题")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default="./output/exam.html")
    parser.add_argument("--output", default="./output")
    args = parser.parse_args()
    parse_questions(args.html, args.output)
