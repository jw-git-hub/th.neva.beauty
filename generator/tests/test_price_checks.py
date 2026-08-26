"""Ворота цен: уровни 2–4 парити-теста.

Уровень 1 (таблица против прайса) стоял в CI с самого начала и через него
ошибки не проезжали. Проехало другое: Davines стоил 2500 ฿ на своей странице
и 1500 ฿ в прайсе раздела — противоречие внутри самого прайса, которое сверка
«таблица против prices.json» видеть не умеет по устройству. Здесь проверяется,
что три дописанных уровня ловят ровно такие ошибки, а не просто молчат.
"""
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_prices
from check_prices import (cross_page_conflicts, check_cards, check_prose,
                          price_numbers, prose_text)

NBSP = " "


@pytest.fixture(autouse=True)
def clear_problems():
    """Находки копятся в списке модуля — каждый тест начинает с пустого."""
    check_prices.problems.clear()
    yield
    check_prices.problems.clear()


# ── Разбор сумм ───────────────────────────────────────────────────────────────

def test_plain_price():
    assert price_numbers("2500 ฿") == [2500]


def test_grouped_thousands():
    assert price_numbers(f"10{NBSP}000{NBSP}฿") == [10000]


def test_range_gives_both_bounds():
    assert price_numbers(f"300–35{NBSP}000{NBSP}฿") == [300, 35000]


def test_spaced_dash_is_punctuation_not_a_range():
    """«Morpheus 8 — 15 000 ฿»: номер модели ценой не становится."""
    assert price_numbers(f"на Morpheus 8 — 15{NBSP}000{NBSP}฿") == [15000]


def test_surcharge_and_per_minute_are_prices_too():
    assert price_numbers("+500 ฿") == [500]
    assert price_numbers("35 ฿/минута") == [35]


def test_number_without_currency_ignored():
    assert price_numbers("курс 10 процедур, 2026 год") == []


# ── Уровень 2: суммы в прозе ──────────────────────────────────────────────────

def test_prose_price_from_catalogue_passes():
    check_prose("страница", "Процедура стоит 2500 ฿.", {2500})
    assert check_prices.problems == []


def test_invented_prose_price_caught():
    check_prose("страница", "Процедура стоит 2400 ฿.", {2500})
    assert len(check_prices.problems) == 1
    assert "2400" in check_prices.problems[0]


def test_prose_skips_the_pricelist_table():
    """Таблицу сверяет уровень 1 — второй раз её читать незачем."""
    soup = BeautifulSoup(
        '<p>от 2500 ฿</p><table class="pricelist"><tr><td>9999 ฿</td></tr></table>',
        "html.parser")
    assert price_numbers(prose_text(soup)) == [2500]


# ── Уровень 3: карточки «от … ฿» ──────────────────────────────────────────────

CARD_HTML = ('<a class="related-card" href="/tokio-inkarami/">'
             '<span class="related-card__price">{shown}</span></a>')
CARD_PRICES = {"tokio-inkarami": [{"section": "Цены", "items": [
    {"name": "Короткие волосы", "desc": "", "price": "от 3000 ฿"},
    {"name": "Длинные волосы", "desc": "", "price": "от 6000 ฿"},
]}]}


@pytest.fixture
def card_prices(monkeypatch):
    monkeypatch.setattr(check_prices, "PRICES", CARD_PRICES)


def test_card_matching_minimum_passes(card_prices):
    check_cards("раздел", BeautifulSoup(CARD_HTML.format(shown=f"от 3000{NBSP}฿"),
                                        "html.parser"))
    assert check_prices.problems == []


def test_card_with_stale_price_caught(card_prices):
    check_cards("раздел", BeautifulSoup(CARD_HTML.format(shown=f"от 2500{NBSP}฿"),
                                        "html.parser"))
    assert len(check_prices.problems) == 1
    assert "tokio-inkarami" in check_prices.problems[0]


def test_card_showing_maximum_instead_of_minimum_caught(card_prices):
    check_cards("раздел", BeautifulSoup(CARD_HTML.format(shown=f"от 6000{NBSP}฿"),
                                        "html.parser"))
    assert len(check_prices.problems) == 1


# ── Уровень 4: противоречия между страницами ──────────────────────────────────

def items(*rows):
    return [(slug, "Цены", {"name": name, "desc": "", "price": price})
            for slug, name, price in rows]


def test_same_price_on_both_pages_passes():
    rows = items(("davines-naturaltech-tailoring", "Любая длина", "1500 ฿"),
                 ("uhod-za-volosami", "Davines Naturaltech Tailoring", "1500 ฿"))
    assert cross_page_conflicts("davines-naturaltech-tailoring",
                                "Davines Naturaltech Tailoring", rows) == []


def test_two_prices_for_one_service_caught():
    """Ровно та ошибка, которую пропустили в задаче 91."""
    rows = items(("davines-naturaltech-tailoring", "Любая длина", "2500 ฿"),
                 ("uhod-za-volosami", "Davines Naturaltech Tailoring", "1500 ฿"))
    conflicts = cross_page_conflicts("davines-naturaltech-tailoring",
                                     "Davines Naturaltech Tailoring", rows)
    assert [item["price"] for _, _, item in conflicts] == ["1500 ฿"]


def test_variant_rows_match_any_of_own_prices():
    """«Tokio Inkarami - Короткие волосы» — вариант услуги, а не другая цена."""
    rows = items(("tokio-inkarami", "Короткие волосы", "от 3000 ฿"),
                 ("tokio-inkarami", "Длинные волосы", "от 6000 ฿"),
                 ("uhod-za-volosami", "Tokio Inkarami - Короткие волосы", "от 3000 ฿"),
                 ("uhod-za-volosami", "Tokio Inkarami - Длинные волосы", "от 6000 ฿"))
    assert cross_page_conflicts("tokio-inkarami", "Tokio Inkarami", rows) == []


def test_own_page_rows_never_conflict_with_themselves():
    rows = items(("smas-lifting", "SMAS-лифтинг лица", "15 000 ฿"),
                 ("smas-lifting", "SMAS-лифтинг шеи", "9000 ฿"))
    assert cross_page_conflicts("smas-lifting", "SMAS-лифтинг", rows) == []
