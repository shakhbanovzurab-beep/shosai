"""The apps Shosai connects, their providers and what each app needs (connectors plan §3.2).

A connection is an app (Gmail, Google Calendar); a grant is the consent of one provider
account, shared by that account's apps (CN-D2). An app names the provider and the OAuth
application (`client_key`) its new grants come from, the capability consumers use it for,
the cabinet's category, how it authenticates and the scopes it needs. Google has two
applications: Gmail waits in Google's test mode in a project of its own while Calendar and
Drive are open (CN-D5). The catalogue lists every app of the owner's list of 2026-10-28;
which of them the cabinet offers is decided by the consumers (CN-D4), not here.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

CLIENT_KEY: Final = re.compile(r"[a-z][a-z0-9_]{1,31}")


class Provider(StrEnum):
    """A service whose accounts people connect."""

    GOOGLE = "google"
    MICROSOFT = "microsoft"
    YANDEX = "yandex"
    MAILRU = "mailru"
    CALDAV = "caldav"
    NOTION = "notion"
    ATLASSIAN = "atlassian"
    DROPBOX = "dropbox"
    GITHUB = "github"
    GITLAB = "gitlab"
    SLACK = "slack"
    HUBSPOT = "hubspot"
    ATTIO = "attio"
    AFFINITY = "affinity"
    ZAPIER = "zapier"


class Capability(StrEnum):
    """What consumers use an app for; each has its port (CN-D1)."""

    MAIL = "mail"
    CALENDAR = "calendar"
    FILES = "files"
    PAGES = "pages"
    TRACKER = "tracker"
    CODE = "code"
    CHAT = "chat"
    CRM = "crm"
    WEBHOOK = "webhook"


class Category(StrEnum):
    """The cabinet's group of an app: its six categories and `calendar`."""

    MAIL = "mail"
    CALENDAR = "calendar"
    FILES = "files"
    NOTES = "notes"
    COMMUNICATION = "communication"
    TASKS = "tasks"
    CRM = "crm"


class AuthKind(StrEnum):
    """How a grant proves itself to the provider."""

    OAUTH2 = "oauth2"
    # Пароль приложения: IMAP, SMTP или CalDAV с логином аккаунта.
    APP_LOGIN = "app_password"
    API_KEY = "api_key"
    WEBHOOK_URL = "webhook_url"


class Owner(StrEnum):
    """Who holds a connection: a person, or a workspace's installation (CN-D3)."""

    PERSON = "person"
    WORKSPACE = "workspace"


class App(StrEnum):
    """An app of the catalogue: the cabinet's id of a row in Settings > Connectors."""

    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    GOOGLE_DRIVE = "google_drive"
    OUTLOOK = "outlook"
    OUTLOOK_CALENDAR = "outlook_calendar"
    YANDEX_MAIL = "yandex_mail"
    YANDEX_CALENDAR = "yandex_calendar"
    YANDEX_DISK = "yandex_disk"
    MAILRU_MAIL = "mailru_mail"
    CALDAV = "caldav"
    NOTION = "notion"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    DROPBOX = "dropbox"
    GITHUB = "github"
    GITLAB = "gitlab"
    SLACK = "slack"
    HUBSPOT = "hubspot"
    ATTIO = "attio"
    AFFINITY = "affinity"
    ZAPIER = "zapier"


@dataclass(frozen=True, slots=True)
class AppSpec:
    """One app: its provider and application, what it is for and what it needs."""

    app: App
    # Название бренда; кабинет показывает его как есть или переводит по id.
    name: str
    provider: Provider
    capability: Capability
    category: Category
    # Первый способ — основной; остальные — запасные (пароль приложения у Mail.ru).
    auth: tuple[AuthKind, ...]
    # Приложение OAuth, от которого выдаются новые гранты; у паролей и ключей — имя провайдера.
    client_key: str
    scopes: frozenset[str] = frozenset()
    # Установка в пространство (бот Slack для чатов): свои права, владелец — пространство.
    installation_scopes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.auth:
            message = f"приложение {self.app}: не задан способ входа"
            raise ValueError(message)
        if not CLIENT_KEY.fullmatch(self.client_key):
            message = f"приложение {self.app}: ключ клиента {self.client_key!r} не в snake_case"
            raise ValueError(message)
        if self.auth[0] is not AuthKind.OAUTH2 and (self.scopes or self.installation_scopes):
            message = f"приложение {self.app}: права бывают только у входа через OAuth"
            raise ValueError(message)

    @property
    def owners(self) -> frozenset[Owner]:
        """Who may hold a connection of this app."""
        if self.installation_scopes:
            return frozenset({Owner.PERSON, Owner.WORKSPACE})
        return frozenset({Owner.PERSON})

    def scopes_for(self, owner: Owner) -> frozenset[str]:
        """The scopes a grant of this owner must hold."""
        return self.installation_scopes if owner is Owner.WORKSPACE else self.scopes


_OAUTH: Final = (AuthKind.OAUTH2,)
_GOOGLE: Final = frozenset({"openid", "email"})
_GOOGLE_API: Final = "https://www.googleapis.com/auth/"
_MICROSOFT: Final = frozenset({"openid", "email", "offline_access", "User.Read"})
_YANDEX: Final = frozenset({"login:email", "login:info"})
_ATLASSIAN: Final = frozenset({"offline_access", "read:me"})

_SPECS: Final = (
    AppSpec(App.GMAIL, "Gmail", Provider.GOOGLE, Capability.MAIL, Category.MAIL, _OAUTH,
            "google_mail", _GOOGLE | {f"{_GOOGLE_API}gmail.modify"}),
    AppSpec(App.GOOGLE_CALENDAR, "Google Calendar", Provider.GOOGLE, Capability.CALENDAR,
            Category.CALENDAR, _OAUTH, "google",
            _GOOGLE | {f"{_GOOGLE_API}calendar.events",
                       f"{_GOOGLE_API}calendar.calendarlist.readonly"}),
    AppSpec(App.GOOGLE_DRIVE, "Google Drive", Provider.GOOGLE, Capability.FILES, Category.FILES,
            _OAUTH, "google", _GOOGLE | {f"{_GOOGLE_API}drive.file"}),
    AppSpec(App.OUTLOOK, "Outlook", Provider.MICROSOFT, Capability.MAIL, Category.MAIL, _OAUTH,
            "microsoft", _MICROSOFT | {"Mail.ReadWrite", "Mail.Send"}),
    AppSpec(App.OUTLOOK_CALENDAR, "Outlook Calendar", Provider.MICROSOFT, Capability.CALENDAR,
            Category.CALENDAR, _OAUTH, "microsoft", _MICROSOFT | {"Calendars.ReadWrite"}),
    AppSpec(App.YANDEX_MAIL, "Yandex Mail", Provider.YANDEX, Capability.MAIL, Category.MAIL,
            _OAUTH, "yandex", _YANDEX | {"mail:imap_full", "mail:smtp"}),
    AppSpec(App.YANDEX_CALENDAR, "Yandex Calendar", Provider.YANDEX, Capability.CALENDAR,
            Category.CALENDAR, (AuthKind.APP_LOGIN,), "yandex"),
    AppSpec(App.YANDEX_DISK, "Yandex Disk", Provider.YANDEX, Capability.FILES, Category.FILES,
            _OAUTH, "yandex", _YANDEX | {"cloud_api:disk.read", "cloud_api:disk.info"}),
    AppSpec(App.MAILRU_MAIL, "Mail.ru", Provider.MAILRU, Capability.MAIL, Category.MAIL,
            (AuthKind.OAUTH2, AuthKind.APP_LOGIN), "mailru",
            frozenset({"userinfo", "mail.imap"})),
    AppSpec(App.CALDAV, "CalDAV", Provider.CALDAV, Capability.CALENDAR, Category.CALENDAR,
            (AuthKind.APP_LOGIN,), "caldav"),
    # Notion не знает прав в адресе: доступ выбирают по страницам в его окне.
    AppSpec(App.NOTION, "Notion", Provider.NOTION, Capability.PAGES, Category.NOTES, _OAUTH,
            "notion"),
    AppSpec(App.CONFLUENCE, "Confluence", Provider.ATLASSIAN, Capability.PAGES, Category.NOTES,
            _OAUTH, "atlassian",
            _ATLASSIAN | {"read:confluence-content.all", "read:confluence-space.summary",
                          "search:confluence", "write:confluence-content"}),
    AppSpec(App.JIRA, "Jira", Provider.ATLASSIAN, Capability.TRACKER, Category.TASKS, _OAUTH,
            "atlassian",
            _ATLASSIAN | {"read:jira-work", "write:jira-work", "manage:jira-webhook"}),
    AppSpec(App.DROPBOX, "Dropbox", Provider.DROPBOX, Capability.FILES, Category.FILES, _OAUTH,
            "dropbox",
            frozenset({"account_info.read", "files.metadata.read", "files.content.read"})),
    # Права GitHub App задаются в самом приложении, а не в адресе входа (CN-D6).
    AppSpec(App.GITHUB, "GitHub", Provider.GITHUB, Capability.CODE, Category.TASKS, _OAUTH,
            "github_app"),
    AppSpec(App.GITLAB, "GitLab", Provider.GITLAB, Capability.CODE, Category.TASKS, _OAUTH,
            "gitlab", frozenset({"read_api", "read_repository", "read_user"})),
    AppSpec(App.SLACK, "Slack", Provider.SLACK, Capability.CHAT, Category.COMMUNICATION,
            _OAUTH, "slack",
            frozenset({"channels:read", "chat:write", "groups:read", "users:read"}),
            installation_scopes=frozenset({
                "app_mentions:read", "channels:history", "channels:join", "channels:read",
                "chat:write", "groups:history", "groups:read", "users:read", "users:read.email",
            })),
    AppSpec(App.HUBSPOT, "HubSpot", Provider.HUBSPOT, Capability.CRM, Category.CRM, _OAUTH,
            "hubspot",
            frozenset({"oauth", "crm.objects.contacts.read", "crm.objects.contacts.write",
                       "crm.objects.companies.read"})),
    # Права Attio задаются в его приложении.
    AppSpec(App.ATTIO, "Attio", Provider.ATTIO, Capability.CRM, Category.CRM, _OAUTH, "attio"),
    AppSpec(App.AFFINITY, "Affinity", Provider.AFFINITY, Capability.CRM, Category.CRM,
            (AuthKind.API_KEY,), "affinity"),
    AppSpec(App.ZAPIER, "Zapier", Provider.ZAPIER, Capability.WEBHOOK, Category.CRM,
            (AuthKind.WEBHOOK_URL,), "zapier"),
)  # fmt: skip

CATALOGUE: Final[Mapping[App, AppSpec]] = MappingProxyType({spec.app: spec for spec in _SPECS})


def spec_of(app: App) -> AppSpec:
    """The catalogue's entry of an app."""
    return CATALOGUE[app]


def apps_of(provider: Provider) -> tuple[App, ...]:
    """The apps of one provider, in the catalogue's order."""
    return tuple(spec.app for spec in _SPECS if spec.provider is provider)
