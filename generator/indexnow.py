"""IndexNow: после деплоя сообщить Bing и Яндексу, какие страницы изменились.

На индексе Bing работают ChatGPT Search и Copilot, а 11.10.2026 Bing знал одну
страницу сайта из 23 (задача 141). Молодой сайт он обходит месяцами; IndexNow —
прямой сигнал «страница новая или изменилась». Один запрос на api.indexnow.org
получают все поисковики протокола: Bing, Яндекс, Seznam, Naver, Yep. Google
протокол не поддерживает.

Что изменилось, видно только до выкладки: собранная страница сравнивается с той,
что сейчас на сайте. Поэтому скрипт запускается в сборке и печатает тело запроса,
а отправляет его отдельная задача деплоя — когда новые страницы уже на сайте.

    python generator/indexnow.py          # изменившиеся страницы
    python generator/indexnow.py --all    # все страницы sitemap

Пустой вывод — сообщать нечего.
"""
import json, sys, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import yaml
from build import OUT, ROOT, indexnow_key_file, page_digest

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
FETCH_TIMEOUT_S = 15
USER_AGENT = "th.neva.beauty deploy (IndexNow)"


def sitemap_urls(sitemap_xml):
    return [loc.text for loc in ET.fromstring(sitemap_xml).findall("sm:url/sm:loc", SITEMAP_NS)]


def built_page_path(url):
    """Собранный файл страницы: /volosy/ → th.neva.beauty/volosy/index.html."""
    return OUT / urllib.parse.urlsplit(url).path.lstrip("/") / "index.html"


def read_built(url):
    return built_page_path(url).read_text(encoding="utf-8")


def read_live(url):
    """Страница с сайта как есть; None, если её нет (новая) или сайт не ответил."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"{url}: {error}", file=sys.stderr)
        return None


def is_changed(built_html, live_html):
    """Отпечаток тот же, что у журнала дат: без ?v= ассетов. Правка одного CSS
    текст страниц не меняет, и сообщать о ней поисковику незачем."""
    return live_html is None or page_digest(built_html) != page_digest(live_html)


def changed_urls(urls, read_built, read_live):
    return [url for url in urls if is_changed(read_built(url), read_live(url))]


def payload(urls, base_url, key):
    return {"host": urllib.parse.urlsplit(base_url).netloc,
            "key": key,
            "keyLocation": f"{base_url}/{indexnow_key_file(key)}",
            "urlList": urls}


def main(argv):
    site = yaml.safe_load((ROOT / "data" / "site.yml").read_text(encoding="utf-8"))
    urls = sitemap_urls((OUT / "sitemap.xml").read_text(encoding="utf-8"))
    if "--all" not in argv:
        urls = changed_urls(urls, read_built, read_live)
    if urls:
        print(json.dumps(payload(urls, site["base_url"], site["indexnow_key"])))


if __name__ == "__main__":
    main(sys.argv[1:])
