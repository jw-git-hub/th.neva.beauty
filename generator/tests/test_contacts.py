"""Метки ссылок связи: что ставит contacts.py и на что он падает."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contacts import CHANNELS, PLACES, fill_contact_links, tracking_attrs

CONTACTS = {"whatsapp_url": "https://wa.me/1", "telegram_url": "https://t.me/x",
            "instagram_url": "https://www.instagram.com/x/"}


class TrackingAttrsTest(unittest.TestCase):
    def test_gives_channel_and_place_marks(self):
        self.assertEqual(tracking_attrs("whatsapp", "hero"),
                         'data-contact="whatsapp" data-place="hero"')

    def test_every_channel_and_place_is_accepted(self):
        for channel in CHANNELS:
            for place in PLACES:
                tracking_attrs(channel, place)

    def test_unknown_channel_fails(self):
        with self.assertRaisesRegex(ValueError, "Неизвестный канал связи"):
            tracking_attrs("viber", "hero")

    def test_unknown_place_fails(self):
        with self.assertRaisesRegex(ValueError, "Неизвестное место кнопки"):
            tracking_attrs("whatsapp", "sidebar")


class FillContactLinksTest(unittest.TestCase):
    def test_href_placeholder_gets_url_and_marks(self):
        html = '<a href="{telegram}" rel="noopener">TG</a>'
        self.assertEqual(
            fill_contact_links(html, CONTACTS, "faq"),
            '<a href="https://t.me/x" data-contact="telegram" data-place="faq" rel="noopener">TG</a>')

    def test_every_channel_is_filled(self):
        html = " ".join(f'<a href="{{{channel}}}">x</a>' for channel in CHANNELS)
        result = fill_contact_links(html, CONTACTS, "text")
        for channel in CHANNELS:
            self.assertIn(f'data-contact="{channel}" data-place="text"', result)

    def test_placeholder_outside_href_is_left_alone(self):
        html = "Пишите: {whatsapp}"
        self.assertEqual(fill_contact_links(html, CONTACTS, "faq"), html)

    def test_unknown_place_fails(self):
        with self.assertRaises(ValueError):
            fill_contact_links("<a>x</a>", CONTACTS, "sidebar")


if __name__ == "__main__":
    unittest.main()
