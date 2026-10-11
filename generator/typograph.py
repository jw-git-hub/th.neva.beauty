"""Типограф: неразрывные пробелы там, где перенос строки портит чтение.

Браузер переносит строку по любому пробелу: предлог остаётся в конце строки,
тире уезжает в начало следующей, число отрывается от слова. На телефоне таких
мест сотни — 621 перенос после короткого слова на ширине 390 px (замер задачи
141). Шаг работает по готовой разметке страницы и трогает только текст между
тегами: атрибуты, <head>, скрипты и JSON-LD остаются как есть, поэтому поиск,
превью ссылок и разметка читают прежние строки.
"""
import re

NBSP = " "

# Короткие предлоги, союзы и частицы: строка не должна на них заканчиваться.
SHORT_WORDS = (
    "в", "во", "с", "со", "к", "ко", "о", "об", "у", "и", "а", "но",
    "на", "по", "за", "из", "от", "до", "не", "ни",
    "для", "при", "без", "над", "под", "про", "или", "что", "как", "то",
)
# Частицы, которые держатся за слово перед собой.
TRAILING_PARTICLES = ("же", "ли", "бы")
# Элементы, чьё содержимое не текст для чтения: служебная часть документа, код,
# иконки. <time> здесь из-за сборки: в нём стоит заглушка даты, которую подменяют
# уже после типографа, и склеенную заглушку подмена бы не нашла.
PROTECTED_TAGS = ("head", "script", "style", "pre", "code", "textarea", "time", "svg")
# Строчные теги: слово перед таким тегом и слово внутри него стоят в одной строке.
INLINE_TAGS = frozenset(("a", "strong", "em", "b", "i", "span"))

_SHORT = "|".join(SHORT_WORDS)
_PARTICLES = "|".join(TRAILING_PARTICLES)
# Слово целиком: перед ним не буква и не дефис («что-то» — не союз «то»).
_AFTER_SHORT_RE = re.compile(rf"(?<![\w-])({_SHORT}) (?=\S)", re.IGNORECASE)
_SHORT_AT_END_RE = re.compile(rf"(?<![\w-])({_SHORT}) $", re.IGNORECASE)
_BEFORE_DASH_RE = re.compile(r" (?=—)")
_NUMBER_WORD_RE = re.compile(r"(?<=\d) (?=[^\W\d_])")
_BEFORE_PARTICLE_RE = re.compile(rf" (?=(?:{_PARTICLES})(?![\w-]))", re.IGNORECASE)

_PROTECTED_RE = re.compile(
    rf"<!--.*?-->|<({'|'.join(PROTECTED_TAGS)})\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"(<[^>]+>)")
_OPENING_TAG_NAME_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)")


def glue_text(text):
    """Текст, в котором обычный пробел заменён неразрывным в четырёх положениях:
    после короткого слова, перед тире, между числом и словом, перед частицей."""
    text = _AFTER_SHORT_RE.sub(rf"\1{NBSP}", text)
    text = _BEFORE_DASH_RE.sub(NBSP, text)
    text = _NUMBER_WORD_RE.sub(NBSP, text)
    return _BEFORE_PARTICLE_RE.sub(NBSP, text)


def _opens_inline(tag):
    name = _OPENING_TAG_NAME_RE.match(tag)
    return bool(name) and name.group(1).lower() in INLINE_TAGS


def _glue_markup(markup):
    """Кусок разметки без защищённых элементов: теги как есть, текст склеен."""
    tokens = _TAG_RE.split(markup)  # чётные — текст, нечётные — теги
    for index in range(0, len(tokens), 2):
        text = glue_text(tokens[index])
        next_tag = tokens[index + 1] if index + 1 < len(tokens) else ""
        if _opens_inline(next_tag):
            # «или <a>Instagram</a>»: слово после предлога уже внутри тега.
            text = _SHORT_AT_END_RE.sub(rf"\1{NBSP}", text)
        tokens[index] = text
    return "".join(tokens)


def typograph_html(html):
    """Страница с типографикой: текст между тегами склеен, защищённое не тронуто."""
    parts, position = [], 0
    for protected in _PROTECTED_RE.finditer(html):
        parts.append(_glue_markup(html[position:protected.start()]))
        parts.append(protected.group(0))
        position = protected.end()
    parts.append(_glue_markup(html[position:]))
    return "".join(parts)
