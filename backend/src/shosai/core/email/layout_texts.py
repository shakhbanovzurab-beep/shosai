"""The words of the layout around every mail: why it came, how to leave, where to ask.

User-facing text in the 16 platform languages (CLAUDE.md "Language"), not model-facing.
"""

from types import MappingProxyType
from typing import Final

type LayoutTexts = MappingProxyType[str, str]

_TEXTS: Final = {
    "en": {
        "account": "You received this email because it concerns your Shosai account.",
        "notification": (
            "You received this email because notifications are on in your Shosai settings."
        ),
        "newsletter": "You received this email because you subscribed to Shosai news.",
        "unsubscribe": "Unsubscribe",
        "questions": "Questions? Write to",
    },
    "zh": {
        "account": "您收到這封郵件，是因為它與您的 Shosai 帳戶有關。",
        "notification": "您收到這封郵件，是因為您在 Shosai 設定中開啟了通知。",
        "newsletter": "您收到這封郵件，是因為您訂閱了 Shosai 的消息。",
        "unsubscribe": "取消訂閱",
        "questions": "有問題嗎？請寫信至",
    },
    "es": {
        "account": "Recibes este correo porque se refiere a tu cuenta de Shosai.",
        "notification": (
            "Recibes este correo porque tienes las notificaciones activadas en la "
            "configuración de Shosai."
        ),
        "newsletter": "Recibes este correo porque te suscribiste a las novedades de Shosai.",
        "unsubscribe": "Cancelar suscripción",
        "questions": "¿Preguntas? Escribe a",
    },
    "ru": {
        "account": "Вы получили это письмо, потому что оно касается вашего аккаунта Shosai.",
        "notification": (
            "Вы получили это письмо, потому что в настройках Shosai включены уведомления."
        ),
        "newsletter": "Вы получили это письмо, потому что подписались на новости Shosai.",
        "unsubscribe": "Отписаться",
        "questions": "Есть вопросы? Пишите на",
    },
    "hi": {
        "account": "आपको यह ईमेल इसलिए मिला है क्योंकि यह आपके Shosai खाते से जुड़ा है।",
        "notification": ("आपको यह ईमेल इसलिए मिला है क्योंकि आपकी Shosai सेटिंग्स में सूचनाएँ चालू हैं।"),
        "newsletter": "आपको यह ईमेल इसलिए मिला है क्योंकि आपने Shosai की ख़बरों की सदस्यता ली है।",
        "unsubscribe": "सदस्यता रद्द करें",
        "questions": "कोई सवाल? लिखें",
    },
    "ar": {
        "account": "تلقيت هذه الرسالة لأنها تتعلق بحسابك في Shosai.",
        "notification": "تلقيت هذه الرسالة لأن الإشعارات مفعّلة في إعدادات Shosai.",
        "newsletter": "تلقيت هذه الرسالة لأنك اشتركت في أخبار Shosai.",
        "unsubscribe": "إلغاء الاشتراك",
        "questions": "لديك أسئلة؟ راسلنا على",
    },
    "pt": {
        "account": "Você recebeu este e-mail porque ele diz respeito à sua conta Shosai.",
        "notification": (
            "Você recebeu este e-mail porque as notificações estão ativadas nas "
            "configurações do Shosai."
        ),
        "newsletter": "Você recebeu este e-mail porque assinou as novidades do Shosai.",
        "unsubscribe": "Cancelar inscrição",
        "questions": "Dúvidas? Escreva para",
    },
    "fr": {
        "account": "Vous recevez cet e-mail car il concerne votre compte Shosai.",
        "notification": (
            "Vous recevez cet e-mail car les notifications sont activées dans vos "
            "paramètres Shosai."
        ),
        "newsletter": "Vous recevez cet e-mail car vous êtes abonné aux actualités de Shosai.",
        "unsubscribe": "Se désabonner",
        "questions": "Des questions ? Écrivez à",
    },
    "it": {
        "account": "Hai ricevuto questa email perché riguarda il tuo account Shosai.",
        "notification": (
            "Hai ricevuto questa email perché le notifiche sono attive nelle "
            "impostazioni di Shosai."
        ),
        "newsletter": "Hai ricevuto questa email perché sei iscritto alle novità di Shosai.",
        "unsubscribe": "Annulla l’iscrizione",
        "questions": "Domande? Scrivi a",
    },
    "de": {
        "account": "Sie erhalten diese E-Mail, weil sie Ihr Shosai-Konto betrifft.",
        "notification": (
            "Sie erhalten diese E-Mail, weil Benachrichtigungen in Ihren "
            "Shosai-Einstellungen aktiviert sind."
        ),
        "newsletter": "Sie erhalten diese E-Mail, weil Sie die Shosai-Neuigkeiten abonniert haben.",
        "unsubscribe": "Abmelden",
        "questions": "Fragen? Schreiben Sie an",
    },
    "ja": {
        "account": "このメールは、お客様の Shosai アカウントに関するものとしてお送りしています。",
        "notification": "このメールは、Shosai の設定で通知がオンになっているためお送りしています。",
        "newsletter": "このメールは、Shosai のお知らせを購読されているためお送りしています。",
        "unsubscribe": "配信を停止",
        "questions": "ご質問は次の宛先へ：",
    },
    "ko": {
        "account": "Shosai 계정과 관련된 메일이라 이 메일을 받으셨습니다.",
        "notification": "Shosai 설정에서 알림이 켜져 있어 이 메일을 받으셨습니다.",
        "newsletter": "Shosai 소식을 구독하셔서 이 메일을 받으셨습니다.",
        "unsubscribe": "수신 거부",
        "questions": "문의 사항은 다음 주소로 보내 주세요:",
    },
    "id": {
        "account": "Anda menerima email ini karena berkaitan dengan akun Shosai Anda.",
        "notification": (
            "Anda menerima email ini karena notifikasi aktif di pengaturan Shosai Anda."
        ),
        "newsletter": "Anda menerima email ini karena berlangganan kabar dari Shosai.",
        "unsubscribe": "Berhenti berlangganan",
        "questions": "Ada pertanyaan? Tulis ke",
    },
    "tr": {
        "account": "Bu e-postayı Shosai hesabınızla ilgili olduğu için aldınız.",
        "notification": "Bu e-postayı Shosai ayarlarınızda bildirimler açık olduğu için aldınız.",
        "newsletter": "Bu e-postayı Shosai haberlerine abone olduğunuz için aldınız.",
        "unsubscribe": "Abonelikten çık",
        "questions": "Sorularınız mı var? Yazın:",
    },
    "vi": {
        "account": "Bạn nhận được email này vì nó liên quan đến tài khoản Shosai của bạn.",
        "notification": (
            "Bạn nhận được email này vì thông báo đang bật trong cài đặt Shosai của bạn."
        ),
        "newsletter": "Bạn nhận được email này vì bạn đã đăng ký nhận tin từ Shosai.",
        "unsubscribe": "Hủy đăng ký",
        "questions": "Có câu hỏi? Hãy viết đến",
    },
    "th": {
        "account": "คุณได้รับอีเมลนี้เนื่องจากเกี่ยวข้องกับบัญชี Shosai ของคุณ",
        "notification": "คุณได้รับอีเมลนี้เนื่องจากเปิดการแจ้งเตือนไว้ในการตั้งค่า Shosai",
        "newsletter": "คุณได้รับอีเมลนี้เนื่องจากสมัครรับข่าวสารจาก Shosai",
        "unsubscribe": "ยกเลิกการรับข่าวสาร",
        "questions": "มีคำถาม? เขียนถึง",
    },
}
LAYOUT_TEXTS: Final = MappingProxyType(
    {locale: MappingProxyType(texts) for locale, texts in _TEXTS.items()}
)
