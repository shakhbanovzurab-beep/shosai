"""Every mail of the platform, its layout and its unsubscribe page speak the 16 languages."""

import pytest

from shosai.composition.email import require_every_language
from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.layout_texts import LAYOUT_TEXTS
from shosai.core.email.messages import EmailKind, EmailParam
from shosai.core.email.page_texts import PAGE_TEXTS
from shosai.core.email.templates import EmailRenderer, EmailTemplate, EmailTemplates
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.identity.emails.deletion_scheduled import DELETION_SCHEDULED
from shosai.features.identity.emails.export_ready import EXPORT_READY
from shosai.features.identity.emails.password_reset import RESET_LINK_MAIL
from shosai.features.identity.emails.registration_attempt import REGISTRATION_ATTEMPT
from shosai.features.identity.emails.registration_code import REGISTRATION_CODE

TEMPLATES = (
    MAIL_CHECK, REGISTRATION_CODE, REGISTRATION_ATTEMPT, RESET_LINK_MAIL, DELETION_SCHEDULED,
    EXPORT_READY,
)  # fmt: skip
VALUES: dict[str, EmailParam] = {
    "minutes": 15,
    "code": "482 913",
    "sample_code": "123 456",
    "link": "https://shosai.example/app/reset-password#token",
    "url": "https://shosai.example/app/",
    "date": "2026-10-21",
    "days": 7,
}


def test_the_layout_and_the_unsubscribe_page_have_every_language() -> None:
    assert set(LAYOUT_TEXTS) == set(SUPPORTED_LANGUAGES)
    assert set(PAGE_TEXTS) == set(SUPPORTED_LANGUAGES)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.key)
def test_every_template_renders_in_every_language(template: EmailTemplate) -> None:
    templates = EmailTemplates()
    templates.install([template])
    renderer = EmailRenderer(templates, "https://shosai.example/", "support@shosai.example")
    english = renderer.render(template.key, EmailKind.ACCOUNT, "en", VALUES)

    for language in SUPPORTED_LANGUAGES:
        rendered = renderer.render(template.key, EmailKind.ACCOUNT, language, VALUES)

        assert f'lang="{language}"' in rendered.html
        assert "{" not in rendered.subject
        assert language == "en" or rendered.subject != english.subject


def test_the_platform_refuses_a_template_without_a_language() -> None:
    texts = {code: text for code, text in MAIL_CHECK.texts.items() if code != "nl"}
    partial = EmailTemplate(key="probe.partial", body=MAIL_CHECK.body, texts=texts)

    require_every_language(TEMPLATES)
    with pytest.raises(ValueError, match="nl"):
        require_every_language([MAIL_CHECK, partial])
