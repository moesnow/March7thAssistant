import os
import sys
import getpass
if sys.platform == 'win32':
    import win32com.client


def apply_task_settings(task_def):
    """
    显式写全任务的运行设置，不依赖 COM 默认值。

    默认值面向“跑完即退”的短任务，与 GUI 长驻进程不兼容：
    - ExecutionTimeLimit 默认 PT72H（即任务计划属性里的
      “如果任务运行时间超过以下时间，停止任务：3 天”），到期会终止长驻的图形界面；
      PT0S 表示不限时长。
    - DisallowStartIfOnBatteries / StopIfGoingOnBatteries 默认 True，
      笔记本用电池时不开机自启，运行中切换到电池还会直接终止任务。
    - AllowHardTerminate 保持 True：请求停止后进程不退出时允许强杀兜底。

    参数:
    - task_def: Schedule.Service.NewTask 返回的任务定义对象。
    """
    settings = task_def.Settings
    settings.ExecutionTimeLimit = "PT0S"  # 不限时长，避免默认 3 天后强杀
    settings.DisallowStartIfOnBatteries = False  # 允许电池供电时启动
    settings.StopIfGoingOnBatteries = False  # 切换到电池不终止任务
    settings.AllowHardTerminate = True  # 请求停止后允许强杀


def create_task(task_name, program_path, program_args=None, delay_seconds=30):
    """
    创建计划任务，指定在用户登录时启动指定程序。

    运行设置显式写全（见 apply_task_settings），例如不限制运行时长。

    参数:
    - task_name (str): 任务的名称。
    - program_path (str): 要启动的程序的绝对路径。
    - program_args (str): 程序启动参数，默认为 None。
    - delay_seconds (int): 延迟时间，单位为秒，默认为30秒。
    """
    # 获取当前用户
    current_user = getpass.getuser()

    # 创建任务服务对象并连接到任务计划服务
    task_service = win32com.client.Dispatch("Schedule.Service")
    task_service.Connect()

    # 获取根任务文件夹
    root_folder = task_service.GetFolder("\\")

    # 创建新的任务定义
    task_def = task_service.NewTask(0)

    # 配置任务触发器（登录时触发）
    trigger = task_def.Triggers.Create(9)  # 9 表示“当用户登录时”触发
    trigger.UserId = f"{os.getenv('USERDOMAIN')}\\{os.getenv('USERNAME')}"  # 当前用户
    trigger.Delay = f"PT{delay_seconds}S"  # 设置触发延迟时间（ISO 8601 格式）

    # 配置任务操作（启动程序）
    action = task_def.Actions.Create(0)  # 0 表示启动程序
    action.Path = program_path
    if program_args:
        action.Arguments = program_args

    # 配置任务的运行设置
    task_def.RegistrationInfo.Description = f"启动 {os.path.basename(program_path)}"
    task_def.Principal.UserId = current_user  # 指定为当前用户
    task_def.Principal.LogonType = 3  # 3 表示交互用户登录
    task_def.Principal.RunLevel = 1  # 1 表示以最高权限运行

    # 配置运行时长等运行设置（显式写全，不依赖默认值）
    apply_task_settings(task_def)

    # 注册任务
    root_folder.RegisterTaskDefinition(
        task_name,
        task_def,
        6,  # 6 表示覆盖同名任务
        None,  # 无需用户名
        None,  # 无需密码
        3,  # 3 表示交互用户
        None
    )
    # print(f"任务计划 '{task_name}' 已成功创建！")


def is_task_exists(task_name):
    """
    检测指定名称的计划任务是否存在。

    参数:
    - task_name (str): 要检查的任务名称。

    返回:
    - bool: 如果任务存在，返回 True；否则返回 False。
    """
    # 创建任务服务对象并连接到任务计划服务
    task_service = win32com.client.Dispatch("Schedule.Service")
    task_service.Connect()

    # 获取根任务文件夹
    root_folder = task_service.GetFolder("\\")

    # 获取所有任务
    tasks = root_folder.GetTasks(0)  # 参数 0 表示不筛选
    for task in tasks:
        if task.Name == task_name:
            return True
    return False


def delete_task(task_name):
    """
    删除指定名称的计划任务。

    参数:
    - task_name (str): 要删除的任务名称。
    """
    # 创建任务服务对象并连接到任务计划服务
    task_service = win32com.client.Dispatch("Schedule.Service")
    task_service.Connect()

    # 获取根任务文件夹
    root_folder = task_service.GetFolder("\\")

    try:
        # 删除任务
        root_folder.DeleteTask(task_name, 0)  # 参数 0 表示普通删除
        # print(f"任务计划 '{task_name}' 已成功删除！")
    except Exception as e:
        pass
        # print(f"删除任务计划 '{task_name}' 失败：{e}")
