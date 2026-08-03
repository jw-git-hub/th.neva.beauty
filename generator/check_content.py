"""Проверки качества собранных страниц.

Ловит то, что парити-тест цен не видит: следы старого бренда, битые внутренние
ссылки, отсутствующие изображения, дубли метатегов, невалидный JSON-LD.
Падает (exit 1) при любом нарушении.
Запуск: .venv/bin/python generator/check_content.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "th.neva.beauty"
BASE_URL = "https://th.neva.beauty"
OG_SIZE = ("1200", "630")  # формат карточки в WhatsApp, Telegram и Facebook

# Следы старого бренда. Instagram-аккаунт avocado.beauty.samui — исключение:
# переименование отложено решением заказчика, ссылка на него легальна.
FORBIDDEN = ["Avocado", "avocado", "doctor-cosmetolog.pro", "Дананг", "Da Nang"]
ALLOWED_BRAND_TRACE = "avocado.beauty.samui"

TITLE_MAX = 65
DESC_MIN, DESC_MAX = 120, 170

problems = []


def report(page, message):
    problems.append(f"{page}: {message}")


def pages():
    return sorted(SITE.rglob("*.html"))


def rel(path):
    return str(path.relative_to(SITE))


def check_forbidden(path, text):
    cleaned = text.replace(ALLOWED_BRAND_TRACE, "")
    for needle in FORBIDDEN:
        if needle in cleaned:
            report(rel(path), f"след старого бренда или города: {needle!r}")


def check_headings(path, soup):
    h1s = soup.select("main h1")
    if len(h1s) != 1:
        report(rel(path), f"заголовков h1 в main: {len(h1s)}, нужен ровно один")


def check_images(path, soup):
    for img in soup.select("img"):
        src = img.get("src", "")
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        target = SITE / src.lstrip("/")
        if not target.exists():
            report(rel(path), f"нет файла изображения: {src}")
        if not img.get("alt", "").strip():
            report(rel(path), f"изображение без alt: {src}")
        if not (img.get("width") and img.get("height")):
            report(rel(path), f"изображение без width/height: {src}")


def check_links(path, soup):
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        target_path = urlsplit(href).path
        if not target_path.startswith("/"):
            continue
        target = SITE / target_path.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        elif not target.suffix:
            target = target.with_suffix(".html")
        if not target.exists():
            report(rel(path), f"битая внутренняя ссылка: {href}")


def check_schema(path, soup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError) as exc:
            report(rel(path), f"невалидный JSON-LD: {exc}")


def check_faq(path, soup):
    """Вопросы из FAQPage должны быть на странице заголовками, слово в слово.

    Разметка без видимого вопроса — обещание поиску, которого страница не держит;
    вопрос не заголовком ИИ и поиск за вопрос не считают."""
    marked = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            graph = json.loads(script.string or "").get("@graph", [])
        except (json.JSONDecodeError, TypeError, AttributeError):
            return
        for node in graph:
            if node.get("@type") == "FAQPage":
                marked += [q["name"] for q in node["mainEntity"]]
    visible = [h.get_text(strip=True) for h in soup.select(".faq__q h3")]
    if marked != visible:
        report(rel(path), f"вопросы FAQ в разметке {marked} ≠ заголовки на странице {visible}")


def og_content(soup, prop):
    tag = soup.select_one(f'meta[property="{prop}"]') or soup.select_one(f'meta[name="{prop}"]')
    return tag.get("content", "").strip() if tag else ""


def check_open_graph(path, soup):
    """Превью ссылки в мессенджерах: картинка на месте и заявленного размера.

    Карточку рисует краулер, который читает только <head>: файла нет или размер
    в разметке разошёлся с настоящим — и вместо превью придёт пустая рамка."""
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and og_content(soup, "og:url") != canonical.get("href", ""):
        report(rel(path), "og:url не совпадает с canonical")
    image = og_content(soup, "og:image")
    if not image.startswith(BASE_URL + "/"):
        report(rel(path), f"og:image не абсолютный: {image!r}")
        return
    if og_content(soup, "twitter:image") != image:
        report(rel(path), "twitter:image не совпадает с og:image")
    if not og_content(soup, "og:image:alt"):
        report(rel(path), "нет og:image:alt")
    target = SITE / image[len(BASE_URL) + 1:]
    if not target.exists():
        report(rel(path), f"нет файла превью: {image}")
        return
    declared = (og_content(soup, "og:image:width"), og_content(soup, "og:image:height"))
    with Image.open(target) as im:
        real = tuple(str(side) for side in im.size)
    if declared != real:
        report(rel(path), f"размер превью в разметке {declared}, у файла {real}")
    if real != OG_SIZE:
        report(rel(path), f"превью {real}, соцсети ждут {OG_SIZE}")


def check_meta(path, soup, titles, descriptions):
    title_el = soup.select_one("title")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        report(rel(path), "нет title")
    elif len(title) > TITLE_MAX:
        report(rel(path), f"title длиной {len(title)}, максимум {TITLE_MAX}")
    titles[title].append(rel(path))

    desc_el = soup.select_one('meta[name="description"]')
    desc = desc_el.get("content", "").strip() if desc_el else ""
    noindex = soup.select_one('meta[name="robots"][content*="noindex"]') is not None
    if noindex:
        return
    if not desc:
        report(rel(path), "нет meta description")
    elif not DESC_MIN <= len(desc) <= DESC_MAX:
        report(rel(path), f"meta description длиной {len(desc)}, нужно {DESC_MIN}–{DESC_MAX}")
    descriptions[desc].append(rel(path))


def check_duplicates(label, groups):
    for value, where in groups.items():
        if value and len(where) > 1:
            problems.append(f"дубль {label} на страницах {', '.join(where)}: {value!r}")


def main():
    titles, descriptions = defaultdict(list), defaultdict(list)
    files = pages()
    if not files:
        print("Сайт не собран — нечего проверять. Запустите generator/build.py")
        return 1
    for path in files:
        text = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(text, "html.parser")
        check_forbidden(path, text)
        check_headings(path, soup)
        check_images(path, soup)
        check_links(path, soup)
        check_schema(path, soup)
        check_meta(path, soup, titles, descriptions)
        check_open_graph(path, soup)
        check_faq(path, soup)
    check_duplicates("title", titles)
    check_duplicates("meta description", descriptions)

    if problems:
        print(f"НАЙДЕНО ПРОБЛЕМ: {len(problems)}")
        for line in problems:
            print(" ", line)
        return 1
    print(f"проверено страниц: {len(files)}")
    print("CONTENT CHECKS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
