
import os
from utils.registry.gameaccount import gamereg_uid, gamereg_export, gamereg_import
from module.logger import log

data_dir = "settings/accounts"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

class Account:
    def __init__(self, account_id: int, account_name: str, timestamp: int = 0):
        self.account_id = account_id
        self.account_name = account_name
        self.timestamp = timestamp

    def __str__(self):
        return f"{self.account_id}: {self.account_name}"
    
def load_all_account():
    accounts = []
    for file in os.listdir(data_dir):
        if file.endswith(".reg"):
            timestamp = os.path.getmtime(os.path.join(data_dir, file))
            account_id = int(file.split(".")[0])
            account_name = str(account_id)
            name_file = os.path.join(data_dir, f"{account_id}.name")
            if os.path.exists(name_file):
                with open(name_file, "r") as f:
                    account_name = f.read().strip()
            accounts.append(Account(account_id, account_name, timestamp))
    return accounts

def dump_current_account():
    gamereg_uid_value = gamereg_uid()
    if gamereg_uid_value is None:
        log.warning("No account found (dump)")
        return
    account_reg_file = os.path.join(data_dir, f"{gamereg_uid_value}.reg")
    gamereg_export(account_reg_file)

def delete_account(account_id: int):
    account_reg_file = os.path.join(data_dir, f"{account_id}.reg")
    if os.path.exists(account_reg_file):
        os.remove(account_reg_file)
    name_file = os.path.join(data_dir, f"{account_id}.name")
    if os.path.exists(name_file):
        os.remove(name_file)

def auto_renewal_account():
    """
    更新保存的账户
    打开游戏前，游戏结束后调用，无论是否开启了多账户功能
    及时更新注册表到文件
    """
    gamereg_uid_value = gamereg_uid()
    if gamereg_uid_value is None:
        return
    if os.path.exists(os.path.join(data_dir, f"{gamereg_uid_value}.reg")):
        dump_current_account()

def load_account(account_id: int):
    account_reg_file = os.path.join(data_dir, f"{account_id}.reg")
    if not os.path.exists(account_reg_file):
        raise FileNotFoundError(f"Account {account_id} not found (load)")
    gamereg_import(account_reg_file)


def save_account_name(account_id: int, account_name: str):
    name_file = os.path.join(data_dir, f"{account_id}.name")
    with open(name_file, "w") as f:
        f.write(account_name)
    reload_all_account()

def load_to_account(account_id: int) -> bool:
    """
    将游戏账号切换到account_id
    return True: 切换成功且需要重新加载游戏
    return False: 不需要重新加载游戏
    抛出异常: 切换失败，账号不存在
    """
    gamereg_uid_value = gamereg_uid()
    if gamereg_uid_value != None and gamereg_uid_value == account_id:
        return False
    load_account(account_id)
    return True

accounts = load_all_account()

def reload_all_account():
    global accounts
    accounts.clear()
    for a in load_all_account():
        accounts.append(a)
