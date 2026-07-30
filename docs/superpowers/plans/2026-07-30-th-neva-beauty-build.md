# th.neva.beauty — план сборки сайта

> **Для агентов:** ОБЯЗАТЕЛЬНЫЙ СУБ-СКИЛЛ: используйте superpowers:subagent-driven-development
> (рекомендуется) или superpowers:executing-plans для выполнения плана задача за задачей.
> Шаги размечены чекбоксами (`- [ ]`).

**Цель:** собрать сайт салона красоты на Самуи на генераторе, скопированном с боевого
`vn.neva.beauty`, с ценами и услугами, перенесёнными со старой Tilda-выгрузки без изменений,
и опубликовать его на `th.neva.beauty`.

**Архитектура:** статический генератор на Python. Данные описаны в YAML/JSON, шаблоны на
Jinja2, на выходе чистый HTML, который раздаётся GitHub Pages. Точность цен защищена
парити-тестом, качество страниц — скриптом проверок. Один проход `build.py` собирает весь сайт.

**Стек:** Python 3.12, Jinja2, PyYAML, BeautifulSoup4, rcssmin, pytest, GitHub Actions,
GitHub Pages.

Спека: `docs/superpowers/specs/2026-07-30-th-neva-beauty-design.md`

Этот план покрывает этапы 0–4 из спеки — от пустого репозитория до живого сайта.
Этапы 5–10 (аудиты, SEO/GEO по страницам, скорость, документация) ведутся по `TODO.md`
отдельными сессиями поверх готового сайта.

## Глобальные ограничения

- **Цены не меняются.** Все 203 позиции переносятся со старого сайта дословно. Нормализуется
  только отступ перед знаком ฿. Ни округлений, ни добавления «от», если на старом сайте
  конкретная цифра.
- **Факты не выдумываются.** Отзывы, рейтинги, число процедур, лицензии, имена и квалификация
  мастеров, марки аппаратов — только то, что есть на старых страницах. `Review` и
  `AggregateRating` не добавляются.
- **Результат не обещается.** Формулировки «навсегда», «гарантированно», «безболезненно»
  со старых страниц не переносятся. Косметология — тематика YMYL.
- **Следов старого бренда нет.** Строки `Avocado`, `avocado`, `doctor-cosmetolog.pro` не должны
  встречаться нигде, кроме ссылки на Instagram-аккаунт `avocado.beauty.samui` — она остаётся
  по решению заказчика.
- **Адрес не публикуется.** В схеме только `addressLocality: Koh Samui`,
  `addressRegion: Surat Thani`, `addressCountry: TH`. Без `streetAddress` и без `geo`.
- **Реквизиты юрлица не публикуются.**
- **Валюта — THB.** Символ ฿, `priceCurrency: "THB"`, `currenciesAccepted: "THB"`.
- **Язык контента — русский.** Технические ключи schema.org и HTML — английские.
- **Бренд.** Полная форма `Neva Beauty — Koh Samui` в шапке, футере, схеме и хотя бы раз
  в тексте каждой страницы. Короткая форма `Neva Beauty` — в `title`.
- **Часы работы** — «Приём по записи». `openingHoursSpecification` в схему не добавляется.
- **Коммит после каждой задачи**, пуш в `main` — он же триггер деплоя.

## Структура файлов

```
th.neva.beauty/
├─ generator/
│  ├─ build.py              оркестратор: данные → HTML, sitemap, llms.txt, CNAME
│  ├─ schema.py             сборка JSON-LD графа schema.org
│  ├─ check_prices.py       парити-тест: prices.json ↔ собранный HTML
│  ├─ check_content.py      проверки качества страниц (задача 13)
│  ├─ data/
│  │  ├─ site.yml           бизнес, контакты, конфиг — задача 4
│  │  ├─ content.yml        таксономия, тексты, FAQ — задачи 7–12
│  │  └─ prices.json        эталон цен, 203 позиции — задача 3
│  ├─ templates/            Jinja2: base, home, category, service, privacy, 404 + партиалы
│  └─ tests/
│     ├─ test_price_values.py    разбор цены для AggregateOffer — задача 2
│     └─ test_prices_parity.py   состав prices.json против старого сайта — задача 3
├─ th.neva.beauty/          сгенерированный сайт → GitHub Pages
│  └─ assets/               css, js, fonts, icons, img
├─ .github/workflows/deploy.yml
├─ requirements.txt
└─ TODO.md
```

Исходники (не в репозитории, в `.gitignore`):
`OLD - doctor.cosmetolog.pro/` — Tilda-выгрузка, `Данные и промты /` — промты SEO/GEO.

---

## Задача 1: Каркас репозитория и перенос генератора

**Файлы:**
- Создать: `requirements.txt`
- Скопировать из vn: `generator/`, `.github/workflows/deploy.yml`, `th.neva.beauty/assets/`,
  `th.neva.beauty/favicon.svg`

**Интерфейсы:**
- Отдаёт: рабочее окружение `.venv`, генератор на месте, зависимости ставятся.

- [ ] **Шаг 1: Создать виртуальное окружение**

```bash
cd "/Users/jw/Мой диск/💼 Работа/Projects/Project - th.neva.beauty"
python3 -m venv .venv
```

- [ ] **Шаг 2: Скопировать генератор, ассеты и workflow из vn**

```bash
VN="/Users/jw/Мой диск/💼 Работа/Projects/Project - vn.neva.beauty"
TH="/Users/jw/Мой диск/💼 Работа/Projects/Project - th.neva.beauty"

mkdir -p "$TH/th.neva.beauty" "$TH/.github/workflows"
cp -R "$VN/generator" "$TH/generator"
cp -R "$VN/vn.neva.beauty/assets" "$TH/th.neva.beauty/assets"
cp "$VN/vn.neva.beauty/favicon.svg" "$TH/th.neva.beauty/favicon.svg"
cp "$VN/.github/workflows/deploy.yml" "$TH/.github/workflows/deploy.yml"

# Данные vn не нужны — они будут написаны заново под Самуи
rm -f "$TH/generator/data/site.yml" "$TH/generator/data/content.yml" "$TH/generator/data/prices.json"
rm -f "$TH/th.neva.beauty/assets/img/"*.jpg "$TH/th.neva.beauty/assets/img/"*.webp
rm -f "$TH/th.neva.beauty/assets/img/CREDITS.txt"
rm -f "$TH/th.neva.beauty/assets/css/bundle.min.css"
find "$TH" -name ".DS_Store" -delete
```

- [ ] **Шаг 3: Записать `requirements.txt`**

Файл `requirements.txt` (pytest добавлен — в vn тестов не было):

```
Jinja2==3.1.4
beautifulsoup4==4.12.3
PyYAML==6.0.2
rcssmin==1.2.2
Pillow==11.0.0
pytest==8.3.3
```

`requests` из vn не переносится — он там не используется. `Pillow` нужен для обработки
изображений в задаче 6.

- [ ] **Шаг 4: Установить зависимости**

Запустить:
```bash
cd "/Users/jw/Мой диск/💼 Работа/Projects/Project - th.neva.beauty"
.venv/bin/pip install -q -r requirements.txt && .venv/bin/python -c "import jinja2, yaml, bs4, rcssmin, PIL, pytest; print('OK')"
```
Ожидаемо: `OK`

- [ ] **Шаг 5: Заменить путь выходной папки в `build.py`**

В `generator/build.py:9` заменить:

```python
OUT = ROOT.parent / "vn.neva.beauty"
```

на:

```python
OUT = ROOT.parent / "th.neva.beauty"
```

- [ ] **Шаг 6: Заменить путь выходной папки в `check_prices.py`**

В `generator/check_prices.py:13` заменить:

```python
NEW = ROOT.parent / "vn.neva.beauty"
```

на:

```python
NEW = ROOT.parent / "th.neva.beauty"
```

- [ ] **Шаг 7: Настроить workflow на новую папку**

В `.github/workflows/deploy.yml` заменить `path: vn.neva.beauty` на `path: th.neva.beauty`.

- [ ] **Шаг 8: Коммит**

```bash
git add -A
git commit -m "Каркас: перенос генератора и ассетов с vn.neva.beauty

Скопированы generator/, assets/, workflow деплоя. Данные vn удалены —
site.yml, content.yml и prices.json пишутся заново под Самуи.
Пути выходной папки переведены на th.neva.beauty.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 2: Разбор цены для AggregateOffer

Текущая реализация вырезает из строки цены всё, кроме цифр. На простых ценах Дананга это
работает, на ценах Самуи ломается: `600 -1200 ฿` превращается в `6001200`. Некорректный
диапазон в структурированных данных — риск ручных санкций Google.

**Файлы:**
- Создать: `generator/tests/test_price_values.py`
- Изменить: `generator/build.py:111-123` (функция `price_aggregate`)

**Интерфейсы:**
- Отдаёт: `price_values(price: str) -> list[int]` — числа-цены из строки прайса;
  `price_aggregate(sections: list, currency: str) -> dict | None` —
  `{"low": int, "high": int, "count": int, "currency": str}` или `None`, если цен нет.

- [ ] **Шаг 1: Написать падающий тест**

Создать `generator/tests/test_price_values.py`:

```python
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
    assert price_values("1 600 000 đ") == [1600000]


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
```

- [ ] **Шаг 2: Запустить тест и убедиться, что он падает**

Запустить:
```bash
cd "/Users/jw/Мой диск/💼 Работа/Projects/Project - th.neva.beauty"
.venv/bin/pytest generator/tests/test_price_values.py -q
```
Ожидаемо: `ImportError: cannot import name 'price_values' from 'build'`

- [ ] **Шаг 3: Реализовать разбор цены**

В `generator/build.py` заменить функцию `price_aggregate` (строки 111–123) на:

```python
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


def price_aggregate(sections, currency):
    """Диапазон цен услуги (min/max/кол-во позиций) для AggregateOffer.
    Возвращает None, если цен нет (числа не выдумываем, берём ровно из прайса)."""
    values, offers = [], 0
    for sec in sections:
        for item in sec["items"]:
            numbers = price_values(item["price"])
            if numbers:
                values.extend(numbers)
                offers += 1
    if not values:
        return None
    return {"low": min(values), "high": max(values),
            "count": offers, "currency": currency}
```

- [ ] **Шаг 4: Запустить тесты и убедиться, что они проходят**

Запустить:
```bash
.venv/bin/pytest generator/tests/test_price_values.py -q
```
Ожидаемо: `12 passed`

- [ ] **Шаг 5: Коммит**

```bash
git add generator/build.py generator/tests/test_price_values.py
git commit -m "Цены: корректный диапазон для AggregateOffer

Прежняя реализация вырезала из строки все нецифры, из-за чего «600 -1200 ฿»
превращалось в 6001200. Теперь из строки берутся все числа, а доплаты (+500 ฿)
и тарифы за единицу времени (35 ฿/минута) в диапазон не входят.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 3: Перенос прайсов со старого сайта

203 позиции с 17 страниц Tilda-выгрузки. Извлечение автоматическое, скрипт одноразовый
и в репозиторий не попадает. В репозиторий попадают `prices.json` и парити-тест состава.

**Файлы:**
- Создать: `generator/data/prices.json`
- Создать: `generator/tests/test_prices_parity.py`
- Временно (в scratchpad, не коммитится): скрипт извлечения

**Интерфейсы:**
- Отдаёт: `generator/data/prices.json` вида
  `{slug: [{"section": str, "items": [{"name": str, "desc": str, "price": str}]}]}`.
  Слаги — из карты ниже. Эту структуру потребляют `build.py`, `check_prices.py`
  и шаблон `service.html.j2`.

**Карта «страница Tilda → слаг → число позиций»:**

| Страница | Слаг | Позиций |
|---|---|---|
| page65556759 | `lazernaya-epilyaciya` | 32 |
| page79940116 | `elektroepilyaciya` | 5 |
| page67695417 | `saharnaya-epilyaciya` | 18 |
| page74422157 | `uhod-za-volosami` | 40 |
| page74519913 | `tokio-inkarami` | 3 |
| page81744456 | `biozavivka-volos` | 4 |
| page81753636 | `keratinovoe-vypryamlenie-volos` | 7 |
| page82202466 | `davines-naturaltech-tailoring` | 1 |
| page60802019 | `permanentnyj-makiyazh` | 11 |
| page79715986 | `igolchatyj-rf-lifting` | 33 |
| page79750196 | `smas-lifting` | 7 |
| page81553916 | `udalenie-tatuirovok-lazerom` | 10 |
| page85635656 | `fotoomolozhenie-m22` | 5 |
| page82430046 | `uhodovaya-kosmetologiya` | 14 |
| page82442846 | `botulinoterapiya` | 5 |
| page78032606 | `endosfera-terapiya` | 4 |
| page81723876 | `massazh` | 4 |
| **Итого** | **17 услуг** | **203** |

- [ ] **Шаг 1: Написать скрипт чернового извлечения в scratchpad**

Создать `extract_prices.py` в директории scratchpad этой сессии — **не в репозитории**:

```python
"""Черновое извлечение прайсов из Tilda-выгрузки старого сайта.

Одноразовый скрипт. Разбиение на секции Tilda в плоском тексте не размечает,
поэтому скрипт складывает все позиции в одну секцию и отдельно выписывает
строки-кандидаты в заголовки секций. Результат вычитывается и правится руками;
в репозиторий попадает только generator/data/prices.json.
"""
import html
import json
import re
from pathlib import Path

OLD = Path("OLD - doctor.cosmetolog.pro")
OUT = Path("generator/data/prices.json")

PAGES = {
    "page65556759.html": "lazernaya-epilyaciya",
    "page79940116.html": "elektroepilyaciya",
    "page67695417.html": "saharnaya-epilyaciya",
    "page74422157.html": "uhod-za-volosami",
    "page74519913.html": "tokio-inkarami",
    "page81744456.html": "biozavivka-volos",
    "page81753636.html": "keratinovoe-vypryamlenie-volos",
    "page82202466.html": "davines-naturaltech-tailoring",
    "page60802019.html": "permanentnyj-makiyazh",
    "page79715986.html": "igolchatyj-rf-lifting",
    "page79750196.html": "smas-lifting",
    "page81553916.html": "udalenie-tatuirovok-lazerom",
    "page85635656.html": "fotoomolozhenie-m22",
    "page82430046.html": "uhodovaya-kosmetologiya",
    "page82442846.html": "botulinoterapiya",
    "page78032606.html": "endosfera-terapiya",
    "page81723876.html": "massazh",
}

# Последняя строка сквозной шапки — всё до неё это меню и логотип, не контент.
HEADER_END = "avocado Beauty - samui"


def page_lines(path):
    """Плоский список видимых строк страницы после сквозной шапки."""
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    raw = re.sub(r"<style.*?</style>", "", raw, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if HEADER_END in lines:
        lines = lines[lines.index(HEADER_END) + 1:]
    return lines


def normalise_price(price):
    """Единый отступ перед ฿. Число и слова вокруг него не трогаем:
    «от», «+», «/минута» и дефисы диапазонов переносятся дословно."""
    return re.sub(r"\s*฿", " ฿", price).strip()


def extract(lines):
    """Позиции прайса и строки-кандидаты в заголовки секций.

    В плоском тексте порядок такой: название, цена, затем либо уточнение,
    либо название следующей позиции, либо заголовок секции. Отличаем по тому,
    где стоит следующая цена: если через одну строку — значит промежуточная
    строка была названием, и уточнения у позиции нет.
    """
    items, used = [], set()
    price_rows = [i for i, line in enumerate(lines) if "฿" in line]
    for i in price_rows:
        name = lines[i - 1] if i else ""
        after = lines[i + 1] if i + 1 < len(lines) else ""
        after2 = lines[i + 2] if i + 2 < len(lines) else ""
        desc = ""
        if after and "฿" not in after and "฿" not in after2:
            desc = after
            used.add(i + 1)
        items.append({"name": name, "desc": desc, "price": normalise_price(lines[i])})
        used.update({i, i - 1})
    orphans = [line for j, line in enumerate(lines) if j not in used and "฿" not in line]
    return items, orphans


def main():
    prices, notes = {}, {}
    for filename, slug in PAGES.items():
        lines = page_lines(OLD / filename)
        items, orphans = extract(lines)
        prices[slug] = [{"section": "Цены", "items": items}]
        notes[slug] = orphans
        print(f"{slug:32} позиций: {len(items):3}")
    print("ИТОГО:", sum(len(s[0]['items']) for s in prices.values()))
    OUT.write_text(json.dumps(prices, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("orphan-lines.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Шаг 2: Запустить извлечение**

Запустить из корня проекта:
```bash
.venv/bin/python <путь-к-scratchpad>/extract_prices.py
```
Ожидаемо: построчный вывод по 17 услугам и `ИТОГО: 203`. Если сумма другая —
разбираться до совпадения, дальше не идти.

- [ ] **Шаг 3: Разметить секции прайса**

Скрипт сложил все позиции каждой услуги в одну секцию `Цены`. Файл `orphan-lines.json`
содержит строки, которые не стали ни названием, ни ценой, ни уточнением — среди них
заголовки секций.

Разнести позиции по секциям вручную в `prices.json`. Реальные секции по услугам:

- `uhod-za-volosami`: «Стрижки», «Окрашивание», «Осветление» и далее по странице
- `uhodovaya-kosmetologiya`: «Чистки и уходовые процедуры», «Акне», «HydraFacial»,
  «Дополнительные услуги»
- `lazernaya-epilyaciya`: «Цены» и «Для женщин» (комбо-наборы)
- `saharnaya-epilyaciya`: «Цены» и «Комплексные предложения»
- остальные услуги — одна секция «Цены», если на странице нет явных подзаголовков

Названия секций брать со страницы дословно.

- [ ] **Шаг 4: Сверить извлечённое с исходными страницами**

Для каждой из 17 страниц вывести рядом позиции старой страницы и позиции из `prices.json`
и сверить построчно: название, уточнение, цена.

```bash
cd "OLD - doctor.cosmetolog.pro" && ../.venv/bin/python -c "
import re, html
s = open('page74422157.html', encoding='utf-8').read()
s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
t = html.unescape(re.sub(r'<[^>]+>', '\n', s))
print('\n'.join(l.strip() for l in t.split('\n') if l.strip()))
"
```

Особое внимание — эвристике уточнений: она путает уточнение с заголовком секции,
если секция стоит сразу после цены. Такие места видны как `desc`, похожий на заголовок
(`Акне`, `Осветление`), — их надо перенести в `section`.

Расхождения править в `prices.json`. Спорные места (неоднозначное уточнение, непонятная
принадлежность позиции к секции) выписать и вынести заказчику отдельным сообщением —
правки в сами цены без подтверждения не вносятся.

- [ ] **Шаг 5: Написать парити-тест состава**

Создать `generator/tests/test_prices_parity.py`:

```python
"""Состав prices.json против старого сайта.

Цены и перечень услуг переносятся со старого сайта без изменений. Тест фиксирует
число позиций по каждой услуге: если извлечение потеряет или задвоит позицию,
тест упадёт. Числа взяты подсчётом строк с символом ฿ на страницах Tilda-выгрузки.
"""
import json
from pathlib import Path

PRICES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "prices.json").read_text(encoding="utf-8")
)

EXPECTED_ITEMS = {
    "lazernaya-epilyaciya": 32,
    "elektroepilyaciya": 5,
    "saharnaya-epilyaciya": 18,
    "uhod-za-volosami": 40,
    "tokio-inkarami": 3,
    "biozavivka-volos": 4,
    "keratinovoe-vypryamlenie-volos": 7,
    "davines-naturaltech-tailoring": 1,
    "permanentnyj-makiyazh": 11,
    "igolchatyj-rf-lifting": 33,
    "smas-lifting": 7,
    "udalenie-tatuirovok-lazerom": 10,
    "fotoomolozhenie-m22": 5,
    "uhodovaya-kosmetologiya": 14,
    "botulinoterapiya": 5,
    "endosfera-terapiya": 4,
    "massazh": 4,
}

TOTAL_ITEMS = 203


def item_count(slug):
    return sum(len(section["items"]) for section in PRICES[slug])


def test_all_services_present():
    assert set(PRICES) == set(EXPECTED_ITEMS)


def test_item_count_per_service():
    actual = {slug: item_count(slug) for slug in EXPECTED_ITEMS}
    assert actual == EXPECTED_ITEMS


def test_total_item_count():
    assert sum(item_count(slug) for slug in PRICES) == TOTAL_ITEMS


def test_every_item_has_name_and_price():
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                assert item["name"].strip(), f"{slug}: позиция без названия"
                assert item["price"].strip(), f"{slug}: {item['name']} без цены"


def test_prices_are_in_baht():
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                assert "฿" in item["price"], f"{slug}: {item['name']} — цена не в батах"


def test_price_symbol_spacing_is_normalised():
    for slug, sections in PRICES.items():
        for section in sections:
            for item in section["items"]:
                assert "  ฿" not in item["price"], f"{slug}: {item['name']} — двойной отступ"
                assert not item["price"].replace(" ฿", "").endswith("฿"), (
                    f"{slug}: {item['name']} — нет отступа перед ฿"
                )
```

- [ ] **Шаг 6: Запустить тест**

Запустить:
```bash
.venv/bin/pytest generator/tests/test_prices_parity.py -q
```
Ожидаемо: `6 passed`

- [ ] **Шаг 7: Коммит**

```bash
git add generator/data/prices.json generator/tests/test_prices_parity.py
git commit -m "Прайсы: 203 позиции со старого сайта + парити-тест состава

Цены перенесены дословно, нормализован только отступ перед ฿.
Тест фиксирует число позиций по каждой из 17 услуг.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 4: Константы бизнеса и параметризация генератора

Генератор скопирован с vn и содержит захардкоженные строки про Дананг, донги и бренд.
Всё это выносится в `site.yml`.

**Файлы:**
- Создать: `generator/data/site.yml`
- Изменить: `generator/build.py` (заголовки privacy/404, sitemap, `build_llms`)
- Изменить: `generator/schema.py:55` (полная форма бренда)
- Изменить: `generator/templates/partials/footer.html.j2` (копирайт)
- Изменить: `generator/templates/home.html.j2` (alt героя, телефон, валюта, заголовок блока)
- Изменить: `generator/templates/service.html.j2` (alt героя, валюта)

**Интерфейсы:**
- Отдаёт: `site.yml` с ключами `brand`, `brand_full`, `brand_location`, `tagline`,
  `location`, `hours`, `base_url`, `base_path`, `metrika_id`, `contacts.*`, `business.*`.
  Эти ключи читают все шаблоны, `build.py` и `schema.py`.

- [ ] **Шаг 1: Записать `generator/data/site.yml`**

```yaml
brand: "Neva Beauty"                    # короткая форма — для title
brand_full: "Neva Beauty — Koh Samui"   # полная форма — шапка, футер, schema, тексты
brand_location: "Koh Samui"
tagline: "Салон красоты · Самуи"
location: "о. Самуи, Таиланд"
hours: "Приём по записи"
base_url: "https://th.neva.beauty"
# Префикс пути для ссылок на ассеты/внутренние страницы (не SEO-URL, те всегда base_url).
# Пусто = сайт в корне домена (боевой). "/th.neva.beauty" = превью на GitHub Pages по подпути.
base_path: ""
# Яндекс.Метрика: счётчик перенесён со старого сайта doctor-cosmetolog.pro.
metrika_id: 99850063
contacts:
  whatsapp_number: "79990289115"
  whatsapp_url: "https://wa.me/79990289115"
  telegram_url: "https://t.me/shyrakras"
  # Аккаунт со старым брендом — переименование отложено решением заказчика.
  instagram_url: "https://www.instagram.com/avocado.beauty.samui/"

# Единый источник фактов о бизнесе для JSON-LD (schema.org). Только реальные
# данные; чего нет — не выдумываем.
business:
  type: "BeautySalon"                 # салон красоты, не мед-клиника
  telephone: "+79990289115"           # основной телефон, он же WhatsApp
  price_range: "฿฿"                   # качественный ориентир (Google priceRange)
  currency: "THB"
  currency_note: "Указаны в тайских батах (฿)."
  language: ["Russian", "English"]    # языки обслуживания → availableLanguage в ContactPoint
  language_code: "ru"
  image: "/assets/img/hero.jpg"
  logo: "/favicon.svg"                # брендовая буква N (отдельного логотипа нет)
  same_as:
    - "https://www.instagram.com/avocado.beauty.samui/"
  address:
    locality: "Koh Samui"
    region: "Surat Thani"
    country: "TH"
    # streetAddress не публикуем — решение заказчика; адрес выдаётся при записи
  # geo не публикуем (адрес по записи)
  # openingHours не задаём — приём по записи (см. site.hours)
```

- [ ] **Шаг 2: Убрать захардкоженный бренд из заголовков privacy и 404**

В `generator/build.py` в блоке privacy заменить:

```python
    page = {"url":"/privacy/", "seo_title":"Политика конфиденциальности — Neva Beauty", "seo_desc":"",
            "schema_json": base_schema, "noindex": True}
```

на:

```python
    page = {"url": "/privacy/", "seo_title": f"Политика конфиденциальности — {site['brand']}",
            "seo_desc": "", "schema_json": base_schema, "noindex": True}
```

В блоке 404 заменить:

```python
    page = {"url": "/404.html", "seo_title": "Страница не найдена — Neva Beauty", "seo_desc": "",
            "schema_json": base_schema, "noindex": True}
```

на:

```python
    page = {"url": "/404.html", "seo_title": f"Страница не найдена — {site['brand']}",
            "seo_desc": "", "schema_json": base_schema, "noindex": True}
```

- [ ] **Шаг 3: Убрать захардкоженный домен из генерации sitemap**

В `generator/build.py` заменить строку генерации `rows`:

```python
    rows = "\n".join(f'  <url><loc>https://vn.neva.beauty{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
```

на:

```python
    rows = "\n".join(f'  <url><loc>{base_url}{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
```

- [ ] **Шаг 4: Перевести `llms.txt` на данные из конфига**

В `generator/build.py` заменить функцию `build_llms` (строки 126–153) на:

```python
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
        f"- Приём: {site['hours']}",
        f"- WhatsApp: {c['whatsapp_url']}",
        f"- Telegram: {c['telegram_url']}",
        f"- Instagram: {c['instagram_url']}",
        "",
    ]
    return "\n".join(lines)
```

Ключ `content['llms_description']` заполняется в задаче 7.

- [ ] **Шаг 5: Использовать полную форму бренда в schema.org**

В `generator/schema.py:55` заменить:

```python
    brand = site["brand"]
```

на:

```python
    # Полная форма — сущность бизнеса для поиска и ИИ должна называться одинаково везде.
    brand = site.get("brand_full", site["brand"])
```

- [ ] **Шаг 6: Убрать захардкоженный копирайт из футера**

В `generator/templates/partials/footer.html.j2` заменить:

```html
    <span>© Neva Beauty — Da Nang, Vietnam</span>
```

на:

```html
    <span>© {{ site.brand_full }}</span>
```

- [ ] **Шаг 7: Убрать захардкоженные строки из шаблона главной**

В `generator/templates/home.html.j2` внести четыре замены.

Alt героя:
```html
      <img class="hero__photo" src="{{ base_path }}/assets/img/hero.webp" alt="Безупречная кожа и макияж — центр красоты Neva Beauty" width="560" height="700">
```
→
```html
      <img class="hero__photo" src="{{ base_path }}/assets/img/hero.webp" alt="{{ home.hero_image_alt }}" width="560" height="700">
```

Телефон в контактной строке:
```html
    <a class="contact-strip__item" href="{{ site.contacts.whatsapp_url }}" target="_blank" rel="noopener">{{ icon('message-circle') }}<span>+84 357 132 621</span></a>
```
→
```html
    <a class="contact-strip__item" href="{{ site.contacts.whatsapp_url }}" target="_blank" rel="noopener">{{ icon('message-circle') }}<span>WhatsApp</span></a>
```

Российский номер в тайском салоне на первом экране выглядит как ошибка, поэтому вместо цифр
показываем название мессенджера. Номер остаётся в `href` и в схеме.

Заголовок блока преимуществ:
```html
      <div class="section-head" data-reveal><p class="eyebrow">Почему Neva Beauty</p><h2>Забота в каждой детали</h2></div>
```
→
```html
      <div class="section-head" data-reveal><p class="eyebrow">Почему {{ site.brand }}</p><h2>{{ home.benefits_title }}</h2></div>
```

Подпись валюты в блоке «Популярное»:
```html
  <div class="section-head" data-reveal><p class="eyebrow">Популярное</p><h2>Частые процедуры</h2><p>Цены указаны во вьетнамских донгах (đ).</p></div>
```
→
```html
  <div class="section-head" data-reveal><p class="eyebrow">Популярное</p><h2>Частые процедуры</h2><p>Цены {{ site.business.currency_note | lower }}</p></div>
```

- [ ] **Шаг 8: Убрать захардкоженные строки из шаблона услуги**

В `generator/templates/service.html.j2` внести две замены.

Alt героя (строка 23):
```html
        <img src="{{ base_path }}/assets/img/{{ svc.hero_image }}.webp" alt="{{ svc.title }} — Neva Beauty, Дананг" width="520" height="650">
```
→
```html
        <img src="{{ base_path }}/assets/img/{{ svc.hero_image }}.webp" alt="{{ svc.title }} — {{ site.brand_full }}" width="520" height="650">
```

Подпись валюты (строка 42):
```html
    <div class="section-head" data-reveal><p class="eyebrow">Стоимость</p><h2>Цены</h2><p>Указаны во вьетнамских донгах (đ).</p></div>
```
→
```html
    <div class="section-head" data-reveal><p class="eyebrow">Стоимость</p><h2>Цены на услугу «{{ svc.title }}»</h2><p>{{ site.business.currency_note }}</p></div>
```

Заголовок блока цен становится осмысленным `H2` с ключом услуги — этого требует промт 1.

- [ ] **Шаг 9: Убедиться, что захардкоженных следов Дананга не осталось**

Запустить:
```bash
cd "/Users/jw/Мой диск/💼 Работа/Projects/Project - th.neva.beauty"
grep -rn "Дананг\|Da Nang\|донг\|đ\|vn\.neva\.beauty\|+84" generator/ --include="*.py" --include="*.j2"
```
Ожидаемо: пустой вывод.

- [ ] **Шаг 10: Коммит**

```bash
git add generator/data/site.yml generator/build.py generator/schema.py generator/templates
git commit -m "Конфиг: константы бизнеса Самуи и параметризация генератора

site.yml с брендом, контактами, THB и адресом уровня острова. Из кода
и шаблонов убраны захардкоженные Дананг, донги, домен vn и копирайт.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 5: Прайс настоящей таблицей

Оба промта требуют, чтобы цены были размечены `<table>`: так их корректно читают
и поисковые системы, и ИИ-ассистенты. Визуально результат должен остаться прежним.

**Файлы:**
- Изменить: `generator/templates/service.html.j2:67-74` (блок `.pricelist__rows`)
- Изменить: `th.neva.beauty/assets/css/service.css:55-61` (стили прайса)
- Изменить: `th.neva.beauty/assets/css/base.css` (класс `.visually-hidden`)
- Изменить: `generator/check_prices.py:41-47` (селекторы)

**Интерфейсы:**
- Потребляет: `prices.json` из задачи 3, `site.brand_full` из задачи 4.
- Отдаёт: разметку с классами `.pricelist__table`, `.pricelist__row`, `.pricelist__name`,
  `.pricelist__desc`, `.pricelist__price`, `.combo`, `.combo__name`, `.combo__price`.
  На эти классы опирается `check_prices.py`.

- [ ] **Шаг 1: Добавить служебный класс для скрытых заголовков**

В конец `th.neva.beauty/assets/css/base.css` добавить:

```css
/* Видно скринридерам и поисковым роботам, не видно глазами: заголовки таблиц,
   у которых визуальная шапка избыточна. */
.visually-hidden{position:absolute;width:1px;height:1px;margin:-1px;padding:0;
  overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
```

- [ ] **Шаг 2: Заменить блок строк прайса на таблицу**

В `generator/templates/service.html.j2` заменить:

```html
        <div class="pricelist__rows">
          {% for it in rows %}
          <div class="pricelist__row">
            <span class="pricelist__name">{{ it.name }}{% if it.desc %}<span class="pricelist__desc">{{ it.desc }}</span>{% endif %}</span>
            <span class="pricelist__price">{{ it.price }}</span>
          </div>
          {% endfor %}
        </div>
```

на:

```html
        {% if rows %}
        <table class="pricelist__table">
          <caption class="visually-hidden">{{ sec.section or 'Цены' }} — {{ svc.title }}, {{ site.brand_full }}</caption>
          <thead class="visually-hidden">
            <tr><th scope="col">Услуга</th><th scope="col">Цена</th></tr>
          </thead>
          <tbody>
            {% for it in rows %}
            <tr class="pricelist__row">
              <th class="pricelist__name" scope="row">{{ it.name }}{% if it.desc %}<span class="pricelist__desc">{{ it.desc }}</span>{% endif %}</th>
              <td class="pricelist__price">{{ it.price }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        {% endif %}
```

- [ ] **Шаг 3: Перевести стили прайса на таблицу**

В `th.neva.beauty/assets/css/service.css` заменить блок:

```css
.pricelist__rows{background:var(--white);border:1px solid var(--line);border-radius:var(--radius-lg);padding:0 var(--sp-5)}
.pricelist__row{display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp-4);
  padding:var(--sp-4) 0;border-bottom:1px dashed var(--line)}
.pricelist__row:last-child{border-bottom:none}
.pricelist__name{display:flex;flex-direction:column;color:var(--ink)}
.pricelist__desc{font-size:var(--fs-200);color:var(--muted);font-weight:400;margin-top:2px}
.pricelist__price{font-weight:700;color:var(--rose-deep);font-variant-numeric:tabular-nums;white-space:nowrap}
```

на:

```css
.pricelist__table{width:100%;background:var(--white);border:1px solid var(--line);
  border-radius:var(--radius-lg);border-collapse:collapse;overflow:hidden}
.pricelist__row{border-bottom:1px dashed var(--line)}
.pricelist__row:last-child{border-bottom:none}
.pricelist__name{display:flex;flex-direction:column;color:var(--ink);text-align:left;
  font-weight:400;padding:var(--sp-4) var(--sp-5)}
.pricelist__desc{font-size:var(--fs-200);color:var(--muted);font-weight:400;margin-top:2px}
.pricelist__price{font-weight:700;color:var(--rose-deep);font-variant-numeric:tabular-nums;
  white-space:nowrap;text-align:right;vertical-align:baseline;padding:var(--sp-4) var(--sp-5)}
```

Отступы переехали с контейнера на ячейки — иначе `padding` на `<table>` не даст рамке
прижаться к краям. Выравнивание по краям обеспечивает сама таблица, `justify-content`
больше не нужен.

- [ ] **Шаг 4: Обновить селекторы в парити-тесте цен**

В `generator/check_prices.py` заменить:

```python
        for row in soup.select(".pricelist__row"):
            name_el = row.select_one(".pricelist__name")
```

на:

```python
        for row in soup.select("tr.pricelist__row"):
            name_el = row.select_one(".pricelist__name")
```

Остальное в функции менять не нужно: `.pricelist__desc`, `.pricelist__price`, `.combo`
и `.combo__name` сохранили имена.

- [ ] **Шаг 5: Проверить, что старые классы нигде не остались**

Запустить:
```bash
grep -rn "pricelist__rows" generator/ th.neva.beauty/assets/
```
Ожидаемо: пустой вывод.

- [ ] **Шаг 6: Коммит**

```bash
git add generator/templates/service.html.j2 generator/check_prices.py th.neva.beauty/assets/css
git commit -m "Прайс: настоящая таблица вместо дивов

Цены размечены table/thead/tbody с th scope=row — так их корректно читают
поиск и ИИ-ассистенты (требование промтов SEO и GEO). Визуально без изменений.
Заголовок блока цен стал осмысленным H2 с названием услуги.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 6: Изображения

24 изображения: 17 героев услуг, герой главной, 6 обложек разделов. Источник — фотографии
со старых страниц. Имена tilda-мусорные (`tild3630-3034-4261-a338-646436343937__1.webp`),
формат горизонтальный, нужны осмысленные имена и форматы под шаблоны vn.

**Файлы:**
- Создать: `th.neva.beauty/assets/img/*.webp` и `*.jpg` (24 пары)
- Создать: `th.neva.beauty/assets/img/CREDITS.txt`

**Интерфейсы:**
- Отдаёт: файлы с именами, на которые ссылаются `services.<slug>.hero_image`
  и `categories[].image` из задач 7–12. Имя героя услуги = слаг услуги.
  Имя обложки раздела = `cat-<слаг раздела>`.

**Целевые размеры (как в vn):**

| Назначение | Пропорция | Размер файла | Рендер в шаблоне |
|---|---|---|---|
| Герой главной | 4:5 | 800×1000 | 560×700 |
| Герой услуги | 4:5 | 760×950 | 520×650 |
| Обложка раздела | 4:3 | 900×675 | 600×440 |

- [ ] **Шаг 1: Определить исходник для каждого изображения**

На каждой странице услуги ровно одно содержательное фото — остальные три файла это
логотипы. Отобрать исходники так: для каждой страницы взять изображения из `images/`,
исключить имена, содержащие `resize`, `_20x` и `logo_-_avatar`, — останется искомое фото.
Для обложек разделов и героя главной отобрать подходящие кадры из 21 изображения
главной страницы (`page57847063.html`).

Составить таблицу соответствия «файл-исходник → целевое имя» и держать её под рукой
для шага 4.

- [ ] **Шаг 2: Написать скрипт обработки в scratchpad**

Скрипт (не в репозитории) принимает таблицу соответствия и для каждого изображения:
кроп по центру до целевой пропорции, ресайз до целевого размера с `Image.LANCZOS`,
сохранение в WebP (`quality=82`, `method=6`) и JPEG (`quality=86`, `progressive=True`,
`optimize=True`).

Кроп по центру для пропорции `target_ratio = w / h`:

```python
from PIL import Image

def crop_center(img, target_ratio):
    """Кроп по центру до заданной пропорции без искажения кадра."""
    width, height = img.size
    if width / height > target_ratio:
        new_width = round(height * target_ratio)
        left = (width - new_width) // 2
        return img.crop((left, 0, left + new_width, height))
    new_height = round(width / target_ratio)
    top = (height - new_height) // 2
    return img.crop((0, top, width, top + new_height))
```

- [ ] **Шаг 3: Запустить обработку**

Ожидаемо: в `th.neva.beauty/assets/img/` появились 48 файлов — 24 пары `.webp` + `.jpg`.

Проверить:
```bash
ls th.neva.beauty/assets/img/*.webp | wc -l
ls th.neva.beauty/assets/img/*.jpg | wc -l
```
Ожидаемо: `24` и `24`.

- [ ] **Шаг 4: Проверить кадрирование глазами**

Открыть все 24 файла и убедиться, что кроп не срезал главное: аппарат, зону процедуры,
лицо. Горизонтальный кадр 1680×1120 при переводе в 4:5 теряет по бокам около 40% ширины —
если центр композиции смещён, кроп надо задать вручную смещением. Файлы с неудачным
кадром переобработать со сдвигом.

- [ ] **Шаг 5: Сделать картинку для превью в соцсетях**

`base.html.j2` подставляет в `og:image` файл `/assets/img/hero.jpg`. Он вертикальный
800×1000, а соцсети и мессенджеры ждут горизонтальный кадр не меньше 1200×630 —
иначе превью обрежется или не покажется вовсе. На старом сайте эта разметка была сломана
(относительный путь), так что превью надо сделать правильно с первого раза.

Сделать из исходника героя главной отдельный файл `og-cover.jpg` — кроп по центру
до пропорции 1200/630, ресайз до 1200×630, JPEG `quality=86`, `optimize=True`.

Затем в `generator/templates/base.html.j2` заменить в двух местах
`page.og_image | default('/assets/img/hero.jpg')` на
`page.og_image | default('/assets/img/og-cover.jpg')` — в `<meta property="og:image">`
и в `<meta name="twitter:image">`.

Проверить:
```bash
sips -g pixelWidth -g pixelHeight th.neva.beauty/assets/img/og-cover.jpg
grep -c "og-cover" generator/templates/base.html.j2
```
Ожидаемо: `1200` и `630`, затем `2`.

- [ ] **Шаг 6: Записать источники изображений**

Создать `th.neva.beauty/assets/img/CREDITS.txt`:

```
# Источники изображений

Фотографии процедур и обложки разделов взяты из материалов салона —
Tilda-экспорт старого сайта doctor-cosmetolog.pro, папка images/.
Показывают реальные аппараты и процедуры салона на Самуи.

Обработка: кроп по центру до пропорции шаблона, ресайз, WebP + JPG-фолбэк.

<целевое имя>: <описание кадра> (<исходный tild…-файл>)
```

Заполнить последний блок по таблице соответствия из шага 1 — по строке на каждое
из 24 изображений плюс `og-cover`.

- [ ] **Шаг 7: Коммит**

```bash
git add th.neva.beauty/assets/img generator/templates/base.html.j2
git commit -m "Изображения: 24 фото со старого сайта под шаблоны vn

17 героев услуг, герой главной, 6 обложек разделов. Кроп по центру,
ресайз под размеры vn, WebP с JPG-фолбэком, осмысленные имена вместо
tilda-мусора. Отдельная горизонтальная картинка og-cover 1200×630 для
превью в соцсетях — на старом сайте оно не работало. Источники в CREDITS.txt.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 7: Таксономия и главная страница

**Файлы:**
- Создать: `generator/data/content.yml` (ключи `home`, `llms_description`, `categories`;
  ключ `services` наполняется в задачах 8–12)

**Интерфейсы:**
- Потребляет: `site.yml` из задачи 4, `prices.json` из задачи 3.
- Отдаёт: `content["home"]`, `content["llms_description"]`, `content["categories"]` —
  список из 6 словарей с ключами `slug`, `title`, `nav_label`, `image`, `seo_title`,
  `seo_desc`, `intro`, `services`, `faq`. Ключ `services` каждой категории — список слагов,
  которые задачи 8–12 обязаны определить в `content["services"]`.

**Таксономия (порядок в меню — как задан):**

| Слаг раздела | Заголовок | `nav_label` | Слаги услуг |
|---|---|---|---|
| `volosy` | Волосы | Волосы | `uhod-za-volosami`, `tokio-inkarami`, `biozavivka-volos`, `keratinovoe-vypryamlenie-volos`, `davines-naturaltech-tailoring` |
| `epilyaciya` | Эпиляция | Эпиляция | `lazernaya-epilyaciya`, `elektroepilyaciya`, `saharnaya-epilyaciya` |
| `apparatnaya-kosmetologiya` | Аппаратная косметология | Аппаратная | `igolchatyj-rf-lifting`, `smas-lifting`, `udalenie-tatuirovok-lazerom`, `fotoomolozhenie-m22` |
| `kosmetologiya` | Косметология | Косметология | `uhodovaya-kosmetologiya`, `botulinoterapiya` |
| `korrekciya-figury` | Коррекция фигуры | Фигура | `endosfera-terapiya`, `massazh` |
| `makiyazh` | Макияж | Макияж | `permanentnyj-makiyazh` |

У раздела «Макияж» одна услуга, поэтому `enrich_categories` не создаст для него страницу,
а пункт меню поведёт сразу на `/permanentnyj-makiyazh/`. Это штатное поведение генератора,
менять его не нужно.

- [ ] **Шаг 1: Записать шапку `content.yml` — главную и описание для ИИ**

```yaml
llms_description: >-
  Neva Beauty — Koh Samui — салон красоты на острове Самуи (Таиланд): косметология,
  аппаратные процедуры, лазерная и сахарная эпиляция, уход за волосами, перманентный
  макияж и коррекция фигуры. Приём по записи, обслуживание на русском и английском.

home:
  seo_title: "Салон красоты и косметология на Самуи — Neva Beauty"
  seo_desc: "Neva Beauty — Koh Samui: косметология, аппаратные процедуры, лазерная эпиляция, уход за волосами и перманентный макияж на острове Самуи. Приём по записи."
  hero_kicker: "Красота под тропическим солнцем"
  hero_title_lines: ["Салон красоты", "Neva Beauty", "на Самуи"]
  hero_sub: "Косметология, аппаратные процедуры, эпиляция и уход за волосами на острове Самуи."
  hero_image_alt: "Уходовая процедура для лица — салон красоты Neva Beauty — Koh Samui"
  benefits_title: "Забота в каждой детали"
  about_lead: >-
    Neva Beauty — Koh Samui — салон красоты на острове Самуи (Таиланд). Здесь делают
    уходовую косметологию, аппаратные процедуры, лазерную, электро- и сахарную эпиляцию,
    уход за волосами, перманентный макияж и коррекцию фигуры. Приём по записи,
    обслуживание на русском и английском языках.
```

Ключ `about_lead` уже используется шаблоном главной vn; проверить его наличие
в `home.html.j2` и, если он там не выводится, не добавлять — лишних ключей не заводим.

- [ ] **Шаг 2: Дописать блок `benefits` главной**

6 карточек, каждая — словарь `{icon, title, text}`. Доступные иконки лежат
в `th.neva.beauty/assets/icons/`: `activity`, `arrow-right`, `check`, `clock`, `cpu`,
`droplet`, `gem`, `heart`, `instagram`, `map-pin`, `message-circle`, `scan-line`, `send`,
`shield`, `sparkles`, `star`, `sun`, `target`, `user-check`, `waves`, `zap`.

Тексты пишутся по фактам старого сайта, без обещаний результата. Пример формы:

```yaml
  benefits:
    - {icon: "cpu", title: "Аппаратные методики", text: "Лазер, ультразвук, RF и вакуумно-роликовый массаж — процедуры выполняются на профессиональных аппаратах."}
```

- [ ] **Шаг 3: Дописать блок `popular` главной**

6 позиций вида `{slug, label, name}`, где `name` — точное название позиции из
`prices.json` для этого слага. Шаблон главной ищет цену по совпадению названия,
поэтому опечатка приведёт к пустой цене в карточке.

```yaml
  popular:
    - {slug: "lazernaya-epilyaciya", label: "Лазерная эпиляция", name: "Глубокое бикини"}
```

Остальные пять подобрать из услуг разных разделов, сверив названия с `prices.json`.

- [ ] **Шаг 4: Дописать `faq` главной**

5 вопросов-ответов. В ответах разрешены HTML-ссылки: внутренние относительными слагами
и плейсхолдеры мессенджеров `{whatsapp}`, `{telegram}`, `{instagram}` — `build.py`
подставит URL из `site.yml`. Формат:

```yaml
  faq:
    - q: "Где находится Neva Beauty — Koh Samui?"
      a: 'Neva Beauty — Koh Samui — салон красоты на острове Самуи (Таиланд). Точный адрес и как добраться подскажем при записи в <a href="{whatsapp}" target="_blank" rel="noopener">WhatsApp</a> или <a href="{telegram}" target="_blank" rel="noopener">Telegram</a>.'
```

Остальные четыре: как записаться, на каких языках обслуживают, какие процедуры делают,
нужна ли предварительная запись.

- [ ] **Шаг 5: Записать 6 разделов**

Для каждого раздела из таблицы таксономии — блок вида:

```yaml
categories:
  - slug: volosy
    title: "Волосы"
    nav_label: "Волосы"
    image: "cat-volosy"
    seo_title: "Уход за волосами на Самуи — стрижка, окрашивание, ботокс"
    seo_desc: "Стрижки, окрашивание, осветление, кератиновое выпрямление, ботокс волос, Tokio Inkarami и Davines Naturaltech в салоне Neva Beauty на Самуи."
    intro: >
      Уход за волосами в салоне Neva Beauty — Koh Samui (о. Самуи, Таиланд) — это стрижки,
      окрашивание и осветление, восстановление Tokio Inkarami, биозавивка, кератиновое
      выпрямление и ботокс волос, а также индивидуальный уход Davines Naturaltech.
    services: ["uhod-za-volosami", "tokio-inkarami", "biozavivka-volos", "keratinovoe-vypryamlenie-volos", "davines-naturaltech-tailoring"]
    faq:
      - q: "Какие услуги по волосам есть на Самуи в Neva Beauty?"
        a: 'В салоне Neva Beauty — Koh Samui доступны <a href="/uhod-za-volosami/">стрижки, окрашивание и осветление</a>, восстановление <a href="/tokio-inkarami/">Tokio Inkarami</a>, <a href="/biozavivka-volos/">биозавивка</a>, <a href="/keratinovoe-vypryamlenie-volos/">кератиновое выпрямление и ботокс волос</a> и подбор индивидуального ухода <a href="/davines-naturaltech-tailoring/">Davines Naturaltech</a>.'
```

Каждый раздел получает 4–5 вопросов FAQ. Обязательные среди них: какие услуги входят
в раздел, чем услуги раздела отличаются друг от друга, сколько стоит, как записаться.

- [ ] **Шаг 6: Проверить, что YAML читается**

Запустить:
```bash
.venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
print('разделов:', len(c['categories']))
print('услуг в разделах:', sum(len(x['services']) for x in c['categories']))
"
```
Ожидаемо:
```
разделов: 6
услуг в разделах: 17
```

- [ ] **Шаг 7: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: таксономия из 6 разделов и главная страница

6 разделов из меню старого сайта, 17 услуг распределены. Главная:
заголовки, преимущества, популярные процедуры и FAQ.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задачи 8–12: Контент услуг по разделам

Пять однотипных задач, по одной на раздел. Разбиение по разделам, а не по услугам, даёт
связный текст внутри раздела: перелинковка и сравнения услуг пишутся, когда все услуги
раздела перед глазами.

**Общие правила для всех пяти задач:**

Источник фактов — соответствующая страница Tilda-выгрузки. Из неё берутся: суть услуги,
блок преимуществ, длительность, число сеансов, зоны, показания, подготовка,
противопоказания. Ничего сверх этого не добавляется.

Формулировки со старых страниц, которые переносить нельзя, потому что обещают результат:
«удаление волос навсегда», «гарантированно разрушает волосяной фолликул»,
«безболезненное удаление», «только гладкая кожа на всю жизнь», «эффект заметен сразу».
Заменяются на описание механизма и honest-формулировки: «воздействует на корень волоса»,
«большинство переносит комфортно», «число сеансов подбирают индивидуально».

Каждая услуга описывается блоком:

```yaml
  <слаг>:
    title: "<название услуги>"
    category: "<заголовок раздела>"        # перезаписывается enrich_categories, но нужен для читаемости
    seo_title: "<услуга> на Самуи — Neva Beauty"      # 50–60 символов, без восклицательных знаков
    seo_desc: "<140–160 символов: ключ, польза, мягкий призыв, без обещаний результата>"
    hero_image: "<слаг>"                   # имя файла из задачи 6, без расширения
    intro: >
      <2–4 предложения, самодостаточные вне контекста страницы: явно назвать услугу,
      бренд «Neva Beauty — Koh Samui» и локацию «о. Самуи, Таиланд». Это тот текст,
      который ИИ-ассистенты цитируют в ответах.>
    benefits:
      - {icon: "<иконка>", title: "<заголовок>", text: "<1–2 предложения>"}
      # 4 карточки; иконки — из th.neva.beauty/assets/icons/
    related: ["<слаг>", "<слаг>", "<слаг>"]   # 3 смежные услуги, осмысленно связанные
    faq:
      - q: "<вопрос как его задаёт клиент>"
        a: "<прямой ответ первым предложением, 40–60 слов>"
      # 5 вопросов
```

Обязательные вопросы FAQ у каждой услуги: сколько стоит на Самуи, сколько сеансов нужно
или сколько держится результат, есть ли противопоказания или как готовиться, как записаться.
В ответе про цену — ссылка на раздел «Цены» этой страницы, конкретные цифры не дублируются:
единственный источник цен `prices.json`.

В ответе про запись — плейсхолдеры `{whatsapp}`, `{telegram}`, `{instagram}`.

Туристический контекст учитывается там, где он есть на исходной странице: сколько дней
займёт курс, можно ли на солнце после процедуры, держится ли результат во влажном климате.

**Полный образец описанной услуги.** По этой форме пишутся все 17:

```yaml
services:
  tokio-inkarami:
    title: "Tokio Inkarami"
    category: "Волосы"
    seo_title: "Tokio Inkarami на Самуи — восстановление волос"
    seo_desc: "Восстановление волос по японской технологии Tokio Inkarami в салоне Neva Beauty на Самуи. Подходит осветлённым и повреждённым волосам. Приём по записи."
    hero_image: "tokio-inkarami"
    intro: >
      Tokio Inkarami в салоне Neva Beauty — Koh Samui (о. Самуи, Таиланд) — японская
      процедура восстановления волос. Состав работает внутри волоса, укрепляя его
      структуру, и подходит для всех типов волос, включая осветлённые и повреждённые.
      Стоимость зависит от длины волос и указана в разделе «Цены» на этой странице.
    benefits:
      - {icon: "droplet", title: "Работа внутри волоса", text: "Состав проникает в структуру волоса, а не остаётся плёнкой на поверхности."}
      - {icon: "shield", title: "Для повреждённых волос", text: "Подходит осветлённым и окрашенным волосам, ослабленным после процедур."}
      - {icon: "sun", title: "Для тропического климата", text: "Помогает волосам, которые ежедневно переносят солнце, море и влажность Самуи."}
      - {icon: "sparkles", title: "Гладкость и блеск", text: "Волосы становятся более гладкими и послушными в укладке."}
    related: ["uhod-za-volosami", "keratinovoe-vypryamlenie-volos", "davines-naturaltech-tailoring"]
    faq:
      - q: "Сколько стоит Tokio Inkarami на Самуи?"
        a: "Стоимость процедуры Tokio Inkarami в салоне Neva Beauty — Koh Samui зависит от длины волос. Актуальные цены в тайских батах (฿) указаны в разделе «Цены» на этой странице. Точную стоимость для вашей длины и густоты подскажут при записи."
      - q: "Кому подходит Tokio Inkarami?"
        a: "Процедура подходит для всех типов волос, в том числе осветлённых, окрашенных и повреждённых. В салоне Neva Beauty — Koh Samui её чаще выбирают, когда волосы ослаблены после окрашивания или пострадали от солнца и морской воды."
      - q: "Сколько держится результат?"
        a: "Длительность эффекта индивидуальна: она зависит от исходного состояния волос, частоты мытья и домашнего ухода. На консультации в Neva Beauty — Koh Samui подберут подходящий интервал повторения процедуры."
      - q: "Чем Tokio Inkarami отличается от кератинового выпрямления?"
        a: 'Tokio Inkarami — процедура восстановления: она работает со структурой волоса и не меняет его форму. <a href="/keratinovoe-vypryamlenie-volos/">Кератиновое выпрямление и ботокс волос</a> распрямляют волос и убирают пушистость. Выбрать подходящее помогут на консультации.'
      - q: "Как записаться на Tokio Inkarami?"
        a: 'Записаться в салон Neva Beauty — Koh Samui можно через <a href="{whatsapp}" target="_blank" rel="noopener">WhatsApp</a>, <a href="{telegram}" target="_blank" rel="noopener">Telegram</a> или <a href="{instagram}" target="_blank" rel="noopener">Instagram</a>. Приём ведётся по предварительной записи, обслуживание — на русском и английском языках.'
```

Обратите внимание на две вещи в образце. Первая: `intro` самодостаточен — из него понятно,
что за услуга, чей это салон и где он находится, даже если абзац вырван из контекста
страницы. Именно такие абзацы цитируют ИИ-ассистенты. Вторая: в ответе про цену нет
конкретных цифр, только отсылка к разделу «Цены» — единственный источник цен `prices.json`,
дублирование в тексте рано или поздно разойдётся с прайсом.

**Проверка после каждой из пяти задач:**

```bash
.venv/bin/python generator/build.py && .venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
print('описано услуг:', len(c.get('services', {})))
"
```

Полная сборка заработает только после задачи 12, когда описаны все 17 услуг: `build.py`
обходит `content["categories"]` и требует, чтобы каждый слаг из `services` был описан.
До этого проверяется только чтение YAML.

---

### Задача 8: Услуги раздела «Волосы»

**Файлы:**
- Изменить: `generator/data/content.yml` (добавить ключ `services` с 5 услугами)

**Интерфейсы:**
- Отдаёт: `content["services"]["uhod-za-volosami"]`, `["tokio-inkarami"]`,
  `["biozavivka-volos"]`, `["keratinovoe-vypryamlenie-volos"]`,
  `["davines-naturaltech-tailoring"]`.

| Слаг | Название | Исходная страница | Позиций прайса |
|---|---|---|---|
| `uhod-za-volosami` | Уход за волосами | `page74422157.html` | 40 |
| `tokio-inkarami` | Tokio Inkarami | `page74519913.html` | 3 |
| `biozavivka-volos` | Биозавивка волос | `page81744456.html` | 4 |
| `keratinovoe-vypryamlenie-volos` | Кератиновое выпрямление и ботокс волос | `page81753636.html` | 7 |
| `davines-naturaltech-tailoring` | Davines Naturaltech Tailoring | `page82202466.html` | 1 |

- [ ] **Шаг 1: Прочитать 5 исходных страниц и выписать факты**

Для каждой страницы снять теги и выписать: подзаголовок, вводный абзац, все карточки
блока преимуществ, секции прайса. Пример команды для одной страницы:

```bash
cd "OLD - doctor.cosmetolog.pro" && ../.venv/bin/python -c "
import re, html
s = open('page74422157.html', encoding='utf-8').read()
s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
t = html.unescape(re.sub(r'<[^>]+>', '\n', s))
print('\n'.join(l.strip() for l in t.split('\n') if l.strip())[:6000])
"
```

- [ ] **Шаг 2: Описать 5 услуг в `content.yml`**

Добавить ключ `services` с пятью блоками по общей форме выше.

Смысловая перелинковка внутри раздела: `uhod-za-volosami` ↔ `tokio-inkarami` ↔
`davines-naturaltech-tailoring` (уход и восстановление), `keratinovoe-vypryamlenie-volos`
↔ `biozavivka-volos` (изменение формы волоса).

У `keratinovoe-vypryamlenie-volos` в FAQ обязателен вопрос «Чем кератиновое выпрямление
отличается от ботокса волос?» — обе процедуры на одной странице и в одном прайсе,
клиент выбирает между ними.

- [ ] **Шаг 3: Проверить, что YAML читается и услуги на месте**

Запустить:
```bash
.venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
s = c['services']
for slug in ['uhod-za-volosami','tokio-inkarami','biozavivka-volos','keratinovoe-vypryamlenie-volos','davines-naturaltech-tailoring']:
    v = s[slug]
    assert len(v['benefits']) == 4, f'{slug}: преимуществ {len(v[\"benefits\"])}, нужно 4'
    assert len(v['faq']) == 5, f'{slug}: вопросов {len(v[\"faq\"])}, нужно 5'
    assert len(v['related']) == 3, f'{slug}: связанных {len(v[\"related\"])}, нужно 3'
print('раздел «Волосы»: 5 услуг описаны')
"
```
Ожидаемо: `раздел «Волосы»: 5 услуг описаны`

- [ ] **Шаг 4: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: 5 услуг раздела «Волосы»

Уход за волосами, Tokio Inkarami, биозавивка, кератиновое выпрямление
и ботокс, Davines Naturaltech. Факты со старых страниц, обещания
результата убраны.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Задача 9: Услуги раздела «Эпиляция»

**Файлы:**
- Изменить: `generator/data/content.yml`

**Интерфейсы:**
- Отдаёт: `content["services"]["lazernaya-epilyaciya"]`, `["elektroepilyaciya"]`,
  `["saharnaya-epilyaciya"]`.

| Слаг | Название | Исходная страница | Позиций прайса |
|---|---|---|---|
| `lazernaya-epilyaciya` | Лазерная эпиляция | `page65556759.html` | 32 |
| `elektroepilyaciya` | Электроэпиляция | `page79940116.html` | 5 |
| `saharnaya-epilyaciya` | Сахарная эпиляция | `page67695417.html` | 18 |

- [ ] **Шаг 1: Прочитать 3 исходные страницы и выписать факты**

Команда та же, что в задаче 8, шаг 1, с подстановкой имён страниц.

- [ ] **Шаг 2: Описать 3 услуги в `content.yml`**

Три метода эпиляции конкурируют между собой, поэтому у каждого в FAQ обязателен вопрос
на сравнение: «Чем лазерная эпиляция отличается от сахарной?», «Когда нужна
электроэпиляция, а когда лазерная?». Ответы связывают страницы ссылками —
это и перелинковка, и то, что ИИ-ассистенты цитируют по сравнительным запросам.

`related` у всех трёх — две другие услуги раздела плюс одна смежная лазерная
(`udalenie-tatuirovok-lazerom`).

На странице лазерной эпиляции старый текст утверждает «удаление волос на несколько лет,
а в некоторых случаях навсегда» и «практически безболезненно». Переписать на описание
механизма и индивидуальной переносимости.

На странице электроэпиляции старый текст утверждает «единственный метод, который
гарантированно разрушает волосяной фолликул навсегда» и «только гладкая кожа на всю
жизнь». Это самое сильное обещание результата на всём сайте — переписать обязательно.

Прайс лазерной эпиляции содержит секцию комбо-наборов: 8 позиций начинаются
с перечисления зон. Шаблон выделяет комбо в карточки по префиксу `КОМБО`/`Комбо`.
На старом сайте такого префикса нет, поэтому комбо-наборы отрендерятся обычными строками
таблицы — это корректно и допустимо; переименовывать позиции прайса нельзя.

- [ ] **Шаг 3: Проверить, что YAML читается и услуги на месте**

Запустить:
```bash
.venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
s = c['services']
for slug in ['lazernaya-epilyaciya','elektroepilyaciya','saharnaya-epilyaciya']:
    v = s[slug]
    assert len(v['benefits']) == 4 and len(v['faq']) == 5 and len(v['related']) == 3, slug
print('раздел «Эпиляция»: 3 услуги описаны, всего:', len(s))
"
```
Ожидаемо: `раздел «Эпиляция»: 3 услуги описаны, всего: 8`

- [ ] **Шаг 4: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: 3 услуги раздела «Эпиляция»

Лазерная, электро- и сахарная эпиляция со сравнительными FAQ.
Обещания «навсегда» и «гарантированно» со старых страниц убраны.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Задача 10: Услуги раздела «Аппаратная косметология»

**Файлы:**
- Изменить: `generator/data/content.yml`

**Интерфейсы:**
- Отдаёт: `content["services"]["igolchatyj-rf-lifting"]`, `["smas-lifting"]`,
  `["udalenie-tatuirovok-lazerom"]`, `["fotoomolozhenie-m22"]`.

| Слаг | Название | Исходная страница | Позиций прайса |
|---|---|---|---|
| `igolchatyj-rf-lifting` | Игольчатый РФ-лифтинг | `page79715986.html` | 33 |
| `smas-lifting` | SMAS-лифтинг | `page79750196.html` | 7 |
| `udalenie-tatuirovok-lazerom` | Удаление тату и татуажа | `page81553916.html` | 10 |
| `fotoomolozhenie-m22` | Фотоомоложение M22 | `page85635656.html` | 5 |

- [ ] **Шаг 1: Прочитать 4 исходные страницы и выписать факты**

- [ ] **Шаг 2: Описать 4 услуги в `content.yml`**

Названия аппаратов — узнаваемые сущности, писать строго единообразно по всему сайту:
`M22`, `SMAS-лифтинг`, `игольчатый РФ-лифтинг`. Разнобой в написании мешает ИИ
собрать единую сущность бизнеса.

`igolchatyj-rf-lifting` и `smas-lifting` конкурируют — у обоих в FAQ вопрос на сравнение
со ссылкой на соседнюю страницу.

`fotoomolozhenie-m22` — единственная услуга, где туристический контекст в исходном тексте
явный: «проживание на Самуи — это ежедневное солнце, которое старит кожу». Вынести это
в `intro` и обязательно добавить в FAQ вопрос про солнце после процедуры.

`udalenie-tatuirovok-lazerom` — старый текст обещает «стираем нежелательные татуировки
и татуаж навсегда». Переписать: число сеансов зависит от пигмента, глубины и давности.

- [ ] **Шаг 3: Проверить, что YAML читается и услуги на месте**

Запустить:
```bash
.venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
s = c['services']
for slug in ['igolchatyj-rf-lifting','smas-lifting','udalenie-tatuirovok-lazerom','fotoomolozhenie-m22']:
    v = s[slug]
    assert len(v['benefits']) == 4 and len(v['faq']) == 5 and len(v['related']) == 3, slug
print('раздел «Аппаратная»: 4 услуги описаны, всего:', len(s))
"
```
Ожидаемо: `раздел «Аппаратная»: 4 услуги описаны, всего: 12`

- [ ] **Шаг 4: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: 4 услуги раздела «Аппаратная косметология»

Игольчатый РФ-лифтинг, SMAS-лифтинг, удаление тату и татуажа,
фотоомоложение M22. Названия аппаратов приведены к единому написанию.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Задача 11: Услуги раздела «Косметология»

**Файлы:**
- Изменить: `generator/data/content.yml`

**Интерфейсы:**
- Отдаёт: `content["services"]["uhodovaya-kosmetologiya"]`, `["botulinoterapiya"]`.

| Слаг | Название | Исходная страница | Позиций прайса |
|---|---|---|---|
| `uhodovaya-kosmetologiya` | Уходовая косметология | `page82430046.html` | 14 |
| `botulinoterapiya` | Ботулинотерапия | `page82442846.html` | 5 |

- [ ] **Шаг 1: Прочитать 2 исходные страницы и выписать факты**

- [ ] **Шаг 2: Описать 2 услуги в `content.yml`**

`botulinoterapiya` — единственная инъекционная процедура на сайте и самая чувствительная
по YMYL. Медицинский статус не заявляется, диагнозы не ставятся, результат не обещается.
Исходный текст говорит «эффект сохраняется до 6 месяцев» — это факт со страницы,
его сохраняем. В FAQ обязателен вопрос про противопоказания и про то, что процедуру
выполняет специалист.

`uhodovaya-kosmetologiya` — прайс с секциями: чистки, уходы при акне, HydraFacial,
дополнительные услуги. Название `HydraFacial` писать единообразно.

- [ ] **Шаг 3: Проверить, что YAML читается и услуги на месте**

Запустить:
```bash
.venv/bin/python -c "
import yaml, pathlib
c = yaml.safe_load(pathlib.Path('generator/data/content.yml').read_text(encoding='utf-8'))
s = c['services']
for slug in ['uhodovaya-kosmetologiya','botulinoterapiya']:
    v = s[slug]
    assert len(v['benefits']) == 4 and len(v['faq']) == 5 and len(v['related']) == 3, slug
print('раздел «Косметология»: 2 услуги описаны, всего:', len(s))
"
```
Ожидаемо: `раздел «Косметология»: 2 услуги описаны, всего: 14`

- [ ] **Шаг 4: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: 2 услуги раздела «Косметология»

Уходовая косметология и ботулинотерапия. Инъекционная процедура описана
без заявления медстатуса и без обещаний результата.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Задача 12: Услуги разделов «Коррекция фигуры» и «Макияж»

**Файлы:**
- Изменить: `generator/data/content.yml`

**Интерфейсы:**
- Отдаёт: `content["services"]["endosfera-terapiya"]`, `["massazh"]`,
  `["permanentnyj-makiyazh"]`. После этой задачи описаны все 17 услуг и `build.py`
  собирает сайт целиком.

| Слаг | Название | Исходная страница | Позиций прайса |
|---|---|---|---|
| `endosfera-terapiya` | Эндосфера-терапия | `page78032606.html` | 4 |
| `massazh` | Профессиональный массаж | `page81723876.html` | 4 |
| `permanentnyj-makiyazh` | Перманентный макияж | `page60802019.html` | 11 |

- [ ] **Шаг 1: Прочитать 3 исходные страницы и выписать факты**

- [ ] **Шаг 2: Описать 3 услуги в `content.yml`**

`massazh` содержит поминутный тариф `35 ฿/минута` — в FAQ про стоимость это стоит назвать
явно, потому что формат цены отличается от остальных услуг сайта.

`permanentnyj-makiyazh` — прайс построен парами «1-я процедура» и «2-я процедура (1-2 мес)».
В FAQ обязателен вопрос, зачем нужна вторая процедура и через сколько её делают: без этого
клиент читает прайс как двойную цену. Исходный текст даёт факт «эффект сохраняется
от 1,5 до 3 лет в зависимости от типа кожи» — сохраняем. Формулировку
«Долговечно, безопасно и безупречно» не переносим.

`permanentnyj-makiyazh` — единственная услуга своего раздела, у него нет соседей
по разделу. `related` заполняется смежными по смыслу: `udalenie-tatuirovok-lazerom`
(удаление татуажа), `uhodovaya-kosmetologiya`, `lazernaya-epilyaciya`.

- [ ] **Шаг 3: Собрать сайт целиком**

Запустить:
```bash
.venv/bin/python generator/build.py
```
Ожидаемо: перечисление записанных файлов, среди них `th.neva.beauty/index.html`,
17 папок услуг, 5 папок разделов, `privacy/index.html`, `404.html`, `sitemap.xml`,
`llms.txt`, `CNAME`, и строка про размер `bundle.min.css`.

- [ ] **Шаг 4: Прогнать парити-тест цен**

Запустить:
```bash
cd generator && ../.venv/bin/python check_prices.py; cd ..
```
Ожидаемо: `expected_items=203 rendered_items=203` и `PRICE PARITY OK`

- [ ] **Шаг 5: Прогнать все тесты**

Запустить:
```bash
.venv/bin/pytest generator/tests -q
```
Ожидаемо: `18 passed`

- [ ] **Шаг 6: Посмотреть сайт локально**

Запустить:
```bash
cd th.neva.beauty && ../.venv/bin/python -m http.server 8000
```
Открыть `http://localhost:8000` и пройти по всем 23 страницам: главная, 5 разделов,
17 услуг. Проверить, что везде есть картинка, прайс, FAQ и работает меню.

- [ ] **Шаг 7: Коммит**

```bash
git add generator/data/content.yml
git commit -m "Контент: услуги разделов «Коррекция фигуры» и «Макияж»

Эндосфера-терапия, массаж, перманентный макияж. Все 17 услуг описаны,
сайт собирается целиком и проходит парити-тест на 203 позиции.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 13: Проверки качества страниц

Автоматические проверки, которые ловят то, что парити-тест цен не видит: следы старого
бренда, битые ссылки, отсутствующие картинки, дубли метатегов, сломанный JSON-LD.

**Файлы:**
- Создать: `generator/check_content.py`

**Интерфейсы:**
- Потребляет: собранный сайт в `th.neva.beauty/`.
- Отдаёт: код возврата 0 при успехе, 1 при любом нарушении; отчёт в stdout.

- [ ] **Шаг 1: Написать скрипт проверок**

Создать `generator/check_content.py`:

```python
"""Проверки качества собранных страниц.

Ловит то, что парити-тест цен не видит: следы старого бренда, битые внутренние
ссылки, отсутствующие изображения, дубли метатегов, невалидный JSON-LD.
Падает (exit 1) при любом нарушении.
Запуск: .venv/bin/python generator/check_content.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "th.neva.beauty"

# Следы старого бренда. Instagram-аккаунт avocado.beauty.samui — исключение:
# переименование отложено решением заказчика, ссылка на него легальна.
FORBIDDEN = ["Avocado", "avocado", "doctor-cosmetolog.pro", "Дананг", "Da Nang"]
ALLOWED_BRAND_TRACE = "avocado.beauty.samui"

TITLE_MAX = 65
DESC_MIN, DESC_MAX = 120, 170

problems = []


def report(page, message):
    problems.append(f"{page}: {message}")


def pages():
    return sorted(SITE.rglob("*.html"))


def rel(path):
    return str(path.relative_to(SITE))


def check_forbidden(path, text):
    cleaned = text.replace(ALLOWED_BRAND_TRACE, "")
    for needle in FORBIDDEN:
        if needle in cleaned:
            report(rel(path), f"след старого бренда или города: {needle!r}")


def check_headings(path, soup):
    h1s = soup.select("main h1")
    if len(h1s) != 1:
        report(rel(path), f"заголовков h1 в main: {len(h1s)}, нужен ровно один")


def check_images(path, soup):
    for img in soup.select("img"):
        src = img.get("src", "")
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        target = SITE / src.lstrip("/")
        if not target.exists():
            report(rel(path), f"нет файла изображения: {src}")
        if not img.get("alt", "").strip():
            report(rel(path), f"изображение без alt: {src}")
        if not (img.get("width") and img.get("height")):
            report(rel(path), f"изображение без width/height: {src}")


def check_links(path, soup):
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        target_path = urlsplit(href).path
        if not target_path.startswith("/"):
            continue
        target = SITE / target_path.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        elif not target.suffix:
            target = target.with_suffix(".html")
        if not target.exists():
            report(rel(path), f"битая внутренняя ссылка: {href}")


def check_schema(path, soup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError) as exc:
            report(rel(path), f"невалидный JSON-LD: {exc}")


def check_meta(path, soup, titles, descriptions):
    title_el = soup.select_one("title")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        report(rel(path), "нет title")
    elif len(title) > TITLE_MAX:
        report(rel(path), f"title длиной {len(title)}, максимум {TITLE_MAX}")
    titles[title].append(rel(path))

    desc_el = soup.select_one('meta[name="description"]')
    desc = desc_el.get("content", "").strip() if desc_el else ""
    noindex = soup.select_one('meta[name="robots"][content*="noindex"]') is not None
    if noindex:
        return
    if not desc:
        report(rel(path), "нет meta description")
    elif not DESC_MIN <= len(desc) <= DESC_MAX:
        report(rel(path), f"meta description длиной {len(desc)}, нужно {DESC_MIN}–{DESC_MAX}")
    descriptions[desc].append(rel(path))


def check_duplicates(label, groups):
    for value, where in groups.items():
        if value and len(where) > 1:
            problems.append(f"дубль {label} на страницах {', '.join(where)}: {value!r}")


def main():
    titles, descriptions = defaultdict(list), defaultdict(list)
    files = pages()
    if not files:
        print("Сайт не собран — нечего проверять. Запустите generator/build.py")
        return 1
    for path in files:
        text = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(text, "html.parser")
        check_forbidden(path, text)
        check_headings(path, soup)
        check_images(path, soup)
        check_links(path, soup)
        check_schema(path, soup)
        check_meta(path, soup, titles, descriptions)
    check_duplicates("title", titles)
    check_duplicates("meta description", descriptions)

    if problems:
        print(f"НАЙДЕНО ПРОБЛЕМ: {len(problems)}")
        for line in problems:
            print(" ", line)
        return 1
    print(f"проверено страниц: {len(files)}")
    print("CONTENT CHECKS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Шаг 2: Запустить проверки**

Запустить:
```bash
.venv/bin/python generator/check_content.py
```
Ожидаемо при первом запуске: список найденных проблем. Разобрать каждую.
Типичные находки: `meta description` вне лимита длины, `title` длиннее 65 символов,
дубль описания на двух страницах.

- [ ] **Шаг 3: Исправить найденное и добиться зелёного прогона**

Править `content.yml`, пересобирать, перепроверять до:
```
проверено страниц: 25
CONTENT CHECKS OK
```

- [ ] **Шаг 4: Добавить проверки в workflow деплоя**

В `.github/workflows/deploy.yml` после шага `Generate site` добавить:

```yaml
      - name: Check prices
        working-directory: generator
        run: python check_prices.py

      - name: Check content
        run: python generator/check_content.py

      - name: Unit tests
        run: pytest generator/tests -q
```

Так сломанные цены или битая ссылка не уедут в прод: деплой не состоится.

- [ ] **Шаг 5: Коммит**

```bash
git add generator/check_content.py .github/workflows/deploy.yml generator/data/content.yml
git commit -m "Проверки: качество страниц и защита деплоя

check_content.py ловит следы старого бренда, битые ссылки, картинки без
alt и размеров, дубли метатегов и невалидный JSON-LD. Проверки и тесты
подключены в workflow — деплой падает при нарушении.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

## Задача 14: Публикация

**Файлы:**
- Создать: `th.neva.beauty/robots.txt`
- Изменить: `generator/build.py` (копирование `robots.txt` в артефакт не нужно —
  файл лежит в выходной папке и коммитится; убедиться, что `build.py` его не затирает)

**Интерфейсы:**
- Отдаёт: живой сайт на `https://th.neva.beauty`.

- [ ] **Шаг 1: Записать `robots.txt`**

Создать `th.neva.beauty/robots.txt`:

```
User-agent: *
Allow: /

# ИИ-ассистенты: разрешаем обход и цитирование — цель попадать в ИИ-ответы.
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: YandexBot
Allow: /

Sitemap: https://th.neva.beauty/sitemap.xml
```

- [ ] **Шаг 2: Убедиться, что sitemap содержит 23 страницы**

Запустить:
```bash
.venv/bin/python generator/build.py >/dev/null && grep -c "<loc>" th.neva.beauty/sitemap.xml
```
Ожидаемо: `23`

Служебные `/privacy/` и `/404.html` помечены `noindex` и в sitemap не входят —
это штатное поведение `build.py`.

- [ ] **Шаг 3: Проверить `CNAME`**

Запустить:
```bash
cat th.neva.beauty/CNAME
```
Ожидаемо: `th.neva.beauty`

Файл генерируется из `base_url` — правится не он, а `site.yml`.

- [ ] **Шаг 4: Включить GitHub Pages**

В настройках репозитория `jw-git-hub/th.neva.beauty` → Pages → Source выбрать
`GitHub Actions`.

- [ ] **Шаг 5: Коммит и пуш — он же деплой**

```bash
git add th.neva.beauty/robots.txt
git commit -m "Публикация: robots.txt с разрешением ИИ-ботов

Обход и цитирование разрешены GPTBot, OAI-SearchBot, Google-Extended,
PerplexityBot, ClaudeBot и Яндексу — цель попадать в ИИ-ответы.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

- [ ] **Шаг 6: Дождаться деплоя и проверить прогон**

Запустить:
```bash
gh run watch
```
Ожидаемо: все шаги зелёные, включая `Check prices`, `Check content` и `Unit tests`.

- [ ] **Шаг 7: Настроить DNS домена**

У регистратора домена `neva.beauty` добавить CNAME-запись:
`th` → `jw-git-hub.github.io`

- [ ] **Шаг 8: Проверить сайт на боевом домене**

Открыть `https://th.neva.beauty` и пройти по страницам. Проверить, что сертификат
выпущен (в настройках Pages включить `Enforce HTTPS` после выпуска).

Проверить ключевые технические файлы:
```bash
curl -sI https://th.neva.beauty | head -1
curl -s https://th.neva.beauty/sitemap.xml | head -3
curl -s https://th.neva.beauty/robots.txt | head -3
curl -s https://th.neva.beauty/llms.txt | head -5
```
Ожидаемо: `HTTP/2 200` и содержимое каждого файла.

---

## Итог

После задачи 14 сайт живой, 23 индексируемые страницы, 203 позиции прайса перенесены
без изменений и защищены тестом, следов старого бренда нет, деплой автоматический
и падает при нарушении проверок.

Дальнейшая работа — этапы 5–10 из `TODO.md`: глубокий аудит, SEO и GEO по промтам
для каждой из 23 страниц отдельными сессиями, маркетинговый аудит, финальный аудит,
оптимизация скорости, документация репозитория.
