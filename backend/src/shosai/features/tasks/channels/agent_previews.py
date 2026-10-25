"""How the cards of Leo's task writes read, in the 16 platform languages (ADR 0068; agent 9b).

Each preview key the task tools return is worded here beside their specs: the title says the
change with the task's name in the language's quotation marks, and the fields carry the values
that change. The words are the cabinet's own — its glossary and its Kanban labels — so a card
and the board name things alike. A field whose value is cleared shows the word for none.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized, PreviewField, PreviewWording

NBSP: Final = " "
DUE: Final[Localized] = {
    "en": "Due", "fr": "Échéance", "de": "Fällig", "ru": "Срок", "nl": "Deadline",
    "it": "Scadenza", "es": "Fecha límite", "pt-BR": "Prazo", "ar": "تاريخ الاستحقاق",
    "tr": "Son tarih", "ko": "마감일", "hi": "आख़िरी तारीख", "vi": "Hạn chót",
    "zh-Hant": "截止日期", "ja": "期限", "id": "Tenggat",
}  # fmt: skip
START: Final[Localized] = {
    "en": "Start", "fr": "Début", "de": "Beginn", "ru": "Начало", "nl": "Start",
    "it": "Inizio", "es": "Inicio", "pt-BR": "Início", "ar": "البداية", "tr": "Başlangıç",
    "ko": "시작일", "hi": "शुरुआत", "vi": "Bắt đầu", "zh-Hant": "開始日期", "ja": "開始日",
    "id": "Mulai",
}  # fmt: skip
PRIORITY: Final[Localized] = {
    "en": "Priority", "fr": "Priorité", "de": "Priorität", "ru": "Приоритет",
    "nl": "Prioriteit", "it": "Priorità", "es": "Prioridad", "pt-BR": "Prioridade",
    "ar": "الأولوية", "tr": "Öncelik", "ko": "우선순위", "hi": "प्राथमिकता", "vi": "Mức ưu tiên",
    "zh-Hant": "優先順序", "ja": "優先度", "id": "Prioritas",
}  # fmt: skip
BOARD: Final[Localized] = {
    "en": "Board", "fr": "Tableau", "de": "Board", "ru": "Доска", "nl": "Bord",
    "it": "Bacheca", "es": "Tablero", "pt-BR": "Quadro", "ar": "لوحة", "tr": "Pano",
    "ko": "보드", "hi": "बोर्ड", "vi": "Bảng", "zh-Hant": "看板", "ja": "ボード", "id": "Papan",
}  # fmt: skip
COLUMN: Final[Localized] = {
    "en": "Column", "fr": "Colonne", "de": "Spalte", "ru": "Колонка", "nl": "Kolom",
    "it": "Colonna", "es": "Columna", "pt-BR": "Coluna", "ar": "العمود", "tr": "Sütun",
    "ko": "열", "hi": "कॉलम", "vi": "Cột", "zh-Hant": "欄", "ja": "列", "id": "Kolom",
}  # fmt: skip
TASKS: Final[Localized] = {
    "en": "Tasks", "fr": "Tâches", "de": "Aufgaben", "ru": "Задачи", "nl": "Taken",
    "it": "Attività", "es": "Tareas", "pt-BR": "Tarefas", "ar": "المهام", "tr": "Görevler",
    "ko": "작업", "hi": "टास्क", "vi": "Công việc", "zh-Hant": "任務", "ja": "タスク",
    "id": "Tugas",
}  # fmt: skip
NEW_TITLE: Final[Localized] = {
    "en": "New title", "fr": "Nouveau titre", "de": "Neuer Titel", "ru": "Новое название",
    "nl": "Nieuwe titel", "it": "Nuovo titolo", "es": "Nuevo título", "pt-BR": "Novo título",
    "ar": "العنوان الجديد", "tr": "Yeni başlık", "ko": "새 제목", "hi": "नया शीर्षक",
    "vi": "Tiêu đề mới", "zh-Hant": "新標題", "ja": "新しいタイトル", "id": "Judul baru",
}  # fmt: skip
ASSIGNEE: Final[Localized] = {
    "en": "Assignee", "fr": "Responsable", "de": "Zugewiesen an", "ru": "Исполнитель",
    "nl": "Toegewezen aan", "it": "Assegnatario", "es": "Responsable", "pt-BR": "Responsável",
    "ar": "المكلف", "tr": "Atanan kişi", "ko": "담당자", "hi": "असाइन किया गया व्यक्ति",
    "vi": "Người được giao", "zh-Hant": "負責人", "ja": "担当者", "id": "Penerima tugas",
}  # fmt: skip
DETAILS: Final[Localized] = {
    "en": "Details", "fr": "Détails", "de": "Details", "ru": "Описание", "nl": "Details",
    "it": "Dettagli", "es": "Detalles", "pt-BR": "Detalhes", "ar": "التفاصيل",
    "tr": "Ayrıntılar", "ko": "세부 정보", "hi": "विवरण", "vi": "Chi tiết",
    "zh-Hant": "詳細資料", "ja": "詳細", "id": "Detail",
}  # fmt: skip
PRIORITIES: Final[dict[str, Localized]] = {
    "high": {
        "en": "High", "fr": "Haute", "de": "Hoch", "ru": "Высокий", "nl": "Hoog", "it": "Alta",
        "es": "Alta", "pt-BR": "Alta", "ar": "عالية", "tr": "Yüksek", "ko": "높음",
        "hi": "ज़्यादा", "vi": "Cao", "zh-Hant": "高", "ja": "高", "id": "Tinggi",
    },
    "medium": {
        "en": "Medium", "fr": "Moyenne", "de": "Mittel", "ru": "Средний", "nl": "Gemiddeld",
        "it": "Media", "es": "Media", "pt-BR": "Média", "ar": "متوسطة", "tr": "Orta",
        "ko": "보통", "hi": "मध्यम", "vi": "Trung bình", "zh-Hant": "中", "ja": "中",
        "id": "Sedang",
    },
    "low": {
        "en": "Low", "fr": "Basse", "de": "Niedrig", "ru": "Низкий", "nl": "Laag",
        "it": "Bassa", "es": "Baja", "pt-BR": "Baixa", "ar": "منخفضة", "tr": "Düşük",
        "ko": "낮음", "hi": "कम", "vi": "Thấp", "zh-Hant": "低", "ja": "低", "id": "Rendah",
    },
}  # fmt: skip
# Код снятого значения: поле показывает «нет» в роде своего слова.
CLEARED: Final = "none"
NO_DATE: Final[Localized] = {
    "en": "None", "fr": "Aucune", "de": "Keine", "ru": "Нет", "nl": "Geen", "it": "Nessuna",
    "es": "Ninguna", "pt-BR": "Nenhum", "ar": "لا يوجد", "tr": "Yok", "ko": "없음",
    "hi": "कोई नहीं", "vi": "Không có", "zh-Hant": "無", "ja": "なし", "id": "Tidak ada",
}  # fmt: skip
NO_START: Final[Localized] = {
    **NO_DATE,
    "fr": "Aucun", "de": "Keiner", "it": "Nessuno", "es": "Ninguno",
}  # fmt: skip
NO_PRIORITY: Final[Localized] = {**NO_DATE, "pt-BR": "Nenhuma"}
NOBODY: Final[Localized] = {
    "en": "Nobody", "fr": "Personne", "de": "Niemand", "ru": "Никто", "nl": "Niemand",
    "it": "Nessuno", "es": "Nadie", "pt-BR": "Ninguém", "ar": "لا أحد", "tr": "Kimse",
    "ko": "없음", "hi": "कोई नहीं", "vi": "Không ai", "zh-Hant": "無", "ja": "なし",
    "id": "Tidak ada",
}  # fmt: skip
DETAIL_VALUES: Final[dict[str, Localized]] = {
    "changed": {
        "en": "Updated", "fr": "Modifiés", "de": "Geändert", "ru": "Изменено",
        "nl": "Gewijzigd", "it": "Modificati", "es": "Modificados", "pt-BR": "Alterados",
        "ar": "تم تعديلها", "tr": "Güncellendi", "ko": "변경됨", "hi": "बदला गया",
        "vi": "Đã thay đổi", "zh-Hant": "已變更", "ja": "変更あり", "id": "Diubah",
    },
    CLEARED: {
        "en": "Removed", "fr": "Supprimés", "de": "Entfernt", "ru": "Удалено",
        "nl": "Verwijderd", "it": "Rimossi", "es": "Eliminados", "pt-BR": "Removidos",
        "ar": "تمت إزالتها", "tr": "Kaldırıldı", "ko": "삭제됨", "hi": "हटाया गया",
        "vi": "Đã xóa", "zh-Hant": "已移除", "ja": "削除", "id": "Dihapus",
    },
}  # fmt: skip


def titled(template: Localized) -> Localized:
    """A title with French's no-break spaces inside its guillemets."""
    french = template["fr"].replace("« ", f"«{NBSP}").replace(" »", f"{NBSP}»")
    return {**template, "fr": french}


CREATE_ONE: Final = PreviewWording(
    key="agent.tasks.create",
    params=("title", "due_on", "priority", "board"),
    title=titled({
        "en": "Create the task “{title}”", "fr": "Créer la tâche « {title} »",
        "de": "Aufgabe „{title}“ erstellen", "ru": "Создать задачу «{title}»",
        "nl": "Taak ‘{title}’ maken", "it": "Crea l’attività «{title}»",
        "es": "Crear la tarea «{title}»", "pt-BR": "Criar a tarefa “{title}”",
        "ar": "إنشاء المهمة «{title}»", "tr": "“{title}” görevini oluştur",
        "ko": "“{title}” 작업 만들기", "hi": "टास्क “{title}” बनाएँ",
        "vi": "Tạo công việc “{title}”", "zh-Hant": "建立任務「{title}」",
        "ja": "タスク「{title}」を作成", "id": "Buat tugas “{title}”",
    }),
    fields=(
        PreviewField("due_on", DUE),
        PreviewField("priority", PRIORITY, PRIORITIES),
        PreviewField("board", BOARD),
    ),
)  # fmt: skip
CREATE_MANY: Final = PreviewWording(
    key="agent.tasks.create_many",
    params=("count", "first", "board"),
    title=titled({
        "en": "Create tasks, starting with “{first}”",
        "fr": "Créer des tâches, en commençant par « {first} »",
        "de": "Aufgaben erstellen, beginnend mit „{first}“",
        "ru": "Создать задачи, начиная с «{first}»", "nl": "Taken maken, te beginnen met ‘{first}’",
        "it": "Crea attività, a partire da «{first}»",
        "es": "Crear tareas, empezando por «{first}»",
        "pt-BR": "Criar tarefas, começando por “{first}”", "ar": "إنشاء مهام، بدءًا من «{first}»",
        "tr": "“{first}” ile başlayarak görevler oluştur", "ko": "“{first}”부터 작업 만들기",
        "hi": "“{first}” से शुरू करके टास्क बनाएँ", "vi": "Tạo các công việc, bắt đầu từ “{first}”",
        "zh-Hant": "建立任務，從「{first}」開始", "ja": "「{first}」から始まるタスクを作成",
        "id": "Buat tugas, dimulai dari “{first}”",
    }),
    fields=(PreviewField("count", TASKS), PreviewField("board", BOARD)),
)  # fmt: skip
UPDATE: Final = PreviewWording(
    key="agent.tasks.update",
    params=("title", "new_title", "due_on", "starts_on", "priority", "assignee", "details"),
    title=titled({
        "en": "Change the task “{title}”", "fr": "Modifier la tâche « {title} »",
        "de": "Aufgabe „{title}“ ändern", "ru": "Изменить задачу «{title}»",
        "nl": "Taak ‘{title}’ wijzigen", "it": "Modifica l’attività «{title}»",
        "es": "Cambiar la tarea «{title}»", "pt-BR": "Alterar a tarefa “{title}”",
        "ar": "تعديل المهمة «{title}»", "tr": "“{title}” görevini değiştir",
        "ko": "“{title}” 작업 변경", "hi": "टास्क “{title}” बदलें",
        "vi": "Thay đổi công việc “{title}”", "zh-Hant": "變更任務「{title}」",
        "ja": "タスク「{title}」を変更", "id": "Ubah tugas “{title}”",
    }),
    fields=(
        PreviewField("new_title", NEW_TITLE),
        PreviewField("due_on", DUE, {CLEARED: NO_DATE}),
        PreviewField("starts_on", START, {CLEARED: NO_START}),
        PreviewField("priority", PRIORITY, PRIORITIES | {CLEARED: NO_PRIORITY}),
        PreviewField("assignee", ASSIGNEE, {CLEARED: NOBODY}),
        PreviewField("details", DETAILS, DETAIL_VALUES),
    ),
)  # fmt: skip
COMPLETE: Final = PreviewWording(
    key="agent.tasks.complete",
    params=("title",),
    title=titled({
        "en": "Mark the task “{title}” as done",
        "fr": "Marquer la tâche « {title} » comme terminée",
        "de": "Aufgabe „{title}“ als erledigt markieren",
        "ru": "Отметить задачу «{title}» выполненной", "nl": "Taak ‘{title}’ als afgerond markeren",
        "it": "Segna l’attività «{title}» come completata",
        "es": "Marcar la tarea «{title}» como completada",
        "pt-BR": "Marcar a tarefa “{title}” como concluída",
        "ar": "وضع علامة مكتملة على المهمة «{title}»",
        "tr": "“{title}” görevini tamamlandı olarak işaretle",
        "ko": "“{title}” 작업을 완료로 표시", "hi": "टास्क “{title}” को पूरा हुआ मार्क करें",
        "vi": "Đánh dấu công việc “{title}” là hoàn thành",
        "zh-Hant": "將任務「{title}」標示為完成",
        "ja": "タスク「{title}」を完了にする", "id": "Tandai tugas “{title}” sebagai selesai",
    }),
)  # fmt: skip
REOPEN: Final = PreviewWording(
    key="agent.tasks.reopen",
    params=("title",),
    title=titled({
        "en": "Reopen the task “{title}”", "fr": "Rouvrir la tâche « {title} »",
        "de": "Aufgabe „{title}“ wieder öffnen", "ru": "Снова открыть задачу «{title}»",
        "nl": "Taak ‘{title}’ heropenen", "it": "Riapri l’attività «{title}»",
        "es": "Reabrir la tarea «{title}»", "pt-BR": "Reabrir a tarefa “{title}”",
        "ar": "إعادة فتح المهمة «{title}»", "tr": "“{title}” görevini yeniden aç",
        "ko": "“{title}” 작업 다시 열기", "hi": "टास्क “{title}” फिर से खोलें",
        "vi": "Mở lại công việc “{title}”", "zh-Hant": "重新開啟任務「{title}」",
        "ja": "タスク「{title}」を再開", "id": "Buka kembali tugas “{title}”",
    }),
)  # fmt: skip
MOVE: Final = PreviewWording(
    key="agent.tasks.move",
    params=("title", "board", "column"),
    title=titled({
        "en": "Move the task “{title}”", "fr": "Déplacer la tâche « {title} »",
        "de": "Aufgabe „{title}“ verschieben", "ru": "Переместить задачу «{title}»",
        "nl": "Taak ‘{title}’ verplaatsen", "it": "Sposta l’attività «{title}»",
        "es": "Mover la tarea «{title}»", "pt-BR": "Mover a tarefa “{title}”",
        "ar": "نقل المهمة «{title}»", "tr": "“{title}” görevini taşı",
        "ko": "“{title}” 작업 이동", "hi": "टास्क “{title}” को ले जाएँ",
        "vi": "Di chuyển công việc “{title}”", "zh-Hant": "移動任務「{title}」",
        "ja": "タスク「{title}」を移動", "id": "Pindahkan tugas “{title}”",
    }),
    fields=(PreviewField("board", BOARD), PreviewField("column", COLUMN)),
)  # fmt: skip
