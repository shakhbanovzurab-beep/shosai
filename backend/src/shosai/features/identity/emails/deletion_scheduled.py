"""The deletion mail: the account is hidden and is erased on the named date (ID-D5).

It goes in the transaction that schedules the deletion, to the address being deleted, and
tells the person that signing in before the date cancels it.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

DELETION_SCHEDULED_KEY: Final = "identity.deletion_scheduled"
BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(base_url ~ "/app/login", t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Your Shosai account will be deleted on {date}",
        "preheader": "Sign in before then to keep it.",
        "heading": "Your account is scheduled for deletion",
        "lead": (
            "You asked to delete your Shosai account. It is hidden now, and on {date} everything "
            "in it will be erased for good. Until then, signing in cancels the deletion and brings "
            "everything back as it was."
        ),
        "button": "Sign in to Shosai",
        "note": "If you did not ask for this, sign in now and change your password.",
    },
    "fr": {
        "subject": "Votre compte Shosai sera supprimé le {date}",
        "preheader": "Connectez-vous avant cette date pour le conserver.",
        "heading": "La suppression de votre compte est programmée",
        "lead": (
            "Vous avez demandé la suppression de votre compte Shosai. Il est désormais masqué et, "
            "le {date}, tout son contenu sera effacé définitivement. D'ici là, vous connecter "
            "annule la suppression et rétablit tout à l'identique."
        ),
        "button": "Se connecter à Shosai",
        "note": (
            "Si vous n'êtes pas à l'origine de cette demande, connectez-vous maintenant et changez "
            "votre mot de passe."
        ),
    },
    "de": {
        "subject": "Dein Shosai-Konto wird am {date} gelöscht",
        "preheader": "Melde dich vorher an, um es zu behalten.",
        "heading": "Die Löschung deines Kontos ist geplant",
        "lead": (
            "Du hast die Löschung deines Shosai-Kontos beantragt. Es ist jetzt ausgeblendet, und "
            "am {date} wird alles darin endgültig gelöscht. Bis dahin hebt eine Anmeldung die "
            "Löschung auf und stellt alles wieder her, wie es war."
        ),
        "button": "Bei Shosai anmelden",
        "note": "Warst du das nicht, melde dich jetzt an und ändere dein Passwort.",
    },
    "ru": {
        "subject": "Ваш аккаунт Shosai будет удалён {date}",
        "preheader": "Войдите до этой даты, чтобы сохранить его.",
        "heading": "Удаление аккаунта запланировано",
        "lead": (
            "Вы попросили удалить аккаунт Shosai. Сейчас он скрыт, а {date} всё в нём будет стёрто "
            "без возможности восстановления. До этой даты вход отменяет удаление и возвращает всё "
            "как было."
        ),
        "button": "Войти в Shosai",
        "note": "Если вы этого не запрашивали, войдите сейчас и смените пароль.",
    },
    "nl": {
        "subject": "Je Shosai-account wordt op {date} verwijderd",
        "preheader": "Log vóór die datum in om het te houden.",
        "heading": "Je account wordt binnenkort verwijderd",
        "lead": (
            "Je hebt gevraagd je Shosai-account te verwijderen. Het is nu verborgen en op {date} "
            "wordt alles erin definitief gewist. Tot die tijd annuleer je de verwijdering door in "
            "te loggen, en komt alles terug zoals het was."
        ),
        "button": "Inloggen bij Shosai",
        "note": "Heb je dit niet gevraagd? Log dan nu in en wijzig je wachtwoord.",
    },
    "it": {
        "subject": "Il tuo account Shosai sarà eliminato il {date}",
        "preheader": "Accedi prima di quella data per conservarlo.",
        "heading": "L'eliminazione del tuo account è programmata",
        "lead": (
            "Hai chiesto di eliminare il tuo account Shosai. Ora è nascosto e il {date} tutto ciò "
            "che contiene sarà cancellato definitivamente. Fino ad allora, accedere annulla "
            "l'eliminazione e riporta tutto com'era."
        ),
        "button": "Accedi a Shosai",
        "note": "Se non l'hai chiesto tu, accedi ora e cambia la password.",
    },
    "es": {
        "subject": "Tu cuenta de Shosai se eliminará el {date}",
        "preheader": "Inicia sesión antes de esa fecha para conservarla.",
        "heading": "La eliminación de tu cuenta está programada",
        "lead": (
            "Pediste eliminar tu cuenta de Shosai. Ahora está oculta y el {date} todo su contenido "
            "se borrará para siempre. Hasta entonces, iniciar sesión cancela la eliminación y lo "
            "deja todo como estaba."
        ),
        "button": "Iniciar sesión en Shosai",
        "note": "Si no lo pediste tú, inicia sesión ahora y cambia tu contraseña.",
    },
    "pt-BR": {
        "subject": "Sua conta Shosai será excluída em {date}",
        "preheader": "Entre antes dessa data para mantê-la.",
        "heading": "A exclusão da sua conta está agendada",
        "lead": (
            "Você pediu para excluir sua conta Shosai. Ela está oculta agora e, em {date}, tudo "
            "nela será apagado para sempre. Até lá, entrar na conta cancela a exclusão e deixa "
            "tudo como estava."
        ),
        "button": "Entrar no Shosai",
        "note": "Se não foi você, entre agora e altere sua senha.",
    },
    "ar": {
        "subject": "سيُحذف حسابك في Shosai بتاريخ {date}",
        "preheader": "سجّل الدخول قبل ذلك التاريخ للاحتفاظ به.",
        "heading": "تمت جدولة حذف حسابك",
        "lead": (
            "طلبت حذف حسابك في Shosai. الحساب مخفي الآن، وفي {date} سيُمحى كل ما فيه نهائيًا. حتى "
            "ذلك الحين، يؤدي تسجيل الدخول إلى إلغاء الحذف وإعادة كل شيء كما كان."
        ),
        "button": "تسجيل الدخول إلى Shosai",
        "note": "إذا لم تطلب ذلك، فسجّل الدخول الآن وغيّر كلمة المرور.",
    },
    "tr": {
        "subject": "Shosai hesabınız {date} tarihinde silinecek",
        "preheader": "Hesabınızı korumak için bu tarihten önce oturum açın.",
        "heading": "Hesabınızın silinmesi planlandı",
        "lead": (
            "Shosai hesabınızın silinmesini istediniz. Hesap şu anda gizli ve {date} tarihinde "
            "içindeki her şey kalıcı olarak silinecek. O zamana kadar oturum açmak silme işlemini "
            "iptal eder ve her şeyi olduğu gibi geri getirir."
        ),
        "button": "Shosai'de oturum açın",
        "note": "Bu isteği siz yapmadıysanız hemen oturum açın ve şifrenizi değiştirin.",
    },
    "ko": {
        "subject": "Shosai 계정이 {date}에 삭제됩니다",
        "preheader": "계정을 유지하려면 그 전에 로그인하세요.",
        "heading": "계정 삭제가 예약되었습니다",
        "lead": (
            "Shosai 계정 삭제를 요청하셨습니다. 계정은 지금 숨겨져 있으며 {date}에 모든 내용이 "
            "영구적으로 삭제됩니다. 그 전까지 로그인하면 삭제가 취소되고 모든 것이 그대로 "
            "돌아옵니다."
        ),
        "button": "Shosai에 로그인",
        "note": "직접 요청하지 않았다면 지금 로그인하여 비밀번호를 변경하세요.",
    },
    "hi": {
        "subject": "आपका Shosai खाता {date} को हटा दिया जाएगा",
        "preheader": "इसे बनाए रखने के लिए उससे पहले साइन इन करें।",
        "heading": "आपके खाते को हटाना निर्धारित है",
        "lead": (
            "आपने अपना Shosai खाता हटाने का अनुरोध किया है। यह अभी छिपा हुआ है, और {date} को इसकी सारी "
            "सामग्री हमेशा के लिए मिटा दी जाएगी। तब तक साइन इन करने से हटाना रद्द हो जाता है और सब कुछ पहले "
            "जैसा लौट आता है।"
        ),
        "button": "Shosai में साइन इन करें",
        "note": "अगर यह अनुरोध आपने नहीं किया, तो अभी साइन इन करें और अपना पासवर्ड बदलें।",
    },
    "vi": {
        "subject": "Tài khoản Shosai của bạn sẽ bị xóa vào {date}",
        "preheader": "Hãy đăng nhập trước ngày đó để giữ tài khoản.",
        "heading": "Tài khoản của bạn đã được lên lịch xóa",
        "lead": (
            "Bạn đã yêu cầu xóa tài khoản Shosai. Tài khoản hiện đã bị ẩn và vào {date}, mọi dữ "
            "liệu trong đó sẽ bị xóa vĩnh viễn. Trước thời điểm đó, đăng nhập sẽ hủy việc xóa và "
            "khôi phục mọi thứ như cũ."
        ),
        "button": "Đăng nhập Shosai",
        "note": "Nếu bạn không yêu cầu điều này, hãy đăng nhập ngay và đổi mật khẩu.",
    },
    "zh-Hant": {
        "subject": "您的 Shosai 帳戶將於 {date} 刪除",
        "preheader": "請在該日期前登入以保留帳戶。",
        "heading": "您的帳戶已排定刪除",
        "lead": (
            "您已要求刪除 Shosai 帳戶。帳戶現已隱藏，並將於 {date} "
            "永久清除其中所有內容。在此之前登入即可取消刪除，一切都會恢復原狀。"
        ),
        "button": "登入 Shosai",
        "note": "如果這不是您提出的要求，請立即登入並變更密碼。",
    },
    "ja": {
        "subject": "Shosai アカウントは {date} に削除されます",
        "preheader": "アカウントを残すには、それまでにログインしてください。",
        "heading": "アカウントの削除が予定されています",
        "lead": (
            "Shosai "
            "アカウントの削除をリクエストされました。アカウントは現在非表示になっており、{date} "
            "にすべての内容が完全に消去されます。それまでにログインすると削除が取り消され、すべて元どおりになります。"
        ),
        "button": "Shosai にログイン",
        "note": "心当たりがない場合は、今すぐログインしてパスワードを変更してください。",
    },
    "id": {
        "subject": "Akun Shosai Anda akan dihapus pada {date}",
        "preheader": "Masuk sebelum tanggal itu untuk mempertahankannya.",
        "heading": "Penghapusan akun Anda telah dijadwalkan",
        "lead": (
            "Anda meminta untuk menghapus akun Shosai. Akun kini disembunyikan, dan pada {date} "
            "semua isinya akan dihapus selamanya. Sebelum itu, masuk ke akun akan membatalkan "
            "penghapusan dan mengembalikan semuanya seperti semula."
        ),
        "button": "Masuk ke Shosai",
        "note": "Jika bukan Anda yang meminta, segera masuk dan ganti kata sandi Anda.",
    },
}

DELETION_SCHEDULED: Final = EmailTemplate(key=DELETION_SCHEDULED_KEY, body=BODY, texts=_TEXTS)
