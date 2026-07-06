from datetime import datetime, timedelta, timezone

from uap_news_hub.locking import acquire_lock


def test_acquire_lock_recovers_stale_lock(tmp_path):
    lock_path = tmp_path / "run.lock"
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    lock_path.write_text(f"pid=999999\nstarted_at={stale_time}\n", encoding="utf-8")

    result = acquire_lock(lock_path, max_age_minutes=55)

    assert result.acquired
    assert result.stale_recovered


def test_acquire_lock_skips_live_lock(tmp_path):
    lock_path = tmp_path / "run.lock"
    lock_path.write_text(
        f"pid={__import__('os').getpid()}\nstarted_at={datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n",
        encoding="utf-8",
    )

    result = acquire_lock(lock_path, max_age_minutes=55)

    assert not result.acquired
    assert result.reason == "locked"
