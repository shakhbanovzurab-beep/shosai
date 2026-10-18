"""The knowledge reminder: Leo stops reading the newest files over the limit on a date (FL-D10).

It goes 30, 7 and 1 day before the end of the 90 days, in the transaction that counts the
reminder, and says that Leo keeps reading everything until then, that nothing is deleted,
and how to choose what Leo reads.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

LEO_OVER_LIMIT_KEY: Final = "files.leo_over_limit"
BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(base_url ~ "/app/knowledge-base", t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Choose what Leo reads before {date}",
        "preheader": (
            "Leo reads more of your files than your plan includes. Nothing has changed yet."
        ),
        "heading": "Leo reads more files than your plan includes",
        "lead": (
            "The files Leo reads take more than your plan's knowledge base, so Leo can't start "
            "reading new ones. Leo keeps reading everything it reads now. Before {date}, switch "
            "off files Leo doesn't need or choose a plan with a larger knowledge base. After that "
            "date, Leo will stop reading the newest files over the limit."
        ),
        "button": "Open Knowledge",
        "note": "No file is deleted. You can choose again which files Leo reads within your plan.",
    },
    "fr": {
        "subject": "Choisissez ce que Leo lit avant le {date}",
        "preheader": "Leo lit plus de fichiers que votre offre n'en comprend. Rien n'a changé.",
        "heading": "Leo lit plus de fichiers que votre offre n'en comprend",
        "lead": (
            "Les fichiers que Leo lit dépassent la base de connaissances de votre offre : Leo ne "
            "peut pas en lire de nouveaux. Leo continue de lire tout ce qu'il lit aujourd'hui. "
            "Avant le {date}, désactivez les fichiers dont Leo n'a pas besoin ou choisissez une "
            "offre avec une base de connaissances plus grande. Après cette date, Leo cessera de "
            "lire les fichiers les plus récents au-delà de la limite."
        ),
        "button": "Ouvrir Connaissances",
        "note": "Aucun fichier n'est supprimé. Vous pourrez choisir à nouveau ce que Leo lit.",
    },
    "de": {
        "subject": "Wähle bis zum {date}, was Leo liest",
        "preheader": (
            "Leo liest mehr Dateien, als dein Tarif enthält. Noch hat sich nichts geändert."
        ),
        "heading": "Leo liest mehr Dateien, als dein Tarif enthält",
        "lead": (
            "Die Dateien, die Leo liest, überschreiten die Wissensdatenbank deines Tarifs, "
            "deshalb kann Leo keine neuen lesen. Was Leo jetzt liest, bleibt erhalten. "
            "Schalte bis zum {date} Dateien aus, die Leo nicht braucht, oder wähle einen Tarif "
            "mit größerer Wissensdatenbank. Danach liest Leo die neuesten Dateien über dem Limit "
            "nicht mehr."
        ),
        "button": "Wissen öffnen",
        "note": "Keine Datei wird gelöscht. Du kannst innerhalb deines Tarifs neu wählen.",
    },
    "ru": {
        "subject": "Выберите, что читает Leo, до {date}",
        "preheader": "Leo читает больше файлов, чем входит в тариф. Пока ничего не изменилось.",
        "heading": "Leo читает больше файлов, чем входит в тариф",
        "lead": (
            "Файлы, которые читает Leo, занимают больше, чем база знаний вашего тарифа, поэтому "
            "новые файлы Leo читать не начнёт. Всё, что Leo читает сейчас, остаётся. "
            "До {date} выключите файлы, которые Leo не нужны, или выберите тариф с базой знаний "
            "побольше. После этой даты Leo перестанет читать самые новые файлы сверх лимита."
        ),
        "button": "Открыть базу знаний",
        "note": "Файлы не удаляются. Вы сможете снова выбрать, что читает Leo, в пределах тарифа.",
    },
    "nl": {
        "subject": "Kies vóór {date} wat Leo leest",
        "preheader": "Leo leest meer bestanden dan je abonnement bevat. Er is nog niets veranderd.",
        "heading": "Leo leest meer bestanden dan je abonnement bevat",
        "lead": (
            "De bestanden die Leo leest, gaan over de kennisbank van je abonnement, dus Leo kan "
            "geen nieuwe gaan lezen. Alles wat Leo nu leest, blijft Leo lezen. Zet vóór {date} "
            "bestanden uit die Leo niet nodig heeft of kies een abonnement met een grotere "
            "kennisbank. Daarna stopt Leo met het lezen van de nieuwste bestanden boven de limiet."
        ),
        "button": "Kennis openen",
        "note": "Er wordt geen bestand verwijderd. Je kunt binnen je abonnement opnieuw kiezen.",
    },
    "it": {
        "subject": "Scegli entro il {date} cosa legge Leo",
        "preheader": (
            "Leo legge più file di quanti ne includa il tuo piano. Non è ancora cambiato nulla."
        ),
        "heading": "Leo legge più file di quanti ne includa il tuo piano",
        "lead": (
            "I file che Leo legge superano la base di conoscenza del tuo piano, quindi Leo non può "
            "iniziare a leggerne di nuovi. Leo continua a leggere tutto ciò che legge ora. Entro "
            "il "
            "{date} disattiva i file che a Leo non servono o scegli un piano con una base di "
            "conoscenza più grande. Dopo quella data Leo smetterà di leggere i file più recenti "
            "oltre il limite."
        ),
        "button": "Apri Conoscenza",
        "note": "Nessun file viene eliminato. Potrai scegliere di nuovo cosa legge Leo.",
    },
    "es": {
        "subject": "Elige qué lee Leo antes del {date}",
        "preheader": (
            "Leo lee más archivos de los que incluye tu plan. Todavía no ha cambiado nada."
        ),
        "heading": "Leo lee más archivos de los que incluye tu plan",
        "lead": (
            "Los archivos que lee Leo superan la base de conocimientos de tu plan, así que Leo no "
            "puede empezar a leer otros nuevos. Leo sigue leyendo todo lo que lee ahora. Antes del "
            "{date}, desactiva los archivos que Leo no necesita o elige un plan con una base de "
            "conocimientos mayor. Después de esa fecha, Leo dejará de leer los archivos más "
            "recientes que superen el límite."
        ),
        "button": "Abrir Conocimiento",
        "note": (
            "No se elimina ningún archivo. Podrás volver a elegir qué lee Leo dentro de tu plan."
        ),
    },
    "pt-BR": {
        "subject": "Escolha o que o Leo lê antes de {date}",
        "preheader": "O Leo lê mais arquivos do que o seu plano inclui. Nada mudou ainda.",
        "heading": "O Leo lê mais arquivos do que o seu plano inclui",
        "lead": (
            "Os arquivos que o Leo lê passam da base de conhecimento do seu plano, então o Leo não "
            "pode começar a ler novos. O Leo continua lendo tudo o que lê agora. Antes de {date}, "
            "desative os arquivos de que o Leo não precisa ou escolha um plano com uma base de "
            "conhecimento maior. Depois dessa data, o Leo deixará de ler os arquivos mais "
            "recentes acima do limite."
        ),
        "button": "Abrir Conhecimento",
        "note": "Nenhum arquivo é excluído. Você poderá escolher de novo o que o Leo lê.",
    },
    "ar": {
        "subject": "اختر ما يقرؤه Leo قبل {date}",
        "preheader": "يقرأ Leo ملفات أكثر مما تتضمنه خطتك. لم يتغير شيء بعد.",
        "heading": "يقرأ Leo ملفات أكثر مما تتضمنه خطتك",
        "lead": (
            "الملفات التي يقرؤها Leo تتجاوز قاعدة المعرفة في خطتك، لذلك لا يستطيع Leo البدء في "
            "قراءة ملفات جديدة. وسيواصل قراءة كل ما يقرؤه الآن. قبل {date} أوقف الملفات التي لا "
            "يحتاجها Leo أو اختر خطة بقاعدة معرفة أكبر. بعد هذا التاريخ سيتوقف Leo عن قراءة أحدث "
            "الملفات التي تتجاوز الحد."
        ),
        "button": "فتح المعرفة",
        "note": "لا يُحذف أي ملف. يمكنك أن تختار من جديد ما يقرؤه Leo ضمن خطتك.",
    },
    "tr": {
        "subject": "{date} tarihinden önce Leo'nun neyi okuyacağını seçin",
        "preheader": "Leo, planınızın içerdiğinden fazla dosya okuyor. Henüz hiçbir şey değişmedi.",
        "heading": "Leo, planınızın içerdiğinden fazla dosya okuyor",
        "lead": (
            "Leo'nun okuduğu dosyalar planınızın bilgi bankası sınırını aşıyor, bu yüzden Leo yeni "
            "dosya okumaya başlayamaz. Şu anda okuduğu her şeyi okumaya devam eder. {date} "
            "tarihinden önce Leo'nun ihtiyaç duymadığı dosyaları kapatın veya daha büyük bilgi "
            "bankası olan bir plan seçin. Bu tarihten sonra Leo, sınırı aşan en yeni dosyaları "
            "okumayı bırakacak."
        ),
        "button": "Bilgi bankasını aç",
        "note": (
            "Hiçbir dosya silinmez. Leo'nun neyi okuyacağını planınız dahilinde yeniden "
            "seçebilirsiniz."
        ),
    },
    "ko": {
        "subject": "{date} 전에 Leo가 읽을 파일을 선택하세요",
        "preheader": (
            "Leo가 플랜에 포함된 것보다 많은 파일을 읽고 있습니다. 아직 바뀐 것은 없습니다."
        ),
        "heading": "Leo가 플랜에 포함된 것보다 많은 파일을 읽고 있습니다",
        "lead": (
            "Leo가 읽는 파일이 플랜의 지식 베이스 한도를 넘어 Leo가 새 파일을 읽기 시작할 수 "
            "없습니다. 지금 읽는 파일은 계속 읽습니다. {date} 전에 Leo에게 필요 없는 파일을 끄거나 "
            "지식 베이스가 더 큰 플랜을 선택하세요. 이 날짜 이후에는 한도를 넘는 가장 최근 "
            "파일부터 "
            "Leo가 읽지 않습니다."
        ),
        "button": "지식 열기",
        "note": (
            "파일은 삭제되지 않습니다. 플랜 한도 안에서 Leo가 읽을 파일을 다시 선택할 수 있습니다."
        ),
    },
    "hi": {
        "subject": "{date} से पहले चुनें कि Leo क्या पढ़े",
        "preheader": ("Leo आपके प्लान में शामिल फ़ाइलों से ज़्यादा फ़ाइलें पढ़ रहा है। अभी कुछ नहीं बदला है।"),
        "heading": "Leo आपके प्लान में शामिल फ़ाइलों से ज़्यादा फ़ाइलें पढ़ रहा है",
        "lead": (
            "Leo जो फ़ाइलें पढ़ता है, वे आपके प्लान के नॉलेज बेस से ज़्यादा हैं, इसलिए Leo नई "
            "फ़ाइलें पढ़ना शुरू नहीं कर सकता। अभी जो कुछ वह पढ़ रहा है, वह पढ़ता रहेगा। {date} से "
            "पहले वे फ़ाइलें बंद करें जिनकी Leo को ज़रूरत नहीं है, या बड़े नॉलेज बेस वाला प्लान "
            "चुनें। "
            "इस तारीख़ के बाद Leo सीमा से ऊपर की सबसे नई फ़ाइलें पढ़ना बंद कर देगा।"
        ),
        "button": "नॉलेज खोलें",
        "note": ("कोई फ़ाइल डिलीट नहीं होती। आप अपने प्लान के भीतर फिर से चुन सकते हैं कि Leo क्या पढ़े।"),
    },
    "vi": {
        "subject": "Chọn những gì Leo đọc trước {date}",
        "preheader": "Leo đang đọc nhiều tệp hơn gói của bạn cho phép. Chưa có gì thay đổi.",
        "heading": "Leo đang đọc nhiều tệp hơn gói của bạn cho phép",
        "lead": (
            "Các tệp Leo đọc vượt quá cơ sở kiến thức trong gói của bạn, nên Leo không thể bắt đầu "
            "đọc tệp mới. Leo vẫn tiếp tục đọc mọi thứ đang đọc. Trước {date}, hãy tắt những tệp "
            "Leo không cần hoặc chọn gói có cơ sở kiến thức lớn hơn. Sau ngày đó, Leo sẽ ngừng đọc "
            "các tệp mới nhất vượt quá giới hạn."
        ),
        "button": "Mở Kiến thức",
        "note": (
            "Không tệp nào bị xóa. Bạn có thể chọn lại những gì Leo đọc trong giới hạn của gói."
        ),
    },
    "zh-Hant": {
        "subject": "請在 {date} 前選擇 Leo 要讀取的檔案",
        "preheader": "Leo 讀取的檔案超出方案所含的容量。目前一切照舊。",
        "heading": "Leo 讀取的檔案超出方案所含的容量",
        "lead": (
            "Leo 讀取的檔案已超過方案的知識庫上限，因此 Leo 無法開始讀取新的檔案。目前讀取的檔案"
            "會繼續讀取。請在 {date} 前關閉 Leo 不需要的檔案，或選擇知識庫更大的方案。過了這個"
            "日期，Leo 會從最新的檔案開始停止讀取超出上限的部分。"
        ),
        "button": "開啟知識庫",
        "note": "檔案不會被刪除。你可以在方案範圍內重新選擇 Leo 要讀取的檔案。",
    },
    "ja": {
        "subject": "{date} までに Leo が読むファイルを選んでください",
        "preheader": (
            "Leo がプランに含まれる量を超えるファイルを読んでいます。まだ何も変わっていません。"
        ),
        "heading": "Leo がプランに含まれる量を超えるファイルを読んでいます",
        "lead": (
            "Leo が読むファイルがプランのナレッジベースの上限を超えているため、Leo は新しいファイル"
            "を読み始められません。今読んでいるものは引き続き読みます。{date} までに Leo に不要な"
            "ファイルをオフにするか、ナレッジベースの大きいプランを選んでください。この日を過ぎると"
            "、"
            "上限を超えた分の新しいファイルから Leo は読まなくなります。"
        ),
        "button": "ナレッジを開く",
        "note": "ファイルは削除されません。プランの範囲内で Leo が読むファイルを選び直せます。",
    },
    "id": {
        "subject": "Pilih apa yang dibaca Leo sebelum {date}",
        "preheader": "Leo membaca lebih banyak file daripada yang termasuk dalam paket Anda.",
        "heading": "Leo membaca lebih banyak file daripada yang termasuk dalam paket Anda",
        "lead": (
            "File yang dibaca Leo melebihi basis pengetahuan dalam paket Anda, jadi Leo tidak bisa "
            "mulai membaca file baru. Leo tetap membaca semua yang dibacanya sekarang. Sebelum "
            "{date}, matikan file yang tidak diperlukan Leo atau pilih paket dengan basis "
            "pengetahuan lebih besar. Setelah tanggal itu, Leo akan berhenti membaca file terbaru "
            "yang melebihi batas."
        ),
        "button": "Buka Pengetahuan",
        "note": "Tidak ada file yang dihapus. Anda bisa memilih lagi apa yang dibaca Leo.",
    },
}

LEO_OVER_LIMIT: Final = EmailTemplate(key=LEO_OVER_LIMIT_KEY, body=BODY, texts=_TEXTS)
