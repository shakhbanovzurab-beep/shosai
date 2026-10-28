"""How the card of Leo's `studio.update_context` reads, in the 16 platform languages (step 13).

The title in the words of Studio's "About you" tab, and the new text as the server will save it.
"""

from typing import Final

from shosai.core.agent_tools.previews import PreviewWording

UPDATE_CONTEXT: Final = PreviewWording(
    key="agent.studio.update_context",
    params=("content",),
    title={
        "en": "Update “About you” in Studio", "fr": "Modifier « À propos de vous » dans Studio",
        "de": "„Über dich“ in Studio ändern", "ru": "Изменить «О вас» в Studio",
        "nl": "‘Over jou’ in Studio bijwerken", "it": "Aggiorna «Su di te» in Studio",
        "es": "Actualizar «Sobre ti» en Studio", "pt-BR": "Atualizar “Sobre você” no Studio",
        "ar": "تحديث «نبذة عنك» في Studio", "tr": "Studio’da “Hakkınızda” bölümünü güncelle",
        "ko": "Studio의 ‘내 소개’ 수정", "hi": "Studio में “आपके बारे में” बदलें",
        "vi": "Cập nhật “Về bạn” trong Studio", "zh-Hant": "更新 Studio 中的「關於你」",
        "ja": "Studio の「自分について」を更新", "id": "Perbarui “Tentang Anda” di Studio",
    },
    body="content",
)  # fmt: skip
