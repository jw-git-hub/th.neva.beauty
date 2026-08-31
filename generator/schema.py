"""Сборка JSON-LD (schema.org) из данных site.yml.

Единый источник разметки бизнеса: один связный граф (@graph) с узлами
Organization + <тип бизнеса> + WebSite, к которому страницы добавляют свои узлы
(Service / FAQPage / BreadcrumbList). JSON собирается в Python, а не в шаблоне,
чтобы не ломаться об autoescape Jinja и оставаться валидным.
"""
import json
import re
from markupsafe import Markup

_TAG_RE = re.compile(r"<[^>]+>")


def _plain(text):
    """Чистый текст без HTML-тегов — для answer в JSON-LD (ссылки в разметке не нужны)."""
    return _TAG_RE.sub("", text)

ORG_ID = "#organization"
BUSINESS_ID = "#business"
WEBSITE_ID = "#website"
# Якоря узлов страницы. Адрес страницы + якорь даёт узлу глобальный идентификатор:
# без него из графа не следует, какой странице принадлежит конкретный Service,
# и связать услугу с её ценами и вопросами робот может только догадкой.
WEBPAGE_ID = "#webpage"
BREADCRUMB_ID = "#breadcrumb"
SERVICE_ID = "#service"
FAQ_ID = "#faq"
ITEMLIST_ID = "#services"


def _postal_address(addr):
    node = {
        "@type": "PostalAddress",
        "addressLocality": addr["locality"],
        "addressCountry": addr["country"],
    }
    if addr.get("region"):
        node["addressRegion"] = addr["region"]
    if addr.get("street"):
        node["streetAddress"] = addr["street"]
    if addr.get("postal_code"):
        node["postalCode"] = addr["postal_code"]
    return node


def _opening_hours(hours):
    return [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": spec["days"],
            "opens": spec["opens"],
            "closes": spec["closes"],
        }
        for spec in hours
    ]


def business_nodes(site):
    """Общие узлы бизнеса — одинаковы на всех страницах (entity consistency)."""
    base = site["base_url"]
    # Полная форма — сущность бизнеса для поиска и ИИ должна называться одинаково везде.
    brand = site.get("brand_full", site["brand"])
    b = site["business"]
    org_ref = {"@id": base + "/" + ORG_ID}

    organization = {
        "@type": "Organization",
        "@id": base + "/" + ORG_ID,
        "name": brand,
        "url": base + "/",
        "logo": base + b.get("logo", "/favicon.svg"),
    }
    if b.get("same_as"):
        organization["sameAs"] = b["same_as"]
    # knowsAbout — темы, в которых организация компетентна. Для поиска и ИИ это
    # ответ на вопрос «чем занимается этот бизнес», не требующий обхода всех
    # страниц. Список берётся из названий услуг сайта, поэтому выдумать тему,
    # которой в салоне нет, нельзя.
    if b.get("knows_about"):
        organization["knowsAbout"] = b["knows_about"]

    business = {
        "@type": b.get("type", "BeautySalon"),
        "@id": base + "/" + BUSINESS_ID,
        "name": brand,
        "url": base + "/",
        "image": base + b.get("image", "/assets/img/hero.jpg"),
        "telephone": b["telephone"],
        "address": _postal_address(b["address"]),
        "areaServed": {"@type": "City", "name": b["address"]["locality"]},
        "parentOrganization": org_ref,
    }
    if b.get("price_range"):
        business["priceRange"] = b["price_range"]
    if b.get("currency"):
        business["currenciesAccepted"] = b["currency"]
    if b.get("language"):
        # availableLanguage не входит в спецификацию BeautySalon — валидное место
        # для языков обслуживания это узел ContactPoint (иначе предупреждение валидатора).
        business["contactPoint"] = {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "telephone": b["telephone"],
            "availableLanguage": b["language"],
        }
    if b.get("same_as"):
        business["sameAs"] = b["same_as"]
    if b.get("geo"):
        business["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": b["geo"]["lat"],
            "longitude": b["geo"]["lng"],
        }
    if b.get("hours"):
        business["openingHoursSpecification"] = _opening_hours(b["hours"])

    website = {
        "@type": "WebSite",
        "@id": base + "/" + WEBSITE_ID,
        "url": base + "/",
        "name": brand,
        "inLanguage": b.get("language_code", "ru"),
        "publisher": org_ref,
    }
    return [organization, business, website]


def webpage_node(url, site_base, name, description, breadcrumb=False,
                 main_entity_id=None, image=None, language="ru", date_modified=None):
    """WebPage — сама страница как узел графа, к которому крепится всё остальное.

    Без неё Service, FAQPage и BreadcrumbList висят в графе без адреса: видно,
    что услуга принадлежит бизнесу, но не видно, на какой странице её искать.

    dateModified — та же дата, что уходит в sitemap. Косметология это YMYL-тема:
    поиск и ИИ спрашивают у такой страницы, когда её последний раз проверяли,
    и страница без даты для них молчит."""
    node = {
        "@type": "WebPage",
        "@id": url + WEBPAGE_ID,
        "url": url,
        "name": name,
        "description": _plain(description),
        "isPartOf": {"@id": site_base + "/" + WEBSITE_ID},
        "about": {"@id": site_base + "/" + BUSINESS_ID},
        "inLanguage": language,
    }
    if date_modified:
        node["dateModified"] = date_modified
    if image:
        node["primaryImageOfPage"] = image
    if breadcrumb:
        node["breadcrumb"] = {"@id": url + BREADCRUMB_ID}
    if main_entity_id:
        node["mainEntity"] = {"@id": main_entity_id}
    return node


def breadcrumb_node(items, page_url=None):
    """BreadcrumbList из [{name, url}, ...] — абсолютные URL, порядок = вложенность.

    Адрес звена дублируется в двух полях: `item` — обязательное для Google/schema.org,
    `url` — поле из документации Яндекса (валидно на ListItem как наследнике Thing).
    """
    return {
        "@type": "BreadcrumbList",
        **({"@id": page_url + BREADCRUMB_ID} if page_url else {}),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": item["name"],
                "item": item["url"],
                "url": item["url"],
            }
            for i, item in enumerate(items)
        ],
    }


def _list_item(position, item):
    """Звено списка: подпись, адрес и — если звено ведёт на услугу — ссылка на её узел.

    Название и адрес в двух полях — как в `breadcrumb_node`: голый URL заставляет
    робота идти на страницу, чтобы узнать, что это за услуга. Ключ `service`
    добавляет `@id` того самого узла Service, который описан на целевой странице:
    без него список раздела и услуга в графе остаются двумя разными сущностями
    с одинаковым адресом."""
    node = {
        "@type": "ListItem",
        "position": position,
        "name": item["name"],
        "item": item["url"],
        "url": item["url"],
    }
    if item.get("service"):
        node["item"] = {
            "@type": "Service",
            "@id": item["url"] + SERVICE_ID,
            "name": item["name"],
            "url": item["url"],
        }
    return node


def item_list_node(name, items, page_url=None):
    """ItemList из [{name, url, service?}, ...] — связывает страницу-список с целями."""
    return {
        "@type": "ItemList",
        **({"@id": page_url + ITEMLIST_ID} if page_url else {}),
        "name": name,
        "numberOfItems": len(items),
        "itemListElement": [_list_item(i + 1, item) for i, item in enumerate(items)],
    }


def faq_node(faq, page_url=None):
    """FAQPage из списка [{q, a}, ...] — только реальные вопросы-ответы."""
    return {
        "@type": "FAQPage",
        **({"@id": page_url + FAQ_ID, "url": page_url,
            "mainEntityOfPage": {"@id": page_url + WEBPAGE_ID}} if page_url else {}),
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": _plain(item["a"])},
            }
            for item in faq
        ],
    }


def _offer_node(item, currency, url):
    """Offer одной позиции прайса: цена + услуга, которую за неё оказывают.

    Фиксированная цена идёт в price, диапазон и «от» — в priceSpecification:
    выдавать нижнюю границу за точную цену значит обещать то, чего в прайсе нет."""
    offer = {"@type": "Offer", "url": url, "priceCurrency": currency,
             "availability": "https://schema.org/InStock"}
    price = item["offer"]
    if "price" in price:
        offer["price"] = price["price"]
    else:
        spec = {"@type": "PriceSpecification", "priceCurrency": currency,
                "minPrice": price["min"]}
        if "max" in price:
            spec["maxPrice"] = price["max"]
        offer["priceSpecification"] = spec
    service = {"@type": "Service", "name": item["name"]}
    if item["desc"]:
        service["description"] = _plain(item["desc"])
    offer["itemOffered"] = service
    return offer


def offer_catalog_node(service_name, catalog, currency, url):
    """OfferCatalog — прайс услуги в машиночитаемом виде: раздел → позиция → цена.

    Разделы прайса становятся вложенными каталогами, поэтому структура страницы
    читается роботом так же, как человеком в таблице."""
    return {
        "@type": "OfferCatalog",
        "name": f"{service_name} — цены",
        "itemListElement": [
            {
                "@type": "OfferCatalog",
                "name": section["section"],
                "itemListElement": [
                    _offer_node(item, currency, url) for item in section["items"]
                ],
            }
            for section in catalog
        ],
    }


def booking_channel_node(contacts, telephone, languages):
    """ServiceChannel — как записаться на услугу: мессенджер и телефон записи.

    Страница отвечает на это блоком записи, разметка до сих пор молчала: из графа
    было видно, что услуга есть и сколько стоит, но не по какому адресу на неё
    записываются."""
    return {
        "@type": "ServiceChannel",
        "name": "Запись в мессенджере",
        "serviceUrl": contacts["whatsapp_url"],
        "availableLanguage": languages,
        "servicePhone": {
            "@type": "ContactPoint",
            "contactType": "reservations",
            "telephone": telephone,
        },
    }


def service_node(name, description, provider_ref, area_name, aggregate_offer=None,
                 offer_catalog=None, page_url=None, image=None, channel=None):
    """Service — профильная услуга страницы. provider ссылается на узел бизнеса,
    areaServed — город. Если передан aggregate_offer {low, high, count, currency},
    добавляется AggregateOffer с диапазоном цен (числа считаются из прайса).
    offer_catalog — тот же прайс попозиционно, цена каждой услуги без догадок.
    image — кадр первого экрана, channel — канал записи (`booking_channel_node`)."""
    node = {
        "@type": "Service",
        **({"@id": page_url + SERVICE_ID, "url": page_url,
            "mainEntityOfPage": {"@id": page_url + WEBPAGE_ID}} if page_url else {}),
        "name": name,
        "description": _plain(description),
        "provider": provider_ref,
        "areaServed": {"@type": "City", "name": area_name},
    }
    if image:
        node["image"] = image
    if channel:
        node["availableChannel"] = channel
    if aggregate_offer:
        node["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": aggregate_offer["currency"],
            "lowPrice": aggregate_offer["low"],
            "highPrice": aggregate_offer["high"],
            "offerCount": aggregate_offer["count"],
        }
    if offer_catalog:
        node["hasOfferCatalog"] = offer_catalog
    return node


def render(site, extra_nodes=None):
    """Готовый безопасный JSON-LD для вставки в <script type=application/ld+json>."""
    graph = business_nodes(site)
    if extra_nodes:
        graph.extend(extra_nodes)
    doc = {"@context": "https://schema.org", "@graph": graph}
    return Markup(json.dumps(doc, ensure_ascii=False, indent=2))
