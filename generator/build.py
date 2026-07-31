import json, re, urllib.parse, yaml, rcssmin
from datetime import date
from pathlib import Path
from markupsafe import Markup
from jinja2 import Environment, FileSystemLoader, select_autoescape
import schema

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "th.neva.beauty"
ICONS = OUT / "assets" / "icons"

RELATED_COUNT = 3  # сколько карточек «Смотрите также» показываем на странице услуги

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
    e.tests["match"] = lambda s, pat: re.match(pat, s) is not None
    e.globals["icon"] = icon
    return e

def write(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("→", path.relative_to(OUT.parent))

def build_css_bundle():
    """Склеивает CSS-слои в порядке каскада и минифицирует в единый bundle.min.css.
    Один render-blocking запрос вместо шести; относительные url() внутри (../fonts,
    ../img) работают и на превью по подпути, и на боевом домене."""
    css_dir = OUT / "assets" / "css"
    parts = [f.read_text(encoding="utf-8")
             for name in CSS_BUNDLE_ORDER
             if (f := css_dir / f"{name}.css").exists()]
    bundle = rcssmin.cssmin("\n".join(parts))
    out = css_dir / "bundle.min.css"
    out.write_text(bundle, encoding="utf-8")
    print("→", out.relative_to(OUT.parent), f"({len(bundle) // 1024} KB minified)")

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

def render_faq_contacts(faq, contacts, base_path=""):
    """Финализирует HTML-ответы FAQ: подставляет URL мессенджеров вместо плейсхолдеров
    {whatsapp}/{telegram}/{instagram} (единый источник — site.yml) и префиксует внутренние
    ссылки href="/..." на base_path — чтобы они работали и на превью по подпути."""
    tokens = {
        "{whatsapp}": contacts["whatsapp_url"],
        "{telegram}": contacts["telegram_url"],
        "{instagram}": contacts["instagram_url"],
    }
    result = []
    for item in faq:
        answer = item["a"]
        for token, url in tokens.items():
            answer = answer.replace(token, url)
        if base_path:
            answer = answer.replace('href="/', f'href="{base_path}/')
        result.append({"q": item["q"], "a": answer})
    return result


# Число цены: первая цифра и дальше цифры с разделителями разрядов (обычный
# и неразрывный пробел). «1 600 000» — одно число, «600 -1200» — два.
_PRICE_NUMBER_RE = re.compile(r"\d[\d\s ]*")


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


def build_llms(site, content):
    """llms.txt — краткая карта сайта для ИИ-ассистентов (llmstxt.org)."""
    base = site["base_url"]
    c = site["contacts"]
    lines = [
        f"# {site['brand_full']}",
        "",
        f"> {content['llms_description']}",
        "",
        "## Направления",
    ]
    for cat in content["categories"]:
        lines.append(f"- [{cat['title']}]({base}{cat['url']})")
    lines += ["", "## Услуги"]
    for slug, svc in content["services"].items():
        lines.append(f"- [{svc['title']}]({base}/{slug}/)")
    lines += [
        "",
        "## Контакты",
        f"- Локация: {site['location']}",
        f"- Режим работы: {site['hours']}",
        f"- WhatsApp: {c['whatsapp_url']}",
        f"- Telegram: {c['telegram_url']}",
        f"- Instagram: {c['instagram_url']}",
        "",
    ]
    return "\n".join(lines)


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
    build_css_bundle()  # единый минифицированный bundle.min.css
    enrich_categories(content)
    fill_related(content)
    site["nav"] = build_nav(content["categories"], content["services"])
    base_schema = schema.render(site)  # общий граф бизнеса — на всех страницах
    # главная
    home_faq = content["home"].get("faq", [])
    if home_faq:
        home_faq = render_faq_contacts(home_faq, site["contacts"], base_path)
        content["home"]["faq"] = home_faq
        home_schema = schema.render(site, [schema.faq_node(home_faq)])
    else:
        home_schema = base_schema
    page = {"url": "/", "seo_title": content["home"].get("seo_title", site["brand_full"]),
            "seo_desc": content["home"].get("seo_desc",""), "schema_json": home_schema,
            "hero_image": "/assets/img/hero.webp"}  # LCP-элемент → preload в base.html.j2
    write(OUT/"index.html", e.get_template("home.html.j2").render(
        site=site, page=page, home=content["home"], categories=content["categories"], prices=prices))
    # услуги
    tpl = e.get_template("service.html.j2")
    base_url = site["base_url"]
    provider_ref = {"@id": base_url + "/" + schema.BUSINESS_ID}
    area_name = site["business"]["address"]["locality"]
    currency = site["business"].get("currency")
    category_by_slug = {slug: cat for cat in content["categories"] for slug in cat["services"]}
    for slug, svc in content["services"].items():
        sections = prices.get(slug, [])
        cat = category_by_slug[slug]
        crumbs = [{"name": "Главная", "url": base_url + "/"}]
        if cat["is_page"]:
            crumbs.append({"name": cat["title"], "url": base_url + cat["url"]})
        crumbs.append({"name": svc["title"], "url": base_url + f"/{slug}/"})
        nodes = [
            schema.breadcrumb_node(crumbs),
            schema.service_node(
                svc["title"], svc["intro"], provider_ref, area_name,
                price_aggregate(sections, currency),
                service_offer_catalog(svc["title"], sections, currency,
                                      base_url + f"/{slug}/")),
        ]
        if svc.get("faq"):
            svc["faq"] = render_faq_contacts(svc["faq"], site["contacts"], base_path)
            nodes.append(schema.faq_node(svc["faq"]))
        page = {"url": f"/{slug}/", "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"],
                "schema_json": schema.render(site, nodes),
                "hero_image": f"/assets/img/{svc['hero_image']}.webp"}  # LCP → preload
        write(OUT/slug/"index.html", tpl.render(
            site=site, page=page, svc=svc, slug=slug, category=cat,
            sections=sections, services=content["services"]))
    # категории (только группы с несколькими услугами)
    cat_tpl = e.get_template("category.html.j2")
    for cat in content["categories"]:
        if not cat["is_page"]:
            continue
        nodes = [
            schema.breadcrumb_node([
                {"name": "Главная", "url": base_url + "/"},
                {"name": cat["title"], "url": base_url + cat["url"]},
            ]),
            schema.item_list_node(cat["title"], [f"{base_url}/{slug}/" for slug in cat["services"]]),
        ]
        if cat.get("faq"):
            cat["faq"] = render_faq_contacts(cat["faq"], site["contacts"], base_path)
            nodes.append(schema.faq_node(cat["faq"]))
        page = {"url": cat["url"], "seo_title": cat["seo_title"], "seo_desc": cat["seo_desc"],
                "schema_json": schema.render(site, nodes)}
        write(OUT/cat["slug"]/"index.html", cat_tpl.render(
            site=site, page=page, cat=cat, services=content["services"]))
    # privacy (служебная — не индексируем)
    page = {"url": "/privacy/", "seo_title": f"Политика конфиденциальности — {site['brand']}",
            "seo_desc": "", "schema_json": base_schema, "noindex": True}
    write(OUT/"privacy"/"index.html", e.get_template("privacy.html.j2").render(site=site, page=page))
    # 404 (служебная — не индексируем)
    page = {"url": "/404.html", "seo_title": f"Страница не найдена — {site['brand']}",
            "seo_desc": "", "schema_json": base_schema, "noindex": True}
    write(OUT/"404.html", e.get_template("404.html.j2").render(site=site, page=page))
    # sitemap
    cat_urls = [cat["url"] for cat in content["categories"] if cat["is_page"]]
    # /privacy/ и /404.html — noindex, в sitemap не включаем
    urls = ["/"] + [f"/{slug}/" for slug in content["services"]] + cat_urls
    today = date.today().isoformat()
    rows = "\n".join(f'  <url><loc>{base_url}{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '\n</urlset>\n'
    write(OUT/"sitemap.xml", sitemap)
    # llms.txt — карта сайта для ИИ-ассистентов
    write(OUT/"llms.txt", build_llms(site, content))
    # CNAME — боевой домен для GitHub Pages. Кладём в артефакт, иначе workflow-деплой
    # каждый раз сбрасывает кастомный домен в настройках Pages. Хост берём из base_url.
    write(OUT/"CNAME", urllib.parse.urlsplit(base_url).netloc + "\n")

if __name__ == "__main__":
    main()
