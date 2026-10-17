"""Mail services where anyone can get an address: such a domain never proves a company.

The list covers the large free and consumer mail services of the platform's markets; it
is data, not a language rule. A company domain that a service hosts (Google Workspace,
Yandex 360) is the company's own domain and is not here.
"""

from typing import Final

PUBLIC_MAIL_DOMAINS: Final = frozenset(
    {
        "aol.com",
        "bk.ru",
        "fastmail.com",
        "gmail.com",
        "gmx.com",
        "gmx.de",
        "gmx.net",
        "googlemail.com",
        "hey.com",
        "hotmail.com",
        "icloud.com",
        "inbox.ru",
        "list.ru",
        "live.com",
        "mac.com",
        "mail.com",
        "mail.ru",
        "me.com",
        "msn.com",
        "naver.com",
        "outlook.com",
        "pm.me",
        "proton.me",
        "protonmail.com",
        "qq.com",
        "rambler.ru",
        "t-online.de",
        "tutanota.com",
        "web.de",
        "ya.ru",
        "yahoo.com",
        "yandex.by",
        "yandex.com",
        "yandex.kz",
        "yandex.ru",
        "zoho.com",
        "163.com",
        "126.com",
    }
)
