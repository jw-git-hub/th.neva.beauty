"""Витрина товара: данные, разметка и место страницы в сайте.

Товар — второй источник истины рядом с прайсом услуг, и ломается он тише:
цена шампуня не участвует в AggregateOffer услуги, поэтому расхождение
не всплывёт нигде, кроме самой карточки. Здесь проверяется то, что связывает
products.yml со страницей: плоский список, разброс цен, узлы Product
и пункт меню, который сдвигает нумерацию всей навигации.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schema
from build import (PRODUCTS_NAV_LABEL, PRODUCTS_URL, build_llms, build_nav,
                   product_items, product_span)

BASE = "https://th.neva.beauty"

PRODUCTS = {
    "page": {"h1": "Косметика для волос", "seo_title": "Косметика — Neva Beauty"},
    "brands": [
        {"name": "Davines", "slug": "davines", "heading": "Davines", "lead": "Из Пармы.",
         "products": [
             {"title": "OI Oil", "line": "OI", "kind": "Масло", "volume": "50 ml",
              "price": "1200 ฿", "desc": "Масло для блеска.",
              "image": "davines-oi-oil-50", "image_alt": "Флакон"},
             {"title": "OI Oil", "line": "OI", "kind": "Масло", "volume": "135 ml",
              "price": "1900 ฿", "desc": "Тот же флакон побольше.",
              "image": "davines-oi-oil-135", "image_alt": "Флакон"},
         ]},
        {"name": "LEBEL", "slug": "lebel", "heading": "LEBEL", "lead": "Из Японии.",
         "products": [
             {"title": "viege Shampoo", "line": "viege", "kind": "Шампунь",
              "volume": "240 ml", "price": "1200 ฿", "desc": "Шампунь на травах.",
              "image": "lebel-viege-shampoo", "image_alt": "Флакон"},
         ]},
    ],
}


def test_flat_list_carries_brand_price_and_image():
    """Плоскому списку хватает данных на разметку: бренд, цена числом, адрес кадра."""
    items = product_items(PRODUCTS, BASE)
    assert [item["brand"] for item in items] == ["Davines", "Davines", "LEBEL"]
    assert [item["price_value"] for item in items] == [1200, 1900, 1200]
    assert items[0]["image_url"] == BASE + "/assets/img/davines-oi-oil-50.webp"


def test_span_covers_cheapest_and_dearest():
    assert product_span(product_items(PRODUCTS, BASE), "฿") == "1200–1900 ฿"


def test_span_collapses_when_everything_costs_the_same():
    """Одна цена на всю витрину — это цена, а не диапазон «от и до себя же»."""
    single = {"brands": [{"name": "Davines", "slug": "davines", "products": [
        {"title": "OI Oil", "kind": "Масло", "volume": "50 ml", "price": "1200 ฿",
         "desc": "", "image": "x"}]}]}
    assert product_span(product_items(single, BASE), "฿") == "1200 ฿"


def test_product_name_carries_volume():
    """«OI Oil» продаётся в двух флаконах: без объёма это один товар с двумя ценами."""
    items = product_items(PRODUCTS, BASE)
    names = [schema.product_node(item, "THB", {"@id": "#business"}, BASE)["name"]
             for item in items]
    assert names[:2] == ["Davines OI Oil, 50 ml", "Davines OI Oil, 135 ml"]
    assert len(set(names)) == len(names)


def test_offer_says_store_only():
    """Корзины нет: InStock обещал бы роботу интернет-магазин, которого не существует."""
    item = product_items(PRODUCTS, BASE)[0]
    offer = schema.product_node(item, "THB", {"@id": "#business"}, BASE)["offers"]
    assert offer["availability"] == schema.IN_STORE_ONLY
    assert offer["price"] == 1200
    assert offer["priceCurrency"] == "THB"


def test_product_list_holds_every_position_in_order():
    url = BASE + PRODUCTS_URL
    node = schema.product_list_node("Витрина", product_items(PRODUCTS, BASE),
                                    "THB", {"@id": "#business"}, url)
    assert node["@id"] == url + schema.PRODUCTS_ID
    assert node["numberOfItems"] == 3
    assert [entry["position"] for entry in node["itemListElement"]] == [1, 2, 3]
    # Своих адресов у товара нет: предложение ведёт на якорь бренда той же страницы.
    assert node["itemListElement"][2]["item"]["offers"]["url"] == url + "#lebel"


NAV_CATEGORIES = [
    {"slug": "volosy", "title": "Волосы", "url": "/volosy/", "is_page": True,
     "services": ["uhod-za-volosami"]},
    {"slug": "kosmetologiya", "title": "Косметология", "url": "/kosmetologiya/",
     "is_page": True, "services": ["uhod-za-volosami"]},
]
NAV_SERVICES = {"uhod-za-volosami": {"title": "Уход за волосами"}}


def test_shop_stands_next_to_hair_not_next_to_cosmetology():
    """«Косметика» и «Косметология» рядом в меню различаются одной буквой,
    поэтому витрина встаёт сразу за своим разделом «Волосы»."""
    labels = [item["label"] for item in build_nav(NAV_CATEGORIES, NAV_SERVICES)]
    assert labels == ["Главная", "Волосы", PRODUCTS_NAV_LABEL, "Косметология"]


def test_llms_lists_goods_with_prices():
    """Ассистента спрашивают «где купить Davines на Самуи» — ответ это список с ценами."""
    site = {
        "brand_full": "Neva Beauty — Koh Samui", "base_url": BASE,
        "location": "о. Самуи, Таиланд", "hours": "Приём по записи",
        "booking_rule": "Отменить можно за сутки.",
        "contacts": {"whatsapp_url": "https://wa.me/1", "telegram_url": "https://t.me/x",
                     "instagram_url": "https://instagram.com/x"},
        "business": {"currency_sign": "฿", "telephone": "+79990289115",
                     "address": {"locality": "Koh Samui", "region": "Surat Thani"}},
    }
    content = {"llms_description": "Салон.", "home": {"seo_title": "Салон", "faq": []},
               "categories": [], "services": {}}
    text = build_llms(site, content, {}, PRODUCTS)
    assert BASE + PRODUCTS_URL in text
    assert "OI Oil, 135 ml — 1900 ฿" in text
    assert "цены 1200–1900 ฿" in text


def test_llms_stays_silent_without_goods():
    """Выжимка собирается и без витрины: раздел не должен появляться пустым."""
    content = {"llms_description": "Салон.", "home": {"seo_title": "Салон", "faq": []},
               "categories": [], "services": {}}
    site = {
        "brand_full": "Neva Beauty — Koh Samui", "base_url": BASE,
        "location": "о. Самуи, Таиланд", "hours": "Приём по записи",
        "booking_rule": "Отменить можно за сутки.",
        "contacts": {"whatsapp_url": "https://wa.me/1", "telegram_url": "https://t.me/x",
                     "instagram_url": "https://instagram.com/x"},
        "business": {"currency_sign": "฿", "telephone": "+79990289115",
                     "address": {"locality": "Koh Samui", "region": "Surat Thani"}},
    }
    assert "## Косметика на продажу" not in build_llms(site, content, {})
