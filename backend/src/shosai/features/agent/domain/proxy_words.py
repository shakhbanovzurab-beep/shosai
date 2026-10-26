"""What a shipped client shows when the proxy's answer breaks off, in the person's language.

The macOS and Windows apps show the error chunk's text in their panel and keep it in the
conversation they send next, so it says only that the answer stopped — no internal code, in
the cabinet's register for the same failure. A language the platform does not have reads in
English.
"""

from collections.abc import Mapping
from typing import Final

ANSWER_STOPPED: Final[Mapping[str, str]] = {
    "en": "The answer was interrupted. Try again.",
    "fr": "La réponse a été interrompue. Réessayez.",
    "de": "Die Antwort wurde unterbrochen. Versuche es erneut.",
    "ru": "Ответ прервался. Попробуйте снова.",
    "nl": "Het antwoord is onderbroken. Probeer het opnieuw.",
    "it": "La risposta si è interrotta. Riprova.",
    "es": "La respuesta se interrumpió. Inténtalo de nuevo.",
    "pt-BR": "A resposta foi interrompida. Tente novamente.",
    "ar": "انقطعت الإجابة. يرجى إعادة المحاولة.",
    "tr": "Yanıt yarıda kesildi. Tekrar deneyin.",
    "ko": "답변이 중단되었습니다. 다시 시도하세요.",
    "hi": "जवाब बीच में रुक गया। फिर से कोशिश करें।",
    "vi": "Câu trả lời bị gián đoạn. Hãy thử lại.",
    "zh-Hant": "回答中斷了，請再試一次。",
    "ja": "回答が中断されました。もう一度お試しください。",
    "id": "Jawaban terputus. Coba lagi.",
}
FALLBACK_LANGUAGE: Final = "en"


def answer_stopped(language: str) -> str:
    """The error chunk's text: on its own line, in brackets, as the draft's clients show it."""
    words = ANSWER_STOPPED.get(language, ANSWER_STOPPED[FALLBACK_LANGUAGE])
    return f"\n[{words}]"
