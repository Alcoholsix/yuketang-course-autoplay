from playwright.sync_api import Page


def mute_video_immediately(page: Page) -> None:
    """视频元素出现后立即执行静音。"""

    video = page.locator("video.xt_video_player")
    video.wait_for(state="attached", timeout=30000)

    result = video.evaluate(
        """video => {
            video.muted = true;
            video.volume = 0;

            return {
                muted: video.muted,
                volume: video.volume
            };
        }"""
    )

    if not result["muted"] and result["volume"] != 0:
        raise RuntimeError(f"视频立即静音失败：{result}")

    print("视频已立即静音")


def set_video_speed(page: Page, speed: float = 2.0) -> None:
    """设置视频倍速，并同步播放器显示。"""

    page.wait_for_selector(
        "video.xt_video_player",
        state="attached",
        timeout=30000
    )

    result = page.evaluate(
        """(speed) => {
            const video = document.querySelector('video.xt_video_player');

            if (!video) {
                return {success: false, error: '没有找到视频元素'};
            }

            const speedButton = document.querySelector(
                'xt-speedbutton.xt_video_player_speed'
            );

            const speedList = speedButton?.querySelector(
                '.xt_video_player_common_list_wrap'
            );

            const speedOption = speedButton?.querySelector(
                `li[data-speed="${speed}"]`
            );

            const speedValue = speedButton?.querySelector('xt-speedvalue');

            let nativeClick = false;

            if (speedButton && speedList && speedOption) {
                const oldStyle = speedList.getAttribute('style');

                speedList.style.display = 'block';
                speedList.style.visibility = 'visible';
                speedList.style.opacity = '1';
                speedList.style.pointerEvents = 'auto';

                const rect = speedOption.getBoundingClientRect();
                const x = rect.left + rect.width / 2;
                const y = rect.top + rect.height / 2;

                const eventOptions = {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: x,
                    clientY: y,
                    screenX: window.screenX + x,
                    screenY: window.screenY + y,
                    button: 0,
                    buttons: 1
                };

                for (const type of [
                    'mousemove',
                    'mouseover',
                    'mousedown',
                    'mouseup',
                    'click'
                ]) {
                    speedOption.dispatchEvent(
                        new MouseEvent(type, eventOptions)
                    );
                }

                if (oldStyle === null) {
                    speedList.removeAttribute('style');
                } else {
                    speedList.setAttribute('style', oldStyle);
                }

                nativeClick = Math.abs(video.playbackRate - speed) < 0.01;
            }

            const updateDisplay = () => {
                if (!video.isConnected) {
                    return;
                }

                if (Math.abs(video.playbackRate - speed) >= 0.01) {
                    video.playbackRate = speed;
                }

                if (speedValue && speedValue.isConnected) {
                    speedValue.textContent = speed.toFixed(2) + 'X';
                }

                if (speedButton && speedButton.isConnected) {
                    speedButton.querySelectorAll('li[data-speed]').forEach(item => {
                        item.classList.toggle(
                            'xt_video_player_common_active',
                            Number(item.dataset.speed) === speed
                        );
                    });
                }
            };

            updateDisplay();

            if (window.__yuketangSpeedGuard) {
                clearInterval(window.__yuketangSpeedGuard);
            }

            window.__yuketangSpeedGuard = setInterval(updateDisplay, 1000);

            return {
                success: Math.abs(video.playbackRate - speed) < 0.01,
                playbackRate: video.playbackRate,
                speedText: speedValue?.textContent ?? '未找到倍速显示元素',
                nativeClick
            };
        }""",
        speed
    )

    if not result.get("success"):
        raise RuntimeError(f"设置视频倍速失败：{result}")

    print(f"视频播放速度：{result['playbackRate']}x")


def set_video_mute(page: Page) -> None:
    """确保视频静音，并同步雨课堂播放器的静音按钮。"""

    video = page.locator("video.xt_video_player")
    video.wait_for(state="attached", timeout=30000)

    # 首先直接静音，避免等待播放器按钮时出现声音
    mute_video_immediately(page)

    page.wait_for_selector(
        "xt-volumebutton.xt_video_player_volume",
        state="attached",
        timeout=15000
    )

    status = page.evaluate(
        """() => {
            const video = document.querySelector('video.xt_video_player');
            const icon = document.querySelector(
                'xt-volumebutton.xt_video_player_volume .xt_video_player_common_icon'
            );

            if (!video || !icon) {
                return {success: false, error: '没有找到视频或音量按钮'};
            }

            return {
                mutedIcon: icon.classList.contains(
                    'xt_video_player_common_icon_muted'
                ),
                muted: video.muted,
                volume: video.volume
            };
        }"""
    )

    if not status.get("success", True):
        raise RuntimeError(f"读取播放器音量状态失败：{status}")

    # 仅当原生图标没有显示静音时，才点击原生按钮
    if not status["mutedIcon"]:
        print("正在同步雨课堂原生静音按钮")

        page.locator(".xt_video_player_wrap").hover()

        volume_button = page.locator(
            "xt-volumebutton.xt_video_player_volume"
        )

        volume_button.hover()

        page.locator(
            "xt-volumebutton.xt_video_player_volume .xt_video_player_common_icon"
        ).click()

        page.wait_for_timeout(300)

    # 再次强制设置视频元素静音，防止按钮操作改变实际音量
    mute_video_immediately(page)

    result = page.evaluate(
        """() => {
            const video = document.querySelector('video.xt_video_player');
            const icon = document.querySelector(
                'xt-volumebutton.xt_video_player_volume .xt_video_player_common_icon'
            );

            const volumeText = document.querySelector(
                '.xt_video_player_volume_value'
            );

            return {
                mutedIcon: icon?.classList.contains(
                    'xt_video_player_common_icon_muted'
                ) ?? false,
                muted: video?.muted ?? false,
                volume: video?.volume ?? -1,
                volumeText: volumeText?.textContent ?? '未知'
            };
        }"""
    )

    if not result["muted"] and result["volume"] != 0:
        raise RuntimeError(f"视频静音设置失败：{result}")

    print(f"播放器音量：{result['volumeText']}")


def start_video(page: Page) -> None:
    """优先通过播放器按钮启动视频，按钮不可用时使用 video.play()。"""

    print("准备启动视频")

    result = page.evaluate(
        """async () => {
            const video = document.querySelector('video.xt_video_player');

            if (!video) {
                return {
                    success: false,
                    error: '没有找到视频元素'
                };
            }

            if (!video.paused) {
                return {
                    success: true,
                    method: 'already playing',
                    paused: video.paused,
                    currentTime: video.currentTime
                };
            }

            const playButton = document.querySelector(
                '.xt_video_bit_play_btn'
            );

            if (playButton && playButton.getClientRects().length > 0) {
                playButton.click();

                await new Promise(resolve => setTimeout(resolve, 1000));

                if (!video.paused) {
                    return {
                        success: true,
                        method: 'native button',
                        paused: video.paused,
                        currentTime: video.currentTime
                    };
                }
            }

            try {
                await video.play();

                await new Promise(resolve => setTimeout(resolve, 500));

                return {
                    success: !video.paused,
                    method: 'video.play()',
                    paused: video.paused,
                    currentTime: video.currentTime
                };

            } catch (error) {
                return {
                    success: false,
                    error: error.message,
                    paused: video.paused
                };
            }
        }"""
    )

    print("视频启动结果：", result)

    if not result.get("success"):
        raise RuntimeError(f"视频启动失败：{result}")

    print("视频已开始播放")


def run_class(page: Page) -> None:
    """设置 2 倍速、静音，并启动视频。"""

    print("等待视频播放器加载……")

    video = page.locator("video.xt_video_player")
    video.wait_for(state="attached", timeout=30000)

    # 1. 立即静音
    mute_video_immediately(page)

    # 2. 等待视频元数据加载
    page.wait_for_function(
        """() => {
            const video = document.querySelector('video.xt_video_player');
            return video && video.readyState >= 1;
        }""",
        timeout=30000
    )

    print("视频播放器已加载")

    # 3. 设置 2 倍速
    print("准备设置视频倍速")
    set_video_speed(page, 2.0)

    # 4. 同步原生静音按钮
    set_video_mute(page)

    # 5. 启动视频
    start_video(page)

    # 6. 检查最终播放状态
    result = video.evaluate(
        """video => ({
            paused: video.paused,
            muted: video.muted,
            volume: video.volume,
            playbackRate: video.playbackRate,
            currentTime: video.currentTime
        })"""
    )

    print("当前视频状态：", result)

    if result["paused"]:
        raise RuntimeError("视频没有正常播放")

    if not result["muted"] and result["volume"] != 0:
        raise RuntimeError("视频没有保持静音状态")

    if abs(result["playbackRate"] - 2.0) > 0.01:
        raise RuntimeError("视频没有成功设置为 2 倍速")

    print("视频播放配置完成")
    
    