"""How the cards of Leo's file writes read, in the 16 platform languages (ADR 0068; agent 9b).

Each preview key the files tools return is worded here beside their specs: the title says the
change with the file's or folder's name in the language's quotation marks — the root is the
cabinet's "My files" — and a Leo-use card says whether it is a file or a folder.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized, PreviewField, PreviewWording

NBSP: Final = " "
KIND: Final[Localized] = {
    "en": "Type", "fr": "Type", "de": "Typ", "ru": "Тип", "nl": "Type", "it": "Tipo",
    "es": "Tipo", "pt-BR": "Tipo", "ar": "النوع", "tr": "Tür", "ko": "유형", "hi": "प्रकार",
    "vi": "Loại", "zh-Hant": "類型", "ja": "種類", "id": "Jenis",
}  # fmt: skip
KINDS: Final[dict[str, Localized]] = {
    "file": {
        "en": "File", "fr": "Fichier", "de": "Datei", "ru": "Файл", "nl": "Bestand",
        "it": "File", "es": "Archivo", "pt-BR": "Arquivo", "ar": "ملف", "tr": "Dosya",
        "ko": "파일", "hi": "फ़ाइल", "vi": "Tệp", "zh-Hant": "檔案", "ja": "ファイル",
        "id": "File",
    },
    "folder": {
        "en": "Folder", "fr": "Dossier", "de": "Ordner", "ru": "Папка", "nl": "Map",
        "it": "Cartella", "es": "Carpeta", "pt-BR": "Pasta", "ar": "مجلد", "tr": "Klasör",
        "ko": "폴더", "hi": "फ़ोल्डर", "vi": "Thư mục", "zh-Hant": "資料夾", "ja": "フォルダ",
        "id": "Folder",
    },
}  # fmt: skip


def titled(template: Localized) -> Localized:
    """A title with French's no-break spaces inside its guillemets."""
    french = template["fr"].replace("« ", f"«{NBSP}").replace(" »", f"{NBSP}»")
    return {**template, "fr": french}


LEO_USE_ON: Final = PreviewWording(
    key="agent.files.leo_use_on",
    params=("name", "target"),
    title=titled({
        "en": "Let Leo use “{name}”", "fr": "Laisser Leo utiliser « {name} »",
        "de": "Leo „{name}“ nutzen lassen", "ru": "Разрешить Leo использовать «{name}»",
        "nl": "Leo ‘{name}’ laten gebruiken", "it": "Lascia che Leo usi «{name}»",
        "es": "Dejar que Leo use «{name}»", "pt-BR": "Deixar o Leo usar “{name}”",
        "ar": "السماح لـ Leo باستخدام «{name}»",
        "tr": "Leo’nun “{name}” öğesini kullanmasına izin ver",
        "ko": "Leo가 “{name}”을(를) 사용하도록 허용", "hi": "Leo को “{name}” इस्तेमाल करने दें",
        "vi": "Cho Leo dùng “{name}”", "zh-Hant": "讓 Leo 使用「{name}」",
        "ja": "Leo に「{name}」を使わせる", "id": "Izinkan Leo menggunakan “{name}”",
    }),
    fields=(PreviewField("target", KIND, KINDS),),
)  # fmt: skip
LEO_USE_OFF: Final = PreviewWording(
    key="agent.files.leo_use_off",
    params=("name", "target"),
    title=titled({
        "en": "Stop Leo using “{name}”", "fr": "Ne plus laisser Leo utiliser « {name} »",
        "de": "Leo „{name}“ nicht mehr nutzen lassen", "ru": "Запретить Leo использовать «{name}»",
        "nl": "Leo ‘{name}’ niet meer laten gebruiken", "it": "Non far più usare «{name}» a Leo",
        "es": "Dejar de permitir que Leo use «{name}»",
        "pt-BR": "Não deixar mais o Leo usar “{name}”", "ar": "إيقاف استخدام Leo لـ «{name}»",
        "tr": "Leo’nun “{name}” öğesini kullanmasını durdur",
        "ko": "Leo가 “{name}”을(를) 사용하지 않도록 설정",
        "hi": "Leo से “{name}” का इस्तेमाल बंद कराएँ", "vi": "Ngừng cho Leo dùng “{name}”",
        "zh-Hant": "停止讓 Leo 使用「{name}」", "ja": "Leo による「{name}」の使用を停止",
        "id": "Hentikan Leo menggunakan “{name}”",
    }),
    fields=(PreviewField("target", KIND, KINDS),),
)  # fmt: skip
MOVE: Final = PreviewWording(
    key="agent.files.move",
    params=("name", "folder"),
    title=titled({
        "en": "Move “{name}” to the folder “{folder}”",
        "fr": "Déplacer « {name} » dans le dossier « {folder} »",
        "de": "„{name}“ in den Ordner „{folder}“ verschieben",
        "ru": "Переместить «{name}» в папку «{folder}»",
        "nl": "‘{name}’ naar de map ‘{folder}’ verplaatsen",
        "it": "Sposta «{name}» nella cartella «{folder}»",
        "es": "Mover «{name}» a la carpeta «{folder}»",
        "pt-BR": "Mover “{name}” para a pasta “{folder}”",
        "ar": "نقل «{name}» إلى المجلد «{folder}»",
        "tr": "“{name}” öğesini “{folder}” klasörüne taşı",
        "ko": "“{name}”을(를) “{folder}” 폴더로 이동",
        "hi": "“{name}” को फ़ोल्डर “{folder}” में ले जाएँ",
        "vi": "Chuyển “{name}” vào thư mục “{folder}”",
        "zh-Hant": "將「{name}」移至資料夾「{folder}」",
        "ja": "「{name}」をフォルダ「{folder}」に移動",
        "id": "Pindahkan “{name}” ke folder “{folder}”",
    }),
)  # fmt: skip
MOVE_TO_ROOT: Final = PreviewWording(
    key="agent.files.move_to_root",
    params=("name",),
    title=titled({
        "en": "Move “{name}” to My files", "fr": "Déplacer « {name} » dans Mes fichiers",
        "de": "„{name}“ nach Meine Dateien verschieben", "ru": "Переместить «{name}» в «Мои файлы»",
        "nl": "‘{name}’ naar Mijn bestanden verplaatsen", "it": "Sposta «{name}» in I miei file",
        "es": "Mover «{name}» a Mis archivos", "pt-BR": "Mover “{name}” para Meus arquivos",
        "ar": "نقل «{name}» إلى ملفاتي", "tr": "“{name}” öğesini Dosyalarım’a taşı",
        "ko": "“{name}”을(를) 내 파일로 이동", "hi": "“{name}” को मेरी फ़ाइलें में ले जाएँ",
        "vi": "Chuyển “{name}” vào Tệp của tôi", "zh-Hant": "將「{name}」移至我的檔案",
        "ja": "「{name}」をマイファイルに移動", "id": "Pindahkan “{name}” ke File saya",
    }),
)  # fmt: skip
DELETE: Final = PreviewWording(
    key="agent.files.delete",
    params=("name",),
    title=titled({
        "en": "Delete the file “{name}”", "fr": "Supprimer le fichier « {name} »",
        "de": "Datei „{name}“ löschen", "ru": "Удалить файл «{name}»",
        "nl": "Bestand ‘{name}’ verwijderen", "it": "Elimina il file «{name}»",
        "es": "Eliminar el archivo «{name}»", "pt-BR": "Excluir o arquivo “{name}”",
        "ar": "حذف الملف «{name}»", "tr": "“{name}” dosyasını sil", "ko": "“{name}” 파일 삭제",
        "hi": "फ़ाइल “{name}” मिटाएँ", "vi": "Xóa tệp “{name}”", "zh-Hant": "刪除檔案「{name}」",
        "ja": "ファイル「{name}」を削除", "id": "Hapus file “{name}”",
    }),
)  # fmt: skip
