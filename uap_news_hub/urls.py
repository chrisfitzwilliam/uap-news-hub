from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _drop_tracking_params(params: list[tuple[str, str]]) -> list[tuple[str, str]]:
    kept: list[tuple[str, str]] = []
    for key, value in params:
      if key in TRACKING_KEYS:
          continue
      if any(key.startswith(prefix) for prefix in TRACKING_PREFIXES):
          continue
      kept.append((key, value))
    return kept


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    params = parse_qsl(parsed.query, keep_blank_values=True)
    params = _drop_tracking_params(params)

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = path.strip("/")
        return f"https://www.youtube.com/watch?v={video_id}"

    if host.endswith("youtube.com") and path == "/watch":
        video_id = None
        retained: list[tuple[str, str]] = []
        for key, value in params:
            if key == "v":
                video_id = value
            elif key in {"list", "index", "t"}:
                retained.append((key, value))
        query_parts: list[tuple[str, str]] = []
        if video_id:
            query_parts.append(("v", video_id))
        query_parts.extend(sorted(retained))
        query = urlencode(query_parts, doseq=True)
        return urlunparse(("https", host, "/watch", "", query, ""))

    query = urlencode(sorted(params), doseq=True)
    return urlunparse((scheme, host, path, "", query, ""))


def item_key_for_url(url: str) -> str:
    return normalize_url(url)

