/** Согласия, которые человек отмечает при регистрации (почтой или первым входом через сервис). */
export interface Consents {
  personalData: boolean;
  crossBorder: boolean;
  marketing: boolean;
}

export const NO_CONSENTS: Consents = { personalData: false, crossBorder: false, marketing: false };

/** Согласия, без которых сервер аккаунт не заведёт; `crossBorder` — спрашивается ли трансграничная передача. */
export function consentsComplete(consents: Consents, crossBorder: boolean): boolean {
  return consents.personalData && (!crossBorder || consents.crossBorder);
}

/** Согласия в виде запроса: трансграничная передача уходит, только если её спрашивали. */
export function consentsBody(consents: Consents, crossBorder: boolean) {
  return {
    personal_data: consents.personalData,
    cross_border: crossBorder && consents.crossBorder,
    marketing: consents.marketing,
  };
}
