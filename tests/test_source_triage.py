import json
from pathlib import Path

from uap_news_hub.agy import AgyRunResult
from uap_news_hub.source_triage import run_source_triage_pipeline
from uap_news_hub.state import StateStore


def _make_packet(root: Path, packet_id: str, *, source_type: str = "news", title: str = "Example") -> Path:
    packets_dir = root / "data" / "source-packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    packet_path = packets_dir / f"{packet_id}.json"
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": packet_id,
                "source_type": source_type,
                "source_name": "Example Source",
                "source_url": f"https://example.com/{packet_id}",
                "title": title,
                "status": "new",
                "published_at": "2026-07-06T18:00:00Z",
                "collected_at": "2026-07-06T18:01:00Z",
                "candidate_reason": "New item from monitored source.",
                "related_urls": [],
            }
        ),
        encoding="utf-8",
    )
    return packet_path


def test_run_source_triage_pipeline_batches_packets_and_updates_status(tmp_path):
    root = tmp_path
    first_packet = _make_packet(root, "packet-one", title="First Packet")
    second_packet = _make_packet(root, "packet-two", title="Second Packet")

    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        state.record_published_index(
            slug="existing",
            title="Existing",
            content_type="latest_briefing",
            source_urls=["https://example.com/existing"],
            published_at="2026-07-06T18:00:00Z",
        )

    calls = []

    triage_payload = [
        {
            "packet_id": "packet-one",
            "decision": "queue_for_daily",
            "content_type": "breaking_brief",
            "importance": "medium",
            "novelty": "new",
            "risk_level": "low",
            "reason": "Useful monitored-source update that can wait for daily review.",
            "required_sources": ["https://example.com/packet-one"],
            "do_not_publish_reason": None,
        },
        {
            "packet_id": "packet-two",
            "decision": "download_transcribe",
            "content_type": "youtube_intel",
            "importance": "high",
            "novelty": "new",
            "risk_level": "medium",
            "reason": "YouTube item should go through transcript extraction.",
            "required_sources": ["https://example.com/packet-two"],
            "do_not_publish_reason": None,
        },
    ]

    def runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(triage_payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(triage_payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(triage_payload), parsed=triage_payload, call_count=1, save_dir=save_dir)

    result = run_source_triage_pipeline(root, runner=runner, batch_size=10)

    assert result.agy_calls == 1
    assert len(result.outcomes) == 2
    assert len(calls) == 1
    assert "packet-one" in calls[0][0]
    assert "https://example.com/existing" in calls[0][0]
    assert (calls[0][1] / "raw.txt").exists()

    first_packet_data = json.loads(first_packet.read_text(encoding="utf-8"))
    second_packet_data = json.loads(second_packet.read_text(encoding="utf-8"))
    assert first_packet_data["status"] == "queue_for_daily"
    assert second_packet_data["status"] == "download_transcribe"
    assert first_packet_data["triage"]["decision"] == "queue_for_daily"
    assert second_packet_data["triage"]["decision"] == "download_transcribe"


def test_run_source_triage_pipeline_stops_when_budget_is_spent(tmp_path):
    root = tmp_path
    _make_packet(root, "packet-one")
    _make_packet(root, "packet-two")

    triage_payload = [
        {
            "packet_id": "packet-one",
            "decision": "ignore",
            "content_type": "breaking_brief",
            "importance": "low",
            "novelty": "duplicate",
            "risk_level": "low",
            "reason": "Already covered.",
            "required_sources": [],
            "do_not_publish_reason": "Duplicate coverage.",
        }
    ]
    calls = []

    def runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(triage_payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(triage_payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(triage_payload), parsed=triage_payload, call_count=1, save_dir=save_dir)

    result = run_source_triage_pipeline(root, runner=runner, batch_size=1, budget_limit=1)

    assert result.agy_calls == 1
    assert result.budget_exhausted is True
    assert len(calls) == 1
