from uap_news_hub.urls import normalize_url


def test_normalize_url_collapses_tracking_params_and_youtube_variants():
    assert (
        normalize_url("https://Example.com/article?utm_source=x&b=2&a=1#frag")
        == "https://example.com/article?a=1&b=2"
    )
    assert (
        normalize_url("https://www.youtube.com/watch?v=ABC123&feature=youtu.be")
        == "https://www.youtube.com/watch?v=ABC123"
    )
