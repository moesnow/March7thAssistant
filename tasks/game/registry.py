from managers.logger_manager import logger
import winreg


class Registry:
    @staticmethod
    def read_registry_value(key, sub_key, value_name):
        try:
            # 打开指定的注册表项
            registry_key = winreg.OpenKey(key, sub_key)
            # 读取注册表中指定值的内容
            value, _ = winreg.QueryValueEx(registry_key, value_name)
            # 关闭注册表项
            winreg.CloseKey(registry_key)
            return value
        except FileNotFoundError:
            logger.debug("指定的注册表项未找到")
        except Exception as e:
            logger.error("发生错误:", e)
        return None

    @staticmethod
    def write_registry_value(key, sub_key, value_name, data):
        try:
            # 打开或创建指定的注册表项
            registry_key = winreg.CreateKey(key, sub_key)
            # 将数据写入注册表
            winreg.SetValueEx(registry_key, value_name, 0, winreg.REG_BINARY, data)
            # 关闭注册表项
            winreg.CloseKey(registry_key)
            logger.debug("成功写入注册表值")
        except Exception as e:
            logger.error("写入注册表值时发生错误:", e)
