"""Связность графа JSON-LD: чем узлы страницы держатся друг за друга.

Разметка полезна ровно настолько, насколько из неё видно, что чему принадлежит.
Здесь проверяется то, что легко потерять правкой шаблона и не увидеть глазами:
дата проверки страницы, кадр и канал записи у услуги, ссылка из списка раздела
на узел самой услуги и темы, в которых компетентен салон.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schema

BASE = "https://th.neva.beauty"
URL = BASE + "/smas-lifting/"

SITE = {
    "brand_full": "Neva Beauty — Koh Samui",
    "brand": "Neva Beauty",
    "base_url": BASE,
    "business": {
        "type": "BeautySalon",
        "telephone": "+79990289115",
        "language": ["Russian", "English"],
        "address": {"locality": "Koh Samui", "region": "Surat Thani", "country": "TH"},
    },
}

CONTACTS = {"whatsapp_url": "https://wa.me/79990289115"}


def node_of(graph, kind):
    return next(node for node in graph if node["@type"] == kind)


def test_webpage_carries_date_modified():
    node = schema.webpage_node(URL, BASE, "SMAS", "Описание", date_modified="2026-08-31")
    assert node["dateModified"] == "2026-08-31"


def test_webpage_without_date_has_no_empty_field():
    """Пустого dateModified быть не должно: дата либо настоящая, либо её нет."""
    assert "dateModified" not in schema.webpage_node(URL, BASE, "SMAS", "Описание")


def test_service_carries_image_and_booking_channel():
    channel = schema.booking_channel_node(CONTACTS, "+79990289115", ["Russian"])
    node = schema.service_node("SMAS-лифтинг", "Описание", {"@id": BASE + "/#business"},
                               "Koh Samui", page_url=URL,
                               image=BASE + "/assets/img/smas-lifting.webp",
                               channel=channel)
    assert node["image"].endswith("smas-lifting.webp")
    assert node["availableChannel"]["serviceUrl"] == CONTACTS["whatsapp_url"]
    assert node["availableChannel"]["servicePhone"]["telephone"] == "+79990289115"


def test_list_item_points_at_service_node_of_target_page():
    """Звено списка раздела ссылается на тот же @id, под которым услуга описана у себя."""
    items = [{"name": "SMAS-лифтинг", "url": URL, "service": True}]
    node = schema.item_list_node("Аппаратная косметология", items, BASE + "/apparatnaya/")
    item = node["itemListElement"][0]["item"]
    assert item["@id"] == URL + schema.SERVICE_ID
    assert node["numberOfItems"] == 1


def test_list_item_without_service_flag_stays_plain_url():
    """Раздел — не услуга: ссылаться на несуществующий узел Service нельзя."""
    node = schema.item_list_node("Направления", [{"name": "Волосы", "url": BASE + "/volosy/"}])
    assert node["itemListElement"][0]["item"] == BASE + "/volosy/"


def test_organization_knows_about_comes_from_services():
    site = {**SITE, "business": {**SITE["business"], "knows_about": ["SMAS-лифтинг"]}}
    assert node_of(schema.business_nodes(site), "Organization")["knowsAbout"] == ["SMAS-лифтинг"]


def test_organization_without_topics_has_no_knows_about():
    assert "knowsAbout" not in node_of(schema.business_nodes(SITE), "Organization")
