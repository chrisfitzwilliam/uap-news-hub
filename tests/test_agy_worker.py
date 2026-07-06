from pathlib import Path

from uap_news_hub.agy import extract_json_document, run_agy_worker


def test_extract_json_document_handles_fenced_output():
    raw = "preamble\n```json\n{\"answer\": 1}\n```\npostamble"
    assert extract_json_document(raw) == {"answer": 1}


def test_run_agy_worker_retries_once_for_malformed_json(tmp_path):
    calls = []

    def call(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return "not json"
        return "{\"answer\": 2}"

    result = run_agy_worker("write json", call=call, save_dir=tmp_path)

    assert result.parsed == {"answer": 2}
    assert result.call_count == 2
    assert (tmp_path / "raw.txt").exists()
    assert (tmp_path / "parsed.json").exists()
    assert "repair" in calls[1].lower()

