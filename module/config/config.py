from ruamel.yaml import YAML
import time


class Config:
    _instance = None

    def __new__(cls, config_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config_path = config_path
            cls._instance.yaml = YAML()
            cls._instance.config = cls._instance.yaml.load(cls._instance._default_config())
            cls._instance._load_config()
        return cls._instance

    def _default_config(self):
        yaml_str = """\
# 欢迎使用 March7th Assistant
# 此程序为免费开源项目 欢迎Star
# QQ交流群 855392201
# https://github.com/moesnow/March7thAssistant
locales: zh_CN # 语言（支持i18n但目前只有zh_CN）
log_level: INFO # 日志等级 INFO、DEBUG（显示更多信息）
auto_exit: 1 # 程序运行完后自动退出游戏
never_stop: 1 # 根据开拓力循环运行程序
power_limit: 160 # 等待再次运行所需开拓力

program_name: March7th Assistant
program_version: 0.0.1
game_title_name: 崩坏：星穹铁道 # 游戏窗口标题
game_process_name: StarRail # 游戏进程名
game_path: C:\\Program Files\\Star Rail\\Game\\StarRail.exe # 游戏路径

power_total: 240 # 开拓力最大值
power_rec_min: 6 # 每开拓力恢复需要的分钟数
dispatch_count: 4 # 派遣次数

instance_type: 侵蚀隧洞 # 副本类型（目前只支持侵蚀隧洞）
instance_name: 药使之径·侵蚀隧洞 # 副本名称
power_need: 40 # 一次副本所需开拓力

borrow_character_enable: 1 # 自动使用支援角色，建议四号位放无关紧要的角色避免练度导致翻车
borrow_force: 0 # 无论何时都要使用支援角色，即使设置的角色都没找到
borrow_character: # 支援角色优先级从高到低
- Seele
- Blade
- JingYuan
- Kafka
- Clara
- Welt
- Yanqing
- Himeko

dispatch_enable: 1 # 启用派遣
mail_enable: 1 # 启用领取邮件奖励
assist_enable: 1 # 启用领取支援奖励
photo_enable: 1 # 启用每日拍照
synthesis_enable: 1 # 启用每日合成/使用 材料/消耗品

fight_enable: 0 # 启用锄大地
fight_command: powershell "" # 锄大地命令（需要自己设置）
fight_timeout: 4 # 锄大地超时（单位小时）
fight_timestamp: 0 # 锄大地战斗结束时间（每天运行）

universe_enable: 0 # 启用模拟宇宙
universe_command: powershell "" # 模拟宇宙命令（需要自己设置）
universe_timeout: 14 # 模拟宇宙超时（单位小时）
universe_timestamp: 0 # 模拟宇宙战斗结束时间（每周运行）

forgottenhall_enable: 1 # 启用忘却之庭
forgottenhall_level: # 混沌回忆关卡范围
- 1
- 10
forgottenhall_retries: 3 # 混沌回忆重试次数

# 混沌回忆队伍
# 数字代表秘技使用次数
# 其中-1代表最后一个放秘技和普攻的角色（当前1-5的双BOSS层必须是远程开怪角色，否则攻击不到第二个BOSS）
# 角色对应的英文名字可以在 "March7thAssistant\\assets\\images\\character" 中查看
forgottenhall_team1: # 混沌回忆队伍1
- - Asta
  - -1
- - Natasha
  - 0
- - Tingyun
  - 2
- - JingYuan
  - 1
forgottenhall_team2: # 混沌回忆队伍2
- - Bronya
  - -1
- - Luocha
  - 1
- - SilverWolf
  - 0
- - Qingque
  - 1
forgottenhall_timestamp: 0 # 混沌回忆战斗结束时间（每周运行，如未刷新跳过）

# 可选消息通知 Telegram已适配支持发送截图
# 还支持更多推送查看下面的链接仿照格式配置即可
# https://github.com/LmeSzinc/AzurLaneAutoScript/wiki/Onepush-configuration-[CN]
notify_telegram_enable: 0 # 启用Telegram通知
notify_telegram_token: ''
notify_telegram_userid: ''
notify_telegram_api_url: ''

notify_wechatworkapp_enable: 0 # 启用企业微信应用通知
notify_wechatworkapp_corpid: ''
notify_wechatworkapp_corpsecret: ''
notify_wechatworkapp_agentid: ''

boss_enable: 0 # 暂不可用
boss_name: 不死的神实 # 暂不可用
boss_kill_required: 3 # 暂不可用

last_run_timestamp: 0 # 上次运行日常时间
boss_kill_completed: 0 # 暂不可用
"""
        return yaml_str

    def _load_config(self):
        try:  # cls._instance.yaml.load(cls._instance._default_config())
            with open(self.config_path, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
                if loaded_config:
                    self.config.update(loaded_config)
                    self.save_config()
        except FileNotFoundError:
            self.save_config()

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as file:
            self.yaml.dump(self.config, file)

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_value(self, key, value):
        self.config[key] = value
        self.save_config()

    def save_timestamp(self, key):
        self.set_value(key, time.time())

    def __getattr__(self, attr):
        if attr in self.config:
            return self.config[attr]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'")
