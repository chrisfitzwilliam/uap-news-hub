from pathlib import Path

from uap_news_hub.state import StateStore


def test_state_store_bootstrap_creates_expected_tables(tmp_path):
    db_path = tmp_path / "state.db"

    with StateStore(db_path) as store:
        store.initialize()

        tables = {row["name"] for row in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"seen_items", "published_index", "run_history"}.issubset(tables)

        store.record_seen_item("item-1", "rss", "new")
        assert store.get_seen_item("item-1")["status"] == "new"
