"""rmfyalk 自动登录脚本 — 按需登录，不保活。

读取 .env 中的账号密码，有头模式 Playwright 自动完成 OAuth 登录流程：

1. 打开 rmfyalk.court.gov.cn
2. 检测登录态 → 未登录则跳转 OAuth 登录页
3. 填入账密 → 点击登录按钮
4. 弹窗出现（直接登录 / 绑定）→ 点击「直接登录」
5. 跳转回 rmfyalk，提取 token → 写入 tokens.json + .env

用法:
    python login_rmfyalk.py                  # 有头模式（默认）
    python login_rmfyalk.py --headless       # 无头模式
    python login_rmfyalk.py --headed         # 有头模式（显式指定）

依赖：
    - playwright (pip install playwright && playwright install msedge)
    - python-dotenv (pip install python-dotenv)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Windows GBK 控制台写不出 emoji（✅🎉）会触发 UnicodeEncodeError 打断日志
# （2026-08-22 实测：登录成功但末尾 logging 报错刷屏；复用路由skill 三脚本同款修法）
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── 日志 ──────────────────────────────────────────────────────────
log = logging.getLogger("rmfyalk_login")
_log_configured = False


def _setup_logging() -> None:
    global _log_configured
    if _log_configured:
        return
    _log_configured = True
    log.setLevel(logging.DEBUG)
    # 隔离 logger：同进程直调（MCP server）时不向 root logger 传播，
    # 避免泄漏到宿主的 rich/默认 handler 刷屏 stderr
    log.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # RMFYALK_LOG_STREAM=0：跳过 stdout StreamHandler。
    # （MCP server 同进程直调时，日志写 stdout 会污染 stdio 协议流；
    #   日志仍写 login.log 文件，不影响排查）
    if os.environ.get("RMFYALK_LOG_STREAM", "1") != "0":
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    # 也写文件
    log_path = Path(__file__).resolve().parent.parent / "login.log"
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)


# ── 路径 ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

ENV_FILE = PROJECT_DIR / ".env"
TOKENS_JSON = PROJECT_DIR / "tokens.json"
BROWSER_DATA_DIR = Path(
    os.environ.get("TEMP", str(PROJECT_DIR)), "rmfyalk-browser-data"
)

_TOKEN_COOKIE_NAMES = {"faxin-cpws004-token", "faxin-cpws-al-token"}


# ── .env 读写 ──────────────────────────────────────────────────────


def _load_env() -> dict:
    """从 .env 读取配置。

    变量名兼容两种格式：
    - RMFYALK_USERNAME / RMFYALK_PASSWORD（新）
    - RMFYALK_USER   / RMFYALK_PASS（云端旧）
    """
    from dotenv import load_dotenv

    load_dotenv(str(ENV_FILE), override=True)

    return {
        "username": os.getenv("RMFYALK_USERNAME") or os.getenv("RMFYALK_USER", ""),
        "password": os.getenv("RMFYALK_PASSWORD") or os.getenv("RMFYALK_PASS", ""),
        "token": os.getenv("RMFYALK_TOKEN", ""),
    }


def _persist_to_env(key: str, value: str) -> None:
    """写入/更新 .env 文件中的值。"""
    env_path = str(ENV_FILE)
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    updated: list[str] = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            updated.append(f"{key}={value}\n")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key}={value}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated)


def _save_to_json(token: str, cpws004: str = "") -> None:
    """保存提取结果到 tokens.json。"""
    existing: dict = {}
    if TOKENS_JSON.exists():
        with open(str(TOKENS_JSON), "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing["rmfyalk"] = {
        "token": token,
        "cpws004_token": cpws004,
        "timestamp": time.time(),
        "source": "login_rmfyalk.py",
    }
    with open(str(TOKENS_JSON), "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ── 反检测 / 拟人化 ──────────────────────────────────────────────

import random as _random

_ANTI_DETECTION_SCRIPT = """
// 隐藏 Playwright/自动化特征
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, '__webdriver', { get: () => undefined });
Object.defineProperty(navigator, '__driver_evaluate', { get: () => undefined });
Object.defineProperty(navigator, '__selenium_evaluate', { get: () => undefined });
Object.defineProperty(navigator, '__fxdriver_evaluate', { get: () => undefined });
Object.defineProperty(navigator, '__webdriver_evaluate', { get: () => undefined });

// 覆盖 chrome 对象
window.chrome = { runtime: {} };
Object.defineProperty(window.chrome, 'loadTimes', { get: () => ({}) });
Object.defineProperty(window.chrome, 'csi', { get: () => ({}) });
Object.defineProperty(window.chrome, 'app', { get: () => ({}) });

// 覆盖 permissions query（Playwright 默认返回不同值）
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => (
    params.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(params)
);

// 覆盖 PluginsArray（Playwright 中为空，真实浏览器有值）
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
"""


async def _inject_anti_detection(page) -> None:
    """在页面上注入反检测脚本。

    必须在每次 navigate 之前调用，因为 SPA 页面跳转会重置 JS 上下文。
    """
    await page.add_init_script(_ANTI_DETECTION_SCRIPT)
    log.debug("已注入反检测脚本")


async def _add_human_like_delay(
    min_ms: float = 300, max_ms: float = 1500
) -> None:
    """拟人化等待，模拟真实用户的思考/操作间隔。"""
    delay = _random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


def _cleanup_screenshots(max_age_days: int = 7) -> None:
    """清理超过 max_age_days 的旧截图。"""
    shot_dir = PROJECT_DIR / "screenshots"
    if not shot_dir.exists():
        return
    now = time.time()
    max_age = max_age_days * 86400
    removed = 0
    for f in shot_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            age = now - f.stat().st_mtime
            if age > max_age:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
    if removed:
        log.info(f"已清理 {removed} 张过期截图（>{max_age_days}天）")


async def _human_type(page, locator, text: str) -> None:
    """模拟人类逐字输入（含随机间隔）。"""
    await locator.click()
    await _add_human_like_delay(200, 600)
    await locator.fill("")  # 先清空
    await _add_human_like_delay(100, 300)
    for char in text:
        await locator.type(char, delay=_random.randint(30, 120))
        await _add_human_like_delay(10, 50)


# ── Token / 登录态检测 ───────────────────────────────────────────


def _decode_jwt_exp(token: str) -> float:
    """解码 JWT exp 返回剩余分钟数。"""
    import base64 as _b64

    if not token or "." not in token:
        return -1
    parts = token.split(".")
    if len(parts) != 3:
        return -1
    try:
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(_b64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp", 0)
        if not exp:
            return -1
        return max(0, (exp - time.time()) / 60)
    except Exception:
        return -1


async def _check_login_status(context, page) -> bool:
    """检查浏览器上下文的登录状态。"""
    cookies = await context.cookies()
    has_token = any(
        c["name"] in _TOKEN_COOKIE_NAMES
        for c in cookies
        if "rmfyalk.court.gov.cn" in c.get("domain", "")
    )
    if has_token:
        return True
    current_url = page.url if page else ""
    if "login" in current_url:
        return False
    return False


# ── 核心：自动登录 ────────────────────────────────────────────────


async def _take_screenshot(page, name: str) -> str:
    """保存截图到项目目录，返回路径。"""
    shot_dir = PROJECT_DIR / "screenshots"
    shot_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = str(shot_dir / f"{name}_{timestamp}.png")
    await page.screenshot(path=path, full_page=True)
    log.info(f"截图已保存: {path}")
    return path


async def _try_fill_login_form(page) -> bool:
    """在 OAuth 登录页面上尝试填充账密。

    因为不确定 DOM 选择器，按常见模式依次尝试。

    Returns:
        True 如果成功提交登录
    """
    env = _load_env()
    username = env["username"]
    password = env["password"]

    if not username or not password:
        log.error("❌ .env 中未配置 RMFYALK_USERNAME 或 RMFYALK_PASSWORD")
        return False

    log.info("等待登录表单加载...")
    await page.wait_for_timeout(3000)

    # ── 尝试查找用户名输入框 ──
    username_selectors = [
        'input[name="username"]',
        'input[id="username"]',
        'input[type="text"]',
        'input[placeholder*="账号"]',
        'input[placeholder*="手机"]',
        'input[placeholder*="用户"]',
        "#username",
        'input[autocomplete="username"]',
    ]

    username_input = None
    for sel in username_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                username_input = el
                log.info(f"找到用户名输入框: selector={sel}")
                break
        except Exception:
            continue

    if username_input is None:
        log.warning("未找到用户名输入框，尝试输入所有可见的 text 输入框...")
        all_inputs = page.locator("input:visible")
        count = await all_inputs.count()
        log.info(f"页面上共有 {count} 个可见 input")
        if count > 0:
            username_input = all_inputs.first

    if username_input is None:
        log.error("❌ 未能找到任何输入框")
        await _take_screenshot(page, "no_input_found")
        return False

    # ── 尝试查找密码输入框 ──
    password_selectors = [
        'input[type="password"]',
        'input[name="password"]',
        'input[id="password"]',
        "#password",
        'input[autocomplete="current-password"]',
    ]

    password_input = None
    for sel in password_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                password_input = el
                log.info(f"找到密码输入框: selector={sel}")
                break
        except Exception:
            continue

    # ── 填入账密（逐字输入，模拟真人） ──
    try:
        await _human_type(page, username_input, username)
        log.info("已填入用户名")
    except Exception as e:
        log.error(f"填入用户名失败: {e}")
        await _take_screenshot(page, "fill_username_failed")
        return False

    if password_input is not None:
        try:
            await _human_type(page, password_input, password)
            log.info("已填入密码")
        except Exception as e:
            log.warning(f"填入密码失败（可忽略如果已自动填充）: {e}")

    # ── 勾选协议（account.court.gov.cn 登录表单需要） ──
    try:
        protocol_cb = page.locator("input[name='protocol']").first
        if await protocol_cb.count() > 0:
            is_checked = await protocol_cb.is_checked()
            if not is_checked:
                await protocol_cb.click()
                log.info("已勾选协议复选框")
    except Exception:
        pass

    await _add_human_like_delay(500, 1500)

    # ── 尝试查找登录按钮 ──
    login_btn_selectors = [
        '[data-action="login-submit"]',
        'button[type="submit"]',
        "button:has-text('登录')",
        "button:has-text('登 录')",
        "#loginBtn",
        ".login-btn",
        ".login-button",
        "button:has-text('Login')",
        'input[type="submit"]',
    ]

    login_btn = None
    for sel in login_btn_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                login_btn = el
                log.info(f"找到登录按钮: selector={sel}")
                break
        except Exception:
            continue

    if login_btn is None:
        log.warning("未找到登录按钮，尝试用回车提交")
        await page.keyboard.press("Enter")
    else:
        try:
            # 模拟鼠标移动到按钮再点击
            box = await login_btn.bounding_box()
            if box:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
                await page.mouse.move(
                    x + _random.uniform(-10, 10),
                    y + _random.uniform(-10, 10),
                )
                await _add_human_like_delay(200, 500)
            await login_btn.click()
            log.info("已点击登录按钮")
        except Exception as e:
            log.error(f"点击登录按钮失败: {e}")
            await page.keyboard.press("Enter")

    return True


async def _quick_handle_popup(page) -> bool:
    """快速检测并处理弹窗（不等待，扫一下页面就回）。

    在回调等待循环中每轮调用，及时发现弹窗并点击「直接登录」。

    Returns:
        True 如果发现并处理了弹窗
    """
    # 2026-08-26 增强：补充选择器 + 两遍探测（零等待扫 DOM → 短等待容错渲染）
    direct_login_selectors = [
        '[data-action="login"]',
        "button.tologin",
        ".tologin",
        "button:has-text('直接登录')",
        "a:has-text('直接登录')",
        "span:has-text('直接登录')",
        "text=直接登录",
        "button:has-text('立即登录')",
        "a:has-text('立即登录')",
        "span:has-text('立即登录')",
        "[class*='login-btn']",
        "[class*='loginBtn']",
    ]

    # 第一遍：零等待扫 DOM，收集存在的候选（避免每轮对全部选择器各等 1.5s）
    candidates = []
    for sel in direct_login_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                candidates.append((sel, loc))
        except Exception:
            continue
    if not candidates:
        return False

    # 第二遍：对存在的候选短等待（容错弹窗动画/渲染时序），命中即点
    for sel, loc in candidates:
        el = None
        try:
            el = await loc.wait_for(state="visible", timeout=1000)
        except Exception:
            el = None
        try:
            if el is not None:
                await el.click()
            else:
                # 元素在 DOM 但不可见（动画/透明/被遮挡）→ force 兜底点击
                await loc.click(force=True)
            log.info(f"已点击弹窗按钮: {sel}")
            return True
        except Exception:
            continue

    return False


async def _handle_post_login_popup(page) -> bool:
    """登录成功后处理弹窗（直接登录 / 绑定）。

    这个函数比 _quick_handle_popup 更耐心，会等待弹窗渲染。

    Returns:
        True 如果弹窗已处理或无需处理
    """
    log.info("等待登录完成后弹窗...")
    await page.wait_for_timeout(2000)

    current_url = page.url
    log.info(f"当前URL: {current_url}")

    # 检查是否已经跳转回 rmfyalk
    if "rmfyalk.court.gov.cn" in current_url and "login" not in current_url:
        log.info("已成功跳转回 rmfyalk，无需处理弹窗")
        return True

    # 处理绑定弹窗（URL 含 #/bind）
    if "#/bind" in current_url:
        log.info("检测到绑定弹窗页面")
    elif "account.court.gov.cn" in current_url:
        # 如果还在 account 域，可能弹窗在前端路由中
        pass

    return await _quick_handle_popup(page)


async def _extract_tokens(context) -> dict | None:
    """从浏览器上下文中提取两个 Token。"""
    cookies = await context.cookies()
    rmfyalk_cookies = [
        c for c in cookies if "rmfyalk.court.gov.cn" in c.get("domain", "")
    ]

    result: dict = {}
    al = [c for c in rmfyalk_cookies if c["name"] == "faxin-cpws-al-token"]
    if al:
        result["token"] = al[0]["value"]

    cpws004 = [c for c in cookies if c["name"] == "faxin-cpws004-token"]
    if cpws004:
        result["cpws004_token"] = cpws004[0]["value"]

    if "token" not in result:
        return None
    return result


def _check_existing_token() -> bool:
    """检查已有的 token 是否仍然有效。

    Returns:
        True 如果 token 有效且在有效期内
    """
    env = _load_env()
    token = env.get("token", "")
    if not token:
        return False
    remaining = _decode_jwt_exp(token)
    log.info(f"现有 JWT 剩余 {remaining:.0f} 分钟")
    return remaining > 5  # 剩余 5 分钟以上视为有效


# ── 公开接口 ──────────────────────────────────────────────────────


async def auto_login(headless: bool = False) -> bool:
    """自动登录 rmfyalk，获取并保存 Token。

    Args:
        headless: 是否无头模式（默认有头）

    Returns:
        True 如果登录成功
    """
    _setup_logging()
    log.info("=" * 50)
    log.info("rmfyalk 自动登录开始")

    # 0. 清理旧截图
    _cleanup_screenshots()

    # 1. 先检查现有 token 是否有效
    if _check_existing_token():
        log.info("当前 Token 仍有效（剩余 >5 分钟），无需重新登录")
        return True

    # 2. 检查 .env 中是否有账密
    env = _load_env()
    if not env["username"] or not env["password"]:
        log.error("❌ .env 中未配置账号密码，无法自动登录")
        log.error("请在 .env 中添加以下两行：")
        log.error("  RMFYALK_USERNAME=你的手机号")
        log.error("  RMFYALK_PASSWORD=你的密码")
        log.error("（也兼容云端旧格式：RMFYALK_USER / RMFYALK_PASS）")
        return False

    from playwright.async_api import async_playwright

    result: dict | None = None

    try:
        async with async_playwright() as p:
            os.makedirs(str(BROWSER_DATA_DIR), exist_ok=True)

            # 用有头模式（用户指定）
            mode_str = "有头" if not headless else "无头"
            log.info(f"启动 Edge ({mode_str}模式) ...")

            context = await p.chromium.launch_persistent_context(
                str(BROWSER_DATA_DIR),
                channel="msedge",
                headless=headless,
                accept_downloads=False,
                # ── 反检测参数 ──
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1920, "height": 1080},
                screen={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            page = (
                context.pages[0]
                if context.pages
                else await context.new_page()
            )

            # ── 注入反检测脚本（在导航前执行） ──
            await _inject_anti_detection(page)

            # ── 检测并完成登录 ──
            # 步骤1：导航到列表页（受保护页面），触发 OAuth 跳转
            log.info("导航到列表页（触发 OAuth 跳转）...")
            await page.goto(
                "https://rmfyalk.court.gov.cn/view/list.html",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            # networkidle 在页面持续有网络请求时可能永不触发 → 短等待 + 容错
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                log.debug("networkidle 等待超时（页面仍有活动请求），继续流程")
            log.info(f"页面加载完成, URL: {page.url}")

            # 步骤2：检测登录态
            logged_in = await _check_login_status(context, page)
            log.info(f"登录态检测结果: {'已登录' if logged_in else '未登录'}")

            if logged_in:
                log.info("已在登录状态，直接提取 Token")
            else:
                # ── 确认已跳转到 OAuth 登录页 ──
                current_url = page.url
                if "account.court.gov.cn" not in current_url and "#/login" not in current_url:
                    log.info(f"当前页面不是登录页（{current_url}），等待 OAuth 重定向...")
                    for _ in range(15):
                        await page.wait_for_timeout(1000)
                        current_url = page.url
                        if "account.court.gov.cn" in current_url or "#/login" in current_url:
                            log.info(f"已跳转到登录页: {current_url}")
                            break
                    else:
                        log.warning("等待 OAuth 重定向超时，截屏供参考")
                        await _take_screenshot(page, "oauth_redirect_timeout")

                log.info("开始自动登录流程...")

                filled = await _try_fill_login_form(page)
                if not filled:
                    log.error("登录失败：无法填写登录表单")
                    await _take_screenshot(page, "login_failed")
                    await context.close()
                    return False

                # ── 点击登录按钮，进入 OAuth 回调循环 ──
                log.info("已点击登录按钮，进入回调等待循环...")

                # 循环中：检测登录成功、处理弹窗、等待回调，一步到位
                # 2026-08-26 增强：无进展检测 → 补充再次点击（弹窗探测失败兜底）
                max_wait = 60  # 最多等 60 秒
                poll_interval = 2
                waited = 0
                logged_in = False
                last_url = page.url
                no_change_since = 0   # URL 未跳转且无弹窗命中的累计秒数
                retry_left = 2        # 「补充再次点击」最多重试 2 次
                while waited < max_wait:
                    await asyncio.sleep(poll_interval)
                    waited += poll_interval

                    current_url = page.url
                    logged_in = await _check_login_status(context, page)

                    # 条件1：已登录且回到 rmfyalk → 成功
                    if logged_in and "rmfyalk.court.gov.cn" in current_url:
                        log.info(f"✅ 登录成功！耗时约 {waited} 秒")
                        break

                    popup_handled = False

                    # 条件2：URL 含 #/bind → 绑定弹窗，处理之
                    if "#/bind" in current_url:
                        log.info(f"检测到绑定弹窗（{waited}s），处理中...")
                        await _handle_post_login_popup(page)
                        last_url = current_url
                        no_change_since = 0
                        continue

                    # 条件3：表单提交后仍在 account 域 → 可能有弹窗 overlay
                    # （弹窗可能不改变 URL，直接检查页面上的按钮）
                    if "account.court.gov.cn" in current_url:
                        popup_handled = await _quick_handle_popup(page)
                        if popup_handled:
                            log.info("弹窗已处理（快速检测）")

                    # ── 无进展检测：URL 未跳转、无弹窗命中、未登录成功 ──
                    # 点击登录/弹窗处理后若连续 ≥8s 页面毫无变化，判定弹窗探测
                    # 失败或提交未生效 → 补充再次点击（先扫弹窗，再重试提交）
                    if current_url == last_url and not popup_handled and not logged_in:
                        no_change_since += poll_interval
                        if no_change_since >= 8 and retry_left > 0:
                            retry_left -= 1
                            no_change_since = 0
                            log.info(
                                f"⚠️ 页面连续 8s 无进展（url 未跳转/无弹窗），"
                                f"补充再次点击（剩余 {retry_left} 次）"
                            )
                            # ① 先再次扫弹窗（增强版含 force 兜底）
                            if await _quick_handle_popup(page):
                                log.info("重试：弹窗已点击")
                                continue
                            # ② 仍无弹窗 → 回车重试提交登录
                            try:
                                await page.keyboard.press("Enter")
                                log.info("重试：已按 Enter 重新提交登录")
                            except Exception as e:
                                log.warning(f"重试：按 Enter 失败: {e}")
                    else:
                        last_url = current_url
                        no_change_since = 0

                    if waited % 10 == 0:
                        log.info(f"  等待中... ({waited}s) url={current_url[:80]}")
                else:
                    log.warning("等待登录超时(60s)，尝试 fallback 方案")
                    # fallback：上次测试已验证，直接导航 list.html 也能拿到 token
                    await _take_screenshot(page, "login_timeout")

                # ── 如果还没进入 list.html，导航触发 token ──
                if "list.html" not in page.url:
                    log.info("导航到列表页触发 token 下发...")
                    await page.goto(
                        "https://rmfyalk.court.gov.cn/view/list.html",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        log.debug("networkidle 等待超时（页面仍有活动请求），继续流程")
                    await page.wait_for_timeout(3000)
                    log.info(f"URL: {page.url}")

            # ── 提取 Token ──
            log.info("提取 Token...")
            await page.wait_for_timeout(2000)
            result = await _extract_tokens(context)

            # ── 关闭浏览器 ──
            await context.close()

    except Exception as e:
        log.error(f"自动登录异常: {type(e).__name__}: {e}")
        return False

    # ── 保存 Token ──
    if result and result.get("token"):
        token = result["token"]
        cpws004 = result.get("cpws004_token", "")
        remaining = _decode_jwt_exp(token)
        log.info(f"✅ Token 提取成功，有效剩余: {remaining:.0f} 分钟")

        _save_to_json(token, cpws004)
        _persist_to_env("RMFYALK_TOKEN", token)
        log.info(f"✅ Token 已保存到: {TOKENS_JSON}")

        return True
    else:
        log.error("❌ 提取 Token 失败")
        return False


# ── CLI 入口 ──────────────────────────────────────────────────────


def main() -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="rmfyalk 自动登录，提取并保存 Token"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式（默认有头）",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        default=False,
        help="有头模式（显式指定）",
    )
    args = parser.parse_args()

    headless = args.headless and not args.headed

    log.info(f"模式: {'无头' if headless else '有头'}")
    success = asyncio.run(auto_login(headless=headless))
    if success:
        log.info("=" * 50)
        log.info("🎉 自动登录完成，Token 已就绪")
        log.info("=" * 50)
        return 0
    else:
        log.error("=" * 50)
        log.error("❌ 自动登录失败")
        log.error("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
