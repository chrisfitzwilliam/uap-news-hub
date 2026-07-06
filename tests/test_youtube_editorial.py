import json
from pathlib import Path

from uap_news_hub.agy import AgyRunResult
from uap_news_hub.youtube_editorial import run_youtube_editorial_pipeline


def test_run_youtube_editorial_pipeline_writes_published_article(tmp_path):
    root = tmp_path
    youtube_url = "https://www.youtube.com/watch?v=A2-y_HasHEw"
    video_id = "A2-y_HasHEw"

    download_dir = root / "data" / "downloads" / video_id
    transcript_dir = root / "data" / "transcripts"
    published_dir = root / "content" / "published"
    queue_dir = root / "content" / "queue"
    for directory in (download_dir, transcript_dir, published_dir, queue_dir, root / "templates"):
        directory.mkdir(parents=True, exist_ok=True)

    (download_dir / "metadata.json").write_text(
        json.dumps(
            {
                "packet_id": "packet-1",
                "video_id": video_id,
                "source_url": youtube_url,
                "title": "Congressman Reveals The Alien Brief That Changed The President’s Life",
                "status": "downloaded",
            }
        ),
        encoding="utf-8",
    )
    (transcript_dir / f"{video_id}.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "source_url": youtube_url,
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start": 10.0,
                        "end": 15.0,
                        "text": "The host says a congressional brief changed how the president reacted.",
                    }
                ],
                "diarization": "unknown",
            }
        ),
        encoding="utf-8",
    )

    analysis_payload = {
        "packet_id": "packet-1",
        "video_id": video_id,
        "summary": "A host discusses a congressional brief and the president's reaction.",
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "start": 10.0,
                "end": 15.0,
                "text": "The host says a congressional brief changed how the president reacted.",
            }
        ],
        "speakers": [
            {
                "speaker": "SPEAKER_00",
                "likely_role": "host",
                "confidence": "medium",
            }
        ],
        "key_claims": [
            {
                "claim": "The host says a congressional brief changed how the president reacted.",
                "speaker": "SPEAKER_00",
                "timestamp_start": "00:00:10",
                "timestamp_end": "00:00:15",
                "claim_type": "reported_claim",
                "support_level": "transcript_only",
                "source_url": youtube_url,
            }
        ],
        "article_recommendation": "draft_youtube_intel",
        "publication_risk": "medium",
        "open_questions": ["Who authored the brief?"],
    }
    draft_payload = {
        "slug": "congressman-reveals-alien-brief",
        "title": "Congressman Reveals the Alien Brief That Changed the President's Life",
        "dek": "A transcript-grounded summary of the video.",
        "content_type": "youtube_intel",
        "confidence": "medium",
        "claim_labels": ["reported_claim", "analysis"],
        "sources": [{"title": "Original video", "url": youtube_url, "type": "primary"}],
        "article_markdown": "# Title\n\nBody.",
        "related_claims": [],
        "should_publish": True,
    }
    calls: list[tuple[str, Path | None]] = []

    def runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        payload = analysis_payload if len(calls) == 1 else draft_payload
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(payload), parsed=payload, call_count=1, save_dir=save_dir)

    review_payload = {
        "review_result": "pass",
        "blocking_issues": [],
        "non_blocking_warnings": ["Only one primary source is available."],
        "required_edits": [],
        "confidence_after_review": "medium",
    }

    def review_runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        payload = analysis_payload if len(calls) == 1 else draft_payload if len(calls) == 2 else review_payload
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(payload), parsed=payload, call_count=1, save_dir=save_dir)

    results = run_youtube_editorial_pipeline(root, runner=review_runner, max_items=1)

    assert len(results.outcomes) == 1
    assert len(calls) == 3
    assert youtube_url in calls[0][0]
    assert video_id in calls[0][0]
    assert youtube_url in calls[1][0]
    assert (calls[0][1] / "raw.txt").exists()
    assert (calls[1][1] / "raw.txt").exists()
    assert (calls[2][1] / "raw.txt").exists()

    article_path = published_dir / f"{draft_payload['slug']}.json"
    assert article_path.exists()
    article = json.loads(article_path.read_text(encoding="utf-8"))
    assert article["review_result"] == "pass"
    assert article["body_markdown"] == draft_payload["article_markdown"]
    assert article["source_urls"] == [youtube_url]
    assert article["content_type"] == "youtube_intel"


def test_run_youtube_editorial_pipeline_stops_when_budget_is_spent(tmp_path):
    root = tmp_path
    first_video_id = "A2-y_HasHEw"
    second_video_id = "B3-y_HasHEw"
    first_url = "https://www.youtube.com/watch?v=A2-y_HasHEw"
    second_url = "https://www.youtube.com/watch?v=B3-y_HasHEw"

    for video_id, youtube_url, title in (
        (first_video_id, first_url, "First Video"),
        (second_video_id, second_url, "Second Video"),
    ):
        download_dir = root / "data" / "downloads" / video_id
        transcript_dir = root / "data" / "transcripts"
        for directory in (download_dir, transcript_dir, root / "content" / "published", root / "content" / "queue", root / "templates"):
            directory.mkdir(parents=True, exist_ok=True)
        (download_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "packet_id": f"packet-{video_id}",
                    "video_id": video_id,
                    "source_url": youtube_url,
                    "title": title,
                    "status": "downloaded",
                }
            ),
            encoding="utf-8",
        )
        (transcript_dir / f"{video_id}.json").write_text(
            json.dumps(
                {
                    "video_id": video_id,
                    "source_url": youtube_url,
                    "segments": [
                        {
                            "speaker": "SPEAKER_00",
                            "start": 10.0,
                            "end": 15.0,
                            "text": "The host says a congressional brief changed how the president reacted.",
                        }
                    ],
                    "diarization": "unknown",
                }
            ),
            encoding="utf-8",
        )

    analysis_payload = {
        "packet_id": "packet-A2-y_HasHEw",
        "video_id": first_video_id,
        "summary": "A host discusses a congressional brief and the president's reaction.",
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "start": 10.0,
                "end": 15.0,
                "text": "The host says a congressional brief changed how the president reacted.",
            }
        ],
        "speakers": [
            {
                "speaker": "SPEAKER_00",
                "likely_role": "host",
                "confidence": "medium",
            }
        ],
        "key_claims": [],
        "article_recommendation": "draft_youtube_intel",
        "publication_risk": "medium",
        "open_questions": [],
    }
    draft_payload = {
        "slug": "first-video",
        "title": "First Video",
        "dek": "A transcript-grounded summary.",
        "content_type": "youtube_intel",
        "confidence": "medium",
        "claim_labels": ["analysis"],
        "sources": [{"title": "Original video", "url": first_url, "type": "primary"}],
        "article_markdown": "# Title\n\nBody.",
        "related_claims": [],
        "should_publish": True,
    }
    review_payload = {
        "review_result": "pass",
        "blocking_issues": [],
        "non_blocking_warnings": [],
        "required_edits": [],
        "confidence_after_review": "medium",
    }
    calls: list[tuple[str, Path | None]] = []

    def runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        payload = analysis_payload if len(calls) == 1 else draft_payload if len(calls) == 2 else review_payload
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(payload), parsed=payload, call_count=1, save_dir=save_dir)

    results = run_youtube_editorial_pipeline(root, runner=runner, budget_limit=3)

    assert len(results.outcomes) == 1
    assert results.agy_calls == 3
    assert len(calls) == 3
    assert (root / "content" / "published" / "first-video.json").exists()
    assert not (root / "content" / "published" / "second-video.json").exists()


def test_run_youtube_editorial_pipeline_queues_when_review_fails(tmp_path):
    root = tmp_path
    youtube_url = "https://www.youtube.com/watch?v=A2-y_HasHEw"
    video_id = "A2-y_HasHEw"

    download_dir = root / "data" / "downloads" / video_id
    transcript_dir = root / "data" / "transcripts"
    published_dir = root / "content" / "published"
    queue_dir = root / "content" / "queue"
    for directory in (download_dir, transcript_dir, published_dir, queue_dir, root / "templates"):
        directory.mkdir(parents=True, exist_ok=True)

    (download_dir / "metadata.json").write_text(
        json.dumps(
            {
                "packet_id": "packet-1",
                "video_id": video_id,
                "source_url": youtube_url,
                "title": "Congressman Reveals The Alien Brief That Changed The President’s Life",
                "status": "downloaded",
            }
        ),
        encoding="utf-8",
    )
    (transcript_dir / f"{video_id}.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "source_url": youtube_url,
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start": 10.0,
                        "end": 15.0,
                        "text": "The host says a congressional brief changed how the president reacted.",
                    }
                ],
                "diarization": "unknown",
            }
        ),
        encoding="utf-8",
    )

    analysis_payload = {
        "packet_id": "packet-1",
        "video_id": video_id,
        "summary": "A host discusses a congressional brief and the president's reaction.",
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "start": 10.0,
                "end": 15.0,
                "text": "The host says a congressional brief changed how the president reacted.",
            }
        ],
        "speakers": [
            {
                "speaker": "SPEAKER_00",
                "likely_role": "host",
                "confidence": "medium",
            }
        ],
        "key_claims": [],
        "article_recommendation": "draft_youtube_intel",
        "publication_risk": "medium",
        "open_questions": [],
    }
    draft_payload = {
        "slug": "congressman-reveals-alien-brief",
        "title": "Congressman Reveals the Alien Brief That Changed the President's Life",
        "dek": "A transcript-grounded summary of the video.",
        "content_type": "youtube_intel",
        "confidence": "medium",
        "claim_labels": ["reported_claim", "analysis"],
        "sources": [{"title": "Original video", "url": youtube_url, "type": "primary"}],
        "article_markdown": "# Title\n\nBody.",
        "related_claims": [],
        "should_publish": False,
    }
    review_payload = {
        "review_result": "reject",
        "blocking_issues": ["Missing primary-source support."],
        "non_blocking_warnings": [],
        "required_edits": ["Hold this item in queue."],
        "confidence_after_review": "low",
    }
    calls: list[tuple[str, Path | None]] = []

    def runner(prompt_text: str, *, save_dir: Path | None = None):
        calls.append((prompt_text, save_dir))
        payload = analysis_payload if len(calls) == 1 else draft_payload if len(calls) == 2 else review_payload
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "raw.txt").write_text(json.dumps(payload), encoding="utf-8")
            (save_dir / "parsed.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return AgyRunResult(raw_text=json.dumps(payload), parsed=payload, call_count=1, save_dir=save_dir)

    results = run_youtube_editorial_pipeline(root, runner=runner, max_items=1)

    assert len(results.outcomes) == 1
    assert len(calls) == 3
    assert not (published_dir / f"{draft_payload['slug']}.json").exists()
    queue_article = queue_dir / f"{draft_payload['slug']}.json"
    assert queue_article.exists()
    article = json.loads(queue_article.read_text(encoding="utf-8"))
    assert article["review_result"] == "reject"
