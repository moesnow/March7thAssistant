from typing import Tuple, Optional
import winreg
import json

# Specify the registry key path
registry_key_path = r"SOFTWARE\miHoYo\崩坏：星穹铁道"
# Specify the value name
resolution_value_name = "GraphicsSettings_PCResolution_h431323223"
graphics_value_name = "GraphicsSettings_Model_h2986158309"


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
            raise ValueError("Registry data is missing required fields: FPS.")

    return None


def set_game_fps(fps: int) -> None:
    """
    Set the FPS of the game.

    Parameters:
    - fps
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name)

    data_dict = json.loads(value.decode('utf-8').strip('\x00'))

    # Validate data format
    if 'FPS' in data_dict:
        if isinstance(data_dict['FPS'], int):
            data_dict['FPS'] = fps
            data = (json.dumps(data_dict) + '\x00').encode('utf-8')
            write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, graphics_value_name, data, winreg.REG_BINARY)
        else:
            raise ValueError("Registry data is invalid: FPS must be of type int.")
    else:
        raise ValueError("Registry data is missing required fields: FPS.")


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
    try:
        # Open the specified registry key
        registry_key = winreg.OpenKey(key, sub_key)
        # Read the content of the specified value in the registry
        value, _ = winreg.QueryValueEx(registry_key, value_name)
        # Close the registry key
        winreg.CloseKey(registry_key)
        return value
    except FileNotFoundError:
        raise FileNotFoundError(f"Specified registry key or value not found: {sub_key}\\{value_name}")
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
    try:
        # Open or create the specified registry key
        registry_key = winreg.CreateKey(key, sub_key)
        # Write data to the registry
        winreg.SetValueEx(registry_key, value_name, 0, mode, data)
        # Close the registry key
        winreg.CloseKey(registry_key)
    except Exception as e:
        raise Exception(f"Error writing registry value: {e}")
