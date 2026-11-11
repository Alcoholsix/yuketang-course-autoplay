#######################################################################################
# 写于 2026年11月11日       乔子凯
# 
# 代码由 ChatGPT 辅助我完成（它是主力）
# 使用方法见 README 文件
# 
# 该项目是本人今天突发奇想，我网课还没听呢，何不做一个协助我方便听网课的程序呢？
# 于是，便产生了这个
#
# 目前还有一些 bug，比如视频中央会停留视频播放图标，进度条反复横跳等
# 
#######################################################################################

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from runClass import run_class
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BROWSER_DATA = BASE_DIR / "browser_data"


def open_unfinished_page(page, course_url):
    """重新进入课程，并打开未完成列表。"""

    page.goto(course_url)

    page.wait_for_selector(".rain-tabs__nav-item", timeout=30000)

    unfinished_tab = page.locator(".rain-tabs__nav-item").filter(has_text="未完成")
    unfinished_tab.click()

    page.wait_for_selector("li.unfinished-study__item", timeout=15000)


def get_first_unfinished_video(page):
    """获取当前未完成列表中的第一个视频。"""

    items = page.locator("li.unfinished-study__item")

    for i in range(items.count()):
        item = items.nth(i)

        type_card = item.locator(".unfinished-study__type-card")
        type_text = item.locator(".unfinished-study__type-text")

        if type_card.count() > 0:
            item_type = type_card.inner_text().strip()
        elif type_text.count() > 0:
            item_type = type_text.inner_text().strip()
        else:
            continue

        if "视频" not in item_type:
            continue

        button = item.locator('button[aria-label="去完成"]')

        if button.count() == 0:
            continue

        title = item.locator(".unfinished-study__item-title").inner_text().strip()

        return {
            "item": item,
            "button": button,
            "title": title
        }

    return None


def wait_video_end(page):
    """等待当前视频真正播放结束。"""

    print("等待视频播放结束……")

    page.wait_for_function(
        """() => {
            const video = document.querySelector('video.xt_video_player');
            return video && video.ended;
        }""",
        timeout=0
    )

    print("视频播放结束")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
            channel="msedge",
            headless=False,
            viewport={"width": 1440, "height": 900}
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            # 1. 进入雨课堂首页
            page.goto("https://changjiang.yuketang.cn/v2/web/index")

            # 2. 等待课程列表加载
            page.wait_for_selector(".studentCol .lesson-cardS h1", timeout=30000)

            print("雨课堂首页已加载")
            print("请在浏览器中点击想学习的课程……")

            # 3. 等待用户进入课程
            page.wait_for_url("**/studentLog/**", timeout=0)

            course_url = page.url

            print("已进入课程：", course_url)

            # 4. 打开未完成列表
            open_unfinished_page(page, course_url)

            # 5. 循环播放未完成视频
            video_number = 0

            while True:
                video = get_first_unfinished_video(page)

                if video is None:
                    print("\n当前课程没有找到未完成的视频，任务结束。")
                    break

                video_number += 1

                print(f"\n========== 第 {video_number} 个视频 ==========")
                print("准备播放：", video["title"])

                # 6. 进入第一个未完成视频
                video["button"].click()

                # 7. 等待播放器加载
                page.wait_for_selector("video.xt_video_player", state="attached", timeout=30000)

                # 8. 设置 2 倍速和静音
                run_class(page)

                # 9. 等待视频真正结束
                wait_video_end(page)

                # 10. 返回课程未完成页面并刷新任务状态
                print("返回未完成页面……")

                open_unfinished_page(page, course_url)

                print("未完成列表已刷新，准备检查下一个视频")

        except PlaywrightTimeoutError as e:
            print("页面元素等待超时：", e)

        except KeyboardInterrupt:
            print("\n用户手动停止程序")

        except Exception as e:
            print("程序运行出错：", repr(e))

        finally:
            browser.close()


if __name__ == "__main__":
    main()
