"""Mail templates and their rendering into an HTML and a plain-text part (F6 plan §3.8).

A slice registers an `EmailTemplate`: a key, a body in Jinja2 written with the layout's
blocks — `e.heading`, `e.paragraph`, `e.note`, `e.button`, `e.code` — and its texts in the
16 languages, English required; a missing language falls back to English. Texts may hold
`{name}` fields filled from the mail's parameters and secrets.

The body is rendered twice from the same source: once as HTML with autoescape, once as
text, the blocks writing themselves in each format — the text part is never HTML stripped
of its tags. Both use strict undefined, so a missing parameter fails the render instead of
sending a hole. Parameters are values, never templates: `{{ 7*7 }}` in a parameter is sent
as those characters, escaped in the HTML part.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from shosai.core.email.layout_texts import LAYOUT_TEXTS
from shosai.core.email.messages import TEMPLATE_KEY, EmailKind, EmailParam
from shosai.core.i18n.locales import LOCALE_BY_CODE

FALLBACK_LOCALE: Final = "en"
REQUIRED_TEXTS: Final = frozenset({"subject", "preheader"})
# Без кавычек внутри: одинарная кавычка закрывала атрибут style (урок черновика).
FONT_STACK: Final = (
    "Geist,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
)
EXTRA_BLANK_LINES: Final = re.compile(r"\n{3,}")
BODY_PREFIX: Final = '{% import "macros.j2" as e with context %}'


class UnknownTemplateError(Exception):
    """A mail names a template no slice registered in this process."""


@dataclass(frozen=True, slots=True)
class EmailTemplate:
    """A slice's mail: its key, its body and its texts by language."""

    key: str
    body: str
    texts: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        if not TEMPLATE_KEY.fullmatch(self.key):
            message = "ключ шаблона письма — «срез.имя» в snake_case"
            raise ValueError(message)
        english = self.texts.get(FALLBACK_LOCALE)
        if english is None or not english.keys() >= REQUIRED_TEXTS:
            message = f"шаблон {self.key}: английские тексты с темой и прехедером обязательны"
            raise ValueError(message)
        for locale, texts in self.texts.items():
            if locale not in LOCALE_BY_CODE or texts.keys() != english.keys():
                message = f"шаблон {self.key}: тексты {locale} — язык платформы, ключи как у en"
                raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """A mail ready to send: subject, HTML and plain text."""

    subject: str
    html: str
    text: str


class _Fields(dict[str, str]):
    """Fields of a text; a missing one fails, as strict undefined does in the body."""

    def __missing__(self, key: str) -> str:
        message = f"в тексте письма поле {key}, которого нет в параметрах"
        raise KeyError(message)


class EmailTemplates:
    """The templates of the process, registered once by composition."""

    def __init__(self) -> None:
        self._templates: Mapping[str, EmailTemplate] | None = None

    def install(self, templates: Iterable[EmailTemplate]) -> None:
        """Register the templates once; a key named twice is a composition error."""
        if self._templates is not None:
            message = "шаблоны писем уже установлены"
            raise RuntimeError(message)
        found: dict[str, EmailTemplate] = {}
        for template in templates:
            if template.key in found:
                message = f"шаблон письма {template.key} объявлен дважды"
                raise ValueError(message)
            found[template.key] = template
        self._templates = MappingProxyType(found)

    def get(self, key: str) -> EmailTemplate:
        """The template of the key."""
        template = (self._templates or {}).get(key)
        if template is None:
            raise UnknownTemplateError(key)
        return template


class EmailRenderer:
    """Renders a mail in the layout of the design system (F6-D7)."""

    def __init__(self, templates: EmailTemplates, base_url: str, support: str) -> None:
        self._templates = templates
        self._base_url = base_url.rstrip("/")
        self._support = support
        loader = PackageLoader("shosai.core.email", "layout")
        self._html = Environment(
            loader=loader, autoescape=True, undefined=StrictUndefined,
            trim_blocks=True, lstrip_blocks=True,
        )  # fmt: skip
        # Текстовая часть уходит как text/plain: экранировать в ней HTML нечего.
        self._text = Environment(
            loader=loader,
            autoescape=select_autoescape(enabled_extensions=(), default_for_string=False),
            undefined=StrictUndefined,
            trim_blocks=True, lstrip_blocks=True,
        )  # fmt: skip

    def render(
        self,
        template_key: str,
        kind: EmailKind,
        locale: str,
        values: Mapping[str, EmailParam],
        unsubscribe_url: str | None = None,
    ) -> RenderedEmail:
        """The mail in its language; values are the parameters and the secrets together."""
        template = self._templates.get(template_key)
        texts = template.texts.get(locale) or template.texts[FALLBACK_LOCALE]
        fields = _Fields(
            {name: "" if value is None else str(value) for name, value in values.items()}
        )
        filled = {name: text.format_map(fields) for name, text in texts.items()}
        rtl = LOCALE_BY_CODE[locale].rtl
        layout = LAYOUT_TEXTS.get(locale) or LAYOUT_TEXTS[FALLBACK_LOCALE]
        shared = {
            "t": filled, "p": dict(values), "font": FONT_STACK, "lang": locale,
            "dir": "rtl" if rtl else "ltr", "start": "right" if rtl else "left",
            "end": "left" if rtl else "right", "base_url": self._base_url,
            "support": self._support, "unsubscribe_url": unsubscribe_url,
            "subject": filled["subject"], "preheader": filled["preheader"],
            "footer": {"reason": layout[kind.value], "unsubscribe": layout["unsubscribe"],
                       "questions": layout["questions"]},
        }  # fmt: skip
        html = self._html.get_template("layout.html.j2").render(
            body=self._html.from_string(BODY_PREFIX + template.body), format="html", **shared
        )
        text = self._text.get_template("layout.txt.j2").render(
            body=self._text.from_string(BODY_PREFIX + template.body), format="text", **shared
        )
        return RenderedEmail(
            subject=filled["subject"],
            html=html,
            text=EXTRA_BLANK_LINES.sub("\n\n", text).strip() + "\n",
        )
