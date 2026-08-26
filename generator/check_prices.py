"""Парити-тест цен: сверяет data/prices.json (источник истины) с ценами
в собранном сайте. Падает (exit 1) при любом расхождении — защищает требование
100% точности цен.

Четыре уровня сверки:
  1. таблица прайса — построчно против прайса своей страницы;
  2. суммы в прозе — каждое число со знаком бата вне таблицы обязано быть
     в прайсе хоть одной услуги;
  3. карточки «от … ฿» — обязаны равняться минимуму той услуги, куда ведут;
  4. противоречия между страницами — услуга со своей страницей, попавшая
     строкой в чужой прайс, обязана стоить там столько же.

Уровень 1 ловит ошибку показа, уровни 2–4 — ошибку содержания: выдуманную сумму
в тексте, устаревшую подпись на карточке и две разные цены одной услуги.
Запуск: cd generator && ../.venv/bin/python check_prices.py"""
import re
import sys
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

from build import PROMO_PREFIX, format_price, load, price_from, price_name_parts

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "th.neva.beauty"
LLMS_TXT = "llms.txt"  # выжимка для ИИ: не HTML, но суммы в ней те же
CURRENCY_SIGN = "฿"

PRICE_ROW = "tr.pricelist__row"
PRICE_NAME = ".pricelist__name"
PRICE_DESC = ".pricelist__desc"
PRICE_VALUE = ".pricelist__price"
PRICE_TABLE = ".pricelist"
CARD = "a.related-card"
CARD_PRICE = ".related-card__price"
ROBOT_MARKUP = "script, style"

_, CONTENT, PRICES = load()

problems = []


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def page_soup(path):
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def displayed_name(name):
    """Название позиции так, как его читает клиент в таблице.

    Строка прайса и строка на странице отличаются подачей: суффикс из выгрузки
    Tilda уходит в подпись, префикс «Акция» — в метку. Сверять надо именно вид
    на странице, иначе парити-тест ловил бы собственное оформление, а не
    расхождение с прайсом."""
    parts = price_name_parts(name)
    prefix = f"{PROMO_PREFIX} " if parts["promo"] else ""
    return clean(f"{prefix}{parts['name']} {parts['note']}")


def price_items():
    """Плоский список позиций всех прайсов: (слаг услуги, раздел, позиция)."""
    return [(slug, section["section"], item)
            for slug, sections in PRICES.items()
            for section in sections
            for item in section["items"]]


# Сумма — это цифры перед знаком бата. Диапазон пишется без пробелов вокруг тире
# («600–1200 ฿»), поэтому «Morpheus 8 — 15 000 ฿» читается как одно число,
# а не как два: тире с пробелами разделяет, тире без пробелов связывает.
DIGITS = r"\d[\d  ]*"
PRICE_RUN_RE = re.compile(rf"{DIGITS}(?:[–-]{DIGITS})?(?={CURRENCY_SIGN})")
NUMBER_RE = re.compile(DIGITS)


def price_numbers(text):
    """Все суммы текста числами: «10 000 ฿» → 10000, «300–5000 ฿» → 300 и 5000."""
    return [int(re.sub(r"\D", "", number))
            for run in PRICE_RUN_RE.findall(text)
            for number in NUMBER_RE.findall(run)]


def catalogue_numbers():
    """Все суммы прайсов — единственные числа, которые сайту можно называть ценой."""
    return {number for _, _, item in price_items()
            for number in price_numbers(item["price"])}


# ── Уровень 1: таблица прайса против prices.json ──────────────────────────────

def expected_rows():
    """Эталон — строки прайса из data/prices.json (источник истины)."""
    rows = Counter()
    for slug, _, item in price_items():
        if clean(item["price"]):
            rows[(slug, displayed_name(item["name"]),
                  clean(format_price(item["price"])))] += 1
    return rows


def rendered_rows():
    """Факт — строки прайса из собранных страниц услуг."""
    rows = Counter()
    for slug in PRICES:
        for row in page_soup(SITE / slug / "index.html").select(PRICE_ROW):
            name = row.select_one(PRICE_NAME)
            desc = name.select_one(PRICE_DESC)
            if desc:
                desc.extract()
            rows[(slug, clean(name.get_text()),
                  clean(row.select_one(PRICE_VALUE).get_text()))] += 1
    return rows


def check_table_rows():
    """Уровень 1. Возвращает пару «позиций в прайсах, позиций на страницах»."""
    expected, rendered = expected_rows(), rendered_rows()
    for label, missing in (("нет на странице", expected - rendered),
                           ("нет в прайсе", rendered - expected)):
        for (slug, name, price), count in sorted(missing.items()):
            problems.append(f"таблица {slug}: {label} — «{name}» {price} ×{count}")
    return sum(expected.values()), sum(rendered.values())


# ── Уровни 2 и 3: один проход по собранным страницам ──────────────────────────

def check_cards(page_name, soup):
    """Уровень 3: «от … ฿» на карточке равно минимуму прайса своей услуги."""
    for card in soup.select(CARD):
        shown = card.select_one(CARD_PRICE)
        if not shown:
            continue
        slug = card["href"].strip("/").rsplit("/", 1)[-1]
        expected = clean(price_from(PRICES.get(slug, []), CURRENCY_SIGN) or "")
        if clean(shown.get_text()) != expected:
            problems.append(f"карточка {page_name} → /{slug}/: показано "
                            f"«{clean(shown.get_text())}», в прайсе «{expected}»")


def prose_text(soup):
    """Текст страницы без таблиц прайса и без разметки для роботов.

    Таблицу сверяет уровень 1, JSON-LD собирается из того же каталога цен —
    здесь остаётся то, что писал человек: описания, преимущества, ответы FAQ."""
    for element in soup.select(f"{ROBOT_MARKUP}, {PRICE_TABLE}"):
        element.decompose()
    return soup.get_text(" ")


def check_prose(page_name, text, allowed):
    """Уровень 2: сумма, названная прозой, обязана быть в прайсе."""
    for number in price_numbers(text):
        if number not in allowed:
            problems.append(f"проза {page_name}: суммы {number} {CURRENCY_SIGN} "
                            f"нет ни в одном прайсе")


def check_pages():
    """Уровни 2 и 3 по всем собранным страницам плюс выжимка для ИИ.

    Карточки читаются до прозы: prose_text() выбрасывает узлы из дерева."""
    allowed = catalogue_numbers()
    for path in sorted(SITE.rglob("*.html")):
        page_name = path.relative_to(SITE)
        soup = page_soup(path)
        check_cards(page_name, soup)
        check_prose(page_name, prose_text(soup), allowed)
    check_prose(LLMS_TXT, (SITE / LLMS_TXT).read_text(encoding="utf-8"), allowed)


# ── Уровень 4: противоречия между страницами ──────────────────────────────────

def cross_page_conflicts(slug, title, items):
    """Строки чужих прайсов, где услуга `slug` стоит не столько же.

    Услуга со своей страницей встречается и в прайсе раздела — там она названа
    полным именем («Davines Naturaltech Tailoring», «Tokio Inkarami - Короткие
    волосы»). Цена такой строки обязана совпадать с одной из цен своей страницы,
    иначе клиент видит два разных числа за одну процедуру, а робот — противоречие
    в разметке."""
    own = {clean(item["price"]) for owner, _, item in items if owner == slug}
    return [(owner, section, item) for owner, section, item in items
            if owner != slug and title.lower() in item["name"].lower()
            and clean(item["price"]) not in own]


def check_cross_page():
    """Уровень 4 по всем услугам, у которых есть своя страница."""
    items = price_items()
    for slug, service in CONTENT["services"].items():
        own = ", ".join(sorted({clean(item["price"])
                                for owner, _, item in items if owner == slug}))
        for owner, section, item in cross_page_conflicts(slug, service["title"], items):
            problems.append(f"противоречие /{slug}/: «{item['name']}» в прайсе "
                            f"{owner} ({section}) стоит {clean(item['price'])}, "
                            f"на своей странице — {own}")


def main():
    expected_total, rendered_total = check_table_rows()
    check_pages()
    check_cross_page()
    for problem in problems:
        print("  ", problem)
    print(f"позиций в прайсах: {expected_total}, на страницах: {rendered_total}")
    print("PRICE PARITY OK" if not problems
          else f"PRICE PARITY FAILED: расхождений {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
