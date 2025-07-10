import base64
import os
from utils.registry.gameaccount import gamereg_uid, gamereg_export, gamereg_import, gamereg_delete_all
from module.logger import log

data_dir = "settings/accounts"
xor_key = "TI4ftRSDaP63kBxxoLoZ5KpVmRBz00JikzLNweryzZ4wecWJxJO9tbxlH9YDvjAr"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

class Account:
    def __init__(self, account_id: int, account_name: str, timestamp: int = 0):
        self.account_id = account_id
        self.account_name = account_name
        self.timestamp = timestamp

    def __str__(self):
        return f"{self.account_id}: {self.account_name}"

def read_all_account_from_files():
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

accounts = []

try:
    accounts = read_all_account_from_files()
except Exception as e:
    log.error(f"read_all_account_from_files: {e}")

def reload_all_account_from_files():
    global accounts
    accounts.clear()
    for a in read_all_account_from_files():
        accounts.append(a)

def dump_current_account():
    gamereg_uid_value = gamereg_uid()
    if gamereg_uid_value is None:
        log.warning("No account found (dump)")
        return
    account_reg_file = os.path.join(data_dir, f"{gamereg_uid_value}.reg")
    gamereg_export(account_reg_file)
    reload_all_account_from_files()

def delete_account(account_id: int):
    acc_file = os.path.join(data_dir, f"{account_id}.acc")
    if os.path.exists(acc_file):
        os.remove(acc_file)
    account_reg_file = os.path.join(data_dir, f"{account_id}.reg")
    if os.path.exists(account_reg_file):
        os.remove(account_reg_file)
    name_file = os.path.join(data_dir, f"{account_id}.name")
    if os.path.exists(name_file):
        os.remove(name_file)
    reload_all_account_from_files()

def auto_renewal_account():
    """
    更新保存的账户
    打开游戏前，游戏结束后调用，无论是否开启了多账户功能
    及时更新注册表到文件
    """
    try:
        gamereg_uid_value = gamereg_uid()
        if gamereg_uid_value is None:
            return
        if os.path.exists(os.path.join(data_dir, f"{gamereg_uid_value}.reg")):
            dump_current_account()
    except Exception as e:
        log.error(f"auto_renewal_account: {e}")

def import_account(account_id: int):
    auto_renewal_account()
    gamereg_uid_value = gamereg_uid()
    if gamereg_uid_value == account_id:
        return
    account_reg_file = os.path.join(data_dir, f"{account_id}.reg")
    if not os.path.exists(account_reg_file):
        raise FileNotFoundError(f"Account {account_id} not found (load)")
    gamereg_import(account_reg_file)

def save_account_name(account_id: int, account_name: str):
    name_file = os.path.join(data_dir, f"{account_id}.name")
    with open(name_file, "w") as f:
        f.write(account_name)
    reload_all_account_from_files()

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
    import_account(account_id)
    return True

def save_acc_and_pwd(account_id: int, account_name: str, account_pass: str):
    encrypted_text = xor_encrypt_to_base64(account_name + "," + account_pass)
    name_file = os.path.join(data_dir, f"{account_id}.acc")
    with open(name_file, "w") as f:
        f.write(encrypted_text)

def load_acc_and_pwd(account_id: int) -> (str, str):
    name_file = os.path.join(data_dir, f"{account_id}.acc")
    if not os.path.exists(name_file):
        return None, None
    with open(name_file, "r") as f:
        encrypted_text = f.read().strip()
    decrypted_text = xor_decrypt_from_base64(encrypted_text)
    return decrypted_text.split(",")

def xor_encrypt_to_base64(plaintext: str) -> str:
    secret_key = xor_key
    plaintext_bytes = plaintext.encode('utf-8')
    key_bytes = secret_key.encode('utf-8')

    encrypted_bytes = bytearray()
    for i in range(len(plaintext_bytes)):
        byte_plaintext = plaintext_bytes[i]
        byte_key = key_bytes[i % len(key_bytes)]
        encrypted_byte = byte_plaintext ^ byte_key
        encrypted_bytes.append(encrypted_byte)

    base64_encoded = base64.b64encode(encrypted_bytes).decode('utf-8')
    return base64_encoded

def xor_decrypt_from_base64(encrypted_base64: str) -> str:
    secret_key = xor_key
    encrypted_bytes = base64.b64decode(encrypted_base64.encode('utf-8'))
    key_bytes = secret_key.encode('utf-8')

    decrypted_bytes = bytearray()
    for i in range(len(encrypted_bytes)):
        byte_encrypted = encrypted_bytes[i]
        byte_key = key_bytes[i % len(key_bytes)]
        decrypted_byte = byte_encrypted ^ byte_key
        decrypted_bytes.append(decrypted_byte)

    decrypted_str = decrypted_bytes.decode('utf-8')
    return decrypted_str

def clear_reg():
    """
    清除注册表中的账户信息
    """
    gamereg_delete_all()
