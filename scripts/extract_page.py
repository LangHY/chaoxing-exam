#!/usr/bin/env python3
"""步骤 1：登录超星学习通并抓取考试页面 HTML。首次需手动登录，后续自动复用。"""
import argparse
import time
from pathlib import Path
from cloakbrowser import launch_persistent_context

def main():
    parser = argparse.ArgumentParser(description="抓取超星学习通考试页面")
    parser.add_argument("--url", required=True, help="考试页面 URL")
    parser.add_argument("--profile", default="./chaoxing_profile", help="持久化 profile 目录")
    parser.add_argument("--output", default="./output", help="输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("正在启动浏览器...")
    context = launch_persistent_context(
        args.profile, headless=False, humanize=True,
        args=["--window-size=1280,900", "--disable-blink-features=AutomationControlled"]
    )
    page = context.new_page()

    try:
        print(f"导航到: {args.url}")
        page.goto(args.url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(6000)

        # 检查是否需要登录
        if "passport" in page.url or "login" in page.url.lower():
            print("⚠️  需要登录！请在浏览器窗口中手动登录。")
            for i in range(600):
                time.sleep(1)
                if "passport" not in page.url and "login" not in page.url.lower():
                    print("✅ 登录成功！")
                    page.goto(args.url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(5000)
                    break

        print(f"页面标题: {page.title()}")

        # 滚动加载所有题目
        print("滚动加载所有题目...")
        prev_h = 0
        for i in range(30):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)
            h = page.evaluate("document.body.scrollHeight")
            if h == prev_h and i > 3:
                break
            prev_h = h

        # 保存 HTML
        html = page.content()
        html_path = output_dir / "exam.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML 已保存: {html_path} ({len(html)} bytes)")

        # 截图
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(output_dir / "exam.png"), full_page=False)
        print("截图已保存")

    except Exception as e:
        print(f"错误: {e}")
    finally:
        context.close()
        print("浏览器已关闭。")

if __name__ == "__main__":
    main()
