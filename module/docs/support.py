"""Actions on the help card; logs_dir follows the active desktop data layout."""
from dataclasses import dataclass
from pathlib import Path

from utils.paths import logs_dir

QQ_GROUP_URL = "https://qm.qq.com/q/C3IryUWCQw"


@dataclass(frozen=True, slots=True)
class SupportActions:
    faq: str
    qq_url: str
    log_folder: Path


def support_actions():
    return SupportActions("doc:FAQ", QQ_GROUP_URL, Path(logs_dir()))
