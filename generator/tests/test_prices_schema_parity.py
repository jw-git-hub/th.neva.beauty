"""Разметка цен против настоящего прайса — по всем 17 услугам сразу.

Цена в JSON-LD это обещание поиску и ИИ-ассистентам: по ней клиент ждёт, что
услугу можно купить именно за столько. Тест сверяет разметку с prices.json,
чтобы в диапазон и в каталог не попало то, что отдельно не продаётся —
доплата, расходник, тариф за единицу, бесплатная позиция.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import item_offer, offer_bounds, price_aggregate, service_offer_catalog

CURRENCY = "THB"
PRICES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "prices.json").read_text(encoding="utf-8")
)

# Услуги без цены процедуры в разметке. Ботулинотерапия продаётся по цене за
# единицу препарата (100–150 ฿/ед), процедура складывается из числа единиц.
# Заявить «ботулинотерапия от 100 ฿» значит назвать цену, которой не бывает,
# поэтому страница остаётся без ценовой разметки, а таблица цен на ней — со
# своим заголовком «Цена за 1 ед» — по-прежнему отвечает на вопрос человеку.
PRICE_ON_REQUEST = {"botulinoterapiya"}

PRICED_SERVICES = sorted(set(PRICES) - PRICE_ON_REQUEST)


def catalog_offers(slug):
    """Все Offer каталога услуги, без разбивки по разделам."""
    node = service_offer_catalog(slug, PRICES[slug], CURRENCY, f"https://th.neva.beauty/{slug}/")
    return [offer for section in node["itemListElement"]
            for offer in section["itemListElement"]]


def bounds_of(offer):
    if "price" in offer:
        return offer["price"], offer["price"]
    spec = offer["priceSpecification"]
    return spec["minPrice"], spec.get("maxPrice", spec["minPrice"])


def standalone_items(slug):
    return [item for section in PRICES[slug] for item in section["items"] if item_offer(item)]


def test_every_priced_service_has_a_catalog():
    for slug in PRICED_SERVICES:
        assert catalog_offers(slug), f"{slug}: пустой каталог предложений"


def test_services_without_price_markup_are_the_documented_ones():
    """Молчание о цене — осознанное решение по конкретной услуге, а не побочный
    эффект правки прайса."""
    silent = {slug for slug in PRICES
              if service_offer_catalog(slug, PRICES[slug], CURRENCY, "u") is None}
    assert silent == PRICE_ON_REQUEST


def test_catalog_covers_every_standalone_price():
    for slug in PRICED_SERVICES:
        assert len(catalog_offers(slug)) == len(standalone_items(slug)), (
            f"{slug}: позиций в каталоге не столько же, сколько цен в прайсе"
        )


def test_catalog_names_match_price_list():
    for slug in PRICED_SERVICES:
        names = [offer["itemOffered"]["name"] for offer in catalog_offers(slug)]
        assert names == [item["name"] for item in standalone_items(slug)], (
            f"{slug}: названия услуг в разметке разошлись с прайсом"
        )


def test_addons_and_rates_never_become_offers():
    """Доплата, расходник и тариф за единицу — не предложение."""
    for slug in PRICED_SERVICES:
        skipped = {item["name"] for section in PRICES[slug] for item in section["items"]
                   if not item_offer(item)}
        marked = {offer["itemOffered"]["name"] for offer in catalog_offers(slug)}
        assert not (skipped & marked), f"{slug}: в разметку попала несамостоятельная цена"


def test_aggregate_bounds_match_catalog():
    """lowPrice и highPrice — настоящие крайние цены услуги, а не цена доплаты."""
    for slug in PRICED_SERVICES:
        pairs = [bounds_of(offer) for offer in catalog_offers(slug)]
        aggregate = price_aggregate(PRICES[slug], CURRENCY)
        assert aggregate["low"] == min(low for low, _ in pairs), f"{slug}: неверный lowPrice"
        assert aggregate["high"] == max(high for _, high in pairs), f"{slug}: неверный highPrice"


def test_aggregate_count_matches_catalog():
    for slug in PRICED_SERVICES:
        assert price_aggregate(PRICES[slug], CURRENCY)["count"] == len(catalog_offers(slug)), (
            f"{slug}: offerCount не совпадает с числом предложений"
        )


def test_no_price_markup_at_all_for_price_on_request():
    for slug in PRICE_ON_REQUEST:
        assert price_aggregate(PRICES[slug], CURRENCY) is None, f"{slug}: остался диапазон цен"


def test_all_marked_prices_are_positive_numbers():
    for slug in PRICED_SERVICES:
        for offer in catalog_offers(slug):
            low, high = bounds_of(offer)
            assert isinstance(low, int) and low > 0, f"{slug}: цена не число"
            assert high >= low, f"{slug}: верхняя граница цены ниже нижней"


def test_markup_bounds_agree_with_parsed_price_string():
    """Разметка не выдумывает чисел: границы цены есть в самой строке прайса."""
    for slug in PRICED_SERVICES:
        for item, offer in zip(standalone_items(slug), catalog_offers(slug)):
            assert bounds_of(offer) == offer_bounds(item_offer(item)), (
                f"{slug}: {item['name']} — цена в разметке разошлась со строкой прайса"
            )


def test_currency_is_set_on_every_offer():
    for slug in PRICED_SERVICES:
        for offer in catalog_offers(slug):
            assert offer["priceCurrency"] == CURRENCY, f"{slug}: цена без валюты"
