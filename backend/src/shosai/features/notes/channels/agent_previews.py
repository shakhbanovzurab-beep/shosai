"""How the cards of Leo's meeting writes read, in the 16 platform languages (ADR 0068; agent 9b).

Each preview key the notes tools return is worded here beside their specs: the title says the
change with the meeting's name in the language's quotation marks, and the fields carry what
the change sets — the folder, the template, how the shared page reads and how long the link
works, the comments a closed link takes with it.
"""

from typing import Final

from shosai.core.agent_tools.previews import PreviewField, PreviewWording
from shosai.features.notes.channels import agent_card_words as words
from shosai.features.notes.channels.agent_template_names import SHIPPED_TEMPLATES

MOVE_TO_FOLDER: Final = PreviewWording(
    key="agent.notes.move_to_folder",
    params=("title", "folder"),
    title=words.titled({
        "en": "Move the meeting “{title}”", "fr": "Déplacer la réunion « {title} »",
        "de": "Meeting „{title}“ verschieben", "ru": "Переместить встречу «{title}»",
        "nl": "Vergadering ‘{title}’ verplaatsen", "it": "Sposta la riunione «{title}»",
        "es": "Mover la reunión «{title}»", "pt-BR": "Mover a reunião “{title}”",
        "ar": "نقل الاجتماع «{title}»", "tr": "“{title}” toplantısını taşı",
        "ko": "“{title}” 회의 이동", "hi": "मीटिंग “{title}” को ले जाएँ",
        "vi": "Di chuyển cuộc họp “{title}”", "zh-Hant": "移動會議「{title}」",
        "ja": "会議「{title}」を移動", "id": "Pindahkan rapat “{title}”",
    }),
    fields=(PreviewField("folder", words.FOLDER),),
)  # fmt: skip
REMOVE_FROM_FOLDER: Final = PreviewWording(
    key="agent.notes.remove_from_folder",
    params=("title",),
    title=words.titled({
        "en": "Take the meeting “{title}” out of its folder",
        "fr": "Retirer la réunion « {title} » de son dossier",
        "de": "Meeting „{title}“ aus dem Ordner nehmen",
        "ru": "Убрать встречу «{title}» из папки",
        "nl": "Vergadering ‘{title}’ uit de map halen",
        "it": "Togli la riunione «{title}» dalla cartella",
        "es": "Quitar la reunión «{title}» de su carpeta",
        "pt-BR": "Tirar a reunião “{title}” da pasta", "ar": "إزالة الاجتماع «{title}» من مجلده",
        "tr": "“{title}” toplantısını klasörden çıkar", "ko": "“{title}” 회의를 폴더에서 빼기",
        "hi": "मीटिंग “{title}” को फ़ोल्डर से हटाएँ", "vi": "Gỡ cuộc họp “{title}” khỏi thư mục",
        "zh-Hant": "將會議「{title}」移出資料夾", "ja": "会議「{title}」をフォルダから外す",
        "id": "Keluarkan rapat “{title}” dari folder",
    }),
)  # fmt: skip
REGENERATE_NOTES: Final = PreviewWording(
    key="agent.notes.regenerate_notes",
    params=("title", "template", "shipped"),
    title=words.titled({
        "en": "Write the notes of “{title}” again", "fr": "Réécrire les notes de « {title} »",
        "de": "Notizen zu „{title}“ neu schreiben", "ru": "Заново написать заметки к «{title}»",
        "nl": "Notities van ‘{title}’ opnieuw schrijven", "it": "Riscrivi le note di «{title}»",
        "es": "Volver a escribir las notas de «{title}»",
        "pt-BR": "Reescrever as notas de “{title}”", "ar": "إعادة كتابة ملاحظات «{title}»",
        "tr": "“{title}” notlarını yeniden yaz", "ko": "“{title}” 노트 다시 작성",
        "hi": "“{title}” के नोट फिर से लिखें", "vi": "Viết lại ghi chú của “{title}”",
        "zh-Hant": "重新撰寫「{title}」的筆記", "ja": "「{title}」のノートを書き直す",
        "id": "Tulis ulang catatan “{title}”",
    }),
    fields=(PreviewField("template", words.TEMPLATE, SHIPPED_TEMPLATES),),
)  # fmt: skip
SET_SHARE_LINK: Final = PreviewWording(
    key="agent.notes.set_share_link",
    params=("title", "new", "show_transcript", "show_names", "allow_comments", "expiry"),
    title=words.titled({
        "en": "Share “{title}” by link", "fr": "Partager « {title} » par lien",
        "de": "„{title}“ per Link teilen", "ru": "Поделиться «{title}» по ссылке",
        "nl": "‘{title}’ delen via een link", "it": "Condividi «{title}» tramite link",
        "es": "Compartir «{title}» con un enlace", "pt-BR": "Compartilhar “{title}” por link",
        "ar": "مشاركة «{title}» عبر رابط", "tr": "“{title}” toplantısını bağlantıyla paylaş",
        "ko": "링크로 “{title}” 공유", "hi": "“{title}” को लिंक से शेयर करें",
        "vi": "Chia sẻ “{title}” bằng liên kết", "zh-Hant": "以連結分享「{title}」",
        "ja": "「{title}」をリンクで共有", "id": "Bagikan “{title}” lewat tautan",
    }),
    fields=(
        PreviewField("new", words.LINK, words.LINK_STATES),
        PreviewField("show_transcript", words.TRANSCRIPT, words.TRANSCRIPT_SHOWN),
        PreviewField("show_names", words.NAMES, words.NAMES_SHOWN),
        PreviewField("allow_comments", words.COMMENTS, words.COMMENTS_ALLOWED),
        PreviewField("expiry", words.EXPIRES, words.EXPIRIES),
    ),
)  # fmt: skip
REVOKE_SHARE_LINK: Final = PreviewWording(
    key="agent.notes.revoke_share_link",
    params=("title", "comments"),
    title=words.titled({
        "en": "Stop sharing “{title}”", "fr": "Arrêter le partage de « {title} »",
        "de": "Teilen von „{title}“ beenden", "ru": "Закрыть доступ по ссылке к «{title}»",
        "nl": "Delen van ‘{title}’ stoppen", "it": "Interrompi la condivisione di «{title}»",
        "es": "Dejar de compartir «{title}»", "pt-BR": "Parar de compartilhar “{title}”",
        "ar": "إيقاف مشاركة «{title}»", "tr": "“{title}” paylaşımını durdur",
        "ko": "“{title}” 공유 중지", "hi": "“{title}” की शेयरिंग बंद करें",
        "vi": "Ngừng chia sẻ “{title}”", "zh-Hant": "停止分享「{title}」",
        "ja": "「{title}」の共有を停止", "id": "Berhenti membagikan “{title}”",
    }),
    fields=(PreviewField("comments", words.DELETED_COMMENTS),),
)  # fmt: skip
