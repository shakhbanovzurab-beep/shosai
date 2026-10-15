"""The unsubscribe page: a confirmation before anything changes, then a done page.

The language comes from `Accept-Language`, English when none of the 16 matches; the page
is the same for every link, valid or not. Headers keep the token in the address bar only:
no referrer, no cache, no framing, no script, and the form posts back to the same URL.
"""

from typing import Final

from jinja2 import Environment, PackageLoader, StrictUndefined

from shosai.core.email.page_texts import PAGE_TEXTS
from shosai.core.email.templates import FALLBACK_LOCALE, FONT_STACK
from shosai.core.i18n.locales import LOCALE_BY_CODE, parse_accept_language

PAGE_HEADERS: Final = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
}


class UnsubscribePage:
    """Renders the confirmation and the done page in the visitor's language."""

    def __init__(self) -> None:
        # Semgrep принимает это за Flask: окружение jinja2 своё, HTML экранируется (autoescape).
        self._template = Environment(  # nosemgrep
            loader=PackageLoader("shosai.core.email", "layout"),
            autoescape=True,
            undefined=StrictUndefined,
        ).get_template("unsubscribe_page.html.j2")

    def render(self, accept_language: str | None, token: str, *, done: bool) -> str:
        """The page; `token` goes back in the form so the POST carries it in the body too."""
        locale = parse_accept_language(accept_language) or FALLBACK_LOCALE
        texts = PAGE_TEXTS.get(locale) or PAGE_TEXTS[FALLBACK_LOCALE]
        stage = "done" if done else "confirm"
        return self._template.render(
            lang=locale,
            dir="rtl" if LOCALE_BY_CODE[locale].rtl else "ltr",
            font=FONT_STACK,
            title=texts[f"{stage}_title"],
            lead=texts[f"{stage}_lead"],
            button=texts["button"],
            token=token,
            done=done,
        )
