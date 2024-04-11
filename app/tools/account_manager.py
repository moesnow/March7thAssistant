
import os
from utils.registry.gameaccount import gamereg_uid, gamereg_export, gamereg_import

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
        print("No account found")
        return
    account_reg_file = os.path.join(data_dir, f"{gamereg_uid_value}.reg")
    gamereg_export(account_reg_file)

def load_account(account_id: int):
    account_reg_file = os.path.join(data_dir, f"{account_id}.reg")
    if not os.path.exists(account_reg_file):
        print(f"Account {account_id} not found")
        return None
    gamereg_import(account_reg_file)

accounts = load_all_account()

def reload_all_account():
    global accounts
    accounts = load_all_account()
