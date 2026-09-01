"""Логика подачи цены: где сумма точная, а где она нижняя граница.

Заказчик 2026-09-01: «женская стрижка 2000, но по факту она зависит от длины,
значит фактически ОТ 2000». Правило: если в прайсе есть строка того же названия
дороже — в тексте и на карточке сумма называется через «от». И обратное: если
самая дорогая позиция прайса сама задана как «от … ฿», верхней границы у услуги
нет, и закрытый диапазон её выдумывает.
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import item_price_label, price_span, pricier_variant

NBSP = "\xa0"  # неразрывный пробел, как в build.py
PRICES = json.loads((Path(__file__).resolve().parent.parent / "data" / "prices.json")
                    .read_text(encoding="utf-8"))
HAIR = PRICES["uhod-za-volosami"]


def section(name, items):
    return [{"section": name, "items": items}]


def test_pricier_variant_found_for_hair_tier():
    assert pricier_variant(HAIR, "Женская") is True


def test_no_pricier_variant_for_flat_position():
    assert pricier_variant(HAIR, "Мужская") is False


def test_pricier_variant_ignores_cheaper_sibling():
    sections = section("Цены", [
        {"name": "Стрижка", "desc": "", "price": "2000 ฿"},
        {"name": "Стрижка - Короткие волосы", "desc": "", "price": "1500 ฿"},
    ])
    assert pricier_variant(sections, "Стрижка") is False


def test_pricier_variant_skips_addon_sibling():
    """Надбавка ценой услуги не является и границу «от» не задаёт."""
    sections = section("Цены", [
        {"name": "Укладка", "desc": "", "price": "1400 ฿"},
        {"name": "Укладка - Длинные / густые волосы", "desc": "", "price": "+300 ฿",
         "addon": True},
    ])
    assert pricier_variant(sections, "Укладка") is False


def test_item_label_gets_ot_when_tier_exists():
    label = item_price_label(PRICES, "uhod-za-volosami", "Балаяж, шатуш", "฿")
    assert label == f"от{NBSP}7000{NBSP}฿"


def test_item_label_stays_exact_without_tier():
    label = item_price_label(PRICES, "massazh", "Массаж тела", "฿")
    assert label == f"1500{NBSP}฿"


def test_item_label_does_not_double_ot():
    """Цена «от 3000 ฿» уже в прайсе — второе «от» приписывать нельзя."""
    label = item_price_label(PRICES, "tokio-inkarami", "Короткие волосы", "฿")
    assert label == f"от{NBSP}3000{NBSP}฿"


def test_span_collapses_to_ot_when_top_is_open_ended():
    assert price_span([PRICES["tokio-inkarami"]], "฿") == f"от{NBSP}3000{NBSP}฿"


def test_span_stays_a_range_when_top_is_exact():
    assert price_span([PRICES["biozavivka-volos"]], "฿") == f"4500–8000{NBSP}฿"


def test_span_ignores_open_ended_below_the_top():
    """«от 2500 ฿» у пилингов не отменяет потолок: дороже есть точная позиция."""
    assert price_span([PRICES["uhodovaya-kosmetologiya"]], "฿") == f"1000–5000{NBSP}฿"


# --- Правило для текстов, а не для кода ---------------------------------------
# Тесты выше держат подачу цены в генераторе. Этот держит сами тексты: сумму,
# у которой в прайсе есть строка дороже, нельзя называть точной. Иначе правило
# живёт только в памяти того, кто правит content.yml.

CONTENT = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "data" / "content.yml")
    .read_text(encoding="utf-8"))
TOKEN = re.compile(r"\{price:([a-z0-9-]+):([^}|]+)(?:\|([^}]+))?\}")
# «от 2000 ฿», «до 5500 ฿», «2300 ฿ вместо 2000 ฿» — во всех трёх формах читателю
# видно, что сумма не единственная.
HEDGED = re.compile(r"\b(?:от|до|вместо)\s*$")


def strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from strings(value, f"{path}[{i}]")


def test_texts_never_call_a_tiered_price_exact():
    unhedged = []
    for path, text in strings(CONTENT):
        for match in TOKEN.finditer(text):
            slug, name = match.group(1), match.group(2)
            if not pricier_variant(PRICES.get(slug, []), name):
                continue
            if HEDGED.search(text[:match.start()]):
                continue
            # Обе строки прайса названы рядом — читатель видит вилку целиком.
            if f"{{price:{slug}:{name} - " in text:
                continue
            unhedged.append(f"{path}: {slug}::{name}")
    assert not unhedged, "сумма названа точной, хотя в прайсе есть строка дороже: " + \
        "; ".join(unhedged)
