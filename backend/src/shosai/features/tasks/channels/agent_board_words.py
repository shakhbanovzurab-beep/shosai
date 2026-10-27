"""How the cards of Leo's board writes read, in the 16 platform languages (Leo §8.4).

The words are the cabinet's own — its Kanban boards' labels and the kinds of a column — so a
card and the board name things alike. A deleted board's card says how many of the person's
tasks go with it; a removed column's card says where its cards go.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized, PreviewField, PreviewWording
from shosai.features.tasks.channels.agent_previews import BOARD, titled

COLUMNS: Final[Localized] = {
    "en": "Columns", "fr": "Colonnes", "de": "Spalten", "ru": "Колонки", "nl": "Kolommen",
    "it": "Colonne", "es": "Columnas", "pt-BR": "Colunas", "ar": "الأعمدة", "tr": "Sütunlar",
    "ko": "열", "hi": "कॉलम", "vi": "Cột", "zh-Hant": "欄", "ja": "列", "id": "Kolom",
}  # fmt: skip
NEW_NAME: Final[Localized] = {
    "en": "New name", "fr": "Nouveau nom", "de": "Neuer Name", "ru": "Новое название",
    "nl": "Nieuwe naam", "it": "Nuovo nome", "es": "Nuevo nombre", "pt-BR": "Novo nome",
    "ar": "الاسم الجديد", "tr": "Yeni ad", "ko": "새 이름", "hi": "नया नाम", "vi": "Tên mới",
    "zh-Hant": "新名稱", "ja": "新しい名前", "id": "Nama baru",
}  # fmt: skip
GONE_TASKS: Final[Localized] = {
    "en": "Tasks deleted with it", "fr": "Tâches supprimées avec lui",
    "de": "Mit gelöschte Aufgaben", "ru": "Задачи, удаляемые вместе с ней",
    "nl": "Taken die mee verdwijnen", "it": "Attività eliminate con essa",
    "es": "Tareas que se eliminan con él", "pt-BR": "Tarefas excluídas junto",
    "ar": "مهام تُحذف معها", "tr": "Onunla silinen görevler", "ko": "함께 삭제되는 작업",
    "hi": "साथ में हटाए जाने वाले टास्क", "vi": "Công việc bị xóa theo",
    "zh-Hant": "一併刪除的任務", "ja": "一緒に削除されるタスク", "id": "Tugas yang ikut terhapus",
}  # fmt: skip
STATUS: Final[Localized] = {
    "en": "Status", "fr": "Statut", "de": "Status", "ru": "Статус", "nl": "Status",
    "it": "Stato", "es": "Estado", "pt-BR": "Status", "ar": "الحالة", "tr": "Durum",
    "ko": "상태", "hi": "स्थिति", "vi": "Trạng thái", "zh-Hant": "狀態", "ja": "ステータス",
    "id": "Status",
}  # fmt: skip
KINDS: Final[dict[str, Localized]] = {
    "todo": {
        "en": "To do", "fr": "À faire", "de": "Zu erledigen", "ru": "К выполнению",
        "nl": "Te doen", "it": "Da fare", "es": "Por hacer", "pt-BR": "A fazer",
        "ar": "للتنفيذ", "tr": "Yapılacaklar", "ko": "할 일", "hi": "करना है", "vi": "Cần làm",
        "zh-Hant": "待辦", "ja": "未着手", "id": "Belum dikerjakan",
    },
    "in_progress": {
        "en": "In progress", "fr": "En cours", "de": "In Arbeit", "ru": "В работе",
        "nl": "Bezig", "it": "In corso", "es": "En curso", "pt-BR": "Em andamento",
        "ar": "قيد التنفيذ", "tr": "Devam ediyor", "ko": "진행 중", "hi": "चल रहा है",
        "vi": "Đang làm", "zh-Hant": "進行中", "ja": "進行中", "id": "Sedang dikerjakan",
    },
    "done": {
        "en": "Done", "fr": "Terminé", "de": "Erledigt", "ru": "Готово", "nl": "Afgerond",
        "it": "Completate", "es": "Listo", "pt-BR": "Concluído", "ar": "مكتملة",
        "tr": "Tamamlandı", "ko": "완료", "hi": "पूरा हुआ", "vi": "Hoàn thành",
        "zh-Hant": "完成", "ja": "完了", "id": "Selesai",
    },
}  # fmt: skip
CARDS_TO: Final[Localized] = {
    "en": "Cards go to", "fr": "Les cartes vont dans", "de": "Karten wandern nach",
    "ru": "Карточки переходят в", "nl": "Kaarten gaan naar", "it": "Le schede vanno in",
    "es": "Las tarjetas pasan a", "pt-BR": "Os cartões vão para", "ar": "تنتقل البطاقات إلى",
    "tr": "Kartların gideceği yer", "ko": "카드가 옮겨질 열", "hi": "कार्ड यहाँ जाएँगे",
    "vi": "Thẻ chuyển sang", "zh-Hant": "卡片移至", "ja": "カードの移動先", "id": "Kartu pindah ke",
}  # fmt: skip

CREATE: Final = PreviewWording(
    key="agent.boards.create",
    params=("name", "columns"),
    title=titled({
        "en": "Create the board “{name}”", "fr": "Créer le tableau « {name} »",
        "de": "Board „{name}“ erstellen", "ru": "Создать доску «{name}»",
        "nl": "Bord ‘{name}’ maken", "it": "Crea la bacheca «{name}»",
        "es": "Crear el tablero «{name}»", "pt-BR": "Criar o quadro “{name}”",
        "ar": "إنشاء اللوحة «{name}»", "tr": "“{name}” panosunu oluştur",
        "ko": "“{name}” 보드 만들기", "hi": "बोर्ड “{name}” बनाएँ", "vi": "Tạo bảng “{name}”",
        "zh-Hant": "建立看板「{name}」",
        "ja": "ボード「{name}」を作成",
        "id": "Buat papan “{name}”",
    }),
    fields=(PreviewField("columns", COLUMNS),),
)  # fmt: skip
UPDATE: Final = PreviewWording(
    key="agent.boards.update",
    params=("name", "new_name"),
    title=titled({
        "en": "Change the board “{name}”", "fr": "Modifier le tableau « {name} »",
        "de": "Board „{name}“ ändern", "ru": "Изменить доску «{name}»",
        "nl": "Bord ‘{name}’ wijzigen", "it": "Modifica la bacheca «{name}»",
        "es": "Cambiar el tablero «{name}»", "pt-BR": "Alterar o quadro “{name}”",
        "ar": "تعديل اللوحة «{name}»", "tr": "“{name}” panosunu değiştir",
        "ko": "“{name}” 보드 변경", "hi": "बोर्ड “{name}” बदलें", "vi": "Thay đổi bảng “{name}”",
        "zh-Hant": "變更看板「{name}」",
        "ja": "ボード「{name}」を変更",
        "id": "Ubah papan “{name}”",
    }),
    fields=(PreviewField("new_name", NEW_NAME),),
)  # fmt: skip
DELETE: Final = PreviewWording(
    key="agent.boards.delete",
    params=("name", "tasks"),
    title=titled({
        "en": "Delete the board “{name}”", "fr": "Supprimer le tableau « {name} »",
        "de": "Board „{name}“ löschen", "ru": "Удалить доску «{name}»",
        "nl": "Bord ‘{name}’ verwijderen", "it": "Elimina la bacheca «{name}»",
        "es": "Eliminar el tablero «{name}»", "pt-BR": "Excluir o quadro “{name}”",
        "ar": "حذف اللوحة «{name}»", "tr": "“{name}” panosunu sil",
        "ko": "“{name}” 보드 삭제", "hi": "बोर्ड “{name}” हटाएँ", "vi": "Xóa bảng “{name}”",
        "zh-Hant": "刪除看板「{name}」",
        "ja": "ボード「{name}」を削除",
        "id": "Hapus papan “{name}”",
    }),
    fields=(PreviewField("tasks", GONE_TASKS),),
)  # fmt: skip
ADD_COLUMN: Final = PreviewWording(
    key="agent.boards.add_column",
    params=("title", "board", "kind"),
    title=titled({
        "en": "Add the column “{title}”", "fr": "Ajouter la colonne « {title} »",
        "de": "Spalte „{title}“ hinzufügen", "ru": "Добавить колонку «{title}»",
        "nl": "Kolom ‘{title}’ toevoegen", "it": "Aggiungi la colonna «{title}»",
        "es": "Añadir la columna «{title}»", "pt-BR": "Adicionar a coluna “{title}”",
        "ar": "إضافة العمود «{title}»", "tr": "“{title}” sütununu ekle",
        "ko": "“{title}” 열 추가", "hi": "कॉलम “{title}” जोड़ें", "vi": "Thêm cột “{title}”",
        "zh-Hant": "新增欄「{title}」",
        "ja": "列「{title}」を追加",
        "id": "Tambahkan kolom “{title}”",
    }),
    fields=(PreviewField("board", BOARD), PreviewField("kind", STATUS, KINDS)),
)  # fmt: skip
UPDATE_COLUMN: Final = PreviewWording(
    key="agent.boards.update_column",
    params=("title", "board", "new_title"),
    title=titled({
        "en": "Change the column “{title}”", "fr": "Modifier la colonne « {title} »",
        "de": "Spalte „{title}“ ändern", "ru": "Изменить колонку «{title}»",
        "nl": "Kolom ‘{title}’ wijzigen", "it": "Modifica la colonna «{title}»",
        "es": "Cambiar la columna «{title}»", "pt-BR": "Alterar a coluna “{title}”",
        "ar": "تعديل العمود «{title}»", "tr": "“{title}” sütununu değiştir",
        "ko": "“{title}” 열 변경", "hi": "कॉलम “{title}” बदलें", "vi": "Thay đổi cột “{title}”",
        "zh-Hant": "變更欄「{title}」", "ja": "列「{title}」を変更", "id": "Ubah kolom “{title}”",
    }),
    fields=(PreviewField("board", BOARD), PreviewField("new_title", NEW_NAME)),
)  # fmt: skip
DELETE_COLUMN: Final = PreviewWording(
    key="agent.boards.delete_column",
    params=("title", "board", "moved_to"),
    title=titled({
        "en": "Remove the column “{title}”", "fr": "Supprimer la colonne « {title} »",
        "de": "Spalte „{title}“ entfernen", "ru": "Удалить колонку «{title}»",
        "nl": "Kolom ‘{title}’ verwijderen", "it": "Rimuovi la colonna «{title}»",
        "es": "Quitar la columna «{title}»", "pt-BR": "Remover a coluna “{title}”",
        "ar": "إزالة العمود «{title}»", "tr": "“{title}” sütununu kaldır",
        "ko": "“{title}” 열 삭제", "hi": "कॉलम “{title}” हटाएँ", "vi": "Xóa cột “{title}”",
        "zh-Hant": "移除欄「{title}」", "ja": "列「{title}」を削除", "id": "Hapus kolom “{title}”",
    }),
    fields=(PreviewField("board", BOARD), PreviewField("moved_to", CARDS_TO)),
)  # fmt: skip
INCOMING: Final = PreviewWording(
    key="agent.boards.incoming",
    params=("board",),
    title=titled({
        "en": "Put incoming tasks on “{board}”",
        "fr": "Mettre les tâches entrantes sur « {board} »",
        "de": "Eingehende Aufgaben auf „{board}“ legen",
        "ru": "Класть входящие задачи на доску «{board}»",
        "nl": "Binnenkomende taken op ‘{board}’ zetten",
        "it": "Mettere le attività in arrivo su «{board}»",
        "es": "Poner las tareas entrantes en «{board}»",
        "pt-BR": "Colocar as tarefas recebidas em “{board}”",
        "ar": "وضع المهام الواردة على «{board}»", "tr": "Gelen görevleri “{board}” panosuna koy",
        "ko": "들어오는 작업을 “{board}” 보드에 넣기", "hi": "आने वाले टास्क “{board}” पर रखें",
        "vi": "Đưa công việc đến vào “{board}”", "zh-Hant": "將收到的任務放到「{board}」",
        "ja": "受け取ったタスクを「{board}」に入れる",
        "id": "Masukkan tugas yang datang ke “{board}”",
    }),
)  # fmt: skip
NO_INCOMING: Final = PreviewWording(
    key="agent.boards.no_incoming",
    params=(),
    title={
        "en": "Stop putting incoming tasks on a board",
        "fr": "Ne plus mettre les tâches entrantes sur un tableau",
        "de": "Eingehende Aufgaben auf kein Board mehr legen",
        "ru": "Больше не класть входящие задачи на доску",
        "nl": "Binnenkomende taken niet meer op een bord zetten",
        "it": "Non mettere più le attività in arrivo su una bacheca",
        "es": "Dejar de poner las tareas entrantes en un tablero",
        "pt-BR": "Parar de colocar as tarefas recebidas em um quadro",
        "ar": "التوقف عن وضع المهام الواردة على لوحة",
        "tr": "Gelen görevleri artık bir panoya koyma",
        "ko": "들어오는 작업을 더 이상 보드에 넣지 않기", "hi": "आने वाले टास्क अब किसी बोर्ड पर न रखें",
        "vi": "Ngừng đưa công việc đến vào bảng", "zh-Hant": "不再將收到的任務放到看板",
        "ja": "受け取ったタスクをボードに入れないようにする",
        "id": "Berhenti memasukkan tugas yang datang ke papan",
    },
)  # fmt: skip
