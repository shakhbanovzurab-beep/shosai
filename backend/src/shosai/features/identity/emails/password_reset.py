"""The reset link: one use, 60 minutes (ADR 0045; draft spec 001).

The link is a secret of the mail: encrypted in its row, never logged.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

RESET_LINK_MAIL_KEY: Final = "identity.password_reset"

BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(p.link, t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Reset your Shosai password",
        "preheader": "The link works once, for {minutes} minutes.",
        "heading": "Set a new password",
        "lead": "Follow the link to choose a new password. It works once, for {minutes} minutes.",
        "button": "Set a new password",
        "note": "If you did not ask to reset your password, ignore this email: nothing changes.",
    },
    "zh": {
        "subject": "重設您的 Shosai 密碼",
        "preheader": "此連結僅能使用一次，{minutes} 分鐘內有效。",
        "heading": "設定新密碼",
        "lead": "點擊連結以設定新密碼。連結僅能使用一次，{minutes} 分鐘內有效。",
        "button": "設定新密碼",
        "note": "如果您沒有要求重設密碼，請忽略這封郵件：一切都不會改變。",
    },
    "es": {
        "subject": "Restablece tu contraseña de Shosai",
        "preheader": "El enlace funciona una vez, durante {minutes} minutos.",
        "heading": "Crea una contraseña nueva",
        "lead": (
            "Sigue el enlace para elegir una contraseña nueva. Funciona una vez, durante {minutes} "
            "minutos."
        ),
        "button": "Crear contraseña nueva",
        "note": "Si no pediste restablecer tu contraseña, ignora este correo: nada cambia.",
    },
    "ru": {
        "subject": "Сброс пароля Shosai",
        "preheader": "Ссылка работает один раз в течение {minutes} минут.",
        "heading": "Задайте новый пароль",
        "lead": (
            "Перейдите по ссылке, чтобы задать новый пароль. Она работает один раз в течение "
            "{minutes} минут."
        ),
        "button": "Задать новый пароль",
        "note": (
            "Если вы не просили сбросить пароль, просто проигнорируйте письмо: ничего не изменится."
        ),
    },
    "hi": {
        "subject": "अपना Shosai पासवर्ड रीसेट करें",
        "preheader": "लिंक एक बार, {minutes} मिनट तक काम करता है।",
        "heading": "नया पासवर्ड सेट करें",
        "lead": "नया पासवर्ड चुनने के लिए लिंक खोलें। यह एक बार, {minutes} मिनट तक काम करता है।",
        "button": "नया पासवर्ड सेट करें",
        "note": "अगर आपने पासवर्ड रीसेट करने को नहीं कहा, तो इस ईमेल को अनदेखा करें: कुछ नहीं बदलेगा।",
    },
    "ar": {
        "subject": "إعادة تعيين كلمة مرور Shosai",
        "preheader": "يعمل الرابط مرة واحدة لمدة {minutes} دقيقة.",
        "heading": "عيِّن كلمة مرور جديدة",
        "lead": "افتح الرابط لاختيار كلمة مرور جديدة. يعمل مرة واحدة لمدة {minutes} دقيقة.",
        "button": "تعيين كلمة مرور جديدة",
        "note": "إذا لم تطلب إعادة تعيين كلمة المرور، فتجاهل هذه الرسالة: لن يتغير شيء.",
    },
    "pt": {
        "subject": "Redefina sua senha do Shosai",
        "preheader": "O link funciona uma vez, por {minutes} minutos.",
        "heading": "Defina uma nova senha",
        "lead": (
            "Abra o link para escolher uma nova senha. Ele funciona uma vez, por {minutes} minutos."
        ),
        "button": "Definir nova senha",
        "note": "Se você não pediu para redefinir a senha, ignore este e-mail: nada muda.",
    },
    "fr": {
        "subject": "Réinitialisez votre mot de passe Shosai",
        "preheader": "Le lien fonctionne une fois, pendant {minutes} minutes.",
        "heading": "Choisissez un nouveau mot de passe",
        "lead": (
            "Suivez le lien pour choisir un nouveau mot de passe. Il fonctionne une fois, pendant "
            "{minutes} minutes."
        ),
        "button": "Choisir un nouveau mot de passe",
        "note": (
            "Si vous n’avez pas demandé de réinitialisation, ignorez cet e-mail : rien ne change."
        ),
    },
    "it": {
        "subject": "Reimposta la password di Shosai",
        "preheader": "Il link funziona una sola volta, per {minutes} minuti.",
        "heading": "Imposta una nuova password",
        "lead": (
            "Apri il link per scegliere una nuova password. Funziona una sola volta, per {minutes} "
            "minuti."
        ),
        "button": "Imposta nuova password",
        "note": (
            "Se non hai chiesto di reimpostare la password, ignora questa email: non cambia nulla."
        ),
    },
    "de": {
        "subject": "Setze dein Shosai-Passwort zurück",
        "preheader": "Der Link funktioniert einmal, {minutes} Minuten lang.",
        "heading": "Neues Passwort festlegen",
        "lead": (
            "Öffne den Link, um ein neues Passwort zu wählen. Er funktioniert einmal, {minutes} "
            "Minuten lang."
        ),
        "button": "Neues Passwort festlegen",
        "note": (
            "Wenn du kein neues Passwort angefordert hast, ignoriere diese E-Mail: Es ändert sich "
            "nichts."
        ),
    },
    "ja": {
        "subject": "Shosai のパスワードを再設定",
        "preheader": "リンクは {minutes} 分間、1 回だけ使えます。",
        "heading": "新しいパスワードを設定",
        "lead": (
            "リンクを開いて新しいパスワードを設定してください。リンクは {minutes} 分間、1 "
            "回だけ使えます。"
        ),
        "button": "新しいパスワードを設定",
        "note": (
            "パスワードの再設定を依頼していない場合は、このメールを無視してください。何も変わりませ"
            "ん。"
        ),
    },
    "ko": {
        "subject": "Shosai 비밀번호 재설정",
        "preheader": "링크는 {minutes}분 동안 한 번만 사용할 수 있습니다.",
        "heading": "새 비밀번호 설정",
        "lead": (
            "링크를 열어 새 비밀번호를 정하세요. 링크는 {minutes}분 동안 한 번만 사용할 수 "
            "있습니다."
        ),
        "button": "새 비밀번호 설정",
        "note": (
            "비밀번호 재설정을 요청하지 않았다면 이 이메일을 무시하세요. 아무것도 바뀌지 않습니다."
        ),
    },
    "id": {
        "subject": "Atur ulang kata sandi Shosai Anda",
        "preheader": "Tautan berlaku sekali, selama {minutes} menit.",
        "heading": "Buat kata sandi baru",
        "lead": (
            "Buka tautan untuk memilih kata sandi baru. Tautan berlaku sekali, selama {minutes} "
            "menit."
        ),
        "button": "Buat kata sandi baru",
        "note": (
            "Jika Anda tidak meminta pengaturan ulang kata sandi, abaikan email ini: tidak ada "
            "yang berubah."
        ),
    },
    "tr": {
        "subject": "Shosai şifrenizi sıfırlayın",
        "preheader": "Bağlantı bir kez, {minutes} dakika boyunca çalışır.",
        "heading": "Yeni bir şifre belirleyin",
        "lead": (
            "Yeni bir şifre seçmek için bağlantıyı açın. Bağlantı bir kez, {minutes} dakika "
            "boyunca çalışır."
        ),
        "button": "Yeni şifre belirle",
        "note": "Şifre sıfırlama istemediyseniz bu e-postayı yok sayın: hiçbir şey değişmez.",
    },
    "vi": {
        "subject": "Đặt lại mật khẩu Shosai",
        "preheader": "Liên kết chỉ dùng được một lần, trong {minutes} phút.",
        "heading": "Đặt mật khẩu mới",
        "lead": (
            "Mở liên kết để chọn mật khẩu mới. Liên kết chỉ dùng được một lần, trong {minutes} "
            "phút."
        ),
        "button": "Đặt mật khẩu mới",
        "note": (
            "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này: không có gì thay đổi."
        ),
    },
    "th": {
        "subject": "รีเซ็ตรหัสผ่าน Shosai ของคุณ",
        "preheader": "ลิงก์ใช้ได้ครั้งเดียว ภายใน {minutes} นาที",
        "heading": "ตั้งรหัสผ่านใหม่",
        "lead": "เปิดลิงก์เพื่อเลือกรหัสผ่านใหม่ ลิงก์ใช้ได้ครั้งเดียว ภายใน {minutes} นาที",
        "button": "ตั้งรหัสผ่านใหม่",
        "note": "หากคุณไม่ได้ขอรีเซ็ตรหัสผ่าน โปรดเพิกเฉยต่ออีเมลนี้ จะไม่มีอะไรเปลี่ยนแปลง",
    },
}

RESET_LINK_MAIL: Final = EmailTemplate(key=RESET_LINK_MAIL_KEY, body=BODY, texts=_TEXTS)
