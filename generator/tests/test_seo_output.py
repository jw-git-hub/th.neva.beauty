"""Служебные файлы и метатеги: то, что читают поиск и ИИ-ассистенты.

Проверяется слой, который не виден на странице и потому легко ломается молча:
цена в тексте против цены в таблице, дата изменения в sitemap, заголовок
карточки в мессенджере и выжимка llms.txt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import build_llms, og_title, page_digest, price_by_name, price_span

NBSP = " "

PRICES = {
    "massazh": [{"section": "Цены", "items": [
        {"name": "Массаж тела", "desc": "", "price": "20000 ฿"},
        {"name": "Массаж лица", "desc": "", "price": "1500 ฿"},
        {"name": "Одноразовая простыня", "desc": "", "price": "+100 ฿", "addon": True},
    ]}],
}

SITE = {
    "brand": "Neva Beauty",
    "brand_full": "Neva Beauty — Koh Samui",
    "base_url": "https://th.neva.beauty",
    "location": "о. Самуи, Таиланд",
    "hours": "Приём по записи",
    "contacts": {"whatsapp_url": "https://wa.me/1", "telegram_url": "https://t.me/x",
                 "instagram_url": "https://instagram.com/x"},
    "business": {"currency_sign": "฿", "telephone": "+79990289115",
                 "address": {"locality": "Koh Samui", "region": "Surat Thani"}},
}

CONTENT = {
    "llms_description": "Салон красоты на Самуи.",
    "home": {"seo_title": "Салон красоты на Самуи — Neva Beauty"},
    "categories": [
        {"slug": "figura", "title": "Коррекция фигуры", "url": "/figura/",
         "is_page": True, "services": ["massazh"]},
        # раздел из одной услуги: своей страницы нет, адрес совпадает с адресом услуги.
        # В боевых данных такого раздела сейчас нет — «Макияж» был последним и снят
        # 2026-08-26, — но правило в генераторе осталось, и проверять его надо.
        {"slug": "odna-usluga", "title": "Раздел из одной услуги", "url": "/odna-usluga/",
         "is_page": False, "services": ["odna-usluga"]},
    ],
    "services": {"massazh": {"title": "Профессиональный массаж"}},
}


def test_price_in_text_matches_price_in_table():
    """Цена из {price:…} набрана так же, как в прайс-таблице."""
    index = price_by_name(PRICES)
    assert index[("massazh", "Массаж тела")] == f"20{NBSP}000 ฿"


def test_price_span_skips_addons():
    assert price_span([PRICES["massazh"]], "฿") == f"1500–20{NBSP}000{NBSP}฿"


def test_price_span_is_none_without_prices():
    assert price_span([[]], "฿") is None


def test_og_title_comes_from_heading_not_from_seo_title():
    entry = {"h1": "Массаж на Самуи", "title": "Профессиональный массаж",
             "seo_title": "Массаж на Самуи — Neva Beauty"}
    assert og_title(entry, SITE) == "Массаж на Самуи — Neva Beauty"


def test_og_title_falls_back_to_title():
    assert og_title({"title": "Массаж"}, SITE) == "Массаж — Neva Beauty"


def test_page_digest_ignores_asset_fingerprints():
    """Правка CSS меняет ?v= на всех страницах, но текст страницы не трогает."""
    before = '<link href="/a.css?v=1a2b3c4d"><p>Текст</p>'
    after = '<link href="/a.css?v=99887766"><p>Текст</p>'
    assert page_digest(before) == page_digest(after)


def test_page_digest_reacts_to_content():
    assert page_digest("<p>Было</p>") != page_digest("<p>Стало</p>")


def test_llms_lists_every_url_once():
    lines = build_llms(SITE, CONTENT, PRICES).splitlines()
    urls = [line.split("](")[1].rstrip(")") for line in lines if line.startswith("- [")]
    assert len(urls) == len(set(urls)), urls
    assert "https://th.neva.beauty/" in urls  # главная выведена ссылкой, а не только заголовком
    assert "https://th.neva.beauty/odna-usluga/" not in urls  # раздел без своей страницы


def test_llms_carries_facts_and_prices():
    text = build_llms(SITE, CONTENT, PRICES)
    assert "о. Самуи, Таиланд" in text
    assert "приём по записи" in text
    assert f"20{NBSP}000" in text
