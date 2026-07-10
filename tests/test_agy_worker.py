from pathlib import Path

from uap_news_hub.agy import call_agy, extract_json_document, run_agy_worker


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


def test_call_agy_writes_large_prompt_to_file(tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))

        class Completed:
            stdout = "{\"ok\": true}"

        return Completed()

    prompt = "x" * 40000
    result = call_agy(prompt, prompt_dir=tmp_path, run=run)

    command, kwargs = calls[0]
    prompt_files = list(tmp_path.glob("agy-prompt-*.md"))
    assert result == "{\"ok\": true}"
    assert len(prompt_files) == 1
    assert prompt_files[0].read_text(encoding="utf-8") == prompt
    assert command[-1] != prompt
    assert command[1] == "--print"
    assert str(prompt_files[0]) in command[2]
    assert len(command[2]) < 1000
    assert "--add-dir" in command[3:]
    assert kwargs["capture_output"] is True
