"""The registration code: the 6 digits that confirm the address (ADR 0045 point 3).

The code is a secret of the mail: encrypted in its row, never logged, kept out of the
subject and the preheader, which mail clients show in lists and notifications.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

REGISTRATION_CODE_KEY: Final = "identity.registration_code"

BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.code(p.code) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Confirm your email for Shosai",
        "preheader": "Your confirmation code is inside. It works for {minutes} minutes.",
        "heading": "Confirm your email",
        "lead": (
            "Enter this code in Shosai to finish creating your account. It works for {minutes} "
            "minutes."
        ),
        "note": "If you did not sign up for Shosai, ignore this email: no account will be created.",
    },
    "zh-Hant": {
        "subject": "確認您在 Shosai 的電子郵件",
        "preheader": "確認碼在郵件中，{minutes} 分鐘內有效。",
        "heading": "確認您的電子郵件",
        "lead": "在 Shosai 中輸入此代碼以完成建立帳戶。代碼在 {minutes} 分鐘內有效。",
        "note": "如果您沒有註冊 Shosai，請忽略這封郵件：不會建立任何帳戶。",
    },
    "es": {
        "subject": "Confirma tu correo para Shosai",
        "preheader": "Dentro está tu código de confirmación. Vale durante {minutes} minutos.",
        "heading": "Confirma tu correo",
        "lead": (
            "Introduce este código en Shosai para terminar de crear tu cuenta. Vale durante "
            "{minutes} minutos."
        ),
        "note": "Si no te registraste en Shosai, ignora este correo: no se creará ninguna cuenta.",
    },
    "ru": {
        "subject": "Подтвердите почту для Shosai",
        "preheader": "Внутри код подтверждения. Он действует {minutes} минут.",
        "heading": "Подтвердите почту",
        "lead": (
            "Введите этот код в Shosai, чтобы завершить создание аккаунта. Код действует {minutes} "
            "минут."
        ),
        "note": (
            "Если вы не регистрировались в Shosai, просто проигнорируйте письмо: аккаунт не будет "
            "создан."
        ),
    },
    "hi": {
        "subject": "Shosai के लिए अपना ईमेल पुष्टि करें",
        "preheader": "पुष्टि कोड अंदर है। यह {minutes} मिनट तक मान्य है।",
        "heading": "अपना ईमेल पुष्टि करें",
        "lead": (
            "अपना खाता बनाना पूरा करने के लिए Shosai में यह कोड दर्ज करें। यह {minutes} मिनट तक मान्य है।"
        ),
        "note": "अगर आपने Shosai के लिए साइन अप नहीं किया, तो इस ईमेल को अनदेखा करें: कोई खाता नहीं बनेगा।",
    },
    "ar": {
        "subject": "أكِّد بريدك الإلكتروني في Shosai",
        "preheader": "رمز التأكيد في الداخل، وهو صالح لمدة {minutes} دقيقة.",
        "heading": "أكِّد بريدك الإلكتروني",
        "lead": "أدخل هذا الرمز في Shosai لإكمال إنشاء حسابك. الرمز صالح لمدة {minutes} دقيقة.",
        "note": "إذا لم تسجّل في Shosai، فتجاهل هذه الرسالة: لن يُنشأ أي حساب.",
    },
    "pt-BR": {
        "subject": "Confirme seu e-mail no Shosai",
        "preheader": "Seu código de confirmação está aqui. Ele vale por {minutes} minutos.",
        "heading": "Confirme seu e-mail",
        "lead": (
            "Digite este código no Shosai para concluir a criação da sua conta. Ele vale por "
            "{minutes} minutos."
        ),
        "note": (
            "Se você não se cadastrou no Shosai, ignore este e-mail: nenhuma conta será criada."
        ),
    },
    "fr": {
        "subject": "Confirmez votre e-mail pour Shosai",
        "preheader": (
            "Votre code de confirmation est à l’intérieur. Il est valable {minutes} minutes."
        ),
        "heading": "Confirmez votre e-mail",
        "lead": (
            "Saisissez ce code dans Shosai pour terminer la création de votre compte. Il est "
            "valable {minutes} minutes."
        ),
        "note": (
            "Si vous ne vous êtes pas inscrit à Shosai, ignorez cet e-mail : aucun compte ne sera "
            "créé."
        ),
    },
    "it": {
        "subject": "Conferma la tua email per Shosai",
        "preheader": "Dentro trovi il codice di conferma. È valido per {minutes} minuti.",
        "heading": "Conferma la tua email",
        "lead": (
            "Inserisci questo codice in Shosai per completare la creazione dell’account. È valido "
            "per {minutes} minuti."
        ),
        "note": (
            "Se non ti sei registrato a Shosai, ignora questa email: non verrà creato alcun "
            "account."
        ),
    },
    "de": {
        "subject": "Bestätige deine E-Mail-Adresse für Shosai",
        "preheader": "Dein Bestätigungscode ist drin. Er gilt {minutes} Minuten.",
        "heading": "Bestätige deine E-Mail-Adresse",
        "lead": (
            "Gib diesen Code in Shosai ein, um dein Konto fertig anzulegen. Er gilt {minutes} "
            "Minuten."
        ),
        "note": (
            "Wenn du dich nicht bei Shosai registriert hast, ignoriere diese E-Mail: Es wird kein "
            "Konto angelegt."
        ),
    },
    "ja": {
        "subject": "Shosai のメールアドレスを確認してください",
        "preheader": "確認コードをお送りします。有効期間は {minutes} 分です。",
        "heading": "メールアドレスの確認",
        "lead": (
            "このコードを Shosai に入力して、アカウントの作成を完了してください。有効期間は "
            "{minutes} 分です。"
        ),
        "note": (
            "Shosai "
            "に登録していない場合は、このメールを無視してください。アカウントは作成されません。"
        ),
    },
    "ko": {
        "subject": "Shosai 이메일 주소를 확인하세요",
        "preheader": "확인 코드가 들어 있습니다. {minutes}분 동안 유효합니다.",
        "heading": "이메일 주소 확인",
        "lead": (
            "Shosai에 이 코드를 입력해 계정 만들기를 마치세요. 코드는 {minutes}분 동안 유효합니다."
        ),
        "note": "Shosai에 가입하지 않았다면 이 이메일을 무시하세요. 계정은 만들어지지 않습니다.",
    },
    "id": {
        "subject": "Konfirmasi email Anda untuk Shosai",
        "preheader": "Kode konfirmasi ada di dalam. Berlaku selama {minutes} menit.",
        "heading": "Konfirmasi email Anda",
        "lead": (
            "Masukkan kode ini di Shosai untuk menyelesaikan pembuatan akun Anda. Kode berlaku "
            "selama {minutes} menit."
        ),
        "note": (
            "Jika Anda tidak mendaftar di Shosai, abaikan email ini: tidak ada akun yang akan "
            "dibuat."
        ),
    },
    "tr": {
        "subject": "Shosai için e-postanızı doğrulayın",
        "preheader": "Doğrulama kodunuz içeride. {minutes} dakika geçerlidir.",
        "heading": "E-postanızı doğrulayın",
        "lead": (
            "Hesabınızı oluşturmayı tamamlamak için bu kodu Shosai’ye girin. Kod {minutes} dakika "
            "geçerlidir."
        ),
        "note": "Shosai’ye kaydolmadıysanız bu e-postayı yok sayın: hiçbir hesap oluşturulmayacak.",
    },
    "vi": {
        "subject": "Xác nhận email của bạn cho Shosai",
        "preheader": "Mã xác nhận ở bên trong. Mã có hiệu lực trong {minutes} phút.",
        "heading": "Xác nhận email của bạn",
        "lead": (
            "Nhập mã này vào Shosai để hoàn tất việc tạo tài khoản. Mã có hiệu lực trong {minutes} "
            "phút."
        ),
        "note": (
            "Nếu bạn không đăng ký Shosai, hãy bỏ qua email này: sẽ không có tài khoản nào được "
            "tạo."
        ),
    },
    "nl": {
        "subject": "Bevestig je e-mailadres voor Shosai",
        "preheader": "Je bevestigingscode staat erin. De code werkt {minutes} minuten.",
        "heading": "Bevestig je e-mailadres",
        "lead": (
            "Voer deze code in Shosai in om het aanmaken van je account af te ronden. De code "
            "werkt {minutes} minuten."
        ),
        "note": (
            "Heb je je niet aangemeld bij Shosai? Negeer dan deze e-mail: er wordt geen account "
            "aangemaakt."
        ),
    },
}

REGISTRATION_CODE: Final = EmailTemplate(key=REGISTRATION_CODE_KEY, body=BODY, texts=_TEXTS)
