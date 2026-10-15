"""The sign-in code: the 6 digits that let a person into the cabinet by email (ADR 0048).

One mail for a known person and for a new one: the same code signs in or starts the account,
so the mail never says which, as the start answer does not. The code is a secret of the
mail: encrypted in its row, never logged, kept out of the subject and the preheader.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

SIGN_IN_CODE_KEY: Final = "identity.sign_in_code"

BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.code(p.code) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Your Shosai sign-in code",
        "preheader": "Your code is inside. It works for {minutes} minutes.",
        "heading": "Your sign-in code",
        "lead": "Enter this code in Shosai to continue. It works for {minutes} minutes.",
        "note": (
            "If you did not ask for this code, ignore this email: no one can sign in without it."
        ),
    },
    "zh-Hant": {
        "subject": "你的 Shosai 登入碼",
        "preheader": "登入碼在郵件中，{minutes} 分鐘內有效。",
        "heading": "你的登入碼",
        "lead": "在 Shosai 中輸入此代碼即可繼續。代碼在 {minutes} 分鐘內有效。",
        "note": "如果你沒有要求這個代碼，請忽略這封郵件：沒有它就無法登入。",
    },
    "es": {
        "subject": "Tu código para entrar en Shosai",
        "preheader": "Dentro está tu código. Vale durante {minutes} minutos.",
        "heading": "Tu código de acceso",
        "lead": "Escribe este código en Shosai para continuar. Vale durante {minutes} minutos.",
        "note": "Si no pediste este código, ignora este correo: nadie puede entrar sin él.",
    },
    "ru": {
        "subject": "Код для входа в Shosai",
        "preheader": "Внутри код. Он действует {minutes} минут.",
        "heading": "Код для входа",
        "lead": "Введите этот код в Shosai, чтобы продолжить. Код действует {minutes} минут.",
        "note": "Если вы не запрашивали код, просто проигнорируйте письмо: без него войти нельзя.",
    },
    "hi": {
        "subject": "आपका Shosai साइन-इन कोड",
        "preheader": "आपका कोड अंदर है। यह {minutes} मिनट तक काम करता है।",
        "heading": "आपका साइन-इन कोड",
        "lead": "आगे बढ़ने के लिए यह कोड Shosai में डालें। यह {minutes} मिनट तक काम करता है।",
        "note": (
            "अगर आपने यह कोड नहीं माँगा, तो इस ईमेल को अनदेखा करें: इसके बिना कोई साइन इन नहीं कर सकता।"
        ),
    },
    "ar": {
        "subject": "رمز الدخول إلى Shosai",
        "preheader": "الرمز في الداخل، وهو صالح لمدة {minutes} دقيقة.",
        "heading": "رمز الدخول",
        "lead": "أدخل هذا الرمز في Shosai للمتابعة. الرمز صالح لمدة {minutes} دقيقة.",
        "note": "إذا لم تطلب هذا الرمز فتجاهل هذه الرسالة: لا يمكن لأحد الدخول من دونه.",
    },
    "pt-BR": {
        "subject": "Seu código para entrar no Shosai",
        "preheader": "Seu código está aqui dentro. Ele vale por {minutes} minutos.",
        "heading": "Seu código de acesso",
        "lead": "Digite este código no Shosai para continuar. Ele vale por {minutes} minutos.",
        "note": "Se você não pediu este código, ignore este e-mail: ninguém entra sem ele.",
    },
    "fr": {
        "subject": "Votre code de connexion à Shosai",
        "preheader": "Votre code est à l’intérieur. Il est valable {minutes} minutes.",
        "heading": "Votre code de connexion",
        "lead": "Saisissez ce code dans Shosai pour continuer. Il est valable {minutes} minutes.",
        "note": (
            "Si vous n’avez pas demandé ce code, ignorez cet e-mail : personne ne peut se "
            "connecter sans lui."
        ),
    },
    "it": {
        "subject": "Il tuo codice di accesso a Shosai",
        "preheader": "Il codice è qui dentro. Vale {minutes} minuti.",
        "heading": "Il tuo codice di accesso",
        "lead": "Inserisci questo codice in Shosai per continuare. Vale {minutes} minuti.",
        "note": (
            "Se non hai chiesto questo codice, ignora questa email: senza di esso nessuno può "
            "accedere."
        ),
    },
    "de": {
        "subject": "Dein Anmeldecode für Shosai",
        "preheader": "Dein Code steht in dieser E-Mail. Er gilt {minutes} Minuten.",
        "heading": "Dein Anmeldecode",
        "lead": "Gib diesen Code in Shosai ein, um fortzufahren. Er gilt {minutes} Minuten.",
        "note": (
            "Wenn du diesen Code nicht angefordert hast, ignoriere diese E-Mail: Ohne ihn kann "
            "sich niemand anmelden."
        ),
    },
    "ja": {
        "subject": "Shosai のサインインコード",
        "preheader": "コードはこのメールに記載されています。有効期限は {minutes} 分です。",
        "heading": "サインインコード",
        "lead": "続けるには、このコードを Shosai に入力してください。有効期限は {minutes} 分です。",
        "note": (
            "このコードに心当たりがない場合は、このメールを無視してください。"
            "コードがなければサインインできません。"
        ),
    },
    "ko": {
        "subject": "Shosai 로그인 코드",
        "preheader": "코드가 안에 있어요. {minutes}분 동안 유효해요.",
        "heading": "로그인 코드",
        "lead": "계속하려면 Shosai에 이 코드를 입력하세요. 코드는 {minutes}분 동안 유효해요.",
        "note": (
            "이 코드를 요청하지 않았다면 이 이메일을 무시하세요. 코드 없이는 아무도 로그인할 수 "
            "없어요."
        ),
    },
    "id": {
        "subject": "Kode masuk Shosai Anda",
        "preheader": "Kode Anda ada di dalam. Kode berlaku selama {minutes} menit.",
        "heading": "Kode masuk Anda",
        "lead": (
            "Masukkan kode ini di Shosai untuk melanjutkan. Kode berlaku selama {minutes} menit."
        ),
        "note": (
            "Jika Anda tidak meminta kode ini, abaikan email ini: tidak ada yang bisa masuk "
            "tanpanya."
        ),
    },
    "tr": {
        "subject": "Shosai giriş kodunuz",
        "preheader": "Kodunuz içeride. {minutes} dakika geçerlidir.",
        "heading": "Giriş kodunuz",
        "lead": "Devam etmek için bu kodu Shosai’de girin. Kod {minutes} dakika geçerlidir.",
        "note": (
            "Bu kodu siz istemediyseniz bu e-postayı yok sayın: kod olmadan kimse giriş yapamaz."
        ),
    },
    "vi": {
        "subject": "Mã đăng nhập Shosai của bạn",
        "preheader": "Mã của bạn ở bên trong. Mã có hiệu lực trong {minutes} phút.",
        "heading": "Mã đăng nhập của bạn",
        "lead": "Nhập mã này vào Shosai để tiếp tục. Mã có hiệu lực trong {minutes} phút.",
        "note": (
            "Nếu bạn không yêu cầu mã này, hãy bỏ qua email: không ai có thể đăng nhập nếu thiếu "
            "mã."
        ),
    },
    "nl": {
        "subject": "Je inlogcode voor Shosai",
        "preheader": "Je code staat erin. De code werkt {minutes} minuten.",
        "heading": "Je inlogcode",
        "lead": "Voer deze code in Shosai in om verder te gaan. De code werkt {minutes} minuten.",
        "note": (
            "Heb je deze code niet aangevraagd? Negeer dan deze e-mail: zonder code kan niemand "
            "inloggen."
        ),
    },
}

SIGN_IN_CODE: Final = EmailTemplate(key=SIGN_IN_CODE_KEY, body=BODY, texts=_TEXTS)
