"""The words on the cards of Leo's meeting writes: labels and values, in 16 languages (9b).

The labels are the cabinet's own where it has them — the folder field, the transcript, the
share panel's expiry and its "never" — so a card and the meeting's screens name things alike;
a value word agrees with its label where the language needs it.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized

NBSP: Final = "\u00a0"
FOLDER: Final[Localized] = {
    "en": "Folder", "fr": "Dossier", "de": "Ordner", "ru": "Папка", "nl": "Map",
    "it": "Cartella", "es": "Carpeta", "pt-BR": "Pasta", "ar": "المجلد", "tr": "Klasör",
    "ko": "폴더", "hi": "फ़ोल्डर", "vi": "Thư mục", "zh-Hant": "資料夾", "ja": "フォルダ",
    "id": "Folder",
}  # fmt: skip
TRANSCRIPT: Final[Localized] = {
    "en": "Transcript", "fr": "Transcription", "de": "Transkript", "ru": "Расшифровка",
    "nl": "Transcriptie", "it": "Trascrizione", "es": "Transcripción", "pt-BR": "Transcrição",
    "ar": "النص", "tr": "Transkript", "ko": "스크립트", "hi": "ट्रांसक्रिप्ट", "vi": "Bản chép lời",
    "zh-Hant": "逐字稿", "ja": "文字起こし", "id": "Transkrip",
}  # fmt: skip
EXPIRES: Final[Localized] = {
    "en": "Expires", "fr": "Expiration", "de": "Läuft ab", "ru": "Срок действия",
    "nl": "Verloopt", "it": "Scadenza", "es": "Caduca", "pt-BR": "Expiração",
    "ar": "انتهاء الصلاحية", "tr": "Geçerlilik süresi", "ko": "만료", "hi": "लिंक की अवधि",
    "vi": "Hết hạn", "zh-Hant": "到期時間", "ja": "有効期限", "id": "Kedaluwarsa",
}  # fmt: skip
NEVER: Final[Localized] = {
    "en": "Never", "fr": "Jamais", "de": "Nie", "ru": "Бессрочно", "nl": "Nooit", "it": "Mai",
    "es": "Nunca", "pt-BR": "Nunca", "ar": "أبدًا", "tr": "Süresiz", "ko": "없음", "hi": "हमेशा",
    "vi": "Không bao giờ", "zh-Hant": "永不", "ja": "なし", "id": "Tidak pernah",
}  # fmt: skip
TEMPLATE: Final[Localized] = {
    "en": "Template", "fr": "Modèle", "de": "Vorlage", "ru": "Шаблон", "nl": "Sjabloon",
    "it": "Modello", "es": "Plantilla", "pt-BR": "Template", "ar": "القالب", "tr": "Şablon",
    "ko": "템플릿", "hi": "टेंप्लेट", "vi": "Mẫu", "zh-Hant": "範本", "ja": "テンプレート",
    "id": "Template",
}  # fmt: skip
LINK: Final[Localized] = {
    "en": "Link", "fr": "Lien", "de": "Link", "ru": "Ссылка", "nl": "Link", "it": "Link",
    "es": "Enlace", "pt-BR": "Link", "ar": "الرابط", "tr": "Bağlantı", "ko": "링크",
    "hi": "लिंक", "vi": "Liên kết", "zh-Hant": "連結", "ja": "リンク", "id": "Tautan",
}  # fmt: skip
NAMES: Final[Localized] = {
    "en": "Participant names", "fr": "Noms des participants", "de": "Namen der Teilnehmer",
    "ru": "Имена участников", "nl": "Namen van deelnemers", "it": "Nomi dei partecipanti",
    "es": "Nombres de los participantes", "pt-BR": "Nomes dos participantes",
    "ar": "أسماء المشاركين", "tr": "Katılımcı adları", "ko": "참석자 이름",
    "hi": "प्रतिभागियों के नाम", "vi": "Tên người tham gia", "zh-Hant": "參與者名稱",
    "ja": "参加者の名前", "id": "Nama peserta",
}  # fmt: skip
COMMENTS: Final[Localized] = {
    "en": "Comments", "fr": "Commentaires", "de": "Kommentare", "ru": "Комментарии",
    "nl": "Opmerkingen", "it": "Commenti", "es": "Comentarios", "pt-BR": "Comentários",
    "ar": "التعليقات", "tr": "Yorumlar", "ko": "댓글", "hi": "टिप्पणियाँ", "vi": "Bình luận",
    "zh-Hant": "留言", "ja": "コメント", "id": "Komentar",
}  # fmt: skip
DELETED_COMMENTS: Final[Localized] = {
    "en": "Comments deleted", "fr": "Commentaires supprimés", "de": "Gelöschte Kommentare",
    "ru": "Удаляемые комментарии", "nl": "Verwijderde opmerkingen", "it": "Commenti eliminati",
    "es": "Comentarios eliminados", "pt-BR": "Comentários excluídos",
    "ar": "التعليقات المحذوفة", "tr": "Silinecek yorumlar", "ko": "삭제되는 댓글",
    "hi": "हटाई जाने वाली टिप्पणियाँ", "vi": "Bình luận bị xóa", "zh-Hant": "將刪除的留言",
    "ja": "削除されるコメント", "id": "Komentar yang dihapus",
}  # fmt: skip
LINK_STATES: Final[dict[str, Localized]] = {
    "true": {
        "en": "New", "fr": "Nouveau", "de": "Neu", "ru": "Новая", "nl": "Nieuw", "it": "Nuovo",
        "es": "Nuevo", "pt-BR": "Novo", "ar": "جديد", "tr": "Yeni", "ko": "새 링크",
        "hi": "नया", "vi": "Mới", "zh-Hant": "新連結", "ja": "新規", "id": "Baru",
    },
    "false": {
        "en": "Changed", "fr": "Modifié", "de": "Geändert", "ru": "Изменена",
        "nl": "Gewijzigd", "it": "Modificato", "es": "Modificado", "pt-BR": "Alterado",
        "ar": "معدّل", "tr": "Değiştirildi", "ko": "변경", "hi": "बदला गया",
        "vi": "Đã thay đổi", "zh-Hant": "已變更", "ja": "変更", "id": "Diubah",
    },
}  # fmt: skip
TRANSCRIPT_SHOWN: Final[dict[str, Localized]] = {
    "true": {
        "en": "Shown", "fr": "Affichée", "de": "Sichtbar", "ru": "Видна", "nl": "Zichtbaar",
        "it": "Visibile", "es": "Visible", "pt-BR": "Visível", "ar": "ظاهر", "tr": "Görünür",
        "ko": "표시", "hi": "दिखेगा", "vi": "Hiện", "zh-Hant": "顯示", "ja": "表示",
        "id": "Ditampilkan",
    },
    "false": {
        "en": "Hidden", "fr": "Masquée", "de": "Ausgeblendet", "ru": "Скрыта",
        "nl": "Verborgen", "it": "Nascosta", "es": "Oculta", "pt-BR": "Oculta", "ar": "مخفي",
        "tr": "Gizli", "ko": "숨김", "hi": "छिपा रहेगा", "vi": "Ẩn", "zh-Hant": "隱藏",
        "ja": "非表示", "id": "Disembunyikan",
    },
}  # fmt: skip
NAMES_SHOWN: Final[dict[str, Localized]] = {
    "true": {
        **TRANSCRIPT_SHOWN["true"], "fr": "Affichés", "ru": "Видны", "it": "Visibili",
        "es": "Visibles", "pt-BR": "Visíveis", "ar": "ظاهرة", "hi": "दिखेंगे",
    },
    "false": {
        **TRANSCRIPT_SHOWN["false"], "fr": "Masqués", "ru": "Скрыты", "it": "Nascosti",
        "es": "Ocultos", "pt-BR": "Ocultos", "ar": "مخفية", "hi": "छिपे रहेंगे",
    },
}  # fmt: skip
COMMENTS_ALLOWED: Final[dict[str, Localized]] = {
    "true": {
        "en": "Allowed", "fr": "Autorisés", "de": "Erlaubt", "ru": "Разрешены",
        "nl": "Toegestaan", "it": "Consentiti", "es": "Permitidos", "pt-BR": "Permitidos",
        "ar": "مسموح بها", "tr": "İzinli", "ko": "허용", "hi": "अनुमति है", "vi": "Cho phép",
        "zh-Hant": "允許", "ja": "許可", "id": "Diizinkan",
    },
    "false": {
        "en": "Off", "fr": "Désactivés", "de": "Aus", "ru": "Выключены", "nl": "Uit",
        "it": "Disattivati", "es": "Desactivados", "pt-BR": "Desativados", "ar": "متوقفة",
        "tr": "Kapalı", "ko": "사용 안 함", "hi": "बंद", "vi": "Tắt", "zh-Hant": "關閉",
        "ja": "オフ", "id": "Nonaktif",
    },
}  # fmt: skip


def in_days(days: int) -> Localized:
    """When a link stops working, counted from now."""
    many = "يومًا" if days > 10 else "أيام"
    return {
        "en": f"In {days} days", "fr": f"Dans {days}{NBSP}jours", "de": f"In {days} Tagen",
        "ru": f"Через {days} дней", "nl": f"Over {days} dagen", "it": f"Tra {days} giorni",
        "es": f"En {days} días", "pt-BR": f"Em {days} dias", "ar": f"بعد {days} {many}",
        "tr": f"{days} gün sonra", "ko": f"{days}일 후", "hi": f"{days} दिनों में",
        "vi": f"Sau {days} ngày", "zh-Hant": f"{days} 天後", "ja": f"{days} 日後",
        "id": f"Dalam {days} hari",
    }  # fmt: skip


EXPIRIES: Final[dict[str, Localized]] = {
    "never": NEVER, "7d": in_days(7), "30d": in_days(30), "90d": in_days(90),
}  # fmt: skip


def titled(template: Localized) -> Localized:
    """A title with French's no-break spaces inside its guillemets."""
    french = template["fr"].replace("« ", f"«{NBSP}").replace(" »", f"{NBSP}»")
    return {**template, "fr": french}
