"""The words of a new board's template columns in the 16 platform languages (§3.14).

A board is created with its template's columns named in the request's language, in the
cabinet's own words (`frontend/src/i18n/messages/*/kanbanBoards.json`, `columnNames`); the
person renames them freely afterwards. A language outside the 16 takes English.
"""

from typing import Final

from shosai.features.tasks.domain.boards import TemplateColumn

DEFAULT_LANGUAGE: Final = "en"
TEMPLATE_WORDS: Final[dict[str, dict[TemplateColumn, str]]] = {
    "en": {
        TemplateColumn.BACKLOG: "Backlog",
        TemplateColumn.TODO: "To do",
        TemplateColumn.IN_PROGRESS: "In progress",
        TemplateColumn.REVIEW: "Review",
        TemplateColumn.DONE: "Done",
    },
    "fr": {
        TemplateColumn.BACKLOG: "À planifier",
        TemplateColumn.TODO: "À faire",
        TemplateColumn.IN_PROGRESS: "En cours",
        TemplateColumn.REVIEW: "En revue",
        TemplateColumn.DONE: "Terminé",
    },
    "de": {
        TemplateColumn.BACKLOG: "Backlog",
        TemplateColumn.TODO: "Zu erledigen",
        TemplateColumn.IN_PROGRESS: "In Arbeit",
        TemplateColumn.REVIEW: "In Prüfung",
        TemplateColumn.DONE: "Erledigt",
    },
    "ru": {
        TemplateColumn.BACKLOG: "Бэклог",
        TemplateColumn.TODO: "К выполнению",
        TemplateColumn.IN_PROGRESS: "В работе",
        TemplateColumn.REVIEW: "На проверке",
        TemplateColumn.DONE: "Готово",
    },
    "nl": {
        TemplateColumn.BACKLOG: "Werkvoorraad",
        TemplateColumn.TODO: "Te doen",
        TemplateColumn.IN_PROGRESS: "Bezig",
        TemplateColumn.REVIEW: "Ter controle",
        TemplateColumn.DONE: "Afgerond",
    },
    "it": {
        TemplateColumn.BACKLOG: "Da pianificare",
        TemplateColumn.TODO: "Da fare",
        TemplateColumn.IN_PROGRESS: "In corso",
        TemplateColumn.REVIEW: "In revisione",
        TemplateColumn.DONE: "Completate",
    },
    "es": {
        TemplateColumn.BACKLOG: "Pendientes",
        TemplateColumn.TODO: "Por hacer",
        TemplateColumn.IN_PROGRESS: "En curso",
        TemplateColumn.REVIEW: "En revisión",
        TemplateColumn.DONE: "Listo",
    },
    "pt-BR": {
        TemplateColumn.BACKLOG: "Pendências",
        TemplateColumn.TODO: "A fazer",
        TemplateColumn.IN_PROGRESS: "Em andamento",
        TemplateColumn.REVIEW: "Em revisão",
        TemplateColumn.DONE: "Concluído",
    },
    "ar": {
        TemplateColumn.BACKLOG: "الأعمال المتراكمة",
        TemplateColumn.TODO: "للتنفيذ",
        TemplateColumn.IN_PROGRESS: "قيد التنفيذ",
        TemplateColumn.REVIEW: "قيد المراجعة",
        TemplateColumn.DONE: "مكتملة",
    },
    "tr": {
        TemplateColumn.BACKLOG: "Bekleyen işler",
        TemplateColumn.TODO: "Yapılacaklar",
        TemplateColumn.IN_PROGRESS: "Devam ediyor",
        TemplateColumn.REVIEW: "İnceleme",
        TemplateColumn.DONE: "Tamamlandı",
    },
    "ko": {
        TemplateColumn.BACKLOG: "백로그",
        TemplateColumn.TODO: "할 일",
        TemplateColumn.IN_PROGRESS: "진행 중",
        TemplateColumn.REVIEW: "검토 중",
        TemplateColumn.DONE: "완료",
    },
    "hi": {
        TemplateColumn.BACKLOG: "बैकलॉग",
        TemplateColumn.TODO: "करना है",
        TemplateColumn.IN_PROGRESS: "चल रहा है",
        TemplateColumn.REVIEW: "रिव्यू",
        TemplateColumn.DONE: "पूरा हुआ",
    },
    "vi": {
        TemplateColumn.BACKLOG: "Tồn đọng",
        TemplateColumn.TODO: "Cần làm",
        TemplateColumn.IN_PROGRESS: "Đang làm",
        TemplateColumn.REVIEW: "Đang duyệt",
        TemplateColumn.DONE: "Hoàn thành",
    },
    "zh-Hant": {
        TemplateColumn.BACKLOG: "待規劃",
        TemplateColumn.TODO: "待辦",
        TemplateColumn.IN_PROGRESS: "進行中",
        TemplateColumn.REVIEW: "審查中",
        TemplateColumn.DONE: "完成",
    },
    "ja": {
        TemplateColumn.BACKLOG: "バックログ",
        TemplateColumn.TODO: "未着手",
        TemplateColumn.IN_PROGRESS: "進行中",
        TemplateColumn.REVIEW: "レビュー",
        TemplateColumn.DONE: "完了",
    },
    "id": {
        TemplateColumn.BACKLOG: "Antrean",
        TemplateColumn.TODO: "Belum dikerjakan",
        TemplateColumn.IN_PROGRESS: "Sedang dikerjakan",
        TemplateColumn.REVIEW: "Peninjauan",
        TemplateColumn.DONE: "Selesai",
    },
}


def column_word(column: TemplateColumn, language: str | None) -> str:
    """The template column's name in the language, English when the language is not one of
    the platform's."""
    words = TEMPLATE_WORDS.get(language or DEFAULT_LANGUAGE, TEMPLATE_WORDS[DEFAULT_LANGUAGE])
    return words[column]
