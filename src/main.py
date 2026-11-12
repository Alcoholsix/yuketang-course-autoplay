#######################################################################################
# 写于 2026年11月11日       乔子凯
#
# 代码由 ChatGPT 辅助完成
# 使用方法见 README 文件
#
# 该项目是本人今天突发奇想，我网课还没听呢，何不做一个协助我方便听网课的程序呢？
#
# 目前还有一些 bug，后续可能会继续完善
#
#######################################################################################

import sys
import time
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from runClass import run_class, mute_video_immediately


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

BROWSER_DATA = BASE_DIR / "browser_data"
LOG_FILE = BASE_DIR / "classAutoPlayer.log"

BROWSER_DATA.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)


def open_unfinished_page(page, course_url: str) -> bool:
    """打开课程页面并等待未完成任务列表加载。"""

    logging.info("正在打开课程页面")
    page.goto(course_url, wait_until="domcontentloaded")

    unfinished_tab = page.locator(".rain-tabs__nav-item").filter(has_text="未完成")
    unfinished_tab.wait_for(state="visible", timeout=30000)
    unfinished_tab.click()

    logging.info("已点击未完成任务标签，等待任务列表加载")

    items = page.locator("li.unfinished-study__item")

    try:
        items.first.wait_for(state="visible", timeout=30000)
        logging.info("未完成任务列表加载成功，当前任务数量：%s", items.count())
        return True

    except PlaywrightTimeoutError:
        logging.error("等待未完成任务列表超时")
        logging.error("当前页面 URL：%s", page.url)

        try:
            logging.error("当前页面文本：\n%s", page.locator("body").inner_text()[:5000])
            page.screenshot(path=str(BASE_DIR / "debug_unfinished.png"), full_page=True)
            logging.info("页面截图已保存：%s", BASE_DIR / "debug_unfinished.png")
        except Exception:
            logging.exception("获取页面调试信息失败")

        return False


def get_first_unfinished_video(page):
    """获取第一个尚未完成的视频任务。"""

    items = page.locator("li.unfinished-study__item")
    count = items.count()

    logging.info("当前未完成任务元素数量：%s", count)

    for i in range(count):
        item = items.nth(i)

        type_element = item.locator(".unfinished-study__type-card, .unfinished-study__type-text").first

        if type_element.count() == 0:
            continue

        task_type = type_element.inner_text().strip()
        logging.info("检测任务：%s，类型：%s", i + 1, task_type)

        if "视频" not in task_type:
            continue

        title_element = item.locator(".unfinished-study__item-title")
        title = title_element.inner_text().strip() if title_element.count() else "未知视频"

        button = item.locator('button[aria-label="去完成"]')

        if button.count() == 0 or not button.is_visible():
            continue

        return {
            "title": title,
            "button": button
        }

    return None


def wait_video_end(page, pause_timeout: int = 10) -> str:
    """等待视频播放结束，或检测到持续暂停。"""

    video = page.locator("video.xt_video_player")
    pause_start = None

    logging.info("开始监测视频播放状态")

    while True:
        if video.count() == 0:
            raise RuntimeError("视频播放器已消失")

        state = video.evaluate(
            """video => ({
                paused: video.paused,
                ended: video.ended,
                currentTime: video.currentTime,
                readyState: video.readyState
            })"""
        )

        if state["ended"]:
            logging.info("视频正常播放结束")
            return "ended"

        if state["paused"]:
            if pause_start is None:
                pause_start = time.monotonic()
                logging.warning("检测到视频暂停，开始计时")

            elif time.monotonic() - pause_start >= pause_timeout:
                logging.warning("视频持续暂停超过 %s 秒", pause_timeout)
                return "paused"

        else:
            if pause_start is not None:
                logging.info("视频已恢复播放")

            pause_start = None

        page.wait_for_timeout(500)


def save_debug_info(page, filename: str) -> None:
    """保存当前页面文本和截图。"""

    try:
        logging.info("当前页面 URL：%s", page.url)
        logging.info("当前页面标题：%s", page.title())
        logging.info("当前任务元素数量：%s", page.locator("li.unfinished-study__item").count())
        logging.info("当前页面文本：\n%s", page.locator("body").inner_text()[:5000])

        screenshot_path = BASE_DIR / filename
        page.screenshot(path=str(screenshot_path), full_page=True)

        logging.info("页面截图已保存：%s", screenshot_path)

    except Exception:
        logging.exception("获取页面调试信息失败")


def process_course(page, course_url: str) -> None:
    """处理当前课程中的未完成视频任务。"""

    if not open_unfinished_page(page, course_url):
        input("任务列表加载失败，请检查浏览器页面和 debug_unfinished.png，按 Enter 退出...")
        return

    retry_counts = {}

    while True:
        task = get_first_unfinished_video(page)

        if task is None:
            logging.warning("未找到符合条件的视频任务，暂不判定全部完成")
            save_debug_info(page, "debug_tasks.png")

            input("请检查浏览器页面和 debug_tasks.png，按 Enter 退出...")
            return

        title = task["title"]
        logging.info("准备播放视频：%s", title)

        print(f"\n当前视频：{title}")

        task["button"].click()

        page.locator("video.xt_video_player").wait_for(state="attached", timeout=30000)

        # 视频元素出现后立即静音
        mute_video_immediately(page)

        # 设置倍速、静音并启动视频
        run_class(page)

        result = wait_video_end(page)

        if result == "ended":
            logging.info("视频完成：%s", title)
            retry_counts.pop(title, None)

        elif result == "paused":
            retry_counts[title] = retry_counts.get(title, 0) + 1

            logging.warning("视频异常暂停：%s，第 %s 次", title, retry_counts[title])

            if retry_counts[title] >= 3:
                logging.error("视频连续异常暂停 3 次，停止程序")
                print(f"\n视频《{title}》连续异常暂停 3 次，程序停止。")
                return

        # 返回课程页面，重新获取未完成任务
        logging.info("返回课程页面，准备处理下一个任务")

        if not open_unfinished_page(page, course_url):
            logging.error("重新打开未完成任务列表失败，程序停止")
            input("请检查浏览器页面和 debug_unfinished.png，按 Enter 退出...")
            return


def main() -> None:
    """程序入口。"""

    logging.info("========== 雨课堂自动播放程序启动 ==========")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
            channel="msedge",
            headless=False,
            viewport={"width": 1440, "height": 900}
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()

            logging.info("正在打开雨课堂")

            page.goto("https://changjiang.yuketang.cn/v2/web/index", wait_until="domcontentloaded")

            page.wait_for_selector(".studentCol .lesson-cardS h1", timeout=60000)

            print("\n请在浏览器中手动点击需要学习的课程。")
            print("程序将在进入课程页面后自动开始运行。\n")

            page.wait_for_url("**/studentLog/**", wait_until="domcontentloaded", timeout=0)

            course_url = page.url
            logging.info("已进入课程：%s", course_url)

            process_course(page, course_url)

        except PlaywrightTimeoutError:
            logging.exception("等待网页元素或页面跳转超时")
            print("\n网页加载超时，详细信息请查看日志文件。")

        except KeyboardInterrupt:
            logging.info("用户手动终止程序")
            print("\n程序已停止。")

        except Exception:
            logging.exception("程序运行过程中发生异常")
            print("\n程序发生异常，详细信息请查看 classAutoPlayer.log。")

        finally:
            try:
                context.close()
                logging.info("浏览器已关闭")
            except Exception:
                logging.exception("关闭浏览器时发生异常")

    logging.info("========== 雨课堂自动播放程序结束 ==========")


if __name__ == "__main__":
    try:
        print("\n============================")
        print("如遇技术问题请联系我：")
        print("名称：乔子凯；")
        print("QQ: 1523175967")
        print("============================\n")
        
        main()
    except Exception:
        logging.exception("程序启动失败")
        print("\n程序启动失败，详细信息请查看 classAutoPlayer.log。")
