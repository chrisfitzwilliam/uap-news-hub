from uap_news_hub.environment import check_environment


def test_check_environment_reports_missing_tools_and_token():
    result = check_environment(
        which=lambda name: None,
        env={},
        free_disk_gb=99,
        run_pip_check=lambda: 0,
        git_push_dry_run=lambda: 0,
    )

    assert not result.passed
    assert "agy" in " ".join(result.errors)
    assert "ffmpeg" in " ".join(result.errors)
    assert "yt-dlp" in " ".join(result.errors)
    assert "HF_TOKEN" in " ".join(result.errors)

