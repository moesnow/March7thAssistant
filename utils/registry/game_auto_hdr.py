from typing import Literal
import winreg
import os


def get_game_auto_hdr(game_path: str) -> Literal["enable", "disable", "unset"]:
    """
    Get the Auto HDR setting for a specific game via Windows Registry.

    Parameters:
    - game_path: The file path to the game executable, ensuring Windows path conventions.

    Returns:
    - A Literal indicating the status of Auto HDR for the game: "enable", "disable", or "unset".
    """
    if not os.path.isabs(game_path):
        raise ValueError(f"'{game_path}' is not an absolute path.")

    game_path = os.path.normpath(game_path)
    reg_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    reg_key = game_path

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            existing_value, _ = winreg.QueryValueEx(key, reg_key)
            settings = dict(item.split("=") for item in existing_value.split(";") if item)
            hdr_status = settings.get("AutoHDREnable", None)
            if hdr_status == "2097":
                return "enable"
            elif hdr_status == "2096":
                return "disable"
            else:
                return "unset"
    except FileNotFoundError:
        return "unset"
    except Exception as e:
        raise Exception(f"Error getting Auto HDR status for '{game_path}': {e}")


def set_game_auto_hdr(game_path: str, status: Literal["enable", "disable", "unset"] = "unset"):
    """
    Set, update, or unset the Auto HDR setting for a specific game via Windows Registry,
    without affecting other settings. Ensures the game path is an absolute path
    and raises exceptions on errors instead of printing.

    Parameters:
    - game_path: The file path to the game executable, ensuring Windows path conventions.
    - status: Literal indicating the desired status for Auto HDR. One of "enable", "disable", or "unset".
    """
    if not os.path.isabs(game_path):
        raise ValueError(f"'{game_path}' is not an absolute path.")

    game_path = os.path.normpath(game_path)
    reg_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    reg_key = game_path

    hdr_value = {"enable": "2097", "disable": "2096"}.get(status, None)

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            if status == "unset":
                try:
                    existing_value, _ = winreg.QueryValueEx(key, reg_key)
                    settings = dict(item.split("=") for item in existing_value.split(";") if item)
                    if "AutoHDREnable" in settings:
                        del settings["AutoHDREnable"]
                        updated_value = ";".join([f"{k}={v}" for k, v in settings.items()]) + ";"
                        if settings:
                            winreg.SetValueEx(key, reg_key, 0, winreg.REG_SZ, updated_value)
                        else:
                            winreg.DeleteValue(key, reg_key)
                except FileNotFoundError:
                    pass
            else:
                try:
                    existing_value, _ = winreg.QueryValueEx(key, reg_key)
                except FileNotFoundError:
                    existing_value = ""
                settings = dict(item.split("=") for item in existing_value.split(";") if item)
                if hdr_value is not None:
                    settings["AutoHDREnable"] = hdr_value
                updated_value = ";".join([f"{k}={v}" for k, v in settings.items()]) + ";"
                winreg.SetValueEx(key, reg_key, 0, winreg.REG_SZ, updated_value)
    except Exception as e:
        raise Exception(f"Error setting Auto HDR for '{game_path}' with status '{status}': {e}")
