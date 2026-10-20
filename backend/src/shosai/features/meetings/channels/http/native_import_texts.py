"""What a failed import's job says, in the 16 platform languages (user-facing, not a prompt).

The shipped clients show the job's `error` as it is, so the server words it in the person's
language: one sentence per failure code the person can act on, and one for the rest.
"""

from typing import Final

from shosai.core.i18n.locales import normalize_language

DEFAULT_LANGUAGE: Final = "en"
OTHER_FAILURE: Final = "failed"
FAILURE_TEXTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "failed": "We couldn't process this recording. Please try again.",
        "upload_exceeds_minutes": (
            "This recording is longer than the minutes you have left this month."
        ),
        "recording_too_long": "This recording is longer than 6 hours.",
        "unsupported_audio_format": "This file's format isn't supported.",
        "media_unreadable": "This file couldn't be read. It may be damaged.",
        "consent_required": (
            "Transcribing this recording needs your consent to processing abroad. You can give it "
            "in Settings."
        ),
        "transcript_empty": "No speech was found in this recording.",
    },
    "fr": {
        "failed": "Impossible de traiter cet enregistrement. Veuillez réessayer.",
        "upload_exceeds_minutes": (
            "Cet enregistrement dépasse les minutes qu'il vous reste ce mois-ci."
        ),
        "recording_too_long": "Cet enregistrement dure plus de 6 heures.",
        "unsupported_audio_format": "Le format de ce fichier n'est pas pris en charge.",
        "media_unreadable": "Impossible de lire ce fichier. Il est peut-être endommagé.",
        "consent_required": (
            "La transcription de cet enregistrement nécessite votre consentement au traitement à "
            "l'étranger. Vous pouvez le donner dans les Paramètres."
        ),
        "transcript_empty": "Aucune parole n'a été détectée dans cet enregistrement.",
    },
    "de": {
        "failed": "Diese Aufnahme konnte nicht verarbeitet werden. Bitte versuchen Sie es erneut.",
        "upload_exceeds_minutes": (
            "Diese Aufnahme ist länger als die Minuten, die Ihnen diesen Monat noch bleiben."
        ),
        "recording_too_long": "Diese Aufnahme ist länger als 6 Stunden.",
        "unsupported_audio_format": "Das Format dieser Datei wird nicht unterstützt.",
        "media_unreadable": (
            "Diese Datei konnte nicht gelesen werden. Möglicherweise ist sie beschädigt."
        ),
        "consent_required": (
            "Für die Transkription dieser Aufnahme ist Ihre Einwilligung zur Verarbeitung im "
            "Ausland erforderlich. Sie können sie in den Einstellungen erteilen."
        ),
        "transcript_empty": "In dieser Aufnahme wurde keine Sprache erkannt.",
    },
    "ru": {
        "failed": "Не удалось обработать запись. Попробуйте ещё раз.",
        "upload_exceeds_minutes": "Запись длиннее, чем осталось минут в этом месяце.",
        "recording_too_long": "Запись длиннее 6 часов.",
        "unsupported_audio_format": "Формат этого файла не поддерживается.",
        "media_unreadable": "Не удалось прочитать файл. Возможно, он повреждён.",
        "consent_required": (
            "Для расшифровки записи нужно ваше согласие на обработку за рубежом. Его можно дать в "
            "настройках."
        ),
        "transcript_empty": "В записи не найдено речи.",
    },
    "nl": {
        "failed": "Deze opname kon niet worden verwerkt. Probeer het opnieuw.",
        "upload_exceeds_minutes": (
            "Deze opname is langer dan het aantal minuten dat je deze maand nog hebt."
        ),
        "recording_too_long": "Deze opname is langer dan 6 uur.",
        "unsupported_audio_format": "De indeling van dit bestand wordt niet ondersteund.",
        "media_unreadable": "Dit bestand kon niet worden gelezen. Mogelijk is het beschadigd.",
        "consent_required": (
            "Voor het transcriberen van deze opname is je toestemming voor verwerking in het "
            "buitenland nodig. Je kunt die geven in Instellingen."
        ),
        "transcript_empty": "Er is geen spraak gevonden in deze opname.",
    },
    "it": {
        "failed": "Impossibile elaborare questa registrazione. Riprova.",
        "upload_exceeds_minutes": (
            "Questa registrazione supera i minuti che ti restano questo mese."
        ),
        "recording_too_long": "Questa registrazione dura più di 6 ore.",
        "unsupported_audio_format": "Il formato di questo file non è supportato.",
        "media_unreadable": "Impossibile leggere questo file. Potrebbe essere danneggiato.",
        "consent_required": (
            "Per trascrivere questa registrazione serve il tuo consenso al trattamento all'estero. "
            "Puoi darlo nelle Impostazioni."
        ),
        "transcript_empty": "Nessun parlato rilevato in questa registrazione.",
    },
    "es": {
        "failed": "No se pudo procesar esta grabación. Inténtalo de nuevo.",
        "upload_exceeds_minutes": "Esta grabación dura más que los minutos que te quedan este mes.",
        "recording_too_long": "Esta grabación dura más de 6 horas.",
        "unsupported_audio_format": "El formato de este archivo no es compatible.",
        "media_unreadable": "No se pudo leer este archivo. Puede que esté dañado.",
        "consent_required": (
            "Para transcribir esta grabación se necesita tu consentimiento para el tratamiento en "
            "el extranjero. Puedes darlo en Ajustes."
        ),
        "transcript_empty": "No se detectó voz en esta grabación.",
    },
    "pt-BR": {
        "failed": "Não foi possível processar esta gravação. Tente novamente.",
        "upload_exceeds_minutes": (
            "Esta gravação é mais longa do que os minutos que restam neste mês."
        ),
        "recording_too_long": "Esta gravação tem mais de 6 horas.",
        "unsupported_audio_format": "O formato deste arquivo não é compatível.",
        "media_unreadable": "Não foi possível ler este arquivo. Ele pode estar danificado.",
        "consent_required": (
            "Para transcrever esta gravação, é preciso seu consentimento para o processamento no "
            "exterior. Você pode dá-lo em Configurações."
        ),
        "transcript_empty": "Nenhuma fala foi encontrada nesta gravação.",
    },
    "ar": {
        "failed": "تعذّرت معالجة هذا التسجيل. يُرجى المحاولة مرة أخرى.",
        "upload_exceeds_minutes": "هذا التسجيل أطول من الدقائق المتبقية لك هذا الشهر.",
        "recording_too_long": "هذا التسجيل أطول من 6 ساعات.",
        "unsupported_audio_format": "تنسيق هذا الملف غير مدعوم.",
        "media_unreadable": "تعذّرت قراءة هذا الملف. ربما يكون تالفًا.",
        "consent_required": (
            "يتطلب تفريغ هذا التسجيل موافقتك على المعالجة خارج البلاد. يمكنك منحها من الإعدادات."
        ),
        "transcript_empty": "لم يُعثر على كلام في هذا التسجيل.",
    },
    "tr": {
        "failed": "Bu kayıt işlenemedi. Lütfen tekrar deneyin.",
        "upload_exceeds_minutes": "Bu kayıt, bu ay kalan dakikalarınızdan daha uzun.",
        "recording_too_long": "Bu kayıt 6 saatten uzun.",
        "unsupported_audio_format": "Bu dosyanın biçimi desteklenmiyor.",
        "media_unreadable": "Bu dosya okunamadı. Hasarlı olabilir.",
        "consent_required": (
            "Bu kaydın yazıya dökülmesi için yurt dışında işlemeye onay vermeniz gerekiyor. Onayı "
            "Ayarlar'dan verebilirsiniz."
        ),
        "transcript_empty": "Bu kayıtta konuşma bulunamadı.",
    },
    "ko": {
        "failed": "이 녹음을 처리하지 못했습니다. 다시 시도해 주세요.",
        "upload_exceeds_minutes": "이 녹음은 이번 달 남은 시간(분)보다 깁니다.",
        "recording_too_long": "이 녹음은 6시간을 초과합니다.",
        "unsupported_audio_format": "지원되지 않는 파일 형식입니다.",
        "media_unreadable": "이 파일을 읽을 수 없습니다. 손상되었을 수 있습니다.",
        "consent_required": (
            "이 녹음을 전사하려면 해외 처리에 대한 동의가 필요합니다. 설정에서 동의할 수 있습니다."
        ),
        "transcript_empty": "이 녹음에서 음성을 찾지 못했습니다.",
    },
    "hi": {
        "failed": "यह रिकॉर्डिंग प्रोसेस नहीं हो सकी। कृपया फिर से कोशिश करें।",
        "upload_exceeds_minutes": "यह रिकॉर्डिंग इस महीने आपके बचे हुए मिनटों से लंबी है।",
        "recording_too_long": "यह रिकॉर्डिंग 6 घंटे से लंबी है।",
        "unsupported_audio_format": "इस फ़ाइल का फ़ॉर्मैट समर्थित नहीं है।",
        "media_unreadable": "यह फ़ाइल पढ़ी नहीं जा सकी। हो सकता है कि यह खराब हो।",
        "consent_required": (
            "इस रिकॉर्डिंग को ट्रांसक्राइब करने के लिए विदेश में प्रोसेसिंग पर आपकी सहमति ज़रूरी "
            "है। आप इसे सेटिंग्स में दे सकते हैं।"
        ),
        "transcript_empty": "इस रिकॉर्डिंग में कोई बोली नहीं मिली।",
    },
    "vi": {
        "failed": "Không thể xử lý bản ghi này. Vui lòng thử lại.",
        "upload_exceeds_minutes": "Bản ghi này dài hơn số phút bạn còn lại trong tháng này.",
        "recording_too_long": "Bản ghi này dài hơn 6 giờ.",
        "unsupported_audio_format": "Định dạng của tệp này không được hỗ trợ.",
        "media_unreadable": "Không thể đọc tệp này. Tệp có thể đã bị hỏng.",
        "consent_required": (
            "Để chép lời bản ghi này, bạn cần đồng ý cho xử lý ở nước ngoài. Bạn có thể đồng ý "
            "trong Cài đặt."
        ),
        "transcript_empty": "Không tìm thấy giọng nói trong bản ghi này.",
    },
    "zh-Hant": {
        "failed": "無法處理這段錄音，請再試一次。",
        "upload_exceeds_minutes": "這段錄音的長度超過你本月剩餘的分鐘數。",
        "recording_too_long": "這段錄音超過 6 小時。",
        "unsupported_audio_format": "不支援此檔案的格式。",
        "media_unreadable": "無法讀取此檔案，檔案可能已損毀。",
        "consent_required": "轉錄這段錄音需要你同意在境外處理。你可以在「設定」中同意。",
        "transcript_empty": "這段錄音中沒有偵測到語音。",
    },
    "ja": {
        "failed": "この録音を処理できませんでした。もう一度お試しください。",
        "upload_exceeds_minutes": "この録音は今月の残り時間（分）より長いです。",
        "recording_too_long": "この録音は6時間を超えています。",
        "unsupported_audio_format": "このファイル形式には対応していません。",
        "media_unreadable": "このファイルを読み取れませんでした。破損している可能性があります。",
        "consent_required": (
            "この録音を文字起こしするには、国外での処理への同意が必要です。同意は設定から行えます。"
        ),
        "transcript_empty": "この録音から音声が検出されませんでした。",
    },
    "id": {
        "failed": "Rekaman ini tidak dapat diproses. Silakan coba lagi.",
        "upload_exceeds_minutes": "Rekaman ini lebih panjang dari sisa menit Anda bulan ini.",
        "recording_too_long": "Rekaman ini lebih dari 6 jam.",
        "unsupported_audio_format": "Format file ini tidak didukung.",
        "media_unreadable": "File ini tidak dapat dibaca. Mungkin file rusak.",
        "consent_required": (
            "Untuk mentranskripsi rekaman ini, diperlukan persetujuan Anda atas pemrosesan di luar "
            "negeri. Anda dapat memberikannya di Pengaturan."
        ),
        "transcript_empty": "Tidak ada ucapan yang ditemukan dalam rekaman ini.",
    },
}


def failure_text(code: str | None, language: str | None) -> str:
    """The sentence for a failure code in the person's language, English without one."""
    texts = FAILURE_TEXTS[normalize_language(language) or DEFAULT_LANGUAGE]
    return texts.get(code or OTHER_FAILURE, texts[OTHER_FAILURE])
