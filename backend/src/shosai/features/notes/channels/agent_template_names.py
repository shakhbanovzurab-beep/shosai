"""The names of the shipped note templates on a card, in the 16 platform languages (agent 9b).

A card that rewrites a meeting's notes by a shipped template names it as the cabinet's template
gallery does; the words are the gallery's, by the template's id. A template the person made is
named by its own name and needs no words.
"""

from typing import Final

from shosai.core.agent_tools.previews import Localized

ENHANCED: Final[Localized] = {
    "en": "Enhanced notes", "fr": "Notes enrichies", "de": "Aufbereitete Notizen",
    "ru": "Улучшенные заметки", "nl": "Verrijkte notities", "it": "Note migliorate",
    "es": "Notas mejoradas", "pt-BR": "Notas aprimoradas", "ar": "ملاحظات محسنة",
    "tr": "Geliştirilmiş notlar", "ko": "AI 노트", "hi": "बेहतर नोट", "vi": "Ghi chú nâng cao",
    "zh-Hant": "強化版筆記", "ja": "AI 版ノート", "id": "Catatan yang disempurnakan",
}  # fmt: skip
CATCH_UP_INVESTOR: Final[Localized] = {
    "en": "Catch-up: investor", "fr": "Point : investisseur", "de": "Austausch: Investor",
    "ru": "Встреча с инвестором", "nl": "Bijpraten: investeerder",
    "it": "Aggiornamento: investitore", "es": "Puesta al día: inversor",
    "pt-BR": "Acompanhamento: investidor", "ar": "متابعة: مستثمر", "tr": "Görüşme: yatırımcı",
    "ko": "근황 공유: 투자자", "hi": "अपडेट: निवेशक", "vi": "Cập nhật: nhà đầu tư",
    "zh-Hant": "近況更新：投資人", "ja": "近況報告：投資家", "id": "Kabar terkini: investor",
}  # fmt: skip
CATCH_UP_PORTFOLIO: Final[Localized] = {
    "en": "Catch-up: portfolio company", "fr": "Point : société du portefeuille",
    "de": "Austausch: Portfoliounternehmen", "ru": "Встреча с портфельной компанией",
    "nl": "Bijpraten: portfoliobedrijf", "it": "Aggiornamento: società in portafoglio",
    "es": "Puesta al día: empresa en cartera", "pt-BR": "Acompanhamento: empresa do portfólio",
    "ar": "متابعة: شركة من المحفظة", "tr": "Görüşme: portföy şirketi",
    "ko": "근황 공유: 포트폴리오 기업",
    "hi": "अपडेट: पोर्टफ़ोलियो कंपनी", "vi": "Cập nhật: công ty trong danh mục",
    "zh-Hant": "近況更新：投資組合公司", "ja": "近況報告：投資先企業",
    "id": "Kabar terkini: perusahaan portofolio",
}  # fmt: skip
LP_PROSPECTIVE: Final[Localized] = {
    "en": "LP: prospective", "fr": "LP : prospect", "de": "LP: Interessent",
    "ru": "LP: потенциальный инвестор", "nl": "LP: kennismaking", "it": "LP: potenziale",
    "es": "LP: potencial", "pt-BR": "LP: em prospecção", "ar": "شريك محدود محتمل",
    "tr": "LP: potansiyel", "ko": "LP: 잠재 출자자", "hi": "LP: संभावित", "vi": "LP: tiềm năng",
    "zh-Hant": "LP：潛在投資人", "ja": "LP：出資候補", "id": "LP: calon mitra",
}  # fmt: skip
VC_BOARD: Final[Localized] = {
    "en": "VC: Board meeting", "fr": "VC : conseil d’administration", "de": "VC: Board-Meeting",
    "ru": "VC: совет директоров", "nl": "VC: bestuursvergadering",
    "it": "VC: consiglio di amministrazione", "es": "VC: reunión del consejo",
    "pt-BR": "VC: reunião do conselho", "ar": "استثمار جريء: اجتماع مجلس الإدارة",
    "tr": "VC: Yönetim kurulu toplantısı", "ko": "VC: 이사회", "hi": "VC: बोर्ड मीटिंग",
    "vi": "VC: Họp hội đồng quản trị", "zh-Hant": "VC：董事會", "ja": "VC：取締役会",
    "id": "VC: Rapat dewan",
}  # fmt: skip
VC_PITCH: Final[Localized] = {
    "en": "VC: Pitch", "fr": "VC : pitch", "de": "VC: Gründer-Pitch", "ru": "VC: питч",
    "nl": "VC: pitch", "it": "VC: pitch", "es": "VC: presentación", "pt-BR": "VC: pitch",
    "ar": "استثمار جريء: عرض تقديمي", "tr": "VC: Sunum", "ko": "VC: 피칭", "hi": "VC: पिच",
    "vi": "VC: Gọi vốn", "zh-Hant": "VC：提案簡報", "ja": "VC：ピッチ", "id": "VC: Sesi pitch",
}  # fmt: skip
ONE_ON_ONE: Final[Localized] = {
    "en": "1:1", "fr": "Entretien individuel", "de": "1:1", "ru": "1:1", "nl": "1:1",
    "it": "1:1", "es": "1:1", "pt-BR": "1:1", "ar": "اجتماع فردي", "tr": "Birebir",
    "ko": "1:1 면담", "hi": "1:1", "vi": "Họp 1:1", "zh-Hant": "一對一", "ja": "1on1", "id": "1:1",
}  # fmt: skip
CUSTOMER_CALL: Final[Localized] = {
    "en": "Customer call", "fr": "Appel client", "de": "Kundengespräch",
    "ru": "Звонок с клиентом", "nl": "Klantgesprek", "it": "Chiamata con un cliente",
    "es": "Llamada con cliente", "pt-BR": "Reunião com cliente", "ar": "مكالمة عميل",
    "tr": "Müşteri görüşmesi", "ko": "고객 통화", "hi": "ग्राहक से कॉल",
    "vi": "Cuộc gọi khách hàng", "zh-Hant": "客戶通話", "ja": "顧客との通話",
    "id": "Panggilan pelanggan",
}  # fmt: skip
TEAM_SYNC: Final[Localized] = {
    "en": "Team sync", "fr": "Point d’équipe", "de": "Team-Abstimmung", "ru": "Встреча команды",
    "nl": "Teamoverleg", "it": "Allineamento del team", "es": "Reunión de equipo",
    "pt-BR": "Alinhamento da equipe", "ar": "اجتماع الفريق", "tr": "Ekip toplantısı",
    "ko": "팀 정기 회의", "hi": "टीम सिंक", "vi": "Họp nhóm", "zh-Hant": "團隊同步",
    "ja": "チーム定例",
    "id": "Sinkronisasi tim",
}  # fmt: skip
# Имена шаблонов по ид, который кладёт превью; ид — коды галереи кабинета.
SHIPPED_TEMPLATES: Final[dict[str, Localized]] = {
    "enhanced": ENHANCED,
    "catchUpInvestor": CATCH_UP_INVESTOR,
    "catchUpPortfolio": CATCH_UP_PORTFOLIO,
    "lpProspective": LP_PROSPECTIVE,
    "vcBoardMeeting": VC_BOARD,
    "vcPitch": VC_PITCH,
    "oneOnOne": ONE_ON_ONE,
    "customerCall": CUSTOMER_CALL,
    "teamSync": TEAM_SYNC,
}
