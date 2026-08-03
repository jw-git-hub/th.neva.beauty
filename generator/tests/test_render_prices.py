"""Подстановка цен в текст по плейсхолдеру {price:слаг:Позиция}.

Цифры в текстах не дублируются — их подставляет сборка из прайса. Молча
оставленный или неверно раскрытый плейсхолдер ушёл бы и в текст страницы,
и в JSON-LD, поэтому неизвестная и неоднозначная позиции роняют сборку.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import price_by_name, render_prices

PRICES = {
    "uhod-za-volosami": [
        {"section": "Стрижки", "items": [{"name": "Женская", "desc": "", "price": "2000 ฿"}]},
        {"section": "Уходы", "items": [{"name": "Tokio Inkarami", "desc": "", "price": "от 3000 ฿"}]},
    ],
    "igolchatyj-rf-lifting": [
        {"section": "Morpheus 8", "items": [{"name": "Лоб", "desc": "", "price": "7000 ฿"}]},
        {"section": "Scarlet S", "items": [{"name": "Лоб", "desc": "", "price": "5000 ฿"}]},
    ],
}


@pytest.fixture
def index():
    return price_by_name(PRICES)


def test_price_substituted_from_pricelist(index):
    text = render_prices("Стрижка — {price:uhod-za-volosami:Женская}.", index)
    assert text == "Стрижка — 2000 ฿."


def test_spaces_inside_price_are_non_breaking(index):
    """Иначе в потоке текста знак бата отрывается от числа переносом строки."""
    text = render_prices("{price:uhod-za-volosami:Tokio Inkarami}", index)
    assert text == "от 3000 ฿"


def test_unknown_position_fails_the_build(index):
    with pytest.raises(KeyError, match="Мужская"):
        render_prices("{price:uhod-za-volosami:Мужская}", index)


def test_ambiguous_position_fails_the_build(index):
    """Одно название в двух секциях прайса с разными ценами — выбрать нельзя."""
    with pytest.raises(KeyError, match="дважды"):
        render_prices("{price:igolchatyj-rf-lifting:Лоб}", index)


def test_text_without_placeholders_is_unchanged(index):
    assert render_prices("Цены в тайских батах.", index) == "Цены в тайских батах."
