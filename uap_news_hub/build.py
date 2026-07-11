from __future__ import annotations

import html
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from .state import StateStore
from .utils import ensure_parent


DEFAULT_SECTION_TITLES = {
    "latest_briefing": "Latest Briefing",
    "breaking_brief": "Breaking Brief",
    "youtube_intel": "YouTube Intel",
    "claim_tracker": "Claim Tracker",
}

DEFAULT_SECTION_DESCRIPTIONS = {
    "latest_briefing": "Short, conservative updates on newly validated reporting.",
    "breaking_brief": "Fast, sourced updates that still stay within the evidence floor.",
    "youtube_intel": "Transcript-driven analysis from monitored YouTube channels.",
    "claim_tracker": "Structured records for recurring claims and how they evolve.",
}

DEFAULT_SECTION_ORDER = [
    "latest_briefing",
    "breaking_brief",
    "youtube_intel",
    "claim_tracker",
]

DEFAULT_TEMPLATES = {
    "base.html": """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1118">
  <title>{{ title }}</title>
  <meta name="description" content="{{ description }}">
  <link rel="canonical" href="{{ canonical_url }}">
  <meta property="og:site_name" content="UFO / UAP News Hub">
  <meta property="og:title" content="{{ title }}">
  <meta property="og:description" content="{{ description }}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{{ canonical_url }}">
  <link rel="alternate" type="application/rss+xml" title="UFO / UAP News Hub RSS" href="{{ site_root }}/rss.xml">
  <link rel="icon" href="{{ site_root }}/assets/img/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{{ site_root }}/assets/css/theme.css">
  <script defer src="{{ site_root }}/assets/js/app.js"></script>
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <main id="content" class="page">
    <nav class="site-nav" aria-label="Primary">
      <a href="{{ site_root }}/">Home</a>
      <a href="{{ site_root }}/sections/index.html">Sections</a>
      <a href="{{ site_root }}/youtube/index.html">YouTube</a>
      <a href="{{ site_root }}/about.html">About</a>
      <a href="{{ site_root }}/editorial-standards.html">Standards</a>
      <a href="{{ site_root }}/status.html">Status</a>
      <a href="{{ site_root }}/rss.xml">RSS</a>
    </nav>
    {% block content %}{% endblock %}
  </main>
</body>
</html>""",
    "index.html": """{% extends "base.html" %}
{% block content %}
<header class="hero">
  <p class="eyebrow">Evidence-first intelligence desk</p>
  <h1>UFO / UAP News Hub</h1>
  <p class="lede">Latest validated items, section indexes, and claim-tracker surfaces.</p>
</header>
<section class="panel">
  <div class="panel-heading">
    <h2>Sections</h2>
    <p>Browse the current editorial lanes.</p>
  </div>
  <div class="card-grid">
  {% if sections %}
  {% for section in sections %}
    <article class="card">
      <h3><a href="{{ section.url }}">{{ section.title }}</a></h3>
      <p>{{ section.description }}</p>
      <p class="meta">{{ section.count }} item{{ 's' if section.count != 1 else '' }}</p>
    </article>
  {% endfor %}
  {% else %}
    <p class="empty-state">No sections have been published yet.</p>
  {% endif %}
  </div>
</section>
<section class="panel">
  <div class="panel-heading">
    <h2>Latest items</h2>
    <p>The freshest validated pieces.</p>
  </div>
  <div class="story-list">
  {% if articles %}
  {% for article in articles %}
    <article class="story-card">
      <p class="kicker">{{ article.section_title }}</p>
      <h3><a href="{{ article.article_url }}">{{ article.title }}</a></h3>
      <p>{{ article.dek }}</p>
      <div class="story-meta">
        <span class="confidence-badge {{ article.confidence_class }}">{{ article.confidence_label }}</span>
        <span class="meta">{{ article.published_at }}</span>
      </div>
    </article>
  {% endfor %}
  {% else %}
    <p class="empty-state">No validated items are available yet.</p>
  {% endif %}
  </div>
</section>
{% endblock %}""",
    "sections/index.html": """{% extends "base.html" %}
{% block content %}
<header class="hero">
  <p class="eyebrow">Section index</p>
  <h1>Sections</h1>
  <p class="lede">Each section groups a specific reporting lane from the pipeline.</p>
</header>
<section class="panel">
  <div class="card-grid">
  {% if sections %}
  {% for section in sections %}
    <article class="card">
      <h2><a href="{{ section.url }}">{{ section.title }}</a></h2>
      <p>{{ section.description }}</p>
      <p class="meta">{{ section.count }} item{{ 's' if section.count != 1 else '' }}</p>
    </article>
  {% endfor %}
  {% else %}
    <p class="empty-state">No sections have been published yet.</p>
  {% endif %}
  </div>
</section>
{% endblock %}""",
    "sections/section.html": """{% extends "base.html" %}
{% block content %}
<header class="hero">
  <p class="eyebrow">Section</p>
  <h1>{{ section.title }}</h1>
  <p class="lede">{{ section.description }}</p>
</header>
<section class="panel">
  <div class="story-list">
  {% if section.articles %}
  {% for article in section.articles %}
    <article class="story-card">
      <p class="kicker">{{ article.section_title }}</p>
      <h2><a href="{{ article.article_url }}">{{ article.title }}</a></h2>
      <p>{{ article.dek }}</p>
      <div class="story-meta">
        <span class="confidence-badge {{ article.confidence_class }}">{{ article.confidence_label }}</span>
        <span class="meta">{{ article.published_at }}</span>
      </div>
    </article>
  {% endfor %}
  {% else %}
    <p class="empty-state">No articles are published in this section yet.</p>
  {% endif %}
  </div>
</section>
{% endblock %}""",
    "youtube/index.html": """{% extends "base.html" %}
{% block content %}
<header class="hero">
  <p class="eyebrow">Monitored video sources</p>
  <h1>YouTube Channel Analysis</h1>
  <p class="lede">Synopsis and analysis staging for the ten monitored UFO/UAP YouTube channels.</p>
</header>
<section class="panel">
  <div class="metric-row">
    <div><strong>{{ dashboard.channel_count }}</strong><span>channels</span></div>
    <div><strong>{{ dashboard.packet_count }}</strong><span>staged episodes</span></div>
    <div><strong>{{ dashboard.download_count }}</strong><span>downloads</span></div>
    <div><strong>{{ dashboard.transcript_count }}</strong><span>transcripts</span></div>
  </div>
</section>
<section class="panel">
  <div class="panel-heading">
    <h2>Channels</h2>
    <p>Local status by monitored source.</p>
  </div>
  <div class="channel-grid">
  {% for channel in dashboard.channels %}
    <article class="channel-card">
      <div class="channel-card__head">
        <div>
          <p class="kicker">{{ channel.category_label }}</p>
          <h3><a href="{{ channel.url }}">{{ channel.name }}</a></h3>
        </div>
        <span class="priority-badge">#{{ channel.priority }}</span>
      </div>
      <p>{{ channel.reason }}</p>
      <div class="story-meta">
        <span class="meta">{{ channel.download_label }}</span>
        <span class="meta">{{ channel.transcript_label }}</span>
      </div>
      {% if channel.episodes %}
      <ul class="episode-list">
      {% for episode in channel.episodes %}
        <li>
          <a href="{{ episode.url }}">{{ episode.title }}</a>
          <span>{{ episode.status_label }}</span>
        </li>
      {% endfor %}
      </ul>
      {% else %}
        <p class="empty-state">No local episodes staged yet.</p>
      {% endif %}
    </article>
  {% endfor %}
  </div>
</section>
{% endblock %}""",
    "article.html": """{% extends "base.html" %}
{% block content %}
<article class="story">
  <header class="story-header">
    <p class="eyebrow">{{ article.section_title }}</p>
    <h1>{{ article.title }}</h1>
    <p class="lede">{{ article.dek }}</p>
    <div class="story-meta">
      <span class="confidence-badge {{ article.confidence_class }}">{{ article.confidence_label }}</span>
      <span class="meta">{{ article.published_at }}</span>
    </div>
    {% if article.claim_labels %}
    <ul class="claim-labels" aria-label="Claim labels">
      {% for label in article.claim_labels %}
      <li>{{ label }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </header>
  <section class="body prose">{{ article.body_html | safe }}</section>
  <aside class="source-panel">
    <h2>Sources</h2>
    <ul>
    {% for source in article.source_items %}
      <li><a href="{{ source.url }}">{{ source.label }}</a></li>
    {% endfor %}
    </ul>
  </aside>
</article>
{% endblock %}""",
    "status.html": """{% extends "base.html" %}
{% block content %}
<header class="hero">
  <p class="eyebrow">Pipeline status</p>
  <h1>Status</h1>
  <p class="lede">The latest run timestamps and queue health.</p>
</header>
<section class="panel">
  <ul class="status-list">
    <li>Last hourly run: {{ status.last_hourly_run }}</li>
    <li>Last daily run: {{ status.last_daily_run }}</li>
    <li>Last publish: {{ status.last_publish }}</li>
    <li>Queued items: {{ status.queued_items }}</li>
    <li>Rejected items: {{ status.rejected_items }}</li>
  </ul>
</section>
{% endblock %}""",
    "info.html": """{% extends "base.html" %}{% block content %}<header class="hero"><p class="eyebrow">UFO / UAP News Hub</p><h1>{{ page.heading }}</h1><p class="lede">{{ page.dek }}</p></header><section class="panel prose">{{ page.body_html | safe }}</section>{% endblock %}""",
}


def _markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    html_parts: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html_parts.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            level = len(stripped) - len(stripped.lstrip("#"))
            content = stripped[level:].strip()
            html_parts.append(f"<h{level}>{html.escape(content)}</h{level}>")
        else:
            paragraph.append(stripped)
    flush_paragraph()
    return "\n".join(html_parts)


def _template_env(templates_dir: Path) -> Environment:
    loaders = []
    if templates_dir.exists():
        loaders.append(FileSystemLoader(str(templates_dir)))
    loaders.append(DictLoader(DEFAULT_TEMPLATES))
    return Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html", "xml"]))


def _render_template(env: Environment, template_name: str, **context: Any) -> str:
    context.setdefault("site_root", "")
    try:
        template = env.get_template(template_name)
    except Exception:
        fallback_env = Environment(loader=DictLoader(DEFAULT_TEMPLATES), autoescape=select_autoescape(["html", "xml"]))
        template = fallback_env.get_template(template_name)
    return template.render(**context)


def _friendly_label(value: str) -> str:
    return value.replace("_", " ").title()


def _section_title(content_type: str) -> str:
    return DEFAULT_SECTION_TITLES.get(content_type, _friendly_label(content_type))


def _section_description(content_type: str) -> str:
    return DEFAULT_SECTION_DESCRIPTIONS.get(content_type, "Validated items from this editorial lane.")


def _sort_key(article: dict[str, Any]) -> tuple[str, str]:
    return (str(article.get("published_at", "")), str(article.get("slug", "")))


def _article_url(slug: str) -> str:
    return f"/articles/{slug}.html"


def _section_url(content_type: str) -> str:
    return f"/sections/{content_type}.html"


def _youtube_url() -> str:
    return "/youtube/index.html"


def _absolute_or_relative(path: str, site_url: str | None) -> str:
    if site_url:
        return f"{site_url.rstrip('/')}{path}"
    return path


def _public_url(path: str, site_url: str | None) -> str:
    if path == "/":
        return _absolute_or_relative("/", site_url)
    return _absolute_or_relative(path, site_url)


def _source_items(source_urls: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for source_url in source_urls:
        parsed = urlparse(source_url)
        label = parsed.netloc or source_url
        items.append({"url": source_url, "label": label})
    return items


def _article_context(article: dict[str, Any], site_url: str | None) -> dict[str, Any]:
    confidence = str(article.get("confidence", "unknown"))
    claim_labels = [_friendly_label(str(label)) for label in article.get("claim_labels", []) if label]
    source_urls = [str(url) for url in article.get("source_urls", [])]
    body_markdown = str(article.get("body_markdown", ""))
    return {
        **article,
        "article_url": _public_url(_article_url(str(article["slug"])), site_url),
        "body_html": _markdown_to_html(body_markdown),
        "claim_labels": claim_labels,
        "confidence_class": f"confidence-badge--{confidence}",
        "confidence_label": f"{_friendly_label(confidence)} confidence",
        "section_title": _section_title(str(article.get("content_type", ""))),
        "source_items": _source_items(source_urls),
        "source_urls": source_urls,
    }


def _section_context(content_type: str, articles: list[dict[str, Any]], site_url: str | None) -> dict[str, Any]:
    section_articles = [_article_context(article, site_url) for article in articles]
    return {
        "slug": content_type,
        "title": _section_title(content_type),
        "description": _section_description(content_type),
        "count": len(section_articles),
        "url": _public_url(_section_url(content_type), site_url),
        "articles": section_articles,
    }


def _group_sections(articles: list[dict[str, Any]], site_url: str | None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        grouped[str(article.get("content_type", "other"))].append(article)

    ordered_types = sorted(
        grouped,
        key=lambda content_type: (
            DEFAULT_SECTION_ORDER.index(content_type) if content_type in DEFAULT_SECTION_ORDER else len(DEFAULT_SECTION_ORDER),
            _section_title(content_type).lower(),
        ),
    )
    return [_section_context(content_type, sorted(grouped[content_type], key=_sort_key, reverse=True), site_url) for content_type in ordered_types]


def _load_articles(content_dir: Path) -> list[dict[str, Any]]:
    published_dir = content_dir / "published"
    articles: list[dict[str, Any]] = []
    if not published_dir.exists():
        return articles
    for path in sorted(published_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        articles.append(article)
    articles.sort(key=_sort_key, reverse=True)
    return articles


def _count_json_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for child in path.glob("*.json") if child.is_file())


def _plural_label(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _format_number(num: int | None) -> str:
    if num is None:
        return "N/A"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M".replace(".0M", "M")
    if num >= 1_000:
        return f"{num / 1_000:.1f}K".replace(".0K", "K")
    return str(num)


def _load_youtube_dashboard(root: Path, site_url: str | None) -> dict[str, Any]:
    registry_path = root / "content" / "registry" / "youtube_channels.json"
    packets_dir = root / "data" / "source-packets"
    downloads_dir = root / "data" / "downloads"

    channels_raw: list[dict[str, Any]] = []
    if registry_path.exists():
        channels_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(channels_payload, list):
            channels_raw = [channel for channel in channels_payload if isinstance(channel, dict) and channel.get("active", True)]

    packets: list[dict[str, Any]] = []
    if packets_dir.exists():
        for packet_path in sorted(packets_dir.glob("*.json")):
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            if isinstance(packet, dict) and packet.get("source_type") == "youtube":
                packets.append(packet)

    download_status_by_video: dict[str, str] = {}
    if downloads_dir.exists():
        for metadata_path in sorted(downloads_dir.glob("*/metadata.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            video_id = str(metadata.get("video_id") or metadata_path.parent.name)
            download_status_by_video[video_id] = str(metadata.get("status", "unknown"))

    channels = []
    for channel in sorted(channels_raw, key=lambda item: (int(item.get("priority") or 999), str(item.get("name", "")).lower())):
        channel_id = str(channel.get("id", ""))
        name = str(channel.get("name", "YouTube channel"))
        channel_packets = [
            packet
            for packet in packets
            if str(packet.get("registry_channel_id", "")) == channel_id
            or str(packet.get("source_name", "")) == name
            or str(packet.get("author_or_channel", "")) == name
        ]
        channel_packets.sort(key=lambda packet: str(packet.get("published_at", "")), reverse=True)
        episodes = []
        download_count = 0
        transcript_count = 0
        for packet in channel_packets:
            video_id = str(packet.get("video_id", ""))
            status = download_status_by_video.get(video_id, str(packet.get("status", "unknown")))
            if status in {"downloaded", "transcribed"}:
                download_count += 1
            if status == "transcribed":
                transcript_count += 1
            episodes.append(
                {
                    "title": str(packet.get("title", "Untitled episode")),
                    "url": str(packet.get("source_url", "")),
                    "status": status,
                    "status_label": _friendly_label(status),
                }
            )

        channels.append(
            {
                "id": channel_id,
                "name": name,
                "url": str(channel.get("url", "")),
                "priority": int(channel.get("priority") or 0),
                "category_label": _friendly_label(str(channel.get("category", "youtube"))),
                "reason": str(channel.get("reason", "")),
                "subscriber_count": _format_number(channel.get("subscriber_count")),
                "video_count": _format_number(channel.get("video_count")),
                "average_views": _format_number(channel.get("average_views")),
                "download_count": download_count,
                "transcript_count": transcript_count,
                "download_label": _plural_label(download_count, "download"),
                "transcript_label": _plural_label(transcript_count, "transcript"),
                "episodes": episodes[:3],
            }
        )

    return {
        "channels": channels,
        "channel_count": len(channels),
        "packet_count": len(packets),
        "download_count": sum(1 for status in download_status_by_video.values() if status in {"downloaded", "transcribed"}),
        "transcript_count": sum(1 for status in download_status_by_video.values() if status == "transcribed"),
        "url": _public_url(_youtube_url(), site_url),
    }


def _clean_site_dir(site_dir: Path) -> None:
    if not site_dir.exists():
        return
    for child in site_dir.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _rss_pub_date(iso_timestamp: str) -> str:
    normalized = iso_timestamp.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt.astimezone(timezone.utc))


def _build_rss(articles: list[dict[str, Any]], site_url: str | None) -> str:
    items: list[str] = []
    for article in articles[:20]:
        title = html.escape(str(article.get("title", "Article")))
        link = html.escape(str(article["article_url"]))
        description = html.escape(str(article.get("dek", "")))
        pub_date = html.escape(_rss_pub_date(str(article.get("published_at", "1970-01-01T00:00:00Z"))))
        items.append(
            "\n".join(
                [
                    "    <item>",
                    f"      <title>{title}</title>",
                    f"      <link>{link}</link>",
                    f"      <guid isPermaLink=\"true\">{link}</guid>",
                    f"      <description>{description}</description>",
                    f"      <pubDate>{pub_date}</pubDate>",
                    "    </item>",
                ]
            )
        )

    feed_title = html.escape("UFO / UAP News Hub")
    feed_link = html.escape(_public_url("/", site_url))
    feed_description = html.escape("Evidence-first UFO/UAP reporting.")
    return "\n".join(
        [
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
            "<rss version=\"2.0\">",
            "  <channel>",
            f"    <title>{feed_title}</title>",
            f"    <link>{feed_link}</link>",
            f"    <description>{feed_description}</description>",
            *items,
            "  </channel>",
            "</rss>",
        ]
    )


def _build_sitemap(
    *,
    articles: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    site_url: str | None,
) -> str:
    urls = {
        _public_url("/", site_url),
        _public_url("/status.html", site_url),
        _public_url(_youtube_url(), site_url),
        _public_url("/rss.xml", site_url),
        _public_url("/sitemap.xml", site_url),
        _public_url("/sections/index.html", site_url),
        _public_url("/about.html", site_url),
        _public_url("/editorial-standards.html", site_url),
        _public_url("/corrections.html", site_url),
        _public_url("/contact.html", site_url),
    }
    urls.update(section["url"] for section in sections)
    urls.update(article["article_url"] for article in articles)
    entries = "\n".join(
        f"  <url><loc>{html.escape(url)}</loc></url>" for url in sorted(urls)
    )
    return "\n".join(
        [
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            entries,
            "</urlset>",
        ]
    )


def build_site(
    content_dir: Path,
    templates_dir: Path,
    site_dir: Path,
    state: StateStore,
    *,
    status_override: dict[str, str] | None = None,
    site_url: str | None = None,
) -> None:
    site_url = site_url or os.getenv("UAPNEWSHUB_SITE_URL", "").strip() or None
    _clean_site_dir(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "img").mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "js").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)
    (site_dir / "sections").mkdir(parents=True, exist_ok=True)
    (site_dir / "youtube").mkdir(parents=True, exist_ok=True)
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    assets_source = Path("templates/assets")
    if assets_source.exists():
        shutil.copytree(assets_source, site_dir / "assets", dirs_exist_ok=True)
    
    # Ensure favicon exists
    favicon_path = site_dir / "assets" / "img" / "favicon.svg"
    if not favicon_path.exists():
        favicon_path.write_text(
            """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#121b27"/><circle cx="32" cy="32" r="12" fill="#9ec1ff"/><path d="M19 39c8-11 18-11 26 0" stroke="#e5edf5" stroke-width="4" fill="none" stroke-linecap="round"/></svg>""",
            encoding="utf-8",
        )

    raw_articles = _load_articles(content_dir)
    articles = [_article_context(article, site_url) for article in raw_articles]
    sections = _group_sections(raw_articles, site_url)
    youtube_dashboard = _load_youtube_dashboard(content_dir.parent, site_url)
    env = _template_env(templates_dir)
    site_root = site_url.rstrip("/") if site_url else ""

    index_html = _render_template(
        env,
        "index.html",
        title="UFO / UAP News Hub",
        description="Evidence-first UFO/UAP reporting.",
        articles=articles[:6],
        sections=sections,
        youtube_dashboard=youtube_dashboard,
        canonical_url=_public_url("/", site_url),
        site_root=site_root,
    )
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")

    sections_index_html = _render_template(
        env,
        "sections/index.html",
        title="Sections",
        description="Current editorial lanes.",
        sections=sections,
        canonical_url=_public_url("/sections/index.html", site_url),
        site_root=site_root,
    )
    (site_dir / "sections" / "index.html").write_text(sections_index_html, encoding="utf-8")

    youtube_html = _render_template(
        env,
        "youtube/index.html",
        title="YouTube Channel Analysis",
        description="Synopsis and analysis staging for monitored UFO/UAP YouTube channels.",
        dashboard=youtube_dashboard,
        canonical_url=_public_url(_youtube_url(), site_url),
        site_root=site_root,
    )
    (site_dir / "youtube" / "index.html").write_text(youtube_html, encoding="utf-8")

    for section in sections:
        section_html = _render_template(
            env,
            "sections/section.html",
            title=section["title"],
            description=section["description"],
            section=section,
            canonical_url=_public_url(section["url"], site_url),
            site_root=site_root,
        )
        (site_dir / "sections" / f"{section['slug']}.html").write_text(section_html, encoding="utf-8")

    for article in articles:
        article_html = _render_template(
            env,
            "article.html",
            title=article.get("title", "Article"),
            description=article.get("dek", ""),
            article=article,
            canonical_url=_public_url(article["article_url"], site_url),
            site_root=site_root,
        )
        (site_dir / "articles" / f"{article['slug']}.html").write_text(article_html, encoding="utf-8")

    status = {
        "last_hourly_run": ((state.latest_run("hourly") or {}).get("finished_at") or "never"),
        "last_daily_run": ((state.latest_run("daily") or {}).get("finished_at") or "never"),
        "last_publish": ((state.latest_run("publish") or {}).get("finished_at") or "never"),
        "queued_items": _count_json_files(content_dir / "queue"),
        "rejected_items": _count_json_files(content_dir / "rejected"),
    }
    latest = status["last_daily_run"] if status["last_daily_run"] != "never" else status["last_hourly_run"]
    try:
        latest_at = datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
        status["stale"] = (datetime.now(timezone.utc) - latest_at).total_seconds() > 36 * 3600
    except ValueError:
        status["stale"] = True
    if status_override:
        status.update(status_override)
    status_html = _render_template(
        env,
        "status.html",
        title="Status",
        description="Pipeline status.",
        status=status,
        canonical_url=_public_url("/status.html", site_url),
        site_root=site_root,
    )
    (site_dir / "status.html").write_text(status_html, encoding="utf-8")

    (site_dir / "rss.xml").write_text(_build_rss(articles, site_url), encoding="utf-8")
    (site_dir / "sitemap.xml").write_text(_build_sitemap(articles=articles, sections=sections, site_url=site_url), encoding="utf-8")
    (site_dir / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + _public_url("/sitemap.xml", site_url) + "\n", encoding="utf-8")
    info_pages = {
        "about.html": ("About this newsroom", "An evidence-first reporting project for UFO/UAP source material.", "# Scope\n\nUFO / UAP News Hub reports source-backed claims, official statements, and unresolved questions. It does not treat a report, sighting, interview, or analysis as confirmation.\n\n# Independence\n\nThe site does not use advertising analytics or third-party tracking scripts."),
        "editorial-standards.html": ("Editorial and evidence standards", "How stories are sourced, labeled, reviewed, and published.", "# Evidence-first policy\n\nEvery published item must identify its sources and use claim labels when a statement has not been independently established. Automated drafts require schema checks, factual review, and deterministic validation.\n\n# What is not published\n\nA malformed AGY response, timeout, budget overrun, missing source, failed review, or emergency stop prevents automatic publication."),
        "corrections.html": ("Corrections policy", "How to report a factual error or missing context.", "# Corrections\n\nSend a source-backed correction request through the configured contact channel. Material corrections are noted in the affected article and reflected in the versioned editorial record."),
        "contact.html": ("Contact", "Source corrections and editorial contact.", "# Contact\n\nUse the contact address or form configured for this deployment: " + (os.getenv("UAPNEWSHUB_CONTACT_URL", "Contact configuration pending.").strip() or "Contact configuration pending.") + "."),
    }
    for filename, (heading, dek, body) in info_pages.items():
        page = {"heading": heading, "dek": dek, "body_html": _markdown_to_html(body)}
        (site_dir / filename).write_text(_render_template(env, "info.html", title=heading, description=dek, page=page, canonical_url=_public_url("/" + filename, site_url), site_root=site_root), encoding="utf-8")
