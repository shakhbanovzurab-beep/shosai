"""How the cards of Leo's meeting writes read, in the 16 platform languages (Leo §8.4).

The words are the room page's own: a meeting is started now and ended for everyone. An
untitled room's card has no title row; the end's card says how many are in the call.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized, PreviewField, PreviewWording

TITLE: Final[Localized] = {
    "en": "Title", "fr": "Titre", "de": "Titel", "ru": "Название", "nl": "Titel",
    "it": "Titolo", "es": "Título", "pt-BR": "Título", "ar": "العنوان", "tr": "Başlık",
    "ko": "제목", "hi": "शीर्षक", "vi": "Tiêu đề", "zh-Hant": "標題", "ja": "タイトル",
    "id": "Judul",
}  # fmt: skip
MEETING: Final[Localized] = {
    "en": "Meeting", "fr": "Réunion", "de": "Meeting", "ru": "Встреча", "nl": "Vergadering",
    "it": "Riunione", "es": "Reunión", "pt-BR": "Reunião", "ar": "الاجتماع", "tr": "Toplantı",
    "ko": "회의", "hi": "मीटिंग", "vi": "Cuộc họp", "zh-Hant": "會議", "ja": "会議",
    "id": "Rapat",
}  # fmt: skip
IN_CALL: Final[Localized] = {
    "en": "In the call now", "fr": "Dans l’appel", "de": "Gerade im Anruf",
    "ru": "Сейчас в звонке", "nl": "Nu in het gesprek", "it": "Ora nella chiamata",
    "es": "Ahora en la llamada", "pt-BR": "Agora na chamada", "ar": "في المكالمة الآن",
    "tr": "Şu anda görüşmede", "ko": "지금 통화 중", "hi": "अभी कॉल में", "vi": "Đang trong cuộc gọi",
    "zh-Hant": "目前通話中", "ja": "通話中の人数", "id": "Sedang dalam panggilan",
}  # fmt: skip

START: Final = PreviewWording(
    key="agent.meetings.start_call",
    params=("title",),
    title={
        "en": "Start a meeting now", "fr": "Démarrer une réunion maintenant",
        "de": "Jetzt ein Meeting starten", "ru": "Начать встречу сейчас",
        "nl": "Nu een vergadering starten", "it": "Inizia una riunione ora",
        "es": "Empezar una reunión ahora", "pt-BR": "Começar uma reunião agora",
        "ar": "بدء اجتماع الآن", "tr": "Şimdi bir toplantı başlat", "ko": "지금 회의 시작",
        "hi": "अभी मीटिंग शुरू करें", "vi": "Bắt đầu cuộc họp ngay", "zh-Hant": "立即開始會議",
        "ja": "今すぐ会議を開始", "id": "Mulai rapat sekarang",
    },
    fields=(PreviewField("title", TITLE),),
)  # fmt: skip
END: Final = PreviewWording(
    key="agent.meetings.end_call",
    params=("title", "people"),
    title={
        "en": "End the meeting for everyone", "fr": "Terminer la réunion pour tous",
        "de": "Meeting für alle beenden", "ru": "Завершить встречу для всех",
        "nl": "Vergadering beëindigen voor iedereen", "it": "Termina la riunione per tutti",
        "es": "Terminar la reunión para todos", "pt-BR": "Encerrar a reunião para todos",
        "ar": "إنهاء الاجتماع للجميع", "tr": "Toplantıyı herkes için bitir",
        "ko": "모두에게 회의 종료", "hi": "सभी के लिए मीटिंग खत्म करें",
        "vi": "Kết thúc cuộc họp cho mọi người", "zh-Hant": "為所有人結束會議",
        "ja": "全員の会議を終了", "id": "Akhiri rapat untuk semua",
    },
    fields=(PreviewField("title", MEETING), PreviewField("people", IN_CALL)),
)  # fmt: skip
