import type { AccountState } from "../domain/contract";

/* Слова админки (только русский): состояния аккаунта, дома, исходы входов и причины действий. */

export const STATE_LABEL: Record<AccountState, string> = {
  active: "Активен",
  frozen: "Заблокирован",
  banned: "Закрыт навсегда",
  deletion_scheduled: "Удаление запланировано",
  deleting: "Удаляется",
  transferring: "Переносится",
  deleted: "Удалён",
};

const HOME_LABEL: Record<string, string> = { ru: "Россия", eu: "ЕС" };
export const homeLabel = (home: string) => HOME_LABEL[home] ?? home.toUpperCase();

const OUTCOME_LABEL: Record<string, string> = {
  success: "Успешно",
  wrong_password: "Неверный пароль",
  account_frozen: "Аккаунт заблокирован",
  account_banned: "Аккаунт закрыт",
};
export const outcomeLabel = (outcome: string) => OUTCOME_LABEL[outcome] ?? outcome;

const CLIENT_LABEL: Record<string, string> = { web: "Браузер", desktop: "Приложение" };
export const clientLabel = (kind: string) => CLIENT_LABEL[kind] ?? kind;

export interface Reason {
  code: string;
  label: string;
}

// Причина уходит в журнал аудита кодом (`^[a-z0-9_.:-]{1,64}$`), не текстом: в журнале нет личных данных.
export const BLOCK_REASONS: readonly Reason[] = [
  { code: "abuse", label: "Нарушение правил" },
  { code: "spam", label: "Спам" },
  { code: "fraud", label: "Мошенничество" },
  { code: "security", label: "Угроза безопасности аккаунта" },
  { code: "legal_request", label: "Требование закона" },
  { code: "owner_request", label: "Просьба владельца аккаунта" },
  { code: "other", label: "Другое" },
];

export const UNBLOCK_REASONS: readonly Reason[] = [
  { code: "resolved", label: "Вопрос решён" },
  { code: "appeal_accepted", label: "Обжалование принято" },
  { code: "blocked_by_mistake", label: "Заблокирован по ошибке" },
  { code: "owner_request", label: "Просьба владельца аккаунта" },
  { code: "other", label: "Другое" },
];
