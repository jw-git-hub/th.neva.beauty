"""Каталог предложений (hasOfferCatalog) — цена каждой позиции прайса машине.

AggregateOffer сообщает только диапазон «от и до»: какая услуга сколько стоит,
робот достраивает разбором таблицы. OfferCatalog связывает название и цену
однозначно. В каталог попадают только те позиции, которые клиент может купить
отдельно: доплата к другой процедуре и тариф за единицу времени предложением
не являются.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schema
from build import (item_offer, price_aggregate, price_catalog, price_offer,
                   service_offer_catalog)

URL = "https://th.neva.beauty/lazernaya-epilyaciya/"


def test_fixed_price_offer():
    assert price_offer("3000 ฿") == {"price": 3000}


def test_range_price_offer_keeps_both_bounds():
    assert price_offer("600 -1200 ฿") == {"min": 600, "max": 1200}


def test_from_price_offer_has_only_lower_bound():
    assert price_offer("от 2500 ฿") == {"min": 2500}


def test_surcharge_is_not_an_offer():
    assert price_offer("+500 ฿") is None


def test_per_unit_rate_is_not_an_offer():
    assert price_offer("35 ฿/минута") is None


def test_empty_price_is_not_an_offer():
    assert price_offer("") is None


def test_catalog_keeps_sections_and_skips_non_offers():
    sections = [
        {
            "section": "Цены",
            "items": [
                {"name": "Верхняя губа", "desc": "", "price": "500 ฿"},
                {"name": "Доплата за густоту", "desc": "", "price": "+500 ฿"},
            ],
        },
        {
            "section": "Только доплаты",
            "items": [
                {"name": "RF-терапия", "desc": "", "price": "+350 ฿"},
            ],
        },
    ]
    assert price_catalog(sections) == [
        {
            "section": "Цены",
            "items": [{"name": "Верхняя губа", "desc": "", "offer": {"price": 500}}],
        }
    ]


def test_catalog_is_empty_without_prices():
    assert price_catalog([]) == []


def test_item_marked_as_addon_is_not_an_offer():
    """Не всякая надбавка видна по строке цены: «Одноразовая игла — 100 ฿»
    выглядит обычной ценой, но отдельно от процедуры не продаётся. Такие позиции
    помечены в прайсе флагом addon."""
    item = {"name": "Одноразовая игла", "desc": "", "price": "100 ฿", "addon": True}
    assert item_offer(item) is None


def test_ordinary_item_is_an_offer():
    assert item_offer({"name": "До 5 волос", "desc": "", "price": "300 ฿"}) == {"price": 300}


def test_catalog_drops_addon_items():
    sections = [{"section": "Цены", "items": [
        {"name": "Одноразовая игла", "desc": "", "price": "100 ฿", "addon": True},
        {"name": "До 5 волос", "desc": "", "price": "300 ฿"},
    ]}]
    assert [item["name"] for item in price_catalog(sections)[0]["items"]] == ["До 5 волос"]


def test_aggregate_range_ignores_addon_items():
    """Главное следствие: страница не заявляет поиску цену, по которой
    услугу купить нельзя."""
    sections = [{"section": "Цены", "items": [
        {"name": "Одноразовая игла", "desc": "", "price": "100 ฿", "addon": True},
        {"name": "До 5 волос", "desc": "", "price": "300 ฿"},
        {"name": "До 20 волос", "desc": "", "price": "700 ฿"},
    ]}]
    assert price_aggregate(sections, "THB") == {
        "low": 300, "high": 700, "count": 2, "currency": "THB"}


def test_service_of_only_addons_has_no_catalog():
    sections = [{"section": "Цена за 1 ед", "items": [
        {"name": "Диспорт (1:3)", "desc": "", "price": "100 ฿", "addon": True},
    ]}]
    assert service_offer_catalog("Ботулинотерапия", sections, "THB", URL) is None
    assert price_aggregate(sections, "THB") is None


def _first_offer(node):
    return node["itemListElement"][0]["itemListElement"][0]


def _catalog(items):
    return [{"section": "Цены", "items": items}]


def test_catalog_node_names_service_and_section():
    node = schema.offer_catalog_node(
        "Лазерная эпиляция",
        _catalog([{"name": "Верхняя губа", "desc": "", "offer": {"price": 500}}]),
        "THB", URL)
    assert node["@type"] == "OfferCatalog"
    assert node["name"] == "Лазерная эпиляция — цены"
    assert node["itemListElement"][0]["@type"] == "OfferCatalog"
    assert node["itemListElement"][0]["name"] == "Цены"


def test_offer_carries_name_currency_and_page_url():
    offer = _first_offer(schema.offer_catalog_node(
        "Лазерная эпиляция",
        _catalog([{"name": "Верхняя губа", "desc": "", "offer": {"price": 500}}]),
        "THB", URL))
    assert offer["@type"] == "Offer"
    assert offer["price"] == 500
    assert offer["priceCurrency"] == "THB"
    assert offer["url"] == URL
    assert offer["itemOffered"] == {"@type": "Service", "name": "Верхняя губа"}


def test_offer_description_comes_from_price_row():
    offer = _first_offer(schema.offer_catalog_node(
        "Уход за волосами",
        _catalog([{"name": "Тотал блонд", "desc": "Не более 2 см корней.",
                   "offer": {"price": 6500}}]),
        "THB", URL))
    assert offer["itemOffered"]["description"] == "Не более 2 см корней."


def test_range_offer_uses_price_specification():
    offer = _first_offer(schema.offer_catalog_node(
        "Сахарная эпиляция",
        _catalog([{"name": "Живот", "desc": "", "offer": {"min": 600, "max": 1200}}]),
        "THB", URL))
    assert "price" not in offer
    assert offer["priceSpecification"] == {
        "@type": "PriceSpecification",
        "priceCurrency": "THB",
        "minPrice": 600,
        "maxPrice": 1200,
    }


def test_from_price_offer_has_no_upper_bound():
    offer = _first_offer(schema.offer_catalog_node(
        "Массаж",
        _catalog([{"name": "Программа", "desc": "", "offer": {"min": 2500}}]),
        "THB", URL))
    assert offer["priceSpecification"] == {
        "@type": "PriceSpecification",
        "priceCurrency": "THB",
        "minPrice": 2500,
    }


def test_service_catalog_is_built_from_price_sections():
    sections = [{"section": "Цены", "items": [
        {"name": "Верхняя губа", "desc": "", "price": "500 ฿"},
        {"name": "Доплата за густоту", "desc": "", "price": "+500 ฿"},
    ]}]
    node = service_offer_catalog("Лазерная эпиляция", sections, "THB", URL)
    assert node["name"] == "Лазерная эпиляция — цены"
    assert len(node["itemListElement"][0]["itemListElement"]) == 1
    assert _first_offer(node)["price"] == 500


def test_service_without_priced_items_has_no_catalog():
    sections = [{"section": "Цены", "items": [
        {"name": "Обработка после сеанса", "desc": "", "price": "бесплатно"},
    ]}]
    assert service_offer_catalog("Электроэпиляция", sections, "THB", URL) is None


def test_service_node_gets_catalog():
    node = schema.service_node(
        "Лазерная эпиляция", "Описание", {"@id": "#business"}, "Koh Samui",
        offer_catalog={"@type": "OfferCatalog", "name": "Лазерная эпиляция — цены"})
    assert node["hasOfferCatalog"]["name"] == "Лазерная эпиляция — цены"


def test_service_node_without_catalog_has_no_field():
    node = schema.service_node("Массаж", "Описание", {"@id": "#business"}, "Koh Samui")
    assert "hasOfferCatalog" not in node
