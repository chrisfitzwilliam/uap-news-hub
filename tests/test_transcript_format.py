from uap_news_hub.transcripts import normalize_transcript_payload


def test_normalize_transcript_payload_handles_labeled_and_unlabeled_forms():
    labeled = {
        "video_id": "abc123",
        "segments": [
            {"speaker": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "Hello"},
        ],
    }
    unlabeled = {
        "video_id": "abc123",
        "segments": [
            {"start": 1.0, "end": 2.0, "text": "Hello"},
        ],
    }

    labeled_result = normalize_transcript_payload(labeled)
    unlabeled_result = normalize_transcript_payload(unlabeled)

    assert labeled_result["segments"][0]["speaker"] == "SPEAKER_00"
    assert unlabeled_result["segments"][0]["speaker"] == "UNKNOWN"

