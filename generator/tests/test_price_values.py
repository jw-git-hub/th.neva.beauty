"""Разбор строки цены для AggregateOffer.

Цена на странице выводится дословно как на старом сайте, поэтому в прайсе
встречаются диапазоны, доплаты и тарифы за единицу времени. В диапазон цен
для schema.org должны попадать только самостоятельные цены.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import price_aggregate, price_values


def test_simple_price():
    assert price_values("3000 ฿") == [3000]


def test_price_without_space_before_symbol():
    assert price_values("500฿") == [500]


def test_thousands_separator_is_one_number():
    assert price_values("1 600 000 ฿") == [1600000]


def test_range_with_hyphen_gives_both_bounds():
    assert price_values("500-1000 ฿") == [500, 1000]


def test_range_with_space_before_hyphen():
    assert price_values("600 -1200 ฿") == [600, 1200]


def test_range_with_en_dash():
    assert price_values("300–500 ฿") == [300, 500]


def test_from_price_gives_lower_bound():
    assert price_values("от 2500 ฿") == [2500]


def test_surcharge_is_not_a_standalone_price():
    assert price_values("+500 ฿") == []


def test_per_minute_rate_is_not_a_standalone_price():
    assert price_values("35 ฿/минута") == []


def test_empty_price():
    assert price_values("") == []


def test_aggregate_uses_range_bounds_and_skips_modifiers():
    sections = [
        {
            "section": "Цены",
            "items": [
                {"name": "Живот", "desc": "", "price": "600 -1200 ฿"},
                {"name": "Доплата за густоту", "desc": "", "price": "+500 ฿"},
                {"name": "Массаж", "desc": "", "price": "35 ฿/минута"},
                {"name": "Чистка", "desc": "", "price": "3000 ฿"},
            ],
        }
    ]
    assert price_aggregate(sections, "THB") == {
        "low": 600,
        "high": 3000,
        "count": 2,
        "currency": "THB",
    }


def test_aggregate_returns_none_when_no_prices():
    assert price_aggregate([], "THB") is None
