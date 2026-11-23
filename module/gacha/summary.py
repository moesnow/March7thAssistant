"""Page-level read model. Keep the returned snapshot when switching segments."""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Mapping

from module.gacha.stats import Stats, all_stats
from module.gacha.store import Account, GachaStore, Issue, _load, _read_issue, file_stamp, updated_text


@dataclass(frozen=True, slots=True)
class Summary:
    accounts: tuple[Account, ...]
    selected: Account | None
    updated_label: str
    pools: Mapping[str, Stats]
    issues: tuple[Issue, ...]


@lru_cache(maxsize=8)
def _statistics(path=None, stamp=None):
    records = _load(path, stamp)[1]["list"] if path is not None else ()
    return MappingProxyType(all_stats(records))


def load_summary(uid=None, *, store=None, now=None):
    store = store or GachaStore()
    issues = list(store.split_legacy())
    accounts = ()
    selected = None
    pools = _statistics()
    current_path = store.directory
    try:
        with store.reading():
            accounts, errors = store._scan()
            issues.extend(errors)
            selected = next((a for a in accounts if a.uid == str(uid)), accounts[0] if accounts else None)
            if selected:
                current_path = store.path(selected.uid)
                pools = _statistics(current_path, file_stamp(current_path))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        issues.append(_read_issue(current_path, exc, selected.uid if selected else None))
        selected = None
    return Summary(accounts, selected, updated_text(selected.updated, now) if selected else "", pools, tuple(issues))
