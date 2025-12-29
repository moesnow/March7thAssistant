from typing import Tuple, Optional
import winreg
import json
import os

# Registry key paths for different server regions
registry_key_path_cn = r"SOFTWARE\miHoYo\崩坏：星穹铁道"
registry_key_path_oversea = r"SOFTWARE\Cognosphere\Star Rail"

# Specify the value name (assumed to be the same for both CN and international servers)
# International server players should verify these key names are correct
resolution_value_name = "GraphicsSettings_PCResolution_h431323223"
graphics_value_name = "GraphicsSettings_Model_h2986158309"


def get_server_by_registry() -> Optional[str]:
    """
    Detect and return the server region based on the installed game server.

    Returns:
        "cn" for CN server, "oversea" for international server, or None if neither exists.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key_path_cn):
            return "cn"
    except FileNotFoundError:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key_path_oversea):
                return "global"
        except FileNotFoundError:
            return None


def get_registry_key_path() -> Optional[str]:
    """
    Detect and return the registry key path based on the installed game server.

    Returns:
        The registry path for CN server if found, otherwise oversea server path, or None if neither exists.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key_path_cn):
            return registry_key_path_cn
    except FileNotFoundError:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key_path_oversea):
                return registry_key_path_oversea
        except FileNotFoundError:
            return None


# Detect the registry path at module load time
registry_key_path = get_registry_key_path()


def set_auto_battle_open_setting(value: bool) -> None:
    write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, "OtherSettings_AutoBattleOpen_h1164514826", value, winreg.REG_DWORD)


def set_is_save_battle_speed_setting(value: bool) -> None:
    write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, "OtherSettings_IsSaveBattleSpeed_h3606297293", value, winreg.REG_DWORD)


def get_auto_battle_open_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, "OtherSettings_AutoBattleOpen_h1164514826")


def get_is_save_battle_speed_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, "OtherSettings_IsSaveBattleSpeed_h3606297293")


def get_graphics_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name)


def get_game_path() -> Optional[str]:
    """
    获取游戏路径函数，尝试从注册表中读取指定键值并验证游戏可执行文件是否存在。
    支持国服和国际服。

    Returns:
        Optional[str]: 如果找到有效的游戏路径，则返回完整路径，否则返回 None。
    """
    # 注册表键路径和键值名称（国服和国际服）
    registry_paths = [
        r"Software\miHoYo\HYP\1_1\hkrpg_cn",     # 国服路径
        r"Software\Cognosphere\HYP\1_0\hkrpg_global"  # 国际服路径
    ]
    registry_value_name = "GameInstallPath"  # 游戏安装路径的键值名称

    # 尝试从不同的注册表路径中读取
    for registry_path in registry_paths:
        install_path = read_registry_value(
            winreg.HKEY_CURRENT_USER,  # 从当前用户的注册表路径中读取
            registry_path,             # 注册表的具体路径
            registry_value_name        # 需要读取的键值名称
        )

        # 如果成功读取到路径，检查对应的游戏可执行文件是否存在
        if install_path:
            game_executable = os.path.join(install_path, "StarRail.exe")  # 构造完整的游戏可执行文件路径
            if os.path.exists(game_executable):  # 验证文件路径是否存在
                return game_executable  # 返回有效的游戏路径

    # 如果路径无效或文件不存在，返回 None
    return None


def get_launcher_path() -> Optional[str]:
    """
    获取启动器路径函数，尝试从注册表中读取指定键值并验证启动器可执行文件是否存在。
    支持国服和国际服。

    Returns:
        Optional[str]: 如果找到有效的启动器路径，则返回完整路径，否则返回 None。
    """
    # 注册表键路径和键值名称（国服和国际服）
    registry_paths = [
        r"Software\miHoYo\HYP\1_1",     # 国服路径
        r"Software\Cognosphere\HYP\1_0"  # 国际服路径
    ]
    registry_value_name = "InstallPath"  # 启动器安装路径的键值名称

    # 尝试从不同的注册表路径中读取
    for registry_path in registry_paths:
        install_path = read_registry_value(
            winreg.HKEY_CURRENT_USER,  # 从当前用户的注册表路径中读取
            registry_path,             # 注册表的具体路径
            registry_value_name        # 需要读取的键值名称
        )

        # 如果成功读取到路径，检查对应的启动器可执行文件是否存在
        if install_path:
            launcher_executable = os.path.join(install_path, "launcher.exe")  # 构造完整的启动器可执行文件路径
            if os.path.exists(launcher_executable):  # 验证文件路径是否存在
                return launcher_executable  # 返回有效的启动器路径
    # 如果路径无效或文件不存在，返回 None
    return None


def get_game_resolution() -> Optional[Tuple[int, int, bool]]:
    """
    Return the game resolution from the registry value.

    This function does not take any parameters.

    Returns:
    - If the registry value exists and data is valid, it returns a tuple (width, height, isFullScreen) representing the game resolution.
    - If the registry value does not exist or data is invalid, it returns None or raises ValueError.
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, resolution_value_name)
    if value:
        data_dict = json.loads(value.decode('utf-8').strip('\x00'))
        # Convert keys to lower case to ensure case-insensitivity
        data_dict = {k.lower(): v for k, v in data_dict.items()}

        # Validate data format with case-insensitive keys
        if 'width' in data_dict and 'height' in data_dict and 'isfullscreen' in data_dict:
            if isinstance(data_dict['width'], int) and isinstance(data_dict['height'], int) and isinstance(data_dict['isfullscreen'], bool):
                return data_dict['width'], data_dict['height'], data_dict['isfullscreen']
            else:
                raise ValueError("Registry data is invalid: width, height, and isFullScreen must be of type int, int, and bool respectively.")
        else:
            raise ValueError("Registry data is missing required fields: width, height, or isFullScreen.")

    return None


def set_game_resolution(width: int, height: int, is_fullscreen: bool) -> None:
    """
    Set the resolution of the game and whether it should run in fullscreen mode.

    Parameters:
    - width: The width of the game window.
    - height: The height of the game window.
    - is_fullscreen: Whether the game should run in fullscreen mode.
    """
    data_dict = {
        'width': width,
        'height': height,
        'isFullScreen': is_fullscreen
    }
    data = (json.dumps(data_dict) + '\x00').encode('utf-8')
    write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, resolution_value_name, data, winreg.REG_BINARY)


def get_game_fps() -> Optional[int]:
    """
    Return the game FPS settings from the registry value.

    This function does not take any parameters.
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name)
    if value:
        data_dict = json.loads(value.decode('utf-8').strip('\x00'))

        # Validate data format
        if 'FPS' in data_dict:
            if isinstance(data_dict['FPS'], int):
                return data_dict['FPS']
            else:
                raise ValueError("Registry data is invalid: FPS must be of type int.")
        else:
            return 60

    return None


def set_game_fps(fps: int) -> None:
    """
    Set the FPS of the game.

    Parameters:
    - fps
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name)

    data_dict = json.loads(value.decode('utf-8').strip('\x00'))

    data_dict['FPS'] = fps
    data = (json.dumps(data_dict) + '\x00').encode('utf-8')
    write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name, data, winreg.REG_BINARY)


def read_registry_value(key, sub_key, value_name):
    """
    Read the content of the specified registry value.

    Parameters:
    - key: The handle of an open registry key.
    - sub_key: The name of the key, relative to key, to open.
    - value_name: The name of the value to query.

    Returns:
        The content of the specified value in the registry.
    """
    if sub_key is None:
        raise Exception("Registry key path not found. Please ensure the game is installed.")
    try:
        # Open the specified registry key
        registry_key = winreg.OpenKey(key, sub_key)
        # Read the content of the specified value in the registry
        value, _ = winreg.QueryValueEx(registry_key, value_name)
        # Close the registry key
        winreg.CloseKey(registry_key)
        return value
    except FileNotFoundError:
        # raise FileNotFoundError(f"Specified registry key or value not found: {sub_key}\\{value_name}")
        return None
    except Exception as e:
        raise Exception(f"Error reading registry value: {e}")


def write_registry_value(key, sub_key, value_name, data, mode) -> None:
    """
    Write a registry value to the specified registry key.

    Parameters:
    - key: The registry key.
    - sub_key: The subkey under the specified registry key.
    - value_name: The name of the registry value.
    - data: The data to be written to the registry.
    - mode: The type of data.
    """
    if sub_key is None:
        raise Exception("Registry key path not found. Please ensure the game is installed.")
    try:
        # Open or create the specified registry key
        registry_key = winreg.CreateKey(key, sub_key)
        # Write data to the registry
        winreg.SetValueEx(registry_key, value_name, 0, mode, data)
        # Close the registry key
        winreg.CloseKey(registry_key)
    except Exception as e:
        raise Exception(f"Error writing registry value: {e}")
