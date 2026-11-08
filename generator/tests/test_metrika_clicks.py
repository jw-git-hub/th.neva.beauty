"""Клики по ссылкам в коде Метрики: цель contact со страницей и канал, внешние переходы."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

GENERATOR = Path(__file__).resolve().parent.parent
HARNESS = Path(__file__).resolve().parent / "js" / "metrika_clicks.js"
NODE = shutil.which("node")
SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.DOTALL)
PAGE = {"id": "massazh", "url": "/massazh/"}
COUNTER_ID = 99850063
CONTACTS_BY_PAGE, EXITS_BY_PAGE = "contacts by page", "exits by page"
OWN_HOSTNAME = "th.neva.beauty"
SECOND_SALON = "vn.neva.beauty"


def web_link(href, hostname, attrs=None):
    return {"href": href, "protocol": "https:", "hostname": hostname, "attrs": attrs or {}}


def click(link, event_type="click", button=0):
    return {"type": event_type, "button": button, "link": link}


WHATSAPP = web_link("https://wa.me/79990000000", "wa.me",
                    {"data-contact": "whatsapp", "data-place": "booking",
                     "href": "https://wa.me/79990000000"})
SECOND_SALON_LINK = web_link("https://vn.neva.beauty/", SECOND_SALON)
MAIL_LINK = {"href": "mailto:a@b.c", "protocol": "mailto:", "hostname": "", "attrs": {}}
PHONE_LINK = {"href": "tel:+79990000000", "protocol": "tel:", "hostname": "", "attrs": {}}
OWN_ABSOLUTE = web_link("https://th.neva.beauty/volosy/", OWN_HOSTNAME)
OWN_RELATIVE = web_link("/volosy/", OWN_HOSTNAME)


def render_metrika_script():
    env = Environment(loader=FileSystemLoader(GENERATOR / "templates"))
    html = env.get_template("partials/metrika.html.j2").render(
        site={"metrika_id": COUNTER_ID}, page=PAGE)
    return SCRIPT_RE.search(html).group(1)


@unittest.skipUnless(NODE, "нужен node: код Метрики проверяется в нём")
class MetrikaClicksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = render_metrika_script()

    def calls_after(self, *events):
        payload = json.dumps({"script": self.script, "events": list(events)})
        result = subprocess.run([NODE, str(HARNESS)], input=payload, capture_output=True,
                                text=True, check=True)
        return json.loads(result.stdout)

    def test_contact_click_reports_flat_params_and_page_branch(self):
        """Клик по whatsapp: плоские параметры плюс ветка «страница → канал → место»."""
        calls = self.calls_after(click(WHATSAPP))
        self.assertEqual(len(calls), 1)
        counter_id, method, goal, params = calls[0]
        self.assertEqual((counter_id, method, goal), (COUNTER_ID, "reachGoal", "contact"))
        self.assertEqual({key: params[key] for key in ("channel", "lang", "page", "place")},
                         {"channel": "whatsapp", "lang": "ru", "page": "massazh", "place": "booking"})
        self.assertEqual(params[CONTACTS_BY_PAGE], {"/massazh/": {"whatsapp": "booking"}})

    def test_external_site_click_reports_exit_param(self):
        """Переход на другой сайт уходит параметром визита без цели."""
        calls = self.calls_after(click(SECOND_SALON_LINK))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], ["params", {EXITS_BY_PAGE: {"/massazh/": SECOND_SALON}}])

    def test_mailto_click_reports_email_exit(self):
        """mailto: учитывается как выход «e-mail»."""
        calls = self.calls_after(click(MAIL_LINK))
        self.assertEqual(calls[0][1:], ["params", {EXITS_BY_PAGE: {"/massazh/": "e-mail"}}])

    def test_tel_click_reports_phone_exit(self):
        """tel: учитывается как выход «phone»."""
        calls = self.calls_after(click(PHONE_LINK))
        self.assertEqual(calls[0][1:], ["params", {EXITS_BY_PAGE: {"/massazh/": "phone"}}])

    def test_internal_links_are_not_reported(self):
        """Абсолютная ссылка на свой сайт и относительная ссылка выходом не считаются."""
        self.assertEqual(self.calls_after(click(OWN_ABSOLUTE), click(OWN_RELATIVE)), [])

    def test_click_outside_link_is_not_reported(self):
        """Клик не по ссылке ничего не отправляет."""
        self.assertEqual(self.calls_after(click(None)), [])

    def test_middle_button_counts_but_right_button_does_not(self):
        """auxclick: средняя кнопка учитывается, правая нет."""
        middle = self.calls_after(click(SECOND_SALON_LINK, "auxclick", 1))
        right = self.calls_after(click(SECOND_SALON_LINK, "auxclick", 2))
        self.assertEqual(len(middle), 1)
        self.assertEqual(right, [])

    def test_contact_link_is_not_reported_as_exit(self):
        """Ссылка связи идёт только в contact, вызова params для неё нет."""
        calls = self.calls_after(click(WHATSAPP))
        self.assertNotIn("params", [call[1] for call in calls])


if __name__ == "__main__":
    unittest.main()
