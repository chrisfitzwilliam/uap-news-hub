import json
from pathlib import Path

from uap_news_hub.state import StateStore
from uap_news_hub.youtube_pipeline import download_youtube_queue, transcribe_downloads
from uap_news_hub.urls import item_key_for_url


YOUTUBE_URL = "https://www.youtube.com/watch?v=A2-y_HasHEw"


def _write_youtube_packet(root: Path, *, status: str = "new", attempts: int = 0) -> Path:
    packets_dir = root / "data" / "source-packets"
    packets_dir.mkdir(parents=True)
    packet_path = packets_dir / "youtube-a2-y-hashew.json"
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "youtube-a2-y-hashew",
                "source_type": "youtube",
                "source_name": "Example",
                "source_url": YOUTUBE_URL,
                "title": "Test Video",
                "published_at": "2026-07-06T18:00:00Z",
                "collected_at": "2026-07-06T18:05:00Z",
                "author_or_channel": "Example Channel",
                "raw_summary": "Example summary",
                "candidate_reason": "Test packet",
                "related_urls": [],
                "status": status,
                "download_attempts": attempts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return packet_path


def test_download_youtube_queue_writes_download_artifacts_and_updates_state(tmp_path):
    root = tmp_path
    _write_youtube_packet(root)

    def downloader(packet, download_dir):
        download_dir.mkdir(parents=True, exist_ok=True)
        audio_path = download_dir / "audio.wav"
        audio_path.write_bytes(b"wav")
        return {
            "metadata": {"id": "A2-y_HasHEw", "title": packet["title"], "duration": 42},
            "audio_path": str(audio_path),
        }

    outcomes = download_youtube_queue(root, downloader=downloader, sleep=lambda _: None, max_items=1)

    assert len(outcomes) == 1
    assert outcomes[0].status == "downloaded"
    download_dir = root / "data" / "downloads" / "A2-y_HasHEw"
    assert (download_dir / "metadata.json").exists()
    assert (download_dir / "audio.wav").exists()

    packet = json.loads((root / "data" / "source-packets" / "youtube-a2-y-hashew.json").read_text(encoding="utf-8"))
    assert packet["status"] == "downloaded"
    assert packet["video_id"] == "A2-y_HasHEw"

    with StateStore(root / "data" / "state.db") as store:
        store.initialize()
        seen = store.get_seen_item(item_key_for_url(YOUTUBE_URL))
        assert seen is not None
        assert seen["status"] == "downloaded"


def test_download_youtube_queue_abandons_after_third_failure(tmp_path):
    root = tmp_path
    _write_youtube_packet(root, status="download_failed", attempts=2)

    def downloader(packet, download_dir):
        raise RuntimeError("bot check")

    outcomes = download_youtube_queue(root, downloader=downloader, sleep=lambda _: None, max_items=1)

    assert len(outcomes) == 1
    assert outcomes[0].status == "download_abandoned"
    packet = json.loads((root / "data" / "source-packets" / "youtube-a2-y-hashew.json").read_text(encoding="utf-8"))
    assert packet["status"] == "download_abandoned"
    assert packet["download_attempts"] == 3


def test_transcribe_downloads_writes_normalized_transcript(tmp_path):
    root = tmp_path
    download_dir = root / "data" / "downloads" / "A2-y_HasHEw"
    download_dir.mkdir(parents=True)
    (download_dir / "audio.wav").write_bytes(b"wav")
    (download_dir / "metadata.json").write_text(
        json.dumps(
            {
                "packet_id": "youtube-a2-y-hashew",
                "video_id": "A2-y_HasHEw",
                "source_url": YOUTUBE_URL,
                "title": "Test Video",
                "status": "downloaded",
                "audio_path": str(download_dir / "audio.wav"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def transcriber(audio_path, metadata):
        assert audio_path.name == "audio.wav"
        assert metadata["video_id"] == "A2-y_HasHEw"
        return {
            "video_id": "A2-y_HasHEw",
            "segments": [
                {"start": 1.0, "end": 2.0, "text": "Hello from the video"},
            ],
        }

    outcomes = transcribe_downloads(root, transcriber=transcriber, max_items=1)

    assert len(outcomes) == 1
    assert outcomes[0].status == "transcribed"
    transcript_json = root / "data" / "transcripts" / "A2-y_HasHEw.json"
    transcript_text = root / "data" / "transcripts" / "A2-y_HasHEw.txt"
    payload = json.loads(transcript_json.read_text(encoding="utf-8"))
    assert payload["segments"][0]["speaker"] == "UNKNOWN"
    assert "Hello from the video" in transcript_text.read_text(encoding="utf-8")

    metadata = json.loads((download_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "transcribed"
    assert metadata["transcript_json"] == str(transcript_json)
