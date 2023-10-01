# coding:utf-8
from managers.config_manager import config
import markdown
import sys

from ..card.messageboxdisclaimer import MessageBoxDisclaimer


def disclaimer(self):
    html_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
    content = '''
- 此程序为免费开源项目，如果你付了钱请立刻退款！！！

- 本项目已经因倒卖行为受到严重威胁，请帮助我们！！！

- 咸鱼倒狗4000+！你付给倒狗的每一分钱都会让开源自动化更艰难，请退款并举报商家！！！

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。

使用本软件产生的所有问题与本项目与开发者团队无关。

请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

    "严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
    "一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"
'''
    try:
        w = MessageBoxDisclaimer(f"免责声明", html_style + markdown.markdown(content), self.window())
        if w.exec():
            config.set_value("agreed_to_disclaimer", True)
            import os
            path = os.path.join(os.getenv('LocalAppData'), "March7thAssistant\\disclaimer")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'a').close()
        else:
            sys.exit(0)
    except Exception as e:
        sys.exit(0)
