import atexit
import os
import json
import psutil
from time import sleep
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, SessionNotCreatedException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.remote.command import Command
from selenium.common.exceptions import WebDriverException

from module.config import Config
from module.game.base import GameControllerBase
from module.logger import Logger
from utils.encryption import wdp_encrypt, wdp_decrypt

class CloudGameController(GameControllerBase):
    COOKIE_PATH = "settings/cookies.enc"          # Cookies 保存地址（仅用于调试）
    GAME_URL = "https://sr.mihoyo.com/cloud"            # 游戏地址
    BROWSER_TAG = "--march-7th-assistant-sr-cloud-game" # 自定义浏览器参数作为标识，用于识别哪些浏览器进程属于三月七小助手
    BROWSER_INSTALL_PATH = os.path.join(os.getcwd(), "3rdparty", "WebBrowser") # 浏览器安装路径
    INTEGRATED_BROWSER_VERSION = "140.0.7339.207"      # 浏览器版本
    INTEGRATED_BROWSER_PATH = os.path.join(BROWSER_INSTALL_PATH, "chrome", "win64", INTEGRATED_BROWSER_VERSION, "chrome.exe")
    INTEGRATED_DRIVER_PATH = os.path.join(BROWSER_INSTALL_PATH, "chromedriver", "win64", INTEGRATED_BROWSER_VERSION, "chromedriver.exe")
    MAX_RETRIES = 3  # 网页加载重试次数，0=不重试
    PERFERENCES = {
        "profile": {
            "content_settings": {
                "exceptions": {
                    "keyboard_lock": { # 允许 keyboard_lock 权限
                        "https://sr.mihoyo.com:443,*": {"setting": 1}
                    },
                    "clipboard": {   # 允许剪贴板读取权限
                        "https://sr.mihoyo.com:443,*": {"setting": 1}
                    }
                }
            }
        }
    }

    def __init__(self, cfg: Config, logger: Logger):
        super().__init__(script_path=cfg.script_path, logger=logger)
        self.driver = None
        self.cfg = cfg
        self.logger = logger
        atexit.register(self._clean_at_exit)
    
    def _wait_game_page_loaded(self, timeout=5) -> None:
        """等待云崩铁网页加载出来，这里以背景图是否加载出来为准"""
        if not self.driver:
            return
        for retry in range(self.MAX_RETRIES + 1):
            if retry > 0:
                self.log_warning(f"页面加载超时，正在刷新重试... ({retry}/{self.MAX_RETRIES})")
                self.driver.refresh()
            try:
                WebDriverWait(self.driver, timeout).until(
                    lambda d: d.execute_script(
                        """
                        const img = document.querySelector('#app > div.home-wrapper > picture > img');
                        if (!img) return false;
                        return img && img.complete && img.naturalWidth > 0;
                        """
                    )
                )
                return
            except TimeoutException:
                pass

        raise Exception("页面加载失败，多次刷新无效。")

    def _confirm_viewport_resolution(self) -> None:
        """
        设置网页分辨率大小
        """
        self.driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False
        })
    
    def _prepare_browser_and_driver(self, browser_type: str, integrated: bool) -> tuple[str, str]:
        self.user_profile_path = os.path.join(self.BROWSER_INSTALL_PATH, "UserProfile", self.cfg.browser_type.capitalize())
        if integrated:
            browser_path = self.INTEGRATED_BROWSER_PATH
            driver_path = self.INTEGRATED_DRIVER_PATH
            if not os.path.exists(browser_path) or not os.path.exists(driver_path):
                args = ["--browser", browser_type,
                        "--cache-path", self.BROWSER_INSTALL_PATH,
                        "--browser-version", self.INTEGRATED_BROWSER_VERSION,
                        "--force-browser-download",
                        "--skip-driver-in-path",
                        "--skip-browser-in-path"]
                if self.cfg.browser_download_use_mirror:
                    self.log_info(f"正在使用镜像源，浏览器镜像源：{self.cfg.browser_mirror_urls['chrome']}，"
                                  f"驱动镜像源：{self.cfg.browser_mirror_urls['chromedriver']}")
                    args.extend([
                        "--browser-mirror-url", self.cfg.browser_mirror_urls["chrome"],
                        "--driver-mirror-url", self.cfg.browser_mirror_urls["chromedriver"],
                    ])
                try:
                    self.log_info("正在下载浏览器和驱动...")
                    SeleniumManager().binary_paths(args)
                except WebDriverException as e:
                    raise Exception(f"浏览器和驱动下载失败：{e}")
        else:
            # 尝试在本地查找浏览器
            args = ["--browser", browser_type,
                    "--cache-path", self.BROWSER_INSTALL_PATH,
                    "--avoid-browser-download",
                    "--skip-driver-in-path"]
            if self.cfg.browser_download_use_mirror:
                if browser_type == "chrome":
                    args.extend([
                        "--driver-mirror-url", self.cfg.browser_mirror_urls["chromedriver"]
                    ])
                elif browser_type == "edge":
                    args.extend([
                        "--driver-mirror-url", self.cfg.browser_mirror_urls["edgedriver"]
                    ])
            try:
                result = SeleniumManager().binary_paths(args)
            except WebDriverException as e:
                raise Exception(f"查找 {browser_type} 浏览器出错：{e}")
            browser_path = result["browser_path"]
            driver_path = result["driver_path"]
        self.log_debug(f"browser_path = {browser_path}, driver_path = {driver_path}")
        return browser_path, driver_path
    
    def _get_browser_arguments(self, headless) -> list[str]:
        args = [
            self.BROWSER_TAG,   # 标记浏览器是由脚本启动
            "--disable-infobars",   # 去掉提示 "Chrome测试版仅适用于自动测试。" 和 "浏览器正由自动测试软件控制。"
            "--lang=zh-CN",     # 浏览器语言中文
            "--log-level=3",    # 浏览器日志等级为error
            f"--force-device-scale-factor={float(self.cfg.browser_scale_factor)}",  # 设置缩放
            f"--app={self.GAME_URL}",   # 以应用模式启动
            "--disable-blink-features=AutomationControlled",  # 去除自动化痕迹，防止被人机验证
            f"--remote-debugging-port={self.cfg.browser_debug_port}",   # 调试端口，可用于复用浏览器
        ]
        if self.cfg.browser_persistent_enable:
            args += [
                f"--user-data-dir={self.user_profile_path}",   # UserProfile 路径
                "--profile-directory=Default",            # UserProfile 名称
            ]
        if headless:
            args += [
                "--headless=new",  # 无窗口模式
                "--mute-audio",    # 后台静音
            ]
        if self.cfg.cloud_game_fullscreen_enable and not headless:
            args.append("--start-fullscreen")  # 全屏启动
        args.extend(self.cfg.browser_launch_argument) # 用户自定义参数
        return args

    def _connect_or_create_browser(self, headless=False) -> None:
        """尝试连接到现有的（由小助手启动的）浏览器，如果没有，那就创建一个"""
        browser_type = "chrome" if self.cfg.browser_type in ["integrated", "chrome"] else "edge"
        integrated = self.cfg.browser_type=="integrated"
        first_run = False
        browser_path, driver_path = self._prepare_browser_and_driver(browser_type, integrated)
        
        if not os.path.exists(self.user_profile_path):
            first_run = True
        
        if browser_type == "chrome":
            options = ChromeOptions()
            service = ChromeService(executable_path=driver_path, log_path=os.devnull)
            webdriver_type = webdriver.Chrome
        else: #edge
            options = EdgeOptions()
            service = EdgeService(executable_path=driver_path, log_path=os.devnull)
            webdriver_type = webdriver.Edge
        # 记录 driver 可执行路径和 service，以便后续清理 chromedriver 进程
        self.driver_path = driver_path
        self._webdriver_service = service
        
        # 关掉 headless 不匹配的浏览器，防止端口冲突
        if self.close_all_m7a_browser(headless=not headless):
            self.log_info(f"已关闭正在运行的{'前台' if headless else '后台'}浏览器")
        if self.get_m7a_browsers(headless=headless):
            # 如果发现已经有浏览器，尝试直接连接
            try:
                options.debugger_address = f"127.0.0.1:{self.cfg.browser_debug_port}"
                self.driver = webdriver_type(service=service, options=options)
                self.log_info("已连接到现有浏览器")
                return # 连接成功，直接返回
            except Exception:
                self.log_info(f"连接现有浏览器失败")
                self.close_all_m7a_browser() # 连接失败，关闭所有浏览器
                options = None
            
        self.log_info(f"正在启动 {browser_type} 浏览器")
        options.binary_location = browser_path
        options.add_experimental_option("prefs", self.PERFERENCES)  # 允许云游戏权限权限

        # 设置浏览器启动参数
        for arg in self._get_browser_arguments(headless=headless):
            options.add_argument(arg)
        
        try:
            self.driver = webdriver_type(service=service, options=options)
        except SessionNotCreatedException as e:
            self.log_error(f"浏览器启动失败: {e}")
            self.log_error("如果设置了浏览器启动参数，请去掉所有浏览器启动参数后重试")
            self.log_error("如果仍然存在问题，请更换浏览器重试")
            raise Exception("浏览器启动失败")
        
        if not self.cfg.cloud_game_fullscreen_enable:
            self.driver.set_window_size(1920, 1120)
        if first_run or not self.cfg.browser_persistent_enable:
            self._load_initial_local_storage()
        if self.cfg.auto_battle_detect_enable:
            self.change_auto_battle(True) 
        if self.cfg.browser_dump_cookies_enable:
            self._load_cookies()
        self._refresh_page()

    def _restart_browser(self, headless=False) -> None:
        """重启浏览器"""
        self.stop_game()
        self._connect_or_create_browser(headless=headless)
    
    def _load_initial_local_storage(self) -> bool:
        """加载初始配置，去除初始引导，免责协议等弹窗"""

        try:
            with open("assets/config/initial_local_storage.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            # settings = json.loads(data["clgm_web_app_settings_hkrpg_cn"])
            # settings["videoMode"] = self.cfg.cloud_game_smooth_first_enable if 1 else 0
            # data["clgm_web_app_settings_hkrpg_cn"] = json.dumps(settings)

            # client_config = json.loads(data["clgm_web_app_client_store_config_hkrpg_cn"])
            # client_config["speedLimitGearId"] = self.cfg.cloud_game_video_quality
            # client_config["fabPosition"]["x"] = self.cfg.cloud_game_fab_pos_x
            # client_config["fabPosition"]["y"] = self.cfg.cloud_game_fab_pos_y
            # client_config["showGameStatBar"] = self.cfg.cloud_game_status_bar_enable
            # client_config["gameStatBarType"] = self.cfg.cloud_game_status_bar_type
            # client_config["volume"] = self.cfg.browser_headless_enable if 0 else 1
            # data["clgm_web_app_client_store_config_hkrpg_cn"] = json.dumps(client_config)

            # 注入浏览器
            for key, value in data.items():
                self.driver.execute_script(
                    "window.localStorage.setItem(arguments[0], arguments[1]);",
                    key,
                    value,
                )
            self.log_info("加载初始配置成功")
            return True
        except Exception as e:
            self.log_error(f"加载初始配置失败 {e}")
            return False

    def _save_cookies(self) -> bool:
        """保存 Cookies （Debug only）""" 
        if not self.driver:
            return
        try:
            cookies_json = json.dumps(self.driver.get_cookies(), ensure_ascii=False, indent=4)
            with open(self.COOKIE_PATH, "wb") as f:
                # f.write(wdp_encrypt(cookies_json.encode()))
                f.write(cookies_json.encode())
            self.log_info("登录信息保存成功。")
        except Exception as e:
            self.log_error(f"保存 cookies 失败: {e}")

    def _load_cookies(self) -> bool:
        """加载 Cookies （Debug only）"""
        if not self.driver:
            return False
        try:
            with open(self.COOKIE_PATH, "rb") as f:
                # cookies = json.loads(wdp_decrypt(f.read()).decode())
                cookies = json.loads(f.read().decode())

            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass  # 忽略无效 cookie

            self.driver.refresh()
            self.log_info("登录信息加载成功。")
            return True
        except FileNotFoundError:
            self.log_info("cookies 文件不存在。")
            return False
        except Exception as e:
            self.log_error(f"加载 cookies 失败: {e}")
            return False
    
    def _refresh_page(self) -> None:
        if self.driver:
            self.driver.refresh()
            self._wait_game_page_loaded()

    def _check_login(self, timeout=5) -> bool:
        """检查是否已经登录"""
        if not self.driver:
            return None
        
        logged_in_selector = "div.user-aid.wel-card__aid, .game-player, [class*='waiting-in-queue']"
        not_logged_in_id = "mihoyo-login-platform-iframe"

        try:
            state = WebDriverWait(self.driver, timeout).until(
                lambda d: (
                    "logged_in"
                    if d.find_elements(By.CSS_SELECTOR, logged_in_selector)
                    else (
                        "not_logged_in"
                        if d.find_elements(By.ID, not_logged_in_id)
                        else None
                    )
                )
            )

            return state == "logged_in"
        except TimeoutException:
            self.log_warning("检测登录状态超时：未出现登录或未登录标志元素")
            return None
            
    def _click_enter_game(self, timeout=5) -> None:
        """
        点击‘进入游戏’按钮。
        """
        if not self.driver:
            return
        
        game_selector = ".game-player"
        enter_button_selector = "div.wel-card__content--start"
        try:
            if self.driver.find_elements(By.CSS_SELECTOR, game_selector):
                self.log_info("已在游戏中")
                return 
            enter_button = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, enter_button_selector))
            )
            self.driver.execute_script("arguments[0].click();", enter_button)
        except Exception as e:
            self.log_error(f"点击进入游戏按钮游戏异常: {e}")
            raise e
        
    def _wait_in_queue(self, timeout=600) -> bool:
        """排队等待进入"""
        in_queue_selector = "[class*='waiting-in-queue']"
        cloud_game_selector = ".game-player"
        select_queue_selector = "[aria-labelledby*='请选择排队队列']"
        
        try:
            # 检查是否需要排队
            status = WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("""
                    if (document.querySelector(arguments[0])) return "game_running";
                    else if (document.querySelector(arguments[1])) return "in_queue";
                    else if (document.querySelector(arguments[2])) return "select_queue";
                    else return null;
                """, cloud_game_selector, in_queue_selector, select_queue_selector)
            )
            
            select_retries = 0
            while status == "select_queue":
                select_retries += 1
                if select_retries >= 5:
                    self.log_error("选择排队队列超时")
                    return False
                self.log_info("检测到选择排队队列界面，选择普通队列")
                self.driver.execute_script("""
                    try {
                        document.getElementsByClassName("coin-prior-choose-item-include-info")[1].click();
                    } catch(e) {}
                """)
                sleep(2)
                status = WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("""
                        if (document.querySelector(arguments[0])) return "game_running";
                        else if (document.querySelector(arguments[1])) return "in_queue";
                        else if (document.querySelector(arguments[2])) return "select_queue";
                        else return null;
                    """, cloud_game_selector, in_queue_selector, select_queue_selector)
                )
            
            if status == "game_running":
                self.log_info("游戏已启动，无需排队")
                return True
            elif status == "in_queue":
                self.log_info("正在排队...")
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, in_queue_selector))
                    )
                    self.log_info("排队成功，正在进入游戏")
                    return True
                except TimeoutException:
                    self.log_error("排队超时")
                    return False
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_error(f"等待排队异常: {e}")
            return False
    
    def _clean_at_exit(self) -> None:
        """当脚本退出时，关闭所有 headless 浏览器"""
        if self.close_all_m7a_browser(headless=True):
            self.log_info("已关闭所有后台浏览器")

        # 退出时再尝试清理 chromedriver 进程（防止残留）
        try:
            closed = self._terminate_chromedriver_processes()
            if closed:
                self.log_info("已关闭残留的 chromedriver 进程")
        except Exception as e:
            self.log_warning(f"退出时清理 chromedriver 进程失败: {e}")
    
    def download_intergrated_browser(self) -> bool:
        self._prepare_browser_and_driver(browser_type="chrome", integrated=True)

    def is_integrated_browser_downloaded(self) -> bool:
        """当前是否已经下载内置浏览器"""
        return os.path.exists(self.INTEGRATED_BROWSER_PATH) and os.path.exists(self.INTEGRATED_DRIVER_PATH)
    
    def get_m7a_browsers(self, headless=None) -> list[psutil.Process]:
        """
        获取由小助手打开的浏览器
        headless: None 所有，True 仅 headless 无窗口浏览器，False 仅有窗口浏览器
        
        return 浏览器的 Process
        """
        all_proc = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['name'] in ('chrome.exe', 'msedge.exe'):
                cmdline = proc.info['cmdline']
                if self.BROWSER_TAG in cmdline and (headless is None or (headless == ("--headless=new" in cmdline))):
                    all_proc.append(proc)
        return all_proc
                    
    def close_all_m7a_browser(self, headless=None) -> list[psutil.Process]:
        """
        关闭所有由小助手打开的浏览器
        headless: None 所有，True 仅 headless 无窗口浏览器，False 仅 headful 有窗口浏览器
        
        return 被关闭浏览器的 Process
        """
        closed_proc = []
        for proc in self.get_m7a_browsers(headless=headless) or []:
            try:
                proc.terminate()
                closed_proc.append(proc)
            except Exception:
                pass

        # 也尝试关闭与当前 driver_path 对应的 chromedriver 进程
        try:
            chromedrivers = []
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'ppid']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'chromedriver.exe':
                        chromedrivers.append(proc)
                except Exception:
                    continue

            for proc in chromedrivers:
                try:
                    exe_path = None
                    try:
                        exe_path = proc.info.get('exe') or proc.exe()
                    except Exception:
                        exe_path = None

                    # 如果我们有记录的 driver_path，优先匹配可执行文件路径
                    if hasattr(self, 'driver_path') and self.driver_path and exe_path and os.path.normcase(exe_path) == os.path.normcase(self.driver_path):
                        proc.terminate()
                        closed_proc.append(proc)
                    else:
                        # 否则，若 chromedriver 的父进程是当前进程，认为是残留并终止
                        if proc.info.get('ppid') == os.getpid():
                            proc.terminate()
                            closed_proc.append(proc)
                except Exception:
                    continue
        except Exception:
            pass

        return closed_proc

    def _terminate_chromedriver_processes(self) -> list[psutil.Process]:
        """单独清理 chromedriver 进程并返回被关闭的进程列表"""
        closed = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'ppid']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == 'chromedriver.exe':
                    exe_path = None
                    try:
                        exe_path = proc.info.get('exe') or proc.exe()
                    except Exception:
                        exe_path = None

                    if hasattr(self, 'driver_path') and self.driver_path and exe_path and os.path.normcase(exe_path) == os.path.normcase(self.driver_path):
                        proc.terminate()
                        closed.append(proc)
                    elif proc.info.get('ppid') == os.getpid():
                        proc.terminate()
                        closed.append(proc)
            except Exception:
                continue
        return closed
        
    def try_dump_page(self, dump_dir="logs/webdump") -> None:
        if self.driver:
            os.makedirs(dump_dir, exist_ok=True)
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            png_path = os.path.join(dump_dir, f"{ts}.png")
            self.driver.save_screenshot(png_path)

            html_path = os.path.join(dump_dir, f"{ts}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)

            self.log_error(f"相关页面和截图已经保存到：{dump_dir}")
    
    def start_game_process(self) -> bool:
        """启动浏览器进程"""
        try:
            self._connect_or_create_browser(headless=self.cfg.browser_headless_enable)
            self._confirm_viewport_resolution()
            return True
        except Exception as e:
            self.log_error(f"启动或连接浏览器失败 {e}")
            return False
    
    def is_in_game(self) -> bool:
        if self.driver:
            return True if self.driver.find_elements(By.CSS_SELECTOR, ".game-player") else False
        
    def enter_cloud_game(self) -> bool:
        """进入云游戏"""
        try:            
            # 检测登录状态
            while not self._check_login():
                self.log_info("未登录")
                
                # 如果是 headless，则以非 headless 模式重启启动让用户登录
                if self.cfg.browser_headless_enable:
                    self._restart_browser(headless=False)
                    
                self.log_info("请在浏览器中完成登录操作")
                
                # 循环检测用户是否登录
                while not self._check_login():
                    sleep(2)
                    
                self.log_info("检测到登录成功")
                
                # 如果为 headless 模式，则重启浏览器回到 headless 模式
                if self.cfg.browser_headless_enable:
                    if self.cfg.browser_dump_cookies_enable:
                        self._save_cookies()
                    self._restart_browser(headless=True)
            
            if self.cfg.browser_dump_cookies_enable:
                self._save_cookies()
            self._click_enter_game()
            if not self._wait_in_queue(int(self.cfg.cloud_game_max_queue_time) * 60):
                return False
            self._confirm_viewport_resolution() # 将浏览器内部分辨率设置为 1920x1080
            
            self.log_info("进入云游戏成功")
            return True 
        except Exception as e:
            self.try_dump_page()
            self.log_error(f"进入云游戏失败: {e}")
            return False
    
    def take_screenshot(self) -> bytes:
        """浏览器内截图"""
        if not self.driver:
            return None
        png = self.driver.get_screenshot_as_png()
        return png
    
    def execute_cdp_cmd(self, cmd: str, cmd_args: dict):
        return self.driver.execute_cdp_cmd(cmd, cmd_args)
    
    def get_window_handle(self) -> int:
        import win32gui
        return win32gui.FindWindow(None, "云·星穹铁道")
    
    def switch_to_game(self) -> bool:
        if self.cfg.browser_headless_enable:
            self.log_warning("游戏切换至前台失败：当前为无窗口模式")
            return False
        else:
            return super().switch_to_game()
    
    def get_input_handler(self):
        from module.automation.cdp_input import CdpInput
        return CdpInput(cloud_game=self, logger=self.logger)
    
    def copy(self, text):
        self.driver.execute_script("""
            (function copy(text) {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);

                ta.focus();
                ta.select();
                document.execCommand('copy');

                document.body.removeChild(ta);
            })(arguments[0]);
        """, text)

    def change_auto_battle(self, status: bool) -> None:
        """从 local storage 中读取并修改 auto battle"""
        ls = json.loads(self.driver.execute_script("return JSON.stringify(localStorage)"))
        cloud = json.loads(ls.get("cg_hkrpg_cn_cloudData", "{}"))
        cloud.setdefault("value", {})
        save = json.loads(cloud["value"].get("RPGCloudSave", "{}") or "{}")
        int_dicts = save.get("IntDicts", {})

        int_dicts["OtherSettings_AutoBattleOpen"] = int(status)
        int_dicts["OtherSettings_IsSaveBattleSpeed"] = int(status)

        save["IntDicts"] = int_dicts
        cloud["value"]["RPGCloudSave"] = json.dumps(save)
        ls["cg_hkrpg_cn_cloudData"] = json.dumps(cloud)

        for k, v in ls.items():
            self.driver.execute_script(f"localStorage.setItem('{k}', arguments[0]);", v)

    def stop_game(self) -> bool:
        """退出游戏，关闭浏览器"""
        if self.driver:
            try:
                self.driver.execute(Command.CLOSE)
                self.log_info("关闭浏览器成功")
            except Exception:
                pass
            self.driver.quit()
            self.driver = None
            
        # 清理所有未正常退出的浏览器
        try:
            if self.close_all_m7a_browser():
                self.log_info("检测到由小助手启动的浏览器，已成功关闭")
        except Exception as e:
            self.log_warning(f"检测到由小助手启动的浏览器，关闭失败: {e}")
            return False
        
        return True
            
