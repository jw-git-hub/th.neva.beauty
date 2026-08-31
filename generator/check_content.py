"""Проверки качества собранных страниц.

Ловит то, что парити-тест цен не видит: следы старого бренда, битые внутренние
ссылки, отсутствующие изображения, дубли метатегов, невалидный JSON-LD.
Падает (exit 1) при любом нарушении.
Запуск: .venv/bin/python generator/check_content.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from bs4 import BeautifulSoup
from PIL import Image
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "th.neva.beauty"
BASE_URL = "https://th.neva.beauty"
OG_SIZE = ("1200", "630")  # формат карточки в WhatsApp, Telegram и Facebook
SITE_YML = ROOT / "data" / "site.yml"
# Мета-теги подтверждения прав: ключ в site.yml → имя тега в разметке.
VERIFICATION_TAGS = {"google": "google-site-verification", "yandex": "yandex-verification"}

# Следы старого бренда. Исключений больше нет: последним был Instagram-аккаунт
# avocado.beauty.samui, переименованный в th.neva.beauty (задача 64).
FORBIDDEN = ["Avocado", "avocado", "doctor-cosmetolog.pro", "Дананг", "Da Nang"]

# Аппараты и методики — поисковые сущности: их ищут точным написанием, и «РФ лифтинг»
# без дефиса или кириллическая «М22» для поиска и ИИ уже другие слова.
# Слева — что нашли на странице, справа — единственно верная форма.
ENTITY_SPELLING = {
    "RF-лифтинг": "РФ-лифтинг",
    "RF лифтинг": "РФ-лифтинг",
    "РФ лифтинг": "РФ-лифтинг",
    "SMAS лифтинг": "SMAS-лифтинг",
    "Смас": "SMAS",
    "М22": "M22",  # кириллическая М вместо латинской
    "Morpheus8": "Morpheus 8",
    "Морфеус": "Morpheus 8",
    "Скарлет": "Scarlet S",
    "Tokyo Inkarami": "Tokio Inkarami",  # марка пишется Tokio, а не как город
    "Токио Инкарами": "Tokio Inkarami",
    "Natural Tech": "Naturaltech",
    "Эндосфера терапия": "Эндосфера-терапия",  # без дефиса писал старый сайт
    "эндосфера терапия": "эндосфера-терапия",
    "эндосферы терапия": "эндосфера-терапия",
    "Lebel": "LEBEL",
    "Давинес": "Davines",
}

# Плейсхолдеры контента, которые обязана раскрыть сборка (build.py: render_faq_contacts).
PLACEHOLDER_RE = re.compile(r"\{(?:whatsapp|telegram|instagram|price:[^}]*)\}")

# Слово, повторённое подряд через пробел (обычный или неразрывный).
DOUBLED_WORD_RE = re.compile(r"\b(\w+)[  ]+\1\b", re.IGNORECASE)

TITLE_MAX = 65
TITLE_PREFIX = 20  # по такому началу заголовка поиск схлопывает похожие страницы
BRAND_SUFFIX = " — Neva Beauty"  # единая связка названия салона с заголовком
DESC_MIN, DESC_MAX = 120, 170

# Знаки, которых нет ни в Manrope, ни в Cormorant, — их рисует системный шрифт.
# Бат в обеих гарнитурах отсутствует, а валюта салона именно тайская.
FONT_FALLBACK_CHARS = {"฿"}

problems = []


def font_charset():
    """Объединённый набор знаков всех самохостовых шрифтов (читается один раз)."""
    if not _font_charset:
        for font_path in sorted((SITE / "assets/fonts").glob("*.woff2")):
            with TTFont(font_path) as font:
                _font_charset.update(chr(code) for code in font.getBestCmap())
    return _font_charset


_font_charset = set()


def report(page, message):
    problems.append(f"{page}: {message}")


def pages():
    return sorted(SITE.rglob("*.html"))


def rel(path):
    return str(path.relative_to(SITE))


def check_forbidden(path, text):
    for needle in FORBIDDEN:
        if needle in text:
            report(rel(path), f"след старого бренда или города: {needle!r}")


def check_entity_spelling(path, text):
    """Написание аппаратов и методик — одно на весь сайт.

    Разнобой рассыпает одну поисковую сущность на несколько: «M22» латиницей
    и «М22» кириллицей для поиска и ИИ — разные слова."""
    for wrong, right in ENTITY_SPELLING.items():
        if wrong in text:
            report(rel(path), f"написание сущности: {wrong!r} → нужно {right!r}")


def check_placeholders(path, text):
    """Нераскрытый плейсхолдер — это цена или ссылка, которых посетитель не увидит.

    Опечатка в имени позиции прайса или в токене оставляет «{price:...}» прямо
    в тексте страницы и в JSON-LD, а сборка при этом проходит молча."""
    for token in sorted(set(PLACEHOLDER_RE.findall(text))):
        report(rel(path), f"нераскрытый плейсхолдер в тексте: {token}")


def check_doubled_words(path, soup):
    """Слово, повторённое подряд: «от от 3000 ฿», «в в салоне».

    Такое рождается при подстановке цен и правке фраз: в прайсе «от 3000 ฿»,
    а в тексте перед плейсхолдером уже написано «от». Глазами в длинном ответе
    FAQ это не видно. Проверяется внутри одного текстового узла — соседние
    подписи в меню и в дровере законно повторяют друг друга."""
    for node in soup.stripped_strings:
        for match in DOUBLED_WORD_RE.finditer(node):
            report(rel(path), f"слово повторено дважды: {match.group(0)!r}")


def check_headings(path, soup):
    h1s = soup.select("main h1")
    if len(h1s) != 1:
        report(rel(path), f"заголовков h1 в main: {len(h1s)}, нужен ровно один")


def collect_h2(path, soup, headings):
    """Копит h2 по всему сайту — дубли ловит check_shared_headings()."""
    for h2 in soup.select("main h2"):
        headings[h2.get_text(strip=True)].append(rel(path))


def check_shared_headings(headings):
    """Один и тот же h2 на нескольких страницах — заголовок ни о чём.

    «Запишитесь на консультацию» стояло на 23 страницах из 23, «Почему это
    работает» — на 17: такой заголовок не говорит ни клиенту, ни роботу, что
    именно под ним, и место в структуре страницы тратится впустую."""
    for text, where in headings.items():
        if len(where) > 1:
            problems.append(
                f"один и тот же h2 на {len(where)} страницах ({', '.join(where[:3])}…): {text!r}"
                if len(where) > 3 else
                f"один и тот же h2 на страницах {', '.join(where)}: {text!r}")


def check_brand_in_title(path, soup):
    """Название салона обязано быть в title каждой индексируемой страницы.

    Без него страница выглядит в выдаче чужой: человек видит запрос и не видит,
    чей это сайт. Форма связки одна на весь сайт — « — Neva Beauty» в конце."""
    if soup.select_one('meta[name="robots"][content*="noindex"]'):
        return
    title_el = soup.select_one("title")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title.endswith(BRAND_SUFFIX):
        report(rel(path), f"title не заканчивается на {BRAND_SUFFIX!r}: {title!r}")


def check_og_title(path, soup):
    """og:title — заголовок карточки в мессенджере, он есть всегда."""
    if not og_content(soup, "og:title"):
        report(rel(path), "нет og:title")


def check_heading_order(path, soup):
    """Уровни заголовков в <main> идут без пропусков: h1 → h2 → h3.

    Прыжок h1 → h3 робот и скринридер читают как пропущенный раздел: список
    оказывается вложен в заголовок, которого на странице нет."""
    previous = 0
    for heading in soup.select("main h1, main h2, main h3, main h4, main h5, main h6"):
        level = int(heading.name[1])
        if previous and level > previous + 1:
            report(rel(path), f"пропуск уровня заголовка: h{previous} → h{level}")
        previous = level


def check_preloaded_image(path, soup):
    """У предзагруженной картинки первого экрана есть fetchpriority="high",
    а её набор ширин совпадает с набором в разметке.

    preload поднимает приоритет самой загрузки, но встреченная ниже <img> без
    приоритета всё равно встаёт в общую очередь отрисовки — LCP-кадр появляется
    позже. Атрибут легко потерять при правке шаблона, а в вёрстке это не видно.
    Расхождение imagesrcset и srcset тише и дороже: браузер скачивает один файл
    по предзагрузке и второй по разметке — вместо ускорения выходит лишний вес."""
    preload = soup.select_one('link[rel="preload"][as="image"]')
    if not preload:
        return
    href = preload.get("href", "")
    img = soup.select_one(f'main img[src="{href}"]')
    if img is None:
        report(rel(path), f"предзагружено изображение, которого нет в main: {href}")
        return
    if img.get("fetchpriority") != "high":
        report(rel(path), f'у предзагруженного изображения нет fetchpriority="high": {href}')
    for preload_attr, img_attr in (("imagesrcset", "srcset"), ("imagesizes", "sizes")):
        if preload.get(preload_attr, "") != img.get(img_attr, ""):
            report(rel(path), f"{preload_attr} предзагрузки не совпадает с {img_attr} картинки: {href}")


def check_srcset(path, soup):
    """Каждый файл из srcset существует, а ширина в дескрипторе — настоящая.

    Набор ширин собирается из имён файлов, поэтому опечатка в лестнице ширин
    или незапущенный make_images.py дают 404 ровно на тех экранах, где браузер
    выберет пропавший вариант, — на своём мониторе этого не увидишь."""
    for img in soup.select("img[srcset]"):
        for candidate in img["srcset"].split(","):
            src, _, descriptor = candidate.strip().rpartition(" ")
            target = SITE / src.lstrip("/")
            if not target.exists():
                report(rel(path), f"нет файла из srcset: {src}")
                continue
            with Image.open(target) as frame:
                if f"{frame.width}w" != descriptor:
                    report(rel(path), f"ширина в srcset ({descriptor}) не совпадает"
                                      f" с файлом ({frame.width}w): {src}")


def check_font_coverage(path, soup):
    """Каждый знак страницы есть в самохостовых шрифтах.

    Шрифты подрезаны под нужный сайту набор знаков (make_fonts.py), поэтому
    новая буква в тексте — например латинская «z» в названии аппарата —
    отрисуется системным шрифтом. В вёрстке это выглядит как одна буква не в
    ту гарнитуру: заметно, только если знать, куда смотреть."""
    visible = (node for node in soup.find_all(string=True)
               if node.parent.name not in ("script", "style"))
    used = {c for text in visible for c in text if c.isprintable() and not c.isspace()}
    missing = sorted(used - font_charset() - FONT_FALLBACK_CHARS)
    if missing:
        report(rel(path), f"знаков нет в шрифтах сайта: {''.join(missing)}")


def check_css_variables():
    """Каждая var(--x) без запасного значения объявлена в CSS сайта.

    Опечатка в имени переменной не ломает сборку и не видна в исходнике: браузер
    молча выбрасывает всё свойство. Так `gap:var(--sp-10)` при отсутствующем
    токене давал не 2,5rem, а ноль — зазор между колонками первого экрана
    пропадал на планшете, и заметить это можно было только замером."""
    declared, used = set(), {}
    for css in sorted((ROOT / "sources/css").glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S)
        declared.update(re.findall(r"(--[\w-]+)\s*:", text))
        # var(--x) без запятой внутри: с запятой есть запасное значение
        used.update({name: css.name for name in re.findall(r"var\(\s*(--[\w-]+)\s*\)", text)})
    # Часть переменных приходит из разметки и из JS, а не из CSS-файлов.
    inline = "".join(path.read_text(encoding="utf-8") for path in pages())
    inline += "".join(js.read_text(encoding="utf-8") for js in (SITE / "assets/js").glob("*.js"))
    declared.update(re.findall(r"(--[\w-]+)\s*:", inline))
    declared.update(re.findall(r'setProperty\(\s*["\'](--[\w-]+)', inline))
    for name, where in sorted(used.items()):
        if name not in declared:
            problems.append(f"sources/css/{where}: переменная {name} не объявлена — свойство не применится")


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


def check_brand_assets(path, soup):
    """Фавиконы, иконка iOS и манифест лежат на диске.

    check_images смотрит только <img>, поэтому битая ссылка на иконку проходила молча —
    именно так буква-заглушка в favicon.svg дожила до задачи 95. Ошибка тихая по своей
    природе: вкладка просто показывает пустой лист, и на странице ничего не ломается.
    """
    for link in soup.select('link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="manifest"]'):
        href = link.get("href", "")
        if not href.startswith("/"):
            report(rel(path), f"ссылка на брендовый ассет не от корня: {href!r}")
            continue
        if not (SITE / href.lstrip("/")).exists():
            report(rel(path), f"нет файла брендового ассета: {href}")


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


def check_verification(files):
    """Мета-теги подтверждения прав стоят на главной и только на ней.

    Панель вебмастера снимает подтверждение, если тег пропал, — а пропасть он может
    молча при любой правке шаблонов. На внутренних страницах тег бесполезен и
    выдаёт токен лишний раз, поэтому лишние вхождения тоже считаем ошибкой.
    """
    tokens = yaml.safe_load(SITE_YML.read_text(encoding="utf-8")).get("verification") or {}
    for key, tag in VERIFICATION_TAGS.items():
        token = (tokens.get(key) or "").strip()
        for path in files:
            el = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").select_one(
                f'meta[name="{tag}"]')
            found = el.get("content", "").strip() if el else ""
            on_home = path.name == "index.html" and path.parent == SITE
            if on_home and token and found != token:
                report(rel(path), f"мета-тег {tag}: ожидался {token!r}, найдено {found!r}")
            elif not on_home and found:
                report(rel(path), f"мета-тег {tag} вне главной страницы")


def check_title_prefixes(titles):
    """Два title с одинаковым началом — заявка на каннибализацию.

    Поиск показывает по запросу одну страницу из пары и выбирает её сам;
    так раздел и его услуга отбирают друг у друга показы."""
    seen = {}
    for title, where in titles.items():
        if not title:
            continue
        prefix = title[:TITLE_PREFIX].lower()
        if prefix in seen:
            problems.append(
                f"одинаковое начало title у {seen[prefix]} и {where[0]}: {prefix!r}")
        seen[prefix] = where[0]


def check_duplicates(label, groups):
    for value, where in groups.items():
        if value and len(where) > 1:
            problems.append(f"дубль {label} на страницах {', '.join(where)}: {value!r}")


def main():
    titles, descriptions, headings = defaultdict(list), defaultdict(list), defaultdict(list)
    files = pages()
    if not files:
        print("Сайт не собран — нечего проверять. Запустите generator/build.py")
        return 1
    for path in files:
        text = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(text, "html.parser")
        check_forbidden(path, text)
        check_entity_spelling(path, text)
        check_placeholders(path, text)
        check_doubled_words(path, soup)
        check_headings(path, soup)
        check_heading_order(path, soup)
        collect_h2(path, soup, headings)
        check_brand_in_title(path, soup)
        check_og_title(path, soup)
        check_images(path, soup)
        check_brand_assets(path, soup)
        check_srcset(path, soup)
        check_font_coverage(path, soup)
        check_preloaded_image(path, soup)
        check_links(path, soup)
        check_schema(path, soup)
        check_meta(path, soup, titles, descriptions)
        check_open_graph(path, soup)
        check_faq(path, soup)
    check_css_variables()
    check_verification(files)
    check_duplicates("title", titles)
    check_title_prefixes(titles)
    check_duplicates("meta description", descriptions)
    check_shared_headings(headings)

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
