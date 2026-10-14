"""Texts of the unsubscribe page in the 16 platform languages (user-facing, not a prompt).

The page says the same for every link, valid or not, so it never names the kind or the
person: `confirm` asks before anything changes, `done` follows the POST.
"""

from typing import Final

PAGE_TEXTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "confirm_title": "Unsubscribe from these emails?",
        "confirm_lead": (
            "You will stop receiving emails of this kind from Shosai. Account emails — sign-in "
            "codes, password resets, receipts — will still arrive."
        ),
        "button": "Unsubscribe",
        "done_title": "You are unsubscribed",
        "done_lead": (
            "Emails of this kind will no longer arrive. You can turn them back on in Shosai "
            "settings."
        ),
    },
    "zh": {
        "confirm_title": "退订此类邮件？",
        "confirm_lead": (
            "你将不再收到 Shosai 的此类邮件。账户邮件——登录验证码、密码重置和收据——仍会照常发送。"
        ),
        "button": "退订",
        "done_title": "你已退订",
        "done_lead": "你将不再收到此类邮件。你可以在 Shosai 设置中重新开启。",
    },
    "es": {
        "confirm_title": "¿Darte de baja de estos correos?",
        "confirm_lead": (
            "Dejarás de recibir correos de este tipo de Shosai. Los correos de tu cuenta —códigos "
            "de acceso, restablecimientos de contraseña, recibos— seguirán llegando."
        ),
        "button": "Darme de baja",
        "done_title": "Te has dado de baja",
        "done_lead": (
            "Ya no recibirás correos de este tipo. Puedes volver a activarlos en la configuración "
            "de Shosai."
        ),
    },
    "ru": {
        "confirm_title": "Отписаться от этих писем?",
        "confirm_lead": (
            "Письма этого вида от Shosai больше не будут приходить. Письма аккаунта — коды входа, "
            "сброс пароля, чеки — продолжат приходить."
        ),
        "button": "Отписаться",
        "done_title": "Вы отписались",
        "done_lead": "Письма этого вида больше не придут. Вернуть их можно в настройках Shosai.",
    },
    "hi": {
        "confirm_title": "इन ईमेल की सदस्यता छोड़ें?",
        "confirm_lead": (
            "आपको Shosai से इस तरह के ईमेल मिलना बंद हो जाएगा। खाते से जुड़े ईमेल — साइन-इन कोड, "
            "पासवर्ड रीसेट, रसीदें — आते रहेंगे।"
        ),
        "button": "सदस्यता छोड़ें",
        "done_title": "आपने सदस्यता छोड़ दी है",
        "done_lead": ("इस तरह के ईमेल अब नहीं आएँगे। आप इन्हें Shosai की सेटिंग में फिर से चालू कर सकते हैं।"),
    },
    "ar": {
        "confirm_title": "إلغاء الاشتراك في هذه الرسائل؟",
        "confirm_lead": (
            "لن تصلك بعد الآن رسائل من هذا النوع من Shosai. أما رسائل الحساب — رموز تسجيل الدخول "
            "وإعادة تعيين كلمة المرور والإيصالات — فستستمر في الوصول."
        ),
        "button": "إلغاء الاشتراك",
        "done_title": "تم إلغاء اشتراكك",
        "done_lead": "لن تصلك رسائل من هذا النوع بعد الآن. يمكنك إعادة تفعيلها من إعدادات Shosai.",
    },
    "pt": {
        "confirm_title": "Cancelar a inscrição nestes e-mails?",
        "confirm_lead": (
            "Você deixará de receber e-mails deste tipo do Shosai. Os e-mails da conta — códigos "
            "de acesso, redefinições de senha, recibos — continuarão chegando."
        ),
        "button": "Cancelar inscrição",
        "done_title": "Sua inscrição foi cancelada",
        "done_lead": (
            "E-mails deste tipo não chegarão mais. Você pode reativá-los nas configurações do "
            "Shosai."
        ),
    },
    "fr": {
        "confirm_title": "Se désabonner de ces e-mails ?",
        "confirm_lead": (
            "Vous ne recevrez plus d’e-mails de ce type de la part de Shosai. Les e-mails liés à "
            "votre compte — codes de connexion, réinitialisations de mot de passe, reçus — "
            "continueront d’arriver."
        ),
        "button": "Se désabonner",
        "done_title": "Vous êtes désabonné",
        "done_lead": (
            "Vous ne recevrez plus d’e-mails de ce type. Vous pouvez les réactiver dans les "
            "paramètres de Shosai."
        ),
    },
    "it": {
        "confirm_title": "Annullare l’iscrizione a queste email?",
        "confirm_lead": (
            "Non riceverai più email di questo tipo da Shosai. Le email dell’account — codici di "
            "accesso, reimpostazioni della password, ricevute — continueranno ad arrivare."
        ),
        "button": "Annulla iscrizione",
        "done_title": "Iscrizione annullata",
        "done_lead": (
            "Le email di questo tipo non arriveranno più. Puoi riattivarle nelle impostazioni di "
            "Shosai."
        ),
    },
    "de": {
        "confirm_title": "Diese E-Mails abbestellen?",
        "confirm_lead": (
            "Sie erhalten keine E-Mails dieser Art mehr von Shosai. E-Mails zu Ihrem Konto — "
            "Anmeldecodes, Passwort-Zurücksetzungen, Belege — kommen weiterhin an."
        ),
        "button": "Abbestellen",
        "done_title": "Sie haben abbestellt",
        "done_lead": (
            "E-Mails dieser Art kommen nicht mehr. Sie können sie in den Einstellungen von Shosai "
            "wieder einschalten."
        ),
    },
    "ja": {
        "confirm_title": "このメールの配信を停止しますか？",
        "confirm_lead": (
            "Shosai "
            "からこの種類のメールは届かなくなります。アカウントに関するメール（サインインコード、パ"
            "スワードの再設定、領収書）は引き続き届きます。"
        ),
        "button": "配信を停止",
        "done_title": "配信を停止しました",
        "done_lead": "この種類のメールは今後届きません。Shosai の設定から再開できます。",
    },
    "ko": {
        "confirm_title": "이 메일 수신을 거부하시겠어요?",
        "confirm_lead": (
            "Shosai에서 이런 종류의 메일을 더 이상 받지 않게 됩니다. 계정 메일(로그인 코드, "
            "비밀번호 재설정, 영수증)은 계속 발송됩니다."
        ),
        "button": "수신 거부",
        "done_title": "수신 거부되었습니다",
        "done_lead": (
            "이런 종류의 메일은 더 이상 발송되지 않습니다. Shosai 설정에서 다시 켤 수 있습니다."
        ),
    },
    "id": {
        "confirm_title": "Berhenti berlangganan email ini?",
        "confirm_lead": (
            "Anda tidak akan lagi menerima email jenis ini dari Shosai. Email akun — kode masuk, "
            "pengaturan ulang kata sandi, tanda terima — tetap akan dikirim."
        ),
        "button": "Berhenti berlangganan",
        "done_title": "Anda telah berhenti berlangganan",
        "done_lead": (
            "Email jenis ini tidak akan dikirim lagi. Anda dapat mengaktifkannya kembali di "
            "pengaturan Shosai."
        ),
    },
    "tr": {
        "confirm_title": "Bu e-postaların aboneliğinden çıkılsın mı?",
        "confirm_lead": (
            "Shosai’den bu türdeki e-postaları artık almayacaksınız. Hesap e-postaları — giriş "
            "kodları, parola sıfırlama, makbuzlar — gelmeye devam edecek."
        ),
        "button": "Abonelikten çık",
        "done_title": "Abonelikten çıktınız",
        "done_lead": (
            "Bu türdeki e-postalar artık gelmeyecek. Bunları Shosai ayarlarından yeniden "
            "açabilirsiniz."
        ),
    },
    "vi": {
        "confirm_title": "Hủy đăng ký nhận các email này?",
        "confirm_lead": (
            "Bạn sẽ không còn nhận email loại này từ Shosai. Email tài khoản — mã đăng nhập, đặt "
            "lại mật khẩu, biên lai — vẫn sẽ được gửi."
        ),
        "button": "Hủy đăng ký",
        "done_title": "Bạn đã hủy đăng ký",
        "done_lead": (
            "Email loại này sẽ không còn được gửi. Bạn có thể bật lại trong phần cài đặt của "
            "Shosai."
        ),
    },
    "th": {
        "confirm_title": "ยกเลิกการรับอีเมลเหล่านี้หรือไม่",
        "confirm_lead": (
            "คุณจะไม่ได้รับอีเมลประเภทนี้จาก Shosai อีก ส่วนอีเมลเกี่ยวกับบัญชี เช่น "
            "รหัสเข้าสู่ระบบ การรีเซ็ตรหัสผ่าน และใบเสร็จ จะยังส่งถึงคุณตามปกติ"
        ),
        "button": "ยกเลิกการรับ",
        "done_title": "ยกเลิกการรับแล้ว",
        "done_lead": ("คุณจะไม่ได้รับอีเมลประเภทนี้อีก และสามารถเปิดรับใหม่ได้ในการตั้งค่าของ Shosai"),
    },
}
