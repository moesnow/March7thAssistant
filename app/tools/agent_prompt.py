# coding:utf-8
"""设置 → 关于 →「AI 助手」：复制给 AI 助手的提示词。"""
import os

from module.config import cfg
from module.localization import tr

# 随包发布的 AI Agent 使用说明（Skill），相对程序目录
SKILL_DIR = os.path.join("assets", "agent", "skills", "march7th-assistant")


def build_agent_prompt(install_dir=None) -> str:
    """带上本机安装目录与版本，让 AI 助手直接读取随包发布的使用说明（Skill）。"""
    install_dir = os.path.abspath(install_dir or ".")
    skill_dir = os.path.join(install_dir, SKILL_DIR)
    return tr(
        "我在这台电脑上安装了「三月七小助手」（崩坏：星穹铁道自动化工具），版本 {version}，安装目录：{install_dir}\n"
        "请先阅读 {skill_file} ，按其中的说明帮我操作它。\n"
        "如果你支持 Skill（技能），请把文件夹 {skill_dir} 复制到你的用户级技能目录"
        "（例如 ~/.agents/skills/ 或 ~/.claude/skills/），以后就不需要我再提供这段说明。"
    ).format(
        version=cfg.version,
        install_dir=install_dir,
        skill_file=os.path.join(skill_dir, "SKILL.md"),
        skill_dir=skill_dir,
    )
