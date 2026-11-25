from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Button:
    id: str
    text: str
    link: str | None = None
    target: str | None = None


@dataclass(frozen=True)
class Greeting:
    state: str
    badge: str
    title: str
    description: str
    mascot: str
    buttons: tuple[Button, ...]
    task_name: str | None = None
    phase: str | None = None


@dataclass(frozen=True)
class PowerReading:
    value: int | None
    read_at: datetime | None
    full_at: datetime | None
    maximum: int = 300


@dataclass(frozen=True)
class DailyTraining:
    completed: bool
    completed_at: datetime | None
    activity: int | None
    target: int = 500


@dataclass(frozen=True)
class WeeklyItem:
    id: str
    name: str
    completed: bool
    enabled: bool


@dataclass(frozen=True)
class ScheduledRun:
    at: datetime
    names: tuple[str, ...]
    post_action: str


@dataclass(frozen=True)
class PlanItem:
    id: str
    name: str
    icon: str
    summary: str
    status: str
    status_text: str
    link: str


@dataclass(frozen=True)
class StepResult:
    id: str
    name: str
    status: str
    seconds: float | None


@dataclass(frozen=True)
class RunInfo:
    id: str
    task: str
    name: str
    started_at: datetime
    ended_at: datetime | None
    seconds: float | None
    trigger: str
    status: str
    steps: tuple[StepResult, ...]
    error: str | None
    link: str
    retry_step: str | None = None
    login_required: str | None = None


@dataclass(frozen=True)
class LiveRun:
    task: str
    name: str
    phase: str = "prepare"
    step: str | None = None
    can_stop: bool = False
    can_pause: bool = False
    paused: bool = False
    run_id: str | None = None
    started_at: datetime | None = None
    account_number: int | None = None
    account_total: int | None = None
    account_name: str | None = None


@dataclass(frozen=True)
class Check:
    id: str
    level: str
    title: str
    description: str
    link: str


@dataclass(frozen=True)
class ShortcutAction:
    id: str
    name: str


@dataclass(frozen=True)
class Shortcut:
    id: str
    name: str
    icon: str
    menu: tuple[ShortcutAction, ...] = ()


@dataclass(frozen=True)
class OverviewSnapshot:
    now: datetime
    greeting: Greeting | None
    power: PowerReading | None
    daily: DailyTraining | None
    weekly: tuple[WeeklyItem, ...] | None
    schedule: ScheduledRun | None
    plan: tuple[PlanItem, ...] | None
    last_run: RunInfo | None
    checks: tuple[Check, ...] | None
    shortcuts: tuple[Shortcut, ...] | None
    background: str
    show_mascot: bool
    unavailable: tuple[str, ...]
    shortcuts_hidden: bool = False  # 有快捷启动，但当前连接方式都不支持
