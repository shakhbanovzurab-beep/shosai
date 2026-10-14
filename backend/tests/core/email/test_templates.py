"""Mail renders in its language and layout; what a person typed never becomes markup."""

import pytest

from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.messages import EmailKind
from shosai.core.email.templates import (
    EmailRenderer,
    EmailTemplate,
    EmailTemplates,
    UnknownTemplateError,
)
from tests.core.email.bench import CODE_MAIL

TYPED = "{{ 7*7 }}<script>alert(1)</script>"


def renderer() -> EmailRenderer:
    """The renderer over the check and the code templates."""
    templates = EmailTemplates()
    templates.install([MAIL_CHECK, CODE_MAIL])
    return EmailRenderer(templates, "https://shosai.example/", "support@shosai.example")


def test_a_parameter_with_template_syntax_is_escaped_text() -> None:
    rendered = renderer().render(
        "probe.code", EmailKind.ACCOUNT, "en", {"code": "482 913", "name": TYPED}
    )

    assert "{{ 7*7 }}&lt;script&gt;alert(1)&lt;/script&gt;" in rendered.html
    assert "<script>" not in rendered.html
    assert "49" not in rendered.html
    assert "Hello, {{ 7*7 }}<script>alert(1)</script>." in rendered.text


def test_a_text_without_its_language_falls_back_to_english() -> None:
    rendered = renderer().render(
        "probe.code", EmailKind.ACCOUNT, "de", {"code": "482 913", "name": "Anna"}
    )

    assert rendered.subject == "Your code 482 913"
    assert 'lang="de"' in rendered.html


def test_arabic_mail_reads_right_to_left_and_the_code_stays_left_to_right() -> None:
    values = {"sample_code": "123 456", "url": "https://shosai.example/app/"}

    rendered = renderer().render("core.mail_check", EmailKind.NOTIFICATION, "ar", values)

    assert 'dir="rtl"' in rendered.html
    assert 'align="right"' in rendered.html
    assert 'dir="ltr"' in rendered.html


def test_the_plain_text_part_carries_the_content_without_markup() -> None:
    values = {"sample_code": "123 456", "url": "https://shosai.example/app/"}

    rendered = renderer().render(
        "core.mail_check", EmailKind.NEWSLETTER, "en", values, "https://shosai.example/u"
    )

    assert "<" not in rendered.text
    assert "123 456" in rendered.text
    assert "Open Shosai: https://shosai.example/app/" in rendered.text
    assert "https://shosai.example/u" in rendered.text
    assert "https://shosai.example/email/shosai-icon.png" in rendered.html


def test_a_missing_parameter_fails_instead_of_sending_a_gap() -> None:
    with pytest.raises(KeyError):
        renderer().render("probe.code", EmailKind.ACCOUNT, "en", {"code": "482 913"})


def test_an_unknown_template_is_named() -> None:
    with pytest.raises(UnknownTemplateError):
        renderer().render("probe.missing", EmailKind.ACCOUNT, "en", {})


@pytest.mark.parametrize(
    ("key", "texts"),
    [
        ("Probe", {"en": {"subject": "s", "preheader": "p"}}),
        ("probe.no_english", {"ru": {"subject": "s", "preheader": "p"}}),
        ("probe.no_preheader", {"en": {"subject": "s"}}),
        ("probe.uneven", {"en": {"subject": "s", "preheader": "p"}, "ru": {"subject": "s"}}),
        ("probe.unknown_language", {"en": {"subject": "s", "preheader": "p"},
                                    "xx": {"subject": "s", "preheader": "p"}}),
    ],
)  # fmt: skip
def test_a_malformed_template_is_refused_when_declared(
    key: str, texts: dict[str, dict[str, str]]
) -> None:
    with pytest.raises(ValueError, match=r"."):
        EmailTemplate(key=key, body="", texts=texts)


def test_a_template_key_registered_twice_is_a_composition_error() -> None:
    with pytest.raises(ValueError, match="дважды"):
        EmailTemplates().install([CODE_MAIL, CODE_MAIL])
