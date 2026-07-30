"""Состав prices.json против старого сайта.

Цены и перечень услуг переносятся со старого сайта без изменений. Тест фиксирует
число позиций по каждой услуге: если извлечение потеряет или задвоит позицию,
тест упадёт. Числа взяты подсчётом позиций прайса на страницах Tilda-выгрузки.
"""
import json
from pathlib import Path

PRICES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "prices.json").read_text(encoding="utf-8")
)

EXPECTED_ITEMS = {
    "lazernaya-epilyaciya": 32,
    "elektroepilyaciya": 6,
    "saharnaya-epilyaciya": 18,
    "uhod-za-volosami": 40,
    "tokio-inkarami": 3,
    "biozavivka-volos": 4,
    "keratinovoe-vypryamlenie-volos": 7,
    "davines-naturaltech-tailoring": 1,
    "permanentnyj-makiyazh": 11,
    "igolchatyj-rf-lifting": 33,
    "smas-lifting": 7,
    "udalenie-tatuirovok-lazerom": 10,
    "fotoomolozhenie-m22": 5,
    "uhodovaya-kosmetologiya": 14,
    "botulinoterapiya": 5,
    "endosfera-terapiya": 4,
    "massazh": 4,
}

TOTAL_ITEMS = 204

# Позиции без денежной цены. На старом сайте такая одна — бесплатная обработка
# после электроэпиляции. Она остаётся в прайсе: бесплатная услуга это выгода
# клиента, терять её при переносе нельзя.
FREE_PRICES = {"бесплатно"}


def item_count(slug):
    return sum(len(section["items"]) for section in PRICES[slug])


def test_all_services_present():
    assert set(PRICES) == set(EXPECTED_ITEMS)


def test_item_count_per_service():
    actual = {slug: item_count(slug) for slug in EXPECTED_ITEMS}
    assert actual == EXPECTED_ITEMS


def test_total_item_count():
    assert sum(item_count(slug) for slug in PRICES) == TOTAL_ITEMS


def test_every_item_has_name_and_price():
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                assert item["name"].strip(), f"{slug}: позиция без названия"
                assert item["price"].strip(), f"{slug}: {item['name']} без цены"


def test_prices_are_in_baht():
    """Все денежные цены — в батах. Исключение — позиции без денежной цены
    («бесплатно»): они есть на старом сайте и переносятся дословно."""
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                if item["price"] in FREE_PRICES:
                    continue
                assert "฿" in item["price"], f"{slug}: {item['name']} — цена не в батах"


def test_price_symbol_spacing_is_normalised():
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                assert "  ฿" not in item["price"], f"{slug}: {item['name']} — двойной отступ"
                assert not item["price"].replace(" ฿", "").endswith("฿"), (
                    f"{slug}: {item['name']} — нет отступа перед ฿"
                )
