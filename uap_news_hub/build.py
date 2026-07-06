from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from .state import StateStore
from .utils import ensure_parent


DEFAULT_TEMPLATES = {
    "base.html": """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <meta name="description" content="{{ description }}">
  <link rel="canonical" href="{{ canonical_url }}">
  <meta property="og:title" content="{{ title }}">
  <meta property="og:description" content="{{ description }}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{{ canonical_url }}">
  <link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/css/theme.css">
  <script defer src="/assets/js/app.js"></script>
</head>
<body>
  <main class="page">
    {% block content %}{% endblock %}
  </main>
</body>
</html>""",
    "index.html": """{% extends "base.html" %}
{% block content %}
<header><h1>UFO / UAP News Hub</h1><p>Latest validated items.</p></header>
<section>
{% for article in articles %}
  <article>
    <h2><a href="/articles/{{ article.slug }}.html">{{ article.title }}</a></h2>
    <p>{{ article.dek }}</p>
    <p class="meta">{{ article.published_at }} | confidence: {{ article.confidence }}</p>
  </article>
{% endfor %}
</section>
{% endblock %}""",
    "article.html": """{% extends "base.html" %}
{% block content %}
<article>
  <h1>{{ article.title }}</h1>
  <p>{{ article.dek }}</p>
  <p class="meta">{{ article.published_at }} | confidence: {{ article.confidence }}</p>
  <section class="body">{{ article.body_html | safe }}</section>
  <section>
    <h2>Sources</h2>
    <ul>
    {% for source_url in article.source_urls %}
      <li><a href="{{ source_url }}">{{ source_url }}</a></li>
    {% endfor %}
    </ul>
  </section>
</article>
{% endblock %}""",
    "status.html": """{% extends "base.html" %}
{% block content %}
<h1>Status</h1>
<ul>
  <li>Last hourly run: {{ status.last_hourly_run }}</li>
  <li>Last daily run: {{ status.last_daily_run }}</li>
  <li>Last publish: {{ status.last_publish }}</li>
</ul>
{% endblock %}""",
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
    try:
        template = env.get_template(template_name)
    except Exception:
        fallback_env = Environment(loader=DictLoader(DEFAULT_TEMPLATES), autoescape=select_autoescape(["html", "xml"]))
        template = fallback_env.get_template(template_name)
    return template.render(**context)


def _load_articles(content_dir: Path) -> list[dict[str, Any]]:
    published_dir = content_dir / "published"
    articles: list[dict[str, Any]] = []
    if not published_dir.exists():
        return articles
    for path in sorted(published_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        article["body_html"] = _markdown_to_html(article.get("body_markdown", ""))
        articles.append(article)
    articles.sort(key=lambda item: (item.get("published_at", ""), item.get("slug", "")), reverse=True)
    return articles


def build_site(
    content_dir: Path,
    templates_dir: Path,
    site_dir: Path,
    state: StateStore,
    *,
    status_override: dict[str, str] | None = None,
) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "img").mkdir(parents=True, exist_ok=True)
    (site_dir / "assets" / "js").mkdir(parents=True, exist_ok=True)
    (site_dir / "articles").mkdir(parents=True, exist_ok=True)
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    (site_dir / "assets" / "css" / "theme.css").write_text(
        """body{font-family:system-ui,sans-serif;background:#0e1116;color:#e6edf3;margin:0}
.page{max-width:960px;margin:0 auto;padding:2rem}
a{color:#8ab4f8}article{border:1px solid #2b313c;padding:1rem;margin:1rem 0;border-radius:12px;background:#141821}
.meta{color:#9da7b1;font-size:.9rem}""",
        encoding="utf-8",
    )
    (site_dir / "assets" / "img" / "favicon.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#141821"/><circle cx="32" cy="32" r="12" fill="#8ab4f8"/><path d="M20 38c8-10 16-10 24 0" stroke="#e6edf3" stroke-width="4" fill="none" stroke-linecap="round"/></svg>""",
        encoding="utf-8",
    )
    (site_dir / "assets" / "js" / "app.js").write_text(
        "document.documentElement.dataset.js = 'enabled';\n",
        encoding="utf-8",
    )

    articles = _load_articles(content_dir)
    env = _template_env(templates_dir)
    index_html = _render_template(
        env,
        "index.html",
        title="UFO / UAP News Hub",
        description="Evidence-first UFO/UAP reporting.",
        articles=articles,
        canonical_url="/",
    )
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")

    for article in articles:
        article_html = _render_template(
            env,
            "article.html",
            title=article.get("title", "Article"),
            description=article.get("dek", ""),
            article=article,
            canonical_url=f"/articles/{article['slug']}.html",
        )
        (site_dir / "articles" / f"{article['slug']}.html").write_text(article_html, encoding="utf-8")

    status = {
        "last_hourly_run": ((state.latest_run("hourly") or {}).get("finished_at") or "never"),
        "last_daily_run": ((state.latest_run("daily") or {}).get("finished_at") or "never"),
        "last_publish": ((state.latest_run("publish") or {}).get("finished_at") or "never"),
    }
    if status_override:
        status.update(status_override)
    status_html = _render_template(
        env,
        "status.html",
        title="Status",
        description="Pipeline status.",
        status=status,
        canonical_url="/status.html",
    )
    (site_dir / "status.html").write_text(status_html, encoding="utf-8")
