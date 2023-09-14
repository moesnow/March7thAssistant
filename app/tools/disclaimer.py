# coding:utf-8
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from managers.config_manager import config
import markdown
import requests
import json
import sys

from ..card.messagebox4 import MessageBox4


def disclaimer(self):
    content = '''
本软件是一个外部工具旨在自动化崩坏星轨的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。

该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。

该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. 

The developer team has the final right to interpret this project. 

All problems arising from the use of this software are not related to this project and the developer team. 

If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. 

The problems and consequences arising from this software have nothing to do with it.

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。

使用本软件产生的所有问题与本项目与开发者团队无关。

若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。


请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

    "严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
    "一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"
'''
    try:
        w = MessageBox4(f"免责声明", markdown.markdown(content), self.window())
        if w.exec():
            config.set_value("agreed_to_disclaimer", True)
        else:
            sys.exit(0)
    except Exception as e:
        sys.exit(0)
