import hashlib, json, re, urllib.parse, yaml, rcssmin
from datetime import date
from pathlib import Path
from markupsafe import Markup
from jinja2 import Environment, FileSystemLoader, select_autoescape
import images, schema

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "th.neva.beauty"
SOURCES = ROOT / "sources"
ICONS = SOURCES / "icons"

RELATED_COUNT = 3  # сколько карточек «Смотрите также» показываем на странице услуги

# Цвет фона бренда (токен --bg). Один и тот же для meta theme-color и для манифеста:
# браузер красит им адресную строку и заставку, и оба должны совпадать с реальным
# фоном страницы, иначе при запуске видна цветная вспышка.
THEME_COLOR = "#FBF4F0"

# Порядок каскада для единого bundle.min.css. Все CSS сайта склеиваются в один
# минифицированный файл → один render-blocking запрос вместо шести, общий кэш на
# весь сайт. fonts первым (@font-face), затем токены/база, затем постраничные слои.
CSS_BUNDLE_ORDER = ["fonts", "tokens", "base", "components",
                    "aurora", "reveal", "home", "service", "legal"]

def icon(name, cls="icon"):
    svg = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    # Strip license comment, collapse multiline <svg ...> tag, replace class attribute
    svg = re.sub(r'<!--.*?-->\s*', '', svg, flags=re.DOTALL)
    svg = re.sub(r'<svg\s+', '<svg ', svg, count=1)
    svg = re.sub(r'<svg ([^>]*?)class="[^"]*"', f'<svg class="{cls}"', svg, count=1)
    return Markup(svg)

def social_handle(profile_url):
    """@имя из ссылки на профиль: подпись всегда совпадает с самой ссылкой."""
    return "@" + profile_url.rstrip("/").rsplit("/", 1)[-1]

def load():
    site = yaml.safe_load((ROOT/"data/site.yml").read_text(encoding="utf-8"))
    content = yaml.safe_load((ROOT/"data/content.yml").read_text(encoding="utf-8"))
    prices = json.loads((ROOT/"data/prices.json").read_text(encoding="utf-8"))
    return site, content, prices

def env():
    e = Environment(loader=FileSystemLoader(ROOT/"templates"),
                    autoescape=select_autoescape(["html","j2"]))
    e.filters["urlencode"] = lambda s: urllib.parse.quote(str(s))
    e.filters["handle"] = social_handle
    e.filters["price"] = format_price
    e.tests["match"] = lambda s, pat: re.match(pat, s) is not None
    e.globals["icon"] = icon
    e.globals["theme_color"] = THEME_COLOR
    # Заглушки даты изменения: настоящую дату подставляет write_page уже в готовый
    # HTML — иначе подстановка даты сама делала бы страницу изменённой (см. ниже).
    e.globals["lastmod_placeholder"] = LASTMOD_PLACEHOLDER
    e.globals["lastmod_human_placeholder"] = LASTMOD_HUMAN_PLACEHOLDER
    return e

def write(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("→", path.relative_to(OUT.parent))

def build_css_bundle():
    """Склеивает CSS-слои в порядке каскада и минифицирует в единый bundle.min.css.
    Один render-blocking запрос вместо шести; относительные url() внутри (../fonts,
    ../img) работают и на превью по подпути, и на боевом домене.

    Слои-исходники лежат в `sources/css/` и в публикуемую папку не копируются:
    страницы ссылаются только на бандл, отдельные файлы никто не запрашивает."""
    parts = [f.read_text(encoding="utf-8")
             for name in CSS_BUNDLE_ORDER
             if (f := SOURCES / "css" / f"{name}.css").exists()]
    bundle = rcssmin.cssmin("\n".join(parts))
    out = OUT / "assets" / "css" / "bundle.min.css"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle, encoding="utf-8")
    print("→", out.relative_to(OUT.parent), f"({len(bundle) // 1024} KB minified)")

def asset_url(base_path, path):
    """Ссылка на ассет с отпечатком содержимого: `?v=1a2b3c4d`.

    Имена файлов постоянные, поэтому без отпечатка вернувшийся посетитель после
    деплоя получает из кэша старый CSS или JS. Отпечаток меняется вместе с файлом
    и заставляет браузер скачать новую версию."""
    digest = hashlib.sha1((OUT / path.lstrip("/")).read_bytes()).hexdigest()[:8]
    return f"{base_path}{path}?v={digest}"


def og_image_path(slug):
    """Превью страницы для мессенджеров: `og-<slug>.jpg`, иначе общая обложка.

    Ссылку на услугу чаще всего пересылают в WhatsApp, и карточка должна
    показывать именно эту процедуру, а не общий кадр салона."""
    path = f"/assets/img/og-{slug}.jpg"
    return path if (OUT / path.lstrip("/")).exists() else None


def og_title(entry, site):
    """Заголовок карточки ссылки в мессенджере — из h1, а не из title.

    Это разные задачи: title пишется под выдачу и несёт поисковый запрос,
    а карточку в WhatsApp читает человек, которому ссылку прислали. Заголовок
    страницы для него понятнее строки с перечислением ключей."""
    heading = entry.get("h1") or entry["title"]
    return f"{heading} — {site['brand']}"


def enrich_categories(content):
    """Обогащает категории (url, is_page) и переопределяет svc.category — единая таксономия."""
    categories = content["categories"]
    category_title_by_slug = {}
    for cat in categories:
        cat["is_page"] = len(cat["services"]) > 1
        cat["url"] = f"/{cat['slug']}/" if cat["is_page"] else f"/{cat['services'][0]}/"
        for svc_slug in cat["services"]:
            category_title_by_slug[svc_slug] = cat["title"]
    for slug, svc in content["services"].items():
        svc["category"] = category_title_by_slug[slug]

def fill_related(content):
    """Гарантирует ровно RELATED_COUNT связанных услуг: кураторский список,
    затем соседи по категории, затем прочие услуги — чтобы блок «Смотрите также»
    никогда не был короче остальных страниц."""
    services = content["services"]
    siblings_by_slug = {
        slug: [s for s in cat["services"] if s != slug]
        for cat in content["categories"] for slug in cat["services"]
    }
    for slug, svc in services.items():
        related = [r for r in dict.fromkeys(svc.get("related", [])) if r != slug and r in services]
        for pool in (siblings_by_slug.get(slug, []), services):
            for candidate in pool:
                if len(related) >= RELATED_COUNT:
                    break
                if candidate != slug and candidate not in related:
                    related.append(candidate)
        svc["related"] = related[:RELATED_COUNT]

# Цена позиции прайса прямо в тексте: {price:слаг-услуги:Точное название позиции}.
# Цифры в content.yml не дублируются — их подставляет сборка из prices.json,
# поэтому текст не может разойтись с прайсом.
# Позицию с неуникальным названием уточняют секцией прайса или подписью строки
# после «|»: {price:biozavivka-volos:Длинные волосы со стрижкой|До поясницы}.
# Разделитель не двоеточие: в названиях позиций оно встречается — «Диспорт (1:3)».
_PRICE_TOKEN_RE = re.compile(r"\{price:([a-z0-9-]+):([^}|]+)(?:\|([^}]+))?\}")


AMBIGUOUS_PRICE = None  # название позиции встречается у услуги дважды — цену не выбрать


def price_by_name(prices):
    """Указатель «слаг услуги + название позиции → цена строкой» по всему прайсу.

    Одно название в двух секциях прайса (зоны РФ-лифтинга у Morpheus 8 и Scarlet S,
    чистка спины для женщин и мужчин) — цены разные, и выбрать за автора текста
    нельзя. Такой ключ помечается и роняет сборку при обращении к нему, а адресовать
    строку можно уточнённым ключом «название + секция» или «название + подпись»."""
    index = {}
    for slug, sections in prices.items():
        for section in sections:
            for item in section["items"]:
                keys = [(slug, item["name"])]
                for qualifier in (section["section"], item["desc"]):
                    if qualifier:
                        keys.append((slug, item["name"], qualifier))
                # Та же типографика, что в таблице: иначе одна сумма выглядит
                # «30 000 ฿» в прайсе и «30000 ฿» в тексте на той же странице.
                price = format_price(item["price"])
                for key in keys:
                    index[key] = AMBIGUOUS_PRICE if key in index else price
    return index


def render_prices(text, index):
    """Подставляет цены вместо {price:...}.

    Неизвестная или неоднозначная позиция роняет сборку: молча оставленный
    плейсхолдер ушёл бы и в текст страницы, и в JSON-LD, а молча выбранная
    цена разошлась бы с прайсом."""
    def replace(match):
        slug, name, qualifier = match.group(1), match.group(2), match.group(3)
        key = (slug, name, qualifier) if qualifier else (slug, name)
        label = f"{name}|{qualifier}" if qualifier else name
        if key not in index:
            raise KeyError(f"нет позиции прайса {label!r} у услуги {slug!r}")
        if index[key] is AMBIGUOUS_PRICE:
            raise KeyError(f"позиция прайса {label!r} у услуги {slug!r} встречается "
                           "дважды с разными ценами — уточните строку секцией прайса "
                           "или подписью: {price:слаг:Название|Уточнение}")
        # Пробелы внутри цены — неразрывные: в потоке текста «2000 ฿» иначе
        # разрывается переносом строки и знак бата уезжает на следующую строку.
        return index[key].replace(" ", " ")
    return _PRICE_TOKEN_RE.sub(replace, text)


def render_page_prices(entry, index):
    """Подставляет цены в тексты страницы — лид первого экрана и описание для поиска.

    Оба уходят дальше по сборке: лид — в описание Service, описание — в сниппет
    и Open Graph. Цены подставляются здесь, до сборки графа, чтобы во всех трёх
    местах стояла одна цифра из прайса."""
    for field in ("intro", "seo_desc"):
        entry[field] = render_prices(entry[field], index)


def render_rich_text(text, contacts, base_path="", prices_index=None):
    """Финализирует HTML-текст страницы: подставляет URL мессенджеров вместо
    плейсхолдеров {whatsapp}/{telegram}/{instagram} (единый источник — site.yml),
    цены из прайса вместо {price:...} и префиксует внутренние ссылки href="/..."
    на base_path — чтобы они работали и на превью по подпути."""
    tokens = {
        "{whatsapp}": contacts["whatsapp_url"],
        "{telegram}": contacts["telegram_url"],
        "{instagram}": contacts["instagram_url"],
    }
    for token, url in tokens.items():
        text = text.replace(token, url)
    if prices_index:
        text = render_prices(text, prices_index)
    if base_path:
        text = text.replace('href="/', f'href="{base_path}/')
    return text


def render_faq_contacts(faq, contacts, base_path="", prices_index=None):
    """Ответы FAQ, готовые к выводу: те же подстановки, что и в остальном тексте."""
    return [{"q": item["q"],
             "a": render_rich_text(item["a"], contacts, base_path, prices_index)}
            for item in faq]


# Число цены: первая цифра и дальше цифры с разделителями разрядов (обычный
# и неразрывный пробел). «1 600 000» — одно число, «600 -1200» — два.
_PRICE_NUMBER_RE = re.compile(r"\d[\d\s ]*")


# --- подача прайса ---------------------------------------------------------
# Цены и названия хранятся в prices.json ровно как на старом сайте — это
# источник истины и предмет парити-теста. Всё ниже меняет только подачу
# на странице: типографику и разбор названия. Значения не трогаются.

# Диапазон в выгрузке записан тремя способами: «600 -1200», «500-1000»,
# «300–500». Для клиента это одна форма, и выглядеть она должна одинаково.
_PRICE_RANGE_RE = re.compile(r"(\d)\s*[-–—]\s*(\d)")
_DIGIT_GROUP_RE = re.compile(r"\d+")
# С какой разрядности сумма получает разделитель: четырёхзначные в русской
# типографике пишут слитно, у пятизначных без пробела теряется порядок.
GROUPED_FROM_DIGITS = 5
NBSP = " "


def _group_digits(match):
    digits = match.group(0)
    if len(digits) < GROUPED_FROM_DIGITS:
        return digits
    return f"{int(digits):,}".replace(",", NBSP)


def format_price(price):
    """Цена в единой типографике: одно тире в диапазоне, разряды у крупных сумм.

    «600 -1200 ฿» и «500-1000 ฿» приходят к «600–1200 ฿», «20000 ฿» —
    к «20 000 ฿». Числа не меняются, парити-тест сверяет с этим же видом."""
    return _DIGIT_GROUP_RE.sub(_group_digits, _PRICE_RANGE_RE.sub(r"\1–\2", price.strip()))


NAME_QUALIFIER_SEP = " - "
PROMO_PREFIX = "Акция"


def price_name_parts(name):
    """Название позиции как «услуга + уточнение цены».

    В выгрузке Tilda модификатор приклеен к названию дефисом: «Женская -
    Длинные / густые волосы», «Тату - 3x5 см». Это не разные услуги, а варианты
    одной, и читаться они должны строкой меню, а не строкой базы. Отдельный
    случай — префикс «Акция»: там уточнением идёт сама услуга, а слово
    «Акция» работает меткой."""
    head, sep, tail = name.partition(NAME_QUALIFIER_SEP)
    if not sep:
        return {"name": name, "note": "", "promo": False}
    if head == PROMO_PREFIX:
        return {"name": tail, "note": "", "promo": True}
    return {"name": head, "note": tail, "promo": False}


def price_view(sections):
    """Разделы прайса в виде для показа — исходные данные не меняются.

    Флаг combo несут разделы из сетов — «Подмышки + глубокое бикини». Строкой
    прайса такой набор не читается: клиенту важно, что это отдельное
    предложение, а не ещё одна зона. Шаблон показывает их карточками, как на
    vn.neva.beauty."""
    return [{
        "section": sec["section"],
        "combo": bool(sec.get("combo")),
        "items": [dict(price_name_parts(item["name"]),
                       desc=item["desc"], price=format_price(item["price"]))
                  for item in sec["items"]],
    } for sec in sections]


def price_values(price):
    """Самостоятельные цены из строки прайса, числами.

    Цена выводится на странице дословно, поэтому в прайсе встречаются формы
    «600 -1200 ฿», «от 2500 ฿», «+500 ฿», «35 ฿/минута». В диапазон для
    AggregateOffer идут только самостоятельные цены: доплата к другой процедуре
    и тариф за единицу времени ценой услуги не являются."""
    text = price.strip()
    if not text or text.startswith("+") or "/" in text:
        return []
    return [int(re.sub(r"\D", "", m)) for m in _PRICE_NUMBER_RE.findall(text)]


def price_offer(price):
    """Цена одной позиции прайса как предложение, или None, если она им не является.

    {"price": n} — фиксированная цена, {"min": a, "max": b} — диапазон,
    {"min": a} — форма «от 2500 ฿». Отсев тот же, что у price_values():
    доплату и тариф за минуту отдельно купить нельзя, предложением они не будут."""
    values = price_values(price)
    if not values:
        return None
    if len(values) > 1:
        return {"min": values[0], "max": values[-1]}
    if price.strip().lower().startswith("от"):
        return {"min": values[0]}
    return {"price": values[0]}


def item_offer(item):
    """Позиция прайса как предложение, или None, если купить её отдельно нельзя.

    Часть надбавок видна по строке цены («+500 ฿», «35 ฿/минута»), часть — нет:
    «Одноразовая игла — 100 ฿» или «Доплата за густоту — 500-1000 ฿» выглядят
    обычной ценой. Такие позиции помечены в прайсе флагом addon вручную."""
    if item.get("addon"):
        return None
    return price_offer(item["price"])


def price_catalog(sections):
    """Разделы прайса с разобранными ценами — сырьё для OfferCatalog.
    Позиции без самостоятельной цены и опустевшие разделы отбрасываются."""
    catalog = []
    for sec in sections:
        items = [
            {"name": item["name"], "desc": item["desc"], "offer": offer}
            for item in sec["items"]
            if (offer := item_offer(item))
        ]
        if items:
            catalog.append({"section": sec["section"], "items": items})
    return catalog


def service_offer_catalog(service_title, sections, currency, url):
    """OfferCatalog страницы услуги, или None, если предлагать нечего."""
    catalog = price_catalog(sections)
    if not catalog:
        return None
    return schema.offer_catalog_node(service_title, catalog, currency, url)


def offer_bounds(offer):
    """Нижняя и верхняя границы цены предложения."""
    if "price" in offer:
        return offer["price"], offer["price"]
    return offer["min"], offer.get("max", offer["min"])


def price_aggregate(sections, currency):
    """Диапазон цен услуги (min/max/кол-во позиций) для AggregateOffer.

    Считается из того же каталога, что и попозиционная разметка, поэтому
    диапазон не может разойтись с ценами конкретных услуг. Возвращает None,
    если самостоятельных цен нет (числа не выдумываем, берём ровно из прайса)."""
    bounds = [offer_bounds(item["offer"])
              for section in price_catalog(sections) for item in section["items"]]
    if not bounds:
        return None
    values = [value for pair in bounds for value in pair]
    offers = len(bounds)
    return {"low": min(values), "high": max(values),
            "count": offers, "currency": currency}


def price_from(sections, currency_sign):
    """Нижняя цена услуги строкой «от 2500 ฿» — подпись для карточки услуги.

    Карточки на странице раздела и в «Смотрите также» показывают только фото
    и название: выбирая между тремя видами эпиляции, клиент вынужден открыть
    каждую страницу, чтобы увидеть цену. Берём ту же нижнюю границу, что уходит
    в AggregateOffer, — расхождение с прайсом невозможно."""
    bounds = [offer_bounds(item["offer"])
              for section in price_catalog(sections) for item in section["items"]]
    if not bounds:
        return None
    return f"от{NBSP}{format_price(str(min(low for low, _ in bounds)))}{NBSP}{currency_sign}"


def open_ended(offer):
    """Цена вида «от 6000 ฿»: нижняя граница есть, верхней нет."""
    return "price" not in offer and "max" not in offer


def price_span(sections_list, currency_sign):
    """Диапазон цен по нескольким прайсам строкой «300–35 000 ฿», или None.

    Границы берутся из того же каталога, что уходит в AggregateOffer, поэтому
    выжимка для ИИ не может назвать цену, которой нет в прайсе.

    Если самая дорогая позиция сама задана как «от … ฿» — верхней границы у прайса
    нет, и закрытый диапазон её выдумает. Такой прайс сворачивается в «от … ฿»:
    у Tokio Inkarami все три длины стоят «от», и «3000–6000 ฿» обещало потолок,
    которого салон не называл."""
    offers = [item["offer"]
              for sections in sections_list
              for section in price_catalog(sections) for item in section["items"]]
    if not offers:
        return None
    bounds = [offer_bounds(offer) for offer in offers]
    top = max(high for _, high in bounds)
    low = format_price(str(min(low for low, _ in bounds)))
    high = format_price(str(top))
    if any(open_ended(offer) for offer, (_, hi) in zip(offers, bounds) if hi == top):
        return f"от{NBSP}{low}{NBSP}{currency_sign}"
    span = low if low == high else f"{low}–{high}"
    return f"{span}{NBSP}{currency_sign}"


def pricier_variant(sections, name):
    """Есть ли в прайсе строка «то же название - уточнение» дороже, чем name.

    Прайс волос устроен парами: «Женская — 2000 ฿» и «Женская - Длинные / густые
    волосы — 2300 ฿». Назвать первую сумму точной значит соврать половине клиентов:
    для них цена начинается от неё. Правило механическое, чтобы новая пара в прайсе
    не потребовала помнить про него."""
    base = None
    for section in sections:
        for item in section["items"]:
            if item["name"] == name:
                base = price_offer(item["price"])
                break
    if not base:
        return False
    ceiling = offer_bounds(base)[1]
    prefix = name + " - "
    return any(offer_bounds(offer)[0] > ceiling
               for section in sections for item in section["items"]
               if item["name"].startswith(prefix) and (offer := item_offer(item)))


def item_price_label(prices, slug, name, currency_sign):
    """Подпись цены позиции для карточки: «7000 ฿» или «от 7000 ฿»."""
    sections = prices.get(slug, [])
    for section in sections:
        for item in section["items"]:
            if item["name"] == name:
                price = format_price(item["price"])
                if not price.lower().startswith("от") and pricier_variant(sections, name):
                    price = f"от {price}"
                return price.replace(" ", NBSP)
    raise KeyError(f"нет позиции прайса {name!r} у услуги {slug!r}")


def price_with_note(svc, span):
    """Диапазон услуги с оговоркой price_note, если он охватывает не весь прайс.

    Диапазон складывается из позиций с самостоятельной ценой, а тариф за минуту
    в него не входит: электроэпиляция выглядела как «300–700 ฿», хотя тело
    считают поминутно и сеанс стоит кратно больше. Оговорка пишется в content.yml
    руками — вывести её из прайса нельзя, длительность сеанса там не задана."""
    note = svc.get("price_note")
    if not span or not note:
        return span
    return f"{span}, {note}"


def category_price_rows(cat, services, prices, site):
    """Строки сводной таблицы раздела: услуга, диапазон цен, длительность.

    Раздел перечисляет услуги карточками, и на вопрос «сколько стоит эпиляция
    на Самуи» отвечать ему было нечем — цена стояла только подписью «от … ฿».
    Таблица собирается из прайса и полей услуг, ничего не добавляя от себя."""
    sign = site["business"]["currency_sign"]
    rows = []
    for slug in cat["services"]:
        svc = services[slug]
        rows.append({
            "slug": slug,
            "label": svc["title"],
            "span": price_with_note(svc, price_span([prices.get(slug, [])], sign)),
            "duration": svc.get("duration"),
        })
    return rows


def home_price_rows(content, prices, site):
    """Строки сводной таблицы главной: направление, состав, диапазон цен."""
    sign = site["business"]["currency_sign"]
    rows = []
    for cat in content["categories"]:
        slugs = cat["services"]
        rows.append({
            "url": cat["url"] if cat["is_page"] else f"/{slugs[0]}/",
            "label": cat["title"],
            "services": ", ".join(content["services"][slug]["title"] for slug in slugs),
            "span": price_span([prices.get(slug, []) for slug in slugs], sign),
        })
    return rows


# Ссылка в HTML-ответе FAQ → markdown-ссылка для llms.txt. Относительный адрес
# разворачивается в абсолютный: файл читают в отрыве от сайта, и «/volosy/»
# из него никуда не ведёт.
_LINK_RE = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def uncapitalize(text):
    """Строчная только первая буква: строка встраивается в перечисление после
    двоеточия. Сплошной lower() испортил бы написание сущностей внутри строки —
    «Hydra Facial» и «Tokio Inkarami» обязаны выглядеть одинаково везде."""
    return text[:1].lower() + text[1:]


def markdown_links(html, base_url):
    """HTML-ответ FAQ как markdown: ссылки сохраняются, остальные теги убираются."""
    def link(match):
        href, text = match.group(1), match.group(2)
        return f"[{text}]({base_url + href if href.startswith('/') else href})"
    return _TAG_RE.sub("", _LINK_RE.sub(link, html)).strip()


def build_llms(site, content, prices):
    """llms.txt — выжимка сайта для ИИ-ассистентов (llmstxt.org).

    Кроме карты ссылок файл несёт факты, цены, длительность процедур и вопросы
    с ответами: ассистент, прочитавший только его, должен уметь ответить, где
    салон, на каком языке говорят, сколько стоит и сколько длится процедура.
    Отдельно перечислено то, чего на сайте нет: без явной строки «адрес
    не публикуется» ассистент дописывает адрес сам. Разделы без своей страницы
    (одна услуга) в карту не выводятся — их адрес это адрес самой услуги,
    и второй раз тот же URL под другой подписью только путает."""
    base = site["base_url"]
    b = site["business"]
    c = site["contacts"]
    sign = b["currency_sign"]
    lines = [
        f"# {site['brand_full']}",
        "",
        f"> {content['llms_description']}",
        "",
        "## Коротко",
        f"- Локация: {site['location']}, провинция {b['address']['region']}",
        f"- Как попасть: {uncapitalize(site['hours'])}",
        "- Языки обслуживания: русский, английский",
        f"- Валюта прайса: тайский бат ({sign})",
        f"- Телефон и WhatsApp: {b['telephone']}",
        f"- Правило переноса: {uncapitalize(site['booking_rule'])}",
        "",
        "## Чего на сайте нет",
        "- Точный адрес не публикуется: его сообщают при записи в мессенджере.",
        "- Часы работы не заявлены: салон принимает по предварительной записи.",
        "- Отзывов и рейтингов на сайте нет, и салон их не собирает.",
        "- Neva Beauty — Koh Samui это салон красоты, а не медицинская клиника.",
        "",
        "## Страницы",
        f"- [{content['home']['seo_title']}]({base}/)",
    ]
    for cat in content["categories"]:
        if not cat["is_page"]:
            continue
        span = price_span([prices.get(slug, []) for slug in cat["services"]], sign)
        note = f" — раздел из {len(cat['services'])} услуг, цены {span}" if span else " — раздел"
        lines.append(f"- [{cat['title']}]({base}{cat['url']}){note}")
    lines += ["", "## Услуги"]
    for slug, svc in content["services"].items():
        span = price_with_note(svc, price_span([prices.get(slug, [])], sign))
        facts = [f"цены {span}" if span else None,
                 f"длительность: {uncapitalize(svc['duration'])}" if svc.get("duration") else None]
        note = " — " + ", ".join(fact for fact in facts if fact) if any(facts) else ""
        lines.append(f"- [{svc['title']}]({base}/{slug}/){note}")
    lines += ["", "## Частые вопросы"]
    for item in content["home"]["faq"]:
        lines += [f"### {item['q']}", markdown_links(item["a"], base), ""]
    lines += [
        "## Контакты",
        f"- WhatsApp: {c['whatsapp_url']}",
        f"- Telegram: {c['telegram_url']}",
        f"- Instagram: {c['instagram_url']}",
        "",
    ]
    return "\n".join(lines)


# Дата последнего изменения страницы для sitemap. Проставлять во все записи дату
# сборки — значит объявлять весь сайт изменённым при каждой пересборке; поисковик
# после двух-трёх таких обходов перестаёт доверять полю целиком. Поэтому дата
# хранится вместе с отпечатком страницы и обновляется только вместе с ней.
LASTMOD_PATH = ROOT / "data" / "lastmod.json"
# Отпечатки ассетов (?v=1a2b3c4d) из отпечатка страницы вырезаем: правка CSS
# меняет ссылку на бандл на всех 23 страницах, но текст страницы не трогает.
_ASSET_VERSION_RE = re.compile(r"\?v=[0-9a-f]+")
# Дата изменения стоит в самой странице (dateModified в JSON-LD), и это замкнутый
# круг: подставить дату — значит изменить страницу, а значит и её дату. Разрываем
# так же, как с отпечатками ассетов: страница рендерится с постоянной заглушкой,
# отпечаток считается по ней, и только потом на её место встаёт настоящая дата.
LASTMOD_PLACEHOLDER = "0000-00-00"
# Ту же дату страница показывает человеку: dateModified в разметке отвечает поиску,
# но ИИ цитирует то, что читает в тексте, а YMYL-страница без видимой даты выглядит
# недатированной. Заглушка отдельная — вид у даты в тексте русский, не ISO.
LASTMOD_HUMAN_PLACEHOLDER = "00 месяца 0000 года"
MONTHS_RU = ("января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря")


def format_date_ru(iso_date):
    """«2026-08-31» → «31 августа 2026 года»."""
    year, month, day = (int(part) for part in iso_date.split("-"))
    return f"{day} {MONTHS_RU[month - 1]} {year} года"


def page_digest(html):
    return hashlib.sha1(_ASSET_VERSION_RE.sub("", html).encode("utf-8")).hexdigest()


def lastmod_history():
    if LASTMOD_PATH.exists():
        return json.loads(LASTMOD_PATH.read_text(encoding="utf-8"))
    return {}


def page_date(url, digest, history, today):
    """Дата изменения страницы: прежняя, если отпечаток совпал, иначе сегодняшняя."""
    known = history.get(url)
    return known["date"] if known and known["hash"] == digest else today


def save_lastmod(journal):
    LASTMOD_PATH.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def write_page(path: Path, url: str, html: str, journal: dict, history: dict, today: str):
    """Записывает индексируемую страницу и проставляет ей дату изменения.

    Отпечаток снимается с разметки, где на месте даты стоит заглушка, поэтому
    подстановка даты сама по себе страницу «изменённой» не делает."""
    digest = page_digest(html)
    date_str = page_date(url, digest, history, today)
    journal[url] = {"hash": digest, "date": date_str}
    write(path, html.replace(LASTMOD_HUMAN_PLACEHOLDER, format_date_ru(date_str))
                    .replace(LASTMOD_PLACEHOLDER, date_str))


def build_manifest(site, base_path):
    """site.webmanifest — имя и иконка для «добавить на главный экран» на Android.
    Собирается, а не лежит статикой: пути внутри должны учитывать base_path, иначе
    на превью по подпути GitHub Pages манифест уводит на несуществующие иконки.
    purpose «any maskable» — одна иконка и как есть, и под маску адаптивных иконок:
    цветок занимает ~58 % кадра и не обрезается ни одной формой маски."""
    icons = [{"src": f"{base_path}/icon-{size}.png", "sizes": f"{size}x{size}",
              "type": "image/png", "purpose": "any maskable"} for size in (192, 512)]
    manifest = {
        "name": f"{site['brand']} — {site['tagline']}",
        "short_name": site["brand"],
        "start_url": f"{base_path}/",
        "display": "standalone",
        "background_color": THEME_COLOR,
        "theme_color": THEME_COLOR,
        "icons": icons,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def build_sitemap(urls, base_url, journal):
    """sitemap.xml по журналу, заполненному при записи страниц."""
    rows = "\n".join(
        f'  <url><loc>{base_url}{url}</loc>'
        f'<lastmod>{journal[url]["date"]}</lastmod></url>' for url in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + rows + '\n</urlset>\n')


def build_nav(categories, services):
    # label — короткая подпись для верхней панели, title — полное название для дровера/страниц
    nav = [{"label": "Главная", "title": "Главная", "url": "/"}]
    for cat in categories:
        item = {"label": cat.get("nav_label", cat["title"]), "title": cat["title"], "url": cat["url"]}
        if cat["is_page"]:
            item["children"] = [{"label": services[svc_slug]["title"], "slug": svc_slug} for svc_slug in cat["services"]]
        nav.append(item)
    return nav

def main():
    site, content, prices = load()
    e = env()
    # Префикс пути для ссылок на ассеты/страницы: пусто на боевом домене (сайт в корне),
    # "/th.neva.beauty" для превью на GitHub Pages по подпути проекта. SEO-URL (base_url) не трогает.
    base_path = site.get("base_path", "").rstrip("/")
    e.globals["base_path"] = base_path
    prices_index = price_by_name(prices)  # цены для плейсхолдеров {price:...} в текстах
    build_css_bundle()  # единый минифицированный bundle.min.css
    e.globals["asset"] = lambda path: asset_url(base_path, path)  # после сборки bundle
    # адаптивные картинки: ширины и sizes из images.py, один набор на разметку и preload
    e.globals["srcset"] = lambda stem, slot: images.srcset(stem, slot, base_path)
    e.globals["img_sizes"] = images.sizes
    e.globals["img_width"] = images.width
    e.globals["img_height"] = images.height
    e.globals["card_image"] = images.related_stem
    enrich_categories(content)
    fill_related(content)
    site["nav"] = build_nav(content["categories"], content["services"])
    # Темы, в которых компетентен салон, — ровно названия его услуг: список
    # уходит в Organization.knowsAbout и собирается здесь, чтобы не разойтись
    # с составом сайта после добавления или снятия услуги.
    site["business"]["knows_about"] = [svc["title"] for svc in content["services"].values()]
    base_schema = schema.render(site)  # общий граф бизнеса — на всех страницах
    # Журнал дат изменения: history — прошлая сборка, journal — текущая.
    today = date.today().isoformat()
    history, journal = lastmod_history(), {}
    # «от N ฿» на карточках услуг — считаем один раз на все страницы,
    # карточка одной услуги встречается и в разделе, и в «Смотрите также».
    currency_sign = site["business"]["currency_sign"]
    price_from_by_slug = {slug: price_from(sections, currency_sign)
                          for slug, sections in prices.items()}
    e.globals["price_from"] = price_from_by_slug.get
    # Цена конкретной позиции для карточек «Частое» на главной — той же формой,
    # что и в текстах: «от N ฿», если у позиции есть строка дороже.
    e.globals["item_price"] = lambda slug, name: item_price_label(
        prices, slug, name, currency_sign)
    # главная
    base_url = site["base_url"]
    home = content["home"]
    home_url = base_url + "/"
    # Список направлений: главная показывает пять разделов карточками, а в графе
    # этого не было — из разметки не следовало, что у салона вообще есть разделы.
    home_sections = schema.item_list_node(
        f"Направления салона {site['brand_full']}",
        [{"name": cat["title"], "url": base_url + cat["url"]}
         for cat in content["categories"]],
        home_url)
    home_nodes = [schema.webpage_node(home_url, base_url, home["seo_title"],
                                      home["seo_desc"],
                                      image=base_url + "/assets/img/hero.webp",
                                      main_entity_id=home_url + schema.ITEMLIST_ID,
                                      date_modified=LASTMOD_PLACEHOLDER),
                  home_sections]
    home_faq = home.get("faq", [])
    if home_faq:
        home["faq"] = render_faq_contacts(home_faq, site["contacts"], base_path, prices_index)
        home_nodes.append(schema.faq_node(home["faq"], home_url))
    page = {"url": "/", "seo_title": home["seo_title"],
            "seo_desc": home["seo_desc"], "og_title": home.get("og_title"),
            "schema_json": schema.render(site, home_nodes),
            "hero_image": "/assets/img/hero.webp",  # LCP-элемент → preload в base.html.j2
            "hero_stem": "hero", "hero_slot": "home_hero",
            "og_image_alt": site["og_image"]["default_alt"]}
    home["price_lead"] = render_rich_text(
        home["price_lead"], site["contacts"], base_path, prices_index)
    write_page(OUT/"index.html", "/", e.get_template("home.html.j2").render(
        site=site, page=page, home=content["home"], categories=content["categories"],
        prices=prices, price_rows=home_price_rows(content, prices, site)),
        journal, history, today)
    # услуги
    tpl = e.get_template("service.html.j2")
    provider_ref = {"@id": base_url + "/" + schema.BUSINESS_ID}
    area_name = site["business"]["address"]["locality"]
    currency = site["business"].get("currency")
    # Канал записи один на все услуги: записываются в мессенджер, номер тот же.
    booking_channel = schema.booking_channel_node(
        site["contacts"], site["business"]["telephone"], site["business"]["language"])
    category_by_slug = {slug: cat for cat in content["categories"] for slug in cat["services"]}
    for slug, svc in content["services"].items():
        sections = prices.get(slug, [])
        cat = category_by_slug[slug]
        render_page_prices(svc, prices_index)
        # Лид блока цен — тот же рич-текст, что и ответы FAQ: ссылки на смежные
        # услуги, суммы плейсхолдерами, префикс base_path для превью по подпути.
        svc["price_lead"] = render_rich_text(
            svc["price_lead"], site["contacts"], base_path, prices_index)
        url = base_url + f"/{slug}/"
        hero = base_url + f"/assets/img/{svc['hero_image']}.webp"
        crumbs = [{"name": "Главная", "url": base_url + "/"}]
        if cat["is_page"]:
            crumbs.append({"name": cat["title"], "url": base_url + cat["url"]})
        crumbs.append({"name": svc["title"], "url": url})
        nodes = [
            schema.webpage_node(url, base_url, svc["seo_title"], svc["seo_desc"],
                                breadcrumb=True, image=hero,
                                main_entity_id=url + schema.SERVICE_ID,
                                date_modified=LASTMOD_PLACEHOLDER),
            schema.breadcrumb_node(crumbs, url),
            schema.service_node(
                svc["title"], svc["intro"], provider_ref, area_name,
                price_aggregate(sections, currency),
                service_offer_catalog(svc["title"], sections, currency, url),
                page_url=url, image=hero, channel=booking_channel,
                category=cat["title"]),
        ]
        if svc.get("faq"):
            svc["faq"] = render_faq_contacts(svc["faq"], site["contacts"], base_path, prices_index)
            nodes.append(schema.faq_node(svc["faq"], url))
        page = {"url": f"/{slug}/", "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"],
                "og_title": svc.get("og_title") or og_title(svc, site),
                "schema_json": schema.render(site, nodes),
                "hero_image": f"/assets/img/{svc['hero_image']}.webp",  # LCP → preload
                "hero_stem": svc["hero_image"], "hero_slot": "service_hero",
                "og_image": og_image_path(slug),
                "og_image_alt": svc.get("image_alt") or f"{svc['title']} — {site['brand_full']}"}
        write_page(OUT/slug/"index.html", f"/{slug}/", tpl.render(
            site=site, page=page, svc=svc, slug=slug, category=cat,
            sections=price_view(sections), services=content["services"]),
            journal, history, today)
    # категории (только группы с несколькими услугами)
    cat_tpl = e.get_template("category.html.j2")
    for cat in content["categories"]:
        if not cat["is_page"]:
            continue
        render_page_prices(cat, prices_index)
        cat["price_lead"] = render_rich_text(
            cat["price_lead"], site["contacts"], base_path, prices_index)
        url = base_url + cat["url"]
        nodes = [
            schema.webpage_node(url, base_url, cat["seo_title"], cat["seo_desc"],
                                breadcrumb=True,
                                image=base_url + f"/assets/img/{cat['image']}.webp",
                                main_entity_id=url + schema.ITEMLIST_ID,
                                date_modified=LASTMOD_PLACEHOLDER),
            schema.breadcrumb_node([
                {"name": "Главная", "url": base_url + "/"},
                {"name": cat["title"], "url": url},
            ], url),
            schema.item_list_node(cat["title"], [
                {"name": content["services"][slug]["title"],
                 "url": f"{base_url}/{slug}/", "service": True}
                for slug in cat["services"]
            ], url),
        ]
        if cat.get("faq"):
            cat["faq"] = render_faq_contacts(cat["faq"], site["contacts"], base_path, prices_index)
            nodes.append(schema.faq_node(cat["faq"], url))
        page = {"url": cat["url"], "seo_title": cat["seo_title"], "seo_desc": cat["seo_desc"],
                "og_title": cat.get("og_title") or og_title(cat, site),
                "schema_json": schema.render(site, nodes),
                "og_image": og_image_path(cat["slug"]),
                "og_image_alt": cat.get("image_alt") or f"{cat['title']} — {site['brand_full']}"}
        write_page(OUT/cat["slug"]/"index.html", cat["url"], cat_tpl.render(
            site=site, page=page, cat=cat, services=content["services"],
            categories=content["categories"],
            price_rows=category_price_rows(cat, content["services"], prices, site)),
            journal, history, today)
    # privacy (служебная — не индексируем; seo_desc нужен для превью ссылки в мессенджере)
    page = {"url": "/privacy/", "seo_title": f"Политика конфиденциальности — {site['brand']}",
            "seo_desc": f"Сайт {site['brand_full']} не собирает данные: форм нет, "
                        "переписка остаётся в мессенджерах, счёт визитов обезличен.",
            "schema_json": base_schema, "noindex": True}
    write(OUT/"privacy"/"index.html", e.get_template("privacy.html.j2").render(site=site, page=page))
    # 404 (служебная — не индексируем)
    page = {"url": "/404.html", "seo_title": f"Страница не найдена — {site['brand']}",
            "seo_desc": "Такой страницы нет. Загляните в услуги и цены "
                        f"салона {site['brand_full']}.",
            "schema_json": base_schema, "noindex": True}
    write(OUT/"404.html", e.get_template("404.html.j2").render(site=site, page=page))
    # sitemap (собирается после страниц: дата берётся из отпечатка готового HTML)
    cat_urls = [cat["url"] for cat in content["categories"] if cat["is_page"]]
    # /privacy/ и /404.html — noindex, в sitemap не включаем
    urls = ["/"] + [f"/{slug}/" for slug in content["services"]] + cat_urls
    save_lastmod(journal)
    write(OUT/"sitemap.xml", build_sitemap(urls, base_url, journal))
    # site.webmanifest — имя и иконка при добавлении на главный экран
    write(OUT/"site.webmanifest", build_manifest(site, base_path))
    # llms.txt — выжимка сайта для ИИ-ассистентов
    write(OUT/"llms.txt", build_llms(site, content, prices))
    # CNAME — боевой домен для GitHub Pages. Кладём в артефакт, иначе workflow-деплой
    # каждый раз сбрасывает кастомный домен в настройках Pages. Хост берём из base_url.
    write(OUT/"CNAME", urllib.parse.urlsplit(base_url).netloc + "\n")

if __name__ == "__main__":
    main()
