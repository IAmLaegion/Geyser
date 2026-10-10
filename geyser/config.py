import json
from dataclasses import asdict, dataclass, field, fields

from .paths import data_dir

KIND_DOWNLOAD = "download"
KIND_FOLLOWUP = "followup"
KINDS = (KIND_DOWNLOAD, KIND_FOLLOWUP)

SETTINGS_FILE = "settings.json"


@dataclass
class Rule:
    text: str
    enabled: bool = True
    kind: str = KIND_DOWNLOAD


def default_rules():
    return [
        Rule("Slow download", True, KIND_DOWNLOAD),
        # Nexus asks this extra question for files over 500MB, after Slow download is clicked.
        Rule("Standard download", True, KIND_FOLLOWUP),
    ]


@dataclass
class Settings:
    process_filter: str = "nolvus"
    window_filter: str = ""
    rules: list = field(default_factory=default_rules)

    scan_interval: float = 1.0
    idle_timeout_min: int = 5  # 0 = never
    auto_arm: bool = True
    nolvus_activity: bool = True
    keep_background: bool = True
    reclick_cooldown: int = 30

    close_to_tray: bool = True
    start_minimized: bool = False
    start_with_windows: bool = False

    notify_download: bool = True
    notify_state: bool = False

    hotkey_enabled: bool = True
    hotkey: str = "Ctrl+Alt+G"

    verbose_log: bool = False
    tray_hint_shown: bool = False


def _coerce(value, default):
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    if isinstance(default, str):
        return str(value)
    return value


def _parse_rules(raw):
    rules = []
    for item in raw:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        kind = item.get("kind", KIND_DOWNLOAD)
        rules.append(Rule(text, bool(item.get("enabled", True)), kind if kind in KINDS else KIND_DOWNLOAD))
    return rules


def load_settings() -> Settings:
    settings = Settings()
    try:
        data = json.loads((data_dir() / SETTINGS_FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return settings
    if not isinstance(data, dict):
        return settings

    known = {f.name for f in fields(Settings)}
    for key, value in data.items():
        if key not in known:
            continue
        try:
            if key == "rules":
                settings.rules = _parse_rules(value)
            else:
                setattr(settings, key, _coerce(value, getattr(settings, key)))
        except (TypeError, ValueError, AttributeError):
            pass
    return settings


def save_settings(settings: Settings):
    path = data_dir() / SETTINGS_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2), "utf-8")
    tmp.replace(path)
