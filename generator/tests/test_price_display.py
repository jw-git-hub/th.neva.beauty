"""Подача прайса: типографика цены и разбор названия позиции.

Цены и названия в prices.json лежат ровно как на старом сайте — это источник
истины. Здесь проверяется только слой показа: он не должен менять ни одной
цифры, иначе парити-тест с прайсом потеряет смысл.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import format_price, price_from, price_name_parts, price_view

NBSP = " "


def test_simple_price_unchanged():
    assert format_price("2500 ฿") == "2500 ฿"


def test_five_digit_price_gets_thousands_separator():
    assert format_price("20000 ฿") == f"20{NBSP}000 ฿"


def test_four_digit_price_stays_solid():
    assert format_price("9000 ฿") == "9000 ฿"


def test_range_with_space_before_hyphen_normalised():
    assert format_price("600 -1200 ฿") == "600–1200 ฿"


def test_range_without_spaces_normalised():
    assert format_price("500-1000 ฿") == "500–1000 ฿"


def test_range_with_en_dash_left_as_is():
    assert format_price("300–500 ฿") == "300–500 ฿"


def test_from_price_keeps_prefix():
    assert format_price("от 3000 ฿") == "от 3000 ฿"


def test_per_minute_rate_keeps_shape():
    assert format_price("35 ฿/минута") == "35 ฿/минута"


def test_plain_name_has_no_qualifier():
    assert price_name_parts("Верхняя губа") == {
        "name": "Верхняя губа", "note": "", "promo": False}


def test_tilda_suffix_becomes_qualifier():
    assert price_name_parts("Женская - Длинные / густые волосы") == {
        "name": "Женская", "note": "Длинные / густые волосы", "promo": False}


def test_promo_prefix_becomes_badge():
    assert price_name_parts("Акция - Фулфейс + зона шеи + декольте") == {
        "name": "Фулфейс + зона шеи + декольте", "note": "", "promo": True}


def test_hyphen_without_spaces_is_part_of_the_name():
    assert price_name_parts("РФ-лифтинг")["name"] == "РФ-лифтинг"


SECTIONS = [
    {"section": "Цены", "items": [
        {"name": "Тату - 3x5 см", "desc": "", "price": "2500 ฿"},
        {"name": "Курс", "desc": "10 процедур", "price": "15000 ฿"},
        {"name": "Одноразовая игла", "desc": "", "price": "+500 ฿", "addon": True},
    ]},
]


def test_view_splits_name_and_formats_price():
    view = price_view(SECTIONS)
    assert view[0]["items"][0] == {
        "name": "Тату", "note": "3x5 см", "promo": False, "desc": "", "price": "2500 ฿"}
    assert view[0]["items"][1]["price"] == f"15{NBSP}000 ฿"


def test_view_keeps_source_untouched():
    price_view(SECTIONS)
    assert SECTIONS[0]["items"][0]["name"] == "Тату - 3x5 см"


def test_price_from_takes_the_lowest_standalone_price():
    assert price_from(SECTIONS, "฿") == f"от 2500{NBSP}฿"


def test_price_from_is_none_without_standalone_prices():
    only_addons = [{"section": "Цены", "items": [
        {"name": "Доплата", "desc": "", "price": "+500 ฿"}]}]
    assert price_from(only_addons, "฿") is None
