from uap_news_hub.environment import check_environment


def test_check_environment_reports_missing_tools_and_token():
    result = check_environment(
        which=lambda name: None,
        has_python_module=lambda name: False,
        env={"UAP_DIARIZATION_ENABLED": "1"},
        free_disk_gb=99,
        run_pip_check=lambda: 0,
        git_push_dry_run=lambda: 0,
    )

    assert not result.passed
    assert "agy" in " ".join(result.errors)
    assert "ffmpeg" in " ".join(result.errors)
    assert "yt-dlp" in " ".join(result.errors)
    assert "HF_TOKEN" in " ".join(result.errors)


def test_check_environment_does_not_require_hf_token_when_diarization_disabled():
    result = check_environment(
        which=lambda name: f"C:/tools/{name}.exe",
        env={"UAP_DIARIZATION_ENABLED": "0"},
        free_disk_gb=99,
        run_pip_check=lambda: 0,
        git_push_dry_run=lambda: 0,
    )

    assert result.passed
    assert "HF_TOKEN" not in " ".join(result.errors)


def test_check_environment_accepts_python_yt_dlp_package_without_cli():
    def which(name):
        if name == "yt-dlp":
            return None
        return f"C:/tools/{name}.exe"

    result = check_environment(
        which=which,
        has_python_module=lambda name: name == "yt_dlp",
        env={"UAP_DIARIZATION_ENABLED": "0"},
        free_disk_gb=99,
        run_pip_check=lambda: 0,
        git_push_dry_run=lambda: 0,
    )

    assert result.passed
