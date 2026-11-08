"""Метки ссылок связи для статистики.

Владелец видит в Яндекс.Метрике, с какой страницы и какой кнопкой гость пошёл
в мессенджер: каждая ссылка связи помечена каналом (data-contact) и местом кнопки
(data-place), а обработчик в partials/metrika.html.j2 читает эти метки при клике
и отправляет цель contact. Адреса и текст обращения здесь не собираются — в шаблонах
и в content.yml они остаются как были; модуль отвечает только за метки.
Ссылка без метки в Метрике не видна: check_content.py ловит такую в готовых страницах.
"""
from markupsafe import Markup, escape

CHANNELS = ("whatsapp", "telegram", "instagram")
PLACES = ("header", "hero", "strip", "booking", "inline", "drawer", "footer",
          "faq", "text", "product", "privacy")


def _check(channel, place):
    if channel not in CHANNELS:
        raise ValueError(f"Неизвестный канал связи {channel!r}, ожидался один из {CHANNELS}")
    if place not in PLACES:
        raise ValueError(f"Неизвестное место кнопки {place!r}, ожидалось одно из {PLACES}")


def _attrs(channel, place):
    return f'data-contact="{channel}" data-place="{place}"'


def tracking_attrs(channel, place):
    """Метки ссылки связи для шаблона: канал и место кнопки."""
    _check(channel, place)
    return Markup(_attrs(channel, place))


def fill_contact_links(html, contacts, place):
    """Ссылки на мессенджеры в HTML из yml: href="{whatsapp}" получает адрес
    и метки. Плейсхолдер вне href не трогается."""
    for channel in CHANNELS:
        _check(channel, place)
        url = escape(contacts[f"{channel}_url"])
        html = html.replace(f'href="{{{channel}}}"',
                            f'href="{url}" {_attrs(channel, place)}')
    return html
