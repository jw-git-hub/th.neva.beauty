"""Типограф: где ставится неразрывный пробел и что он обязан не тронуть.

Шаг идёт по готовой разметке всех страниц, и ошибается он тихо: склеенный
атрибут или JSON-LD глазами не видно, а поиск и превью ссылок читают именно их.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typograph import NBSP, glue_text, typograph_html


def test_short_word_holds_the_next_one():
    assert glue_text("Запись в салон") == f"Запись в{NBSP}салон"


def test_short_words_in_a_row_are_all_glued():
    assert glue_text("и в салоне, и на дому") == f"и{NBSP}в{NBSP}салоне, и{NBSP}на{NBSP}дому"


def test_capital_letter_at_sentence_start_counts():
    assert glue_text("У нас. С поправкой") == f"У{NBSP}нас. С{NBSP}поправкой"


def test_part_of_a_longer_word_is_left_alone():
    """«то» в «что-то» и «на» в «она» — не предлоги."""
    assert glue_text("что-то она знает") == "что-то она знает"


def test_dash_stays_with_the_previous_word():
    assert glue_text("Neva Beauty — Koh Samui") == f"Neva Beauty{NBSP}— Koh Samui"


def test_number_stays_with_its_word():
    assert glue_text("курс 10 процедур, 250 ml") == f"курс 10{NBSP}процедур, 250{NBSP}ml"


def test_number_is_not_glued_to_another_number():
    assert glue_text("с 2025 2026") == f"с{NBSP}2025 2026"


def test_particle_stays_with_the_word_before_it():
    assert glue_text("тот же состав, если бы") == f"тот{NBSP}же состав, если{NBSP}бы"


def test_result_is_stable_on_second_pass():
    once = glue_text("и в то же время — 2 часа")
    assert glue_text(once) == once


def test_attributes_keep_plain_spaces():
    html = '<img alt="Мастер в салоне на Самуи"><p>Мастер в салоне</p>'
    assert typograph_html(html) == (
        f'<img alt="Мастер в салоне на Самуи"><p>Мастер в{NBSP}салоне</p>')


def test_head_and_json_ld_are_untouched():
    html = ('<head><title>Салон на Самуи — Neva Beauty</title></head>'
            '<body><script type="application/ld+json">{"name": "Уход и стрижка"}</script>'
            '<p>Уход и стрижка</p></body>')
    assert typograph_html(html) == html.replace("<p>Уход и стрижка", f"<p>Уход и{NBSP}стрижка")


def test_header_is_not_mistaken_for_head():
    assert typograph_html("<header><p>Запись в салон</p></header>") == (
        f"<header><p>Запись в{NBSP}салон</p></header>")


def test_date_placeholder_inside_time_survives():
    """Заглушку даты сборка подменяет после типографа — склеенную она бы не нашла."""
    html = '<span>Обновлена <time datetime="0000-00-00">00 месяца 0000 года</time></span>'
    assert typograph_html(html) == html


def test_comment_is_untouched():
    html = "<!-- запись в салон --><p>ok</p>"
    assert typograph_html(html) == html


def test_short_word_before_a_link_holds_the_link_text():
    html = '<p>в WhatsApp или <a href="#">Instagram</a></p>'
    assert typograph_html(html) == (
        f'<p>в{NBSP}WhatsApp или{NBSP}<a href="#">Instagram</a></p>')


def test_short_word_before_a_block_tag_is_not_glued():
    html = "<p>Запись и </p><div>блок</div>"
    assert typograph_html(html) == html
