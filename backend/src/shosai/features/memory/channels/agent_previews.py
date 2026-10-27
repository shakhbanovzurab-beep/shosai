"""How the card of Leo's `memory.forget` reads, in the 16 platform languages (memory step 6).

One card for one fact or several: the title in the words of Settings > Memory, how many
facts go, and each statement as the server reads it when the card is drawn, one per line.
"""

from typing import Final

from shosai.core.agent_tools.previews import PreviewField, PreviewWording

FORGET: Final = PreviewWording(
    key="agent.memory.forget",
    params=("count", "statements"),
    title={
        "en": "Forget what Leo remembers", "fr": "Oublier ce dont Leo se souvient",
        "de": "Vergessen, was Leo sich merkt", "ru": "Забыть то, что помнит Leo",
        "nl": "Vergeten wat Leo onthoudt", "it": "Dimentica ciò che ricorda Leo",
        "es": "Olvidar lo que recuerda Leo", "pt-BR": "Esquecer o que o Leo lembra",
        "ar": "نسيان ما يتذكره Leo", "tr": "Leo’nun hatırladıklarını unut",
        "ko": "Leo가 기억하는 내용 잊기", "hi": "Leo को जो याद है, उसे भुला दें",
        "vi": "Quên những gì Leo ghi nhớ", "zh-Hant": "忘記 Leo 記得的事",
        "ja": "Leo が覚えていることを忘れる", "id": "Lupakan yang diingat Leo",
    },
    fields=(
        PreviewField("count", {
            "en": "Facts", "fr": "Informations", "de": "Fakten", "ru": "Факты", "nl": "Feiten",
            "it": "Informazioni", "es": "Datos", "pt-BR": "Fatos", "ar": "المعلومات",
            "tr": "Bilgiler", "ko": "항목", "hi": "तथ्य", "vi": "Thông tin", "zh-Hant": "資訊",
            "ja": "件数", "id": "Fakta",
        }),
    ),
    body="statements",
)  # fmt: skip
