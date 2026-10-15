"""IndexNow: какие адреса уходят поисковику после деплоя.

Ошибка здесь не видна ни на странице, ни в сборке: лишние адреса поисковик
со временем перестаёт принимать всерьёз, пропущенные он узнает только при
следующем обходе — у молодого сайта через месяцы.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import OUT
from indexnow import built_page_path, changed_urls, payload, sitemap_urls

BASE_URL = "https://th.neva.beauty"
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://th.neva.beauty/</loc><lastmod>2026-10-11</lastmod></url>
  <url><loc>https://th.neva.beauty/volosy/</loc><lastmod>2026-10-11</lastmod></url>
</urlset>
"""


def test_sitemap_urls_are_read_in_order():
    assert sitemap_urls(SITEMAP) == [f"{BASE_URL}/", f"{BASE_URL}/volosy/"]


def test_url_maps_to_its_built_file():
    assert built_page_path(f"{BASE_URL}/") == OUT / "index.html"
    assert built_page_path(f"{BASE_URL}/volosy/") == OUT / "volosy" / "index.html"


def check(built, live):
    return changed_urls(["u"], lambda url: built, lambda url: live)


def test_same_page_is_not_sent():
    assert check("<p>Стрижка</p>", "<p>Стрижка</p>") == []


def test_changed_text_is_sent():
    assert check("<p>Стрижка и укладка</p>", "<p>Стрижка</p>") == ["u"]


def test_page_missing_on_site_is_sent():
    """Новая страница или сайт не ответил — лучше лишний адрес, чем пропущенный."""
    assert check("<p>Стрижка</p>", None) == ["u"]


def test_asset_version_alone_is_not_a_change():
    built = '<link href="/assets/css/bundle.min.css?v=1a2b3c4d">'
    live = '<link href="/assets/css/bundle.min.css?v=9f8e7d6c">'
    assert check(built, live) == []


def test_payload_points_to_the_key_file_at_site_root():
    assert payload([f"{BASE_URL}/volosy/"], BASE_URL, "abc123") == {
        "host": "th.neva.beauty",
        "key": "abc123",
        "keyLocation": f"{BASE_URL}/abc123.txt",
        "urlList": [f"{BASE_URL}/volosy/"],
    }
