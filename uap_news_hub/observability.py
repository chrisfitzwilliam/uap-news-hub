from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .utils import utc_now


def record_event(root: Path, event: str, *, level: str = "info", **context: Any) -> dict[str, Any]:
    payload = {"at": utc_now(), "event": event, "level": level, **context}
    log_dir = Path(root) / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"pipeline-{payload['at'][:10]}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def notify_windows(title: str, message: str) -> bool:
    """Best-effort toast: logging remains the durable notification path."""
    escaped_title = title.replace("'", "''")
    escaped_message = message.replace("'", "''")
    command = (
        "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null; "
        "$template=[Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
        "$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
        f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{escaped_title}')) > $null; "
        f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{escaped_message}')) > $null; "
        "$toast=[Windows.UI.Notifications.ToastNotification]::new($xml); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('UAP News Hub').Show($toast)"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], check=True, capture_output=True, text=True, timeout=15)
    except Exception:
        return False
    return True
