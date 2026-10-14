"""The check mail: what `shosai email check` sends to prove the mail path end to end.

It uses every block of the layout — heading, paragraph, code, button, note — so the same
mail shows the operator that SMTP delivers and the owner how the layout looks (F6-D7).
User-facing text in the 16 platform languages.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

CHECK_BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.code(p.sample_code) }}
{{ e.button(p.url, t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Shosai mail check",
        "preheader": "If you can read this, mail from Shosai reaches you.",
        "heading": "Mail is working",
        "lead": (
            "This is a check message from Shosai. If you can read it, our "
            "mail reaches you and looks as it should."
        ),
        "button": "Open Shosai",
        "note": (
            "Nothing needs to be done: this message only checks that mail "
            "works. The code above is a sample."
        ),
    },
    "zh-Hant": {
        "subject": "Shosai 郵件檢查",
        "preheader": "如果您能看到這封郵件，代表 Shosai 的郵件可以送達。",
        "heading": "郵件運作正常",
        "lead": (
            "這是一封來自 Shosai 的檢查郵件。如果您能閱讀它，代表我們的郵件能送達您，且顯示正常。"
        ),
        "button": "開啟 Shosai",
        "note": ("您無需採取任何行動：這封郵件僅用於檢查郵件是否正常運作。上方的代碼只是範例。"),
    },
    "es": {
        "subject": "Comprobación de correo de Shosai",
        "preheader": "Si puedes leer esto, el correo de Shosai te llega.",
        "heading": "El correo funciona",
        "lead": (
            "Este es un mensaje de comprobación de Shosai. Si puedes "
            "leerlo, nuestro correo te llega y se ve como debe."
        ),
        "button": "Abrir Shosai",
        "note": (
            "No tienes que hacer nada: este mensaje solo comprueba que el "
            "correo funciona. El código de arriba es un ejemplo."
        ),
    },
    "ru": {
        "subject": "Проверка почты Shosai",
        "preheader": "Если вы видите это письмо, почта Shosai до вас доходит.",
        "heading": "Почта работает",
        "lead": (
            "Это проверочное письмо от Shosai. Если вы его читаете, наша "
            "почта до вас доходит и выглядит так, как должна."
        ),
        "button": "Открыть Shosai",
        "note": (
            "Ничего делать не нужно: письмо только проверяет, что почта "
            "работает. Код выше — пример."
        ),
    },
    "hi": {
        "subject": "Shosai ईमेल जाँच",
        "preheader": "अगर आप यह पढ़ पा रहे हैं, तो Shosai का ईमेल आप तक पहुँच रहा है।",
        "heading": "ईमेल काम कर रहा है",
        "lead": (
            "यह Shosai का एक जाँच संदेश है। अगर आप इसे पढ़ पा रहे हैं, तो "
            "हमारा ईमेल आप तक पहुँचता है और सही दिखता है।"
        ),
        "button": "Shosai खोलें",
        "note": (
            "आपको कुछ करने की ज़रूरत नहीं है: यह संदेश सिर्फ़ जाँचता है "
            "कि ईमेल काम कर रहा है। ऊपर का कोड एक उदाहरण है।"
        ),
    },
    "ar": {
        "subject": "فحص بريد Shosai",
        "preheader": "إذا كنت تقرأ هذا، فإن بريد Shosai يصل إليك.",
        "heading": "البريد يعمل",
        "lead": ("هذه رسالة فحص من Shosai. إذا كنت تقرؤها، فإن بريدنا يصل إليك ويظهر كما ينبغي."),
        "button": "افتح Shosai",
        "note": ("لا حاجة لأي إجراء: هذه الرسالة تتحقق فقط من عمل البريد. الرمز أعلاه مجرد مثال."),
    },
    "pt-BR": {
        "subject": "Verificação de e-mail do Shosai",
        "preheader": "Se você consegue ler isto, o e-mail do Shosai chega até você.",
        "heading": "O e-mail está funcionando",
        "lead": (
            "Esta é uma mensagem de verificação do Shosai. Se você "
            "consegue lê-la, nosso e-mail chega até você e aparece como "
            "deve."
        ),
        "button": "Abrir o Shosai",
        "note": (
            "Não é preciso fazer nada: esta mensagem só verifica se o "
            "e-mail funciona. O código acima é um exemplo."
        ),
    },
    "fr": {
        "subject": "Vérification de l’e-mail Shosai",
        "preheader": "Si vous lisez ceci, les e-mails de Shosai vous parviennent.",
        "heading": "L’e-mail fonctionne",
        "lead": (
            "Ceci est un message de vérification de Shosai. Si vous "
            "pouvez le lire, nos e-mails vous parviennent et s’affichent "
            "correctement."
        ),
        "button": "Ouvrir Shosai",
        "note": (
            "Vous n’avez rien à faire : ce message vérifie seulement que "
            "l’e-mail fonctionne. Le code ci-dessus est un exemple."
        ),
    },
    "it": {
        "subject": "Verifica email di Shosai",
        "preheader": "Se riesci a leggere questo messaggio, le email di Shosai ti arrivano.",
        "heading": "L’email funziona",
        "lead": (
            "Questo è un messaggio di verifica di Shosai. Se riesci a "
            "leggerlo, le nostre email ti arrivano e si vedono come "
            "devono."
        ),
        "button": "Apri Shosai",
        "note": (
            "Non devi fare nulla: questo messaggio verifica solo che "
            "l’email funzioni. Il codice qui sopra è un esempio."
        ),
    },
    "de": {
        "subject": "Shosai-E-Mail-Test",
        "preheader": "Wenn Sie das lesen können, erreicht Sie die E-Mail von Shosai.",
        "heading": "Die E-Mail funktioniert",
        "lead": (
            "Dies ist eine Testnachricht von Shosai. Wenn Sie sie lesen "
            "können, erreicht Sie unsere E-Mail und wird richtig "
            "angezeigt."
        ),
        "button": "Shosai öffnen",
        "note": (
            "Sie müssen nichts tun: Diese Nachricht prüft nur, ob die "
            "E-Mail funktioniert. Der Code oben ist ein Beispiel."
        ),
    },
    "ja": {
        "subject": "Shosai メール確認",
        "preheader": "このメールが読めていれば、Shosai からのメールは届いています。",
        "heading": "メールは正常です",
        "lead": (
            "これは Shosai からの確認メールです。読めていれば、メールは正"
            "しく届き、正しく表示されています。"
        ),
        "button": "Shosai を開く",
        "note": (
            "対応は不要です。このメールはメールが正常に動作しているかを確"
            "認するためのものです。上のコードは見本です。"
        ),
    },
    "ko": {
        "subject": "Shosai 메일 확인",
        "preheader": "이 메일이 보인다면 Shosai 메일이 잘 도착하고 있습니다.",
        "heading": "메일이 정상입니다",
        "lead": (
            "Shosai에서 보낸 확인 메일입니다. 이 메일을 읽으실 수 있다면 "
            "메일이 잘 도착하고 제대로 표시되는 것입니다."
        ),
        "button": "Shosai 열기",
        "note": (
            "따로 하실 일은 없습니다. 이 메일은 메일이 정상인지 확인할 뿐"
            "이며, 위의 코드는 예시입니다."
        ),
    },
    "id": {
        "subject": "Pemeriksaan email Shosai",
        "preheader": "Jika Anda bisa membaca ini, email dari Shosai sampai kepada Anda.",
        "heading": "Email berfungsi",
        "lead": (
            "Ini adalah pesan pemeriksaan dari Shosai. Jika Anda bisa "
            "membacanya, email kami sampai kepada Anda dan tampil "
            "sebagaimana mestinya."
        ),
        "button": "Buka Shosai",
        "note": (
            "Anda tidak perlu melakukan apa pun: pesan ini hanya "
            "memeriksa bahwa email berfungsi. Kode di atas hanyalah "
            "contoh."
        ),
    },
    "tr": {
        "subject": "Shosai e-posta kontrolü",
        "preheader": "Bunu okuyabiliyorsanız Shosai’den gelen e-postalar size ulaşıyor.",
        "heading": "E-posta çalışıyor",
        "lead": (
            "Bu, Shosai’den bir kontrol mesajıdır. Okuyabiliyorsanız "
            "e-postalarımız size ulaşıyor ve olması gerektiği gibi "
            "görünüyor."
        ),
        "button": "Shosai’yi aç",
        "note": (
            "Bir şey yapmanıza gerek yok: bu mesaj yalnızca e-postanın "
            "çalıştığını kontrol eder. Yukarıdaki kod bir örnektir."
        ),
    },
    "vi": {
        "subject": "Kiểm tra email Shosai",
        "preheader": "Nếu bạn đọc được dòng này, email từ Shosai đã đến được với bạn.",
        "heading": "Email đang hoạt động",
        "lead": (
            "Đây là thư kiểm tra từ Shosai. Nếu bạn đọc được thư này, "
            "email của chúng tôi đã đến được với bạn và hiển thị đúng."
        ),
        "button": "Mở Shosai",
        "note": (
            "Bạn không cần làm gì: thư này chỉ kiểm tra rằng email hoạt "
            "động. Mã ở trên chỉ là ví dụ."
        ),
    },
    "nl": {
        "subject": "Mailcontrole van Shosai",
        "preheader": "Kun je dit lezen, dan bereikt mail van Shosai je.",
        "heading": "Mail werkt",
        "lead": (
            "Dit is een controlebericht van Shosai. Kun je het lezen, dan bereikt onze mail je en "
            "ziet die er goed uit."
        ),
        "button": "Shosai openen",
        "note": (
            "Je hoeft niets te doen: dit bericht controleert alleen of mail werkt. De code "
            "hierboven is een voorbeeld."
        ),
    },
}

MAIL_CHECK: Final = EmailTemplate(key="core.mail_check", body=CHECK_BODY, texts=_TEXTS)
