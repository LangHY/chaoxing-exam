#!/usr/bin/env python3
"""步骤 3：用视觉模型提取题目图片中的文字内容。
视觉模型只负责"看图输出文字"，不做解题判断。

需要配置环境变量 VISION_API_URL 和 VISION_API_KEY，或通过命令行传入。
"""
import json
import base64
import time
import argparse
import urllib.request
import ssl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def call_vision_api(api_url, api_key, model, content, max_tokens=1500):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    )
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        return json.loads(resp.read().decode())["choices"][0]["message"]["content"].strip()

def extract_question(q, img_dir, api_url, api_key, model):
    num = q["number"]
    qtype = q["type"]
    content = []

    stem_img = Path(img_dir) / f"q{num}_stem.png"
    if stem_img.exists():
        content.append({"type": "text", "text": f"这是第{num}题（{qtype}）的题干图片。请完整识别其中的文字和数学公式，原样输出，不要分析、不要给答案。"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(stem_img)}"}})
    elif q.get("stem_text"):
        content.append({"type": "text", "text": f"题干：{q['stem_text']}"})

    for opt in q.get("options", []):
        letter = opt.get("letter", "")
        opt_img = Path(img_dir) / f"q{num}_opt_{letter}.png"
        if opt_img.exists():
            content.append({"type": "text", "text": f"选项{letter}的图片："})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(opt_img)}"}})

    text_opts = [f"{o['letter']}. {o.get('text', '')}" for o in q.get("options", []) if o.get("text")]
    if text_opts:
        content.append({"type": "text", "text": "文字选项：" + " | ".join(text_opts)})

    content.append({"type": "text", "text": "请将以上所有图片内容转为文字输出。格式：\n题干：...\nA. ...\nB. ...\n只输出文字，不要分析。"})

    try:
        return num, call_vision_api(api_url, api_key, model, content), None
    except Exception as e:
        return num, None, str(e)

def main():
    parser = argparse.ArgumentParser(description="视觉模型提取题目文字")
    parser.add_argument("--questions", default="./output/questions.json")
    parser.add_argument("--images", default="./output/images")
    parser.add_argument("--output", default="./output")
    parser.add_argument("--api-url", required=True, help="视觉模型 API base_url")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--model", default="mimo-v2-omni", help="视觉模型名称")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    with open(args.questions, "r") as f:
        questions = json.load(f)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"开始视觉提取 {len(questions)} 道题...")
    start = time.time()
    results = {}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(extract_question, q, args.images, args.api_url, args.api_key, args.model): q
            for q in questions
        }
        for i, future in enumerate(as_completed(futures)):
            num, text, err = future.result()
            results[num] = f"[错误: {err}]" if err else (text or "")
            if (i + 1) % 10 == 0:
                print(f"  进度: {i+1}/{len(questions)} ({time.time()-start:.0f}s)")

    with open(output_dir / "vision_extracted.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 整理为 Markdown
    q_map = {str(q["number"]): q for q in questions}
    md = ["# 考试题目（视觉模型提取）\n"]
    for num in sorted(results.keys(), key=lambda x: int(x)):
        q = q_map[num]
        md.append(f"\n## 第 {num} 题（{q['type']}，{q.get('score', 2)}分）\n")
        md.append(results[num])
        md.append("")

    with open(output_dir / "vision_questions.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n完成！耗时 {time.time()-start:.0f}s")
    print(f"  原始结果: {output_dir / 'vision_extracted.json'}")
    print(f"  整理文档: {output_dir / 'vision_questions.md'}")

if __name__ == "__main__":
    main()
