"""The export mail: the archive of the person's data is ready in the cabinet (§3.6).

It goes in the transaction that marks the job ready and sends the person to Settings,
where a fresh download link is made on each visit; the mail carries no link to the file.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

EXPORT_READY_KEY: Final = "identity.export_ready"
BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(base_url ~ "/app/settings", t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Your Shosai data is ready to download",
        "preheader": "The archive is kept for {days} days.",
        "heading": "Your archive is ready",
        "lead": (
            "Everything Shosai keeps about you is now in one archive. Download it in Shosai "
            "settings within {days} days; after that it is deleted."
        ),
        "button": "Open settings",
        "note": "If you did not ask for this archive, sign in and change your password.",
    },
    "fr": {
        "subject": "Vos données Shosai sont prêtes à être téléchargées",
        "preheader": "L'archive est conservée {days} jours.",
        "heading": "Votre archive est prête",
        "lead": (
            "Tout ce que Shosai conserve à votre sujet se trouve désormais dans une seule archive. "
            "Téléchargez-la dans les paramètres de Shosai sous {days} jours ; elle sera ensuite "
            "supprimée."
        ),
        "button": "Ouvrir les paramètres",
        "note": (
            "Si vous n'avez pas demandé cette archive, connectez-vous et changez votre mot de "
            "passe."
        ),
    },
    "de": {
        "subject": "Deine Shosai-Daten stehen zum Download bereit",
        "preheader": "Das Archiv wird {days} Tage aufbewahrt.",
        "heading": "Dein Archiv ist fertig",
        "lead": (
            "Alles, was Shosai über dich speichert, liegt jetzt in einem Archiv. Lade es innerhalb "
            "von {days} Tagen in den Shosai-Einstellungen herunter; danach wird es gelöscht."
        ),
        "button": "Einstellungen öffnen",
        "note": (
            "Wenn du dieses Archiv nicht angefordert hast, melde dich an und ändere dein Passwort."
        ),
    },
    "ru": {
        "subject": "Ваши данные Shosai готовы к скачиванию",
        "preheader": "Архив хранится {days} дней.",
        "heading": "Архив готов",
        "lead": (
            "Всё, что Shosai хранит о вас, собрано в один архив. Скачайте его в настройках Shosai "
            "в течение {days} дней, потом он будет удалён."
        ),
        "button": "Открыть настройки",
        "note": "Если вы не запрашивали архив, войдите и смените пароль.",
    },
    "nl": {
        "subject": "Je Shosai-gegevens staan klaar om te downloaden",
        "preheader": "Het archief wordt {days} dagen bewaard.",
        "heading": "Je archief is klaar",
        "lead": (
            "Alles wat Shosai over je bewaart, staat nu in één archief. Download het binnen {days} "
            "dagen in de instellingen van Shosai; daarna wordt het verwijderd."
        ),
        "button": "Instellingen openen",
        "note": "Heb je dit archief niet aangevraagd? Log dan in en wijzig je wachtwoord.",
    },
    "it": {
        "subject": "I tuoi dati Shosai sono pronti per il download",
        "preheader": "L'archivio viene conservato per {days} giorni.",
        "heading": "Il tuo archivio è pronto",
        "lead": (
            "Tutto ciò che Shosai conserva su di te ora è in un unico archivio. Scaricalo dalle "
            "impostazioni di Shosai entro {days} giorni; dopo verrà eliminato."
        ),
        "button": "Apri le impostazioni",
        "note": "Se non hai richiesto questo archivio, accedi e cambia la password.",
    },
    "es": {
        "subject": "Tus datos de Shosai están listos para descargar",
        "preheader": "El archivo se conserva durante {days} días.",
        "heading": "Tu archivo está listo",
        "lead": (
            "Todo lo que Shosai guarda sobre ti está ahora en un solo archivo. Descárgalo en la "
            "configuración de Shosai en un plazo de {days} días; después se eliminará."
        ),
        "button": "Abrir la configuración",
        "note": "Si no pediste este archivo, inicia sesión y cambia tu contraseña.",
    },
    "pt-BR": {
        "subject": "Seus dados do Shosai estão prontos para download",
        "preheader": "O arquivo fica disponível por {days} dias.",
        "heading": "Seu arquivo está pronto",
        "lead": (
            "Tudo o que o Shosai guarda sobre você agora está em um único arquivo. Baixe-o nas "
            "configurações do Shosai em até {days} dias; depois disso, ele será excluído."
        ),
        "button": "Abrir configurações",
        "note": "Se você não pediu este arquivo, entre e altere sua senha.",
    },
    "ar": {
        "subject": "بياناتك في Shosai جاهزة للتنزيل",
        "preheader": "يُحفظ الأرشيف لمدة {days} أيام.",
        "heading": "أرشيفك جاهز",
        "lead": (
            "أصبح كل ما يحتفظ به Shosai عنك في أرشيف واحد. نزّله من إعدادات Shosai خلال {days} "
            "أيام، وبعد ذلك سيُحذف."
        ),
        "button": "فتح الإعدادات",
        "note": "إذا لم تطلب هذا الأرشيف، فسجّل الدخول وغيّر كلمة المرور.",
    },
    "tr": {
        "subject": "Shosai verileriniz indirilmeye hazır",
        "preheader": "Arşiv {days} gün saklanır.",
        "heading": "Arşiviniz hazır",
        "lead": (
            "Shosai'nin sizinle ilgili sakladığı her şey artık tek bir arşivde. Arşivi {days} gün "
            "içinde Shosai ayarlarından indirin; sonrasında silinir."
        ),
        "button": "Ayarları açın",
        "note": "Bu arşivi siz istemediyseniz oturum açın ve şifrenizi değiştirin.",
    },
    "ko": {
        "subject": "Shosai 데이터를 다운로드할 준비가 되었습니다",
        "preheader": "아카이브는 {days}일 동안 보관됩니다.",
        "heading": "아카이브가 준비되었습니다",
        "lead": (
            "Shosai가 보관하는 모든 정보를 하나의 아카이브로 모았습니다. {days}일 안에 Shosai "
            "설정에서 다운로드하세요. 그 이후에는 삭제됩니다."
        ),
        "button": "설정 열기",
        "note": "아카이브를 요청하지 않으셨다면 로그인하여 비밀번호를 변경하세요.",
    },
    "hi": {
        "subject": "आपका Shosai डेटा डाउनलोड के लिए तैयार है",
        "preheader": "संग्रह {days} दिनों तक रखा जाता है।",
        "heading": "आपका संग्रह तैयार है",
        "lead": (
            "Shosai आपके बारे में जो कुछ भी रखता है, वह अब एक संग्रह में है। इसे {days} दिनों के भीतर Shosai की "
            "सेटिंग्स से डाउनलोड करें; उसके बाद इसे हटा दिया जाएगा।"
        ),
        "button": "सेटिंग्स खोलें",
        "note": "अगर आपने यह संग्रह नहीं माँगा, तो साइन इन करें और अपना पासवर्ड बदलें।",
    },
    "vi": {
        "subject": "Dữ liệu Shosai của bạn đã sẵn sàng để tải xuống",
        "preheader": "Tệp lưu trữ được giữ trong {days} ngày.",
        "heading": "Tệp lưu trữ của bạn đã sẵn sàng",
        "lead": (
            "Mọi thông tin Shosai lưu giữ về bạn giờ đã nằm trong một tệp lưu trữ. Hãy tải xuống "
            "trong phần cài đặt của Shosai trong vòng {days} ngày; sau đó tệp sẽ bị xóa."
        ),
        "button": "Mở cài đặt",
        "note": "Nếu bạn không yêu cầu tệp này, hãy đăng nhập và đổi mật khẩu.",
    },
    "zh-Hant": {
        "subject": "您的 Shosai 資料已可下載",
        "preheader": "封存檔會保留 {days} 天。",
        "heading": "您的封存檔已準備就緒",
        "lead": (
            "Shosai 保存的所有關於您的資料，現在都在同一個封存檔中。請在 {days} 天內從 Shosai "
            "設定下載，之後檔案將被刪除。"
        ),
        "button": "開啟設定",
        "note": "如果您沒有要求此封存檔，請登入並變更密碼。",
    },
    "ja": {
        "subject": "Shosai のデータをダウンロードできるようになりました",
        "preheader": "アーカイブは {days} 日間保管されます。",
        "heading": "アーカイブの準備ができました",
        "lead": (
            "Shosai が保管しているあなたに関するすべての情報を、1 "
            "つのアーカイブにまとめました。{days} 日以内に Shosai "
            "の設定からダウンロードしてください。その後は削除されます。"
        ),
        "button": "設定を開く",
        "note": (
            "このアーカイブをリクエストしていない場合は、ログインしてパスワードを変更してください。"
        ),
    },
    "id": {
        "subject": "Data Shosai Anda siap diunduh",
        "preheader": "Arsip disimpan selama {days} hari.",
        "heading": "Arsip Anda sudah siap",
        "lead": (
            "Semua yang disimpan Shosai tentang Anda kini ada dalam satu arsip. Unduh arsip itu di "
            "pengaturan Shosai dalam {days} hari; setelah itu arsip akan dihapus."
        ),
        "button": "Buka pengaturan",
        "note": "Jika Anda tidak meminta arsip ini, masuk dan ganti kata sandi Anda.",
    },
}

EXPORT_READY: Final = EmailTemplate(key=EXPORT_READY_KEY, body=BODY, texts=_TEXTS)
