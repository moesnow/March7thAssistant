"""按当前登录账号开始执行本轮账号队列。"""
from module.automation import auto
from module.config import cfg
from module.config.accounts import account_config, bind_uid
from module.logger import log
from module.screen import screen
from utils.registry.gameaccount import gamereg_uid
from tasks.game import wait_until


# 坐标均为相对屏幕的 (x, y, 宽, 高)，像素坐标按 1920×1080 换算。
FULL_SCREEN_REGION = (0, 0, 1, 1)
RETURN_TITLE_BUTTON_REGION = (1845 / 1920, 952 / 1080, 48 / 1920, 54 / 1080)
RETURN_TITLE_PROMPT_REGION = (0.35, 0.42, 0.3, 0.12)
RETURN_TITLE_CONFIRM_REGION = (0.51, 0.58, 0.20, 0.10)
LOGOUT_BUTTON_REGION = (0.92, 0.20, 0.08, 0.22)
KEEP_LOGIN_PROMPT_REGION = (0.35, 0.47, 0.3, 0.12)
KEEP_LOGIN_CHECKBOX_REGION = (690 / 1920, 560 / 1080, 22 / 1920, 22 / 1080)
LOGOUT_CONFIRM_REGION = (0.5, 0.59, 0.14, 0.08)
OTHER_ACCOUNT_PROMPT_REGION = (0.35, 0.62, 0.3, 0.09)
ACCOUNT_DROPDOWN_BUTTON_REGION = (1190 / 1920, 486 / 1080, 22 / 1920, 22 / 1080)
ACCOUNT_LIST_REGION = (0.40, 0.50, 0.20, 0.16)
LOGIN_BUTTON_REGION = (0.35, 0.54, 0.3, 0.09)
WELCOME_MESSAGE_REGION = (0.35, 0.1, 0.3, 0.15)
ENTER_WORLD_BUTTON_REGION = (0.45, 0.76, 0.1, 0.04)


def return_to_title():
    """通过手机菜单返回标题页。"""
    screen.change_to("menu")
    auto.click_element(RETURN_TITLE_BUTTON_REGION, "crop")
    wait_for_text("是否返回登录页面", crop=RETURN_TITLE_PROMPT_REGION, include=True)
    auto.click_element("确认", "text", crop=RETURN_TITLE_CONFIRM_REGION)
    wait_for_text("登出", crop=LOGOUT_BUTTON_REGION)


def current_uid():
    # 进入大世界后游戏才会更新此值，复用已有账户管理的 UID 读取。
    screen.change_to("main")
    return str(gamereg_uid())


def wait_for_text(text, crop=FULL_SCREEN_REGION, *, include=False):
    if not wait_until(lambda: auto.find_element(text, "text", crop=crop, include=include), 30, period=0.2):
        raise TimeoutError(f"多账号切换：等待「{text}」超时")


def switch_account(account):
    # 从大世界切换时先返回标题页。
    if not auto.find_element("登出", "text", crop=LOGOUT_BUTTON_REGION):
        return_to_title()
    auto.click_element("登出", "text", crop=LOGOUT_BUTTON_REGION)
    wait_for_text("退出并保留登录记录", crop=KEEP_LOGIN_PROMPT_REGION)
    # 点击圆圈选择保留登录记录。
    auto.click_element(KEEP_LOGIN_CHECKBOX_REGION, "crop")
    auto.click_element("退出", "text", crop=LOGOUT_CONFIRM_REGION)
    wait_for_text("登录其他账号", crop=OTHER_ACCOUNT_PROMPT_REGION)
    auto.click_element(ACCOUNT_DROPDOWN_BUTTON_REGION, "crop")
    # 符号账号通过图像定位，文字账号按显示名查找。
    if account["login_name"] == "*.":
        target = "./assets/images/screen/login_account_star_dot.png"
        if not wait_until(lambda: auto.find_element(target, "image", 0.9, crop=ACCOUNT_LIST_REGION),
                          30, period=0.2):
            raise TimeoutError("多账号切换：等待「*.」超时")
        auto.click_element(target, "image", 0.9, crop=ACCOUNT_LIST_REGION)
    else:
        wait_for_text(account["login_name"], crop=ACCOUNT_LIST_REGION)
        auto.click_element(account["login_name"], "text", crop=ACCOUNT_LIST_REGION, include=False)
    wait_for_text("进入游戏", crop=LOGIN_BUTTON_REGION)
    auto.click_element("进入游戏", "text", crop=LOGIN_BUTTON_REGION)

    def logged_in():
        if auto.find_element("欢迎进入游戏", "text", include=True, crop=WELCOME_MESSAGE_REGION):
            log.info("已识别到欢迎进入游戏提示")
            return True
        # 欢迎条短暂显示，错过后标题页的登出按钮同样说明登录完成。
        return auto.find_element("登出", "text", crop=LOGOUT_BUTTON_REGION)

    if not wait_until(logged_in, 30, period=0.2):
        raise TimeoutError("多账号切换：等待登录完成超时")
    auto.click_element(ENTER_WORLD_BUTTON_REGION, "crop")
    if not wait_until(lambda: screen.get_current_screen(autotry=False, max_retries=1),
                      cfg.start_game_timeout * 60):
        raise TimeoutError("多账号切换：等待进入游戏超时")
    return current_uid()


def get_enabled_accounts():
    pending = [account for account in cfg.get_value("multi_accounts", []) if account["enabled"]]
    if not pending:
        raise ValueError("多账号运行未配置启用账号，请在设置的账号管理中添加并启用至少一个账号")
    return pending


def run_accounts(run_tasks):
    pending = get_enabled_accounts()
    uid = current_uid()
    while pending:
        account = next((item for item in pending if item["uid"] and str(item["uid"]) == uid), None)
        if account is None:
            account = pending[0]
            uid = switch_account(account)
            if not account["uid"]:
                account["uid"] = uid
                bind_uid(cfg, account["id"], uid)
        log.info(f"开始运行账号：{account['name'] or account['login_name']}（UID：{uid}）")
        with account_config(cfg, account):
            # 切换账号后重新读取培养目标。
            from tasks.daily.buildtarget import BuildTarget
            BuildTarget._initialized = False
            run_tasks()
        pending.remove(account)
        log.info(f"账号运行完成，本轮剩余 {len(pending)} 个账号")
