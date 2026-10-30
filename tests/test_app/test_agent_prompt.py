# coding:utf-8
"""设置 → 关于 →「AI 助手」：复制给 AI 助手的提示词，以及随包发布的 Agent 说明文件。"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / "assets" / "agent" / "skills" / "march7th-assistant"


def test_prompt_points_to_bundled_skill(monkeypatch):
    monkeypatch.chdir(REPO)
    from app.tools.agent_prompt import build_agent_prompt
    from module.config import cfg

    prompt = build_agent_prompt()
    assert str(REPO) in prompt
    assert cfg.version in prompt
    assert str(SKILL_DIR / "SKILL.md") in prompt
    assert "{" not in prompt  # 占位符全部替换


def test_skill_frontmatter_follows_agent_skills_spec():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md 必须以 YAML frontmatter 开头"
    from ruamel.yaml import YAML
    meta = YAML(typ="safe").load(match.group(1))
    # name：小写字母、数字与连字符，且与目录名一致；description 不超过 1024 字符
    assert meta["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta["name"])
    assert 0 < len(meta["description"]) <= 1024
    assert all(isinstance(value, str) for value in (meta.get("metadata") or {}).values())


def test_skill_relative_links_exist():
    for md in [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]:
        for link in re.findall(r"\]\(([^)#:]+\.md)(?:#[^)]*)?\)", md.read_text(encoding="utf-8")):
            assert (md.parent / link).exists(), f"{md.name} 引用的 {link} 不存在"


def test_documented_cli_flags_exist():
    """Skill 与 AGENTS.md 里写到的命令行参数必须真实存在于 main.py。"""
    main_source = (REPO / "main.py").read_text(encoding="utf-8")
    docs = [SKILL_DIR / "SKILL.md", *SKILL_DIR.glob("references/*.md"), REPO / "assets" / "agent" / "AGENTS.md"]
    flags = set()
    for doc in docs:
        flags.update(re.findall(r"m7a\.exe[^`\n]*?(--[a-z][a-z-]+)", doc.read_text(encoding="utf-8")))
    assert flags, "未从文档中解析到任何参数"
    for flag in flags:
        assert f"'{flag}'" in main_source, f"文档中的 {flag} 在 main.py 中不存在"
