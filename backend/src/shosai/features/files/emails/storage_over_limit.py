"""The storage reminder: files over the plan's limit go on the named date (FL-D2).

It goes 30, 7 and 1 day before the end of the 90 days, in the transaction that counts the
reminder, and says that everything stays available, that new uploads wait, and what to do.
"""

from typing import Final

from shosai.core.email.templates import EmailTemplate

STORAGE_OVER_LIMIT_KEY: Final = "files.storage_over_limit"
BODY: Final = """
{{ e.heading(t.heading) }}
{% call e.paragraph() %}{{ t.lead }}{% endcall %}
{{ e.button(base_url ~ "/app/file-manager", t.button) }}
{% call e.note() %}{{ t.note }}{% endcall %}
"""

_TEXTS: Final = {
    "en": {
        "subject": "Free up space in Shosai before {date}",
        "preheader": "Your files are over your plan's storage. Nothing is lost yet.",
        "heading": "Your files are over your plan's storage",
        "lead": (
            "Your files take more space than your plan includes, so new uploads are paused. "
            "Everything you have stays available. Delete what you no longer need or choose a plan "
            "with more storage before {date}. After that date, the newest files over the limit "
            "will be deleted."
        ),
        "button": "Open my files",
        "note": "Support can restore a deleted file for 7 days after it is deleted.",
    },
    "fr": {
        "subject": "Libérez de l'espace dans Shosai avant le {date}",
        "preheader": "Vos fichiers dépassent le stockage de votre offre. Rien n'est perdu.",
        "heading": "Vos fichiers dépassent le stockage de votre offre",
        "lead": (
            "Vos fichiers occupent plus d'espace que votre offre n'en comprend : les nouveaux "
            "envois sont suspendus. Tout reste accessible. Supprimez ce dont vous n'avez plus "
            "besoin ou choisissez une offre avec plus de stockage avant le {date}. Après cette "
            "date, les fichiers les plus récents au-delà de la limite seront supprimés."
        ),
        "button": "Ouvrir mes fichiers",
        "note": "L'assistance peut restaurer un fichier supprimé pendant 7 jours.",
    },
    "de": {
        "subject": "Schaffe bis zum {date} Platz in Shosai",
        "preheader": (
            "Deine Dateien überschreiten den Speicher deines Tarifs. Noch geht nichts verloren."
        ),
        "heading": "Deine Dateien überschreiten den Speicher deines Tarifs",
        "lead": (
            "Deine Dateien belegen mehr Platz, als dein Tarif enthält, deshalb sind neue Uploads "
            "pausiert. Alles bleibt verfügbar. Lösche, was du nicht mehr brauchst, oder wähle bis "
            "zum {date} einen Tarif mit mehr Speicher. Danach werden die neuesten Dateien über "
            "dem Limit gelöscht."
        ),
        "button": "Meine Dateien öffnen",
        "note": "Der Support kann eine gelöschte Datei 7 Tage lang wiederherstellen.",
    },
    "ru": {
        "subject": "Освободите место в Shosai до {date}",
        "preheader": "Файлы занимают больше места, чем даёт тариф. Пока ничего не потеряно.",
        "heading": "Файлы занимают больше места, чем даёт тариф",
        "lead": (
            "Ваши файлы занимают больше места, чем входит в тариф, поэтому новые загрузки "
            "приостановлены. Всё остаётся доступным. Удалите ненужное или выберите тариф с "
            "большим хранилищем до {date}. После этой даты самые новые файлы сверх лимита будут "
            "удалены."
        ),
        "button": "Открыть мои файлы",
        "note": "Удалённый файл поддержка может восстановить в течение 7 дней.",
    },
    "nl": {
        "subject": "Maak vóór {date} ruimte vrij in Shosai",
        "preheader": "Je bestanden gaan over de opslag van je abonnement. Er is nog niets weg.",
        "heading": "Je bestanden gaan over de opslag van je abonnement",
        "lead": (
            "Je bestanden nemen meer ruimte in dan je abonnement bevat, dus nieuwe uploads zijn "
            "gepauzeerd. Alles blijft beschikbaar. Verwijder wat je niet meer nodig hebt of kies "
            "vóór {date} een abonnement met meer opslag. Daarna worden de nieuwste bestanden "
            "boven de limiet verwijderd."
        ),
        "button": "Mijn bestanden openen",
        "note": "Support kan een verwijderd bestand 7 dagen lang terugzetten.",
    },
    "it": {
        "subject": "Libera spazio in Shosai entro il {date}",
        "preheader": "I tuoi file superano lo spazio del tuo piano. Non hai ancora perso nulla.",
        "heading": "I tuoi file superano lo spazio del tuo piano",
        "lead": (
            "I tuoi file occupano più spazio di quello incluso nel piano, quindi i nuovi "
            "caricamenti sono sospesi. Tutto resta disponibile. Elimina ciò che non ti serve o "
            "scegli un piano con più spazio entro il {date}. Dopo quella data, i file più recenti "
            "oltre il limite verranno eliminati."
        ),
        "button": "Apri i miei file",
        "note": "L'assistenza può ripristinare un file eliminato per 7 giorni.",
    },
    "es": {
        "subject": "Libera espacio en Shosai antes del {date}",
        "preheader": "Tus archivos superan el almacenamiento de tu plan. Aún no has perdido nada.",
        "heading": "Tus archivos superan el almacenamiento de tu plan",
        "lead": (
            "Tus archivos ocupan más espacio del que incluye tu plan, así que las nuevas subidas "
            "están en pausa. Todo sigue disponible. Elimina lo que ya no necesites o elige un plan "
            "con más almacenamiento antes del {date}. Después de esa fecha, se eliminarán los "
            "archivos más recientes que superen el límite."
        ),
        "button": "Abrir mis archivos",
        "note": "El soporte puede restaurar un archivo eliminado durante 7 días.",
    },
    "pt-BR": {
        "subject": "Libere espaço no Shosai até {date}",
        "preheader": "Seus arquivos passam do armazenamento do seu plano. Nada foi perdido.",
        "heading": "Seus arquivos passam do armazenamento do seu plano",
        "lead": (
            "Seus arquivos ocupam mais espaço do que o seu plano inclui, então novos envios estão "
            "pausados. Tudo continua disponível. Exclua o que não precisa mais ou escolha um plano "
            "com mais armazenamento até {date}. Depois dessa data, os arquivos mais recentes "
            "acima do limite serão excluídos."
        ),
        "button": "Abrir meus arquivos",
        "note": "O suporte pode restaurar um arquivo excluído por 7 dias.",
    },
    "ar": {
        "subject": "وفّر مساحة في Shosai قبل {date}",
        "preheader": "ملفاتك تتجاوز مساحة خطتك. لم يُفقد شيء بعد.",
        "heading": "ملفاتك تتجاوز مساحة خطتك",
        "lead": (
            "تشغل ملفاتك مساحة أكبر مما تتضمنه خطتك، لذا أُوقف رفع الملفات الجديدة مؤقتًا. يبقى كل "
            "شيء متاحًا. احذف ما لم تعد تحتاج إليه أو اختر خطة بمساحة أكبر قبل {date}. بعد هذا "
            "التاريخ ستُحذف أحدث الملفات التي تتجاوز الحد."
        ),
        "button": "افتح ملفاتي",
        "note": "يمكن للدعم استعادة الملف المحذوف خلال 7 أيام.",
    },
    "tr": {
        "subject": "{date} tarihinden önce Shosai'de yer açın",
        "preheader": "Dosyalarınız planınızın depolama alanını aşıyor. Henüz bir şey kaybolmadı.",
        "heading": "Dosyalarınız planınızın depolama alanını aşıyor",
        "lead": (
            "Dosyalarınız planınızın içerdiğinden fazla yer kaplıyor, bu yüzden yeni yüklemeler "
            "duraklatıldı. Her şey erişilebilir kalıyor. {date} tarihinden önce artık gerekmeyen "
            "dosyaları silin veya daha fazla depolama alanı olan bir plan seçin. Bu tarihten sonra "
            "sınırı aşan en yeni dosyalar silinecek."
        ),
        "button": "Dosyalarımı aç",
        "note": "Destek ekibi silinen bir dosyayı 7 gün boyunca geri yükleyebilir.",
    },
    "ko": {
        "subject": "{date} 전에 Shosai 저장 공간을 확보하세요",
        "preheader": "파일이 요금제의 저장 공간을 넘었습니다. 아직 잃은 것은 없습니다.",
        "heading": "파일이 요금제의 저장 공간을 넘었습니다",
        "lead": (
            "파일이 요금제에 포함된 공간보다 많은 공간을 차지해 새 업로드가 일시 중지되었습니다. "
            "모든 파일은 그대로 사용할 수 있습니다. {date} 전에 필요 없는 파일을 삭제하거나 저장 "
            "공간이 더 큰 요금제를 선택하세요. 이 날짜가 지나면 한도를 넘는 최신 파일부터 "
            "삭제됩니다."
        ),
        "button": "내 파일 열기",
        "note": "삭제된 파일은 7일 동안 지원팀이 복원할 수 있습니다.",
    },
    "hi": {
        "subject": "{date} से पहले Shosai में जगह खाली करें",
        "preheader": "आपकी फ़ाइलें आपके प्लान के स्टोरेज से ज़्यादा हैं। अभी कुछ नहीं खोया है।",
        "heading": "आपकी फ़ाइलें आपके प्लान के स्टोरेज से ज़्यादा हैं",
        "lead": (
            "आपकी फ़ाइलें आपके प्लान में शामिल जगह से ज़्यादा जगह ले रही हैं, इसलिए नए अपलोड रोक दिए "
            "गए हैं। सब कुछ उपलब्ध रहता है। {date} से पहले जो ज़रूरी नहीं है उसे हटाएँ या ज़्यादा "
            "स्टोरेज वाला प्लान चुनें। उस तारीख के बाद सीमा से ऊपर की सबसे नई फ़ाइलें हटा दी जाएँगी।"
        ),
        "button": "मेरी फ़ाइलें खोलें",
        "note": "हटाई गई फ़ाइल को सपोर्ट 7 दिनों तक वापस ला सकता है।",
    },
    "vi": {
        "subject": "Giải phóng dung lượng trong Shosai trước {date}",
        "preheader": "Tệp của bạn vượt quá dung lượng của gói. Chưa có gì bị mất.",
        "heading": "Tệp của bạn vượt quá dung lượng của gói",
        "lead": (
            "Tệp của bạn chiếm nhiều dung lượng hơn mức gói của bạn bao gồm, nên việc tải lên mới "
            "đang tạm dừng. Mọi thứ vẫn dùng được. Hãy xóa những gì bạn không cần nữa hoặc chọn "
            "gói có nhiều dung lượng hơn trước {date}. Sau ngày đó, các tệp mới nhất vượt giới "
            "hạn sẽ bị xóa."
        ),
        "button": "Mở tệp của tôi",
        "note": "Bộ phận hỗ trợ có thể khôi phục tệp đã xóa trong vòng 7 ngày.",
    },
    "zh-Hant": {
        "subject": "請在 {date} 前釋出 Shosai 的空間",
        "preheader": "你的檔案超出方案的儲存空間。目前還沒有任何損失。",
        "heading": "你的檔案超出方案的儲存空間",
        "lead": (
            "你的檔案佔用的空間超過方案所含的容量，因此新的上傳已暫停。所有檔案仍可使用。請在 "
            "{date} 前刪除不再需要的檔案，或選擇儲存空間更大的方案。該日期之後，超出上限的最新檔案"
            "將被刪除。"
        ),
        "button": "開啟我的檔案",
        "note": "檔案刪除後 7 天內，客服可以為你復原。",
    },
    "ja": {
        "subject": "{date} までに Shosai の空き容量を確保してください",
        "preheader": "ファイルがプランの容量を超えています。まだ何も失われていません。",
        "heading": "ファイルがプランの容量を超えています",
        "lead": (
            "ファイルがプランに含まれる容量を超えているため、新しいアップロードを一時停止しています。"
            "すべてのファイルは引き続き利用できます。{date} までに不要なファイルを削除するか、"
            "容量の大きいプランを選んでください。この日を過ぎると、上限を超えた分の新しいファイルから削除"
            "されます。"
        ),
        "button": "ファイルを開く",
        "note": "削除されたファイルは、7 日間はサポートが復元できます。",
    },
    "id": {
        "subject": "Kosongkan ruang di Shosai sebelum {date}",
        "preheader": "File Anda melebihi penyimpanan paket Anda. Belum ada yang hilang.",
        "heading": "File Anda melebihi penyimpanan paket Anda",
        "lead": (
            "File Anda memakai lebih banyak ruang daripada yang termasuk dalam paket, jadi "
            "unggahan baru dijeda. Semuanya tetap tersedia. Hapus yang tidak lagi Anda perlukan "
            "atau pilih paket dengan penyimpanan lebih besar sebelum {date}. Setelah tanggal itu, "
            "file "
            "terbaru yang melebihi batas akan dihapus."
        ),
        "button": "Buka file saya",
        "note": "Tim dukungan dapat memulihkan file yang dihapus selama 7 hari.",
    },
}

STORAGE_OVER_LIMIT: Final = EmailTemplate(key=STORAGE_OVER_LIMIT_KEY, body=BODY, texts=_TEXTS)
