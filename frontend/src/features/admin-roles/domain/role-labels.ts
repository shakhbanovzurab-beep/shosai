import type { Role } from "./role";

export const roleGroupLabels: Record<string, string> = {
  "Needs review": "Требуют проверки",
  "System roles": "Системные роли",
  "Custom roles": "Пользовательские роли",
};

export const roleStatusLabels: Record<Role["status"], string> = {
  Active: "Активна",
  "Needs review": "Требует проверки",
};

export const roleOwnerLabels: Record<string, string> = {
  System: "Система",
};

const lastReviewFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
  year: "numeric",
});

export function formatLastReview(value: string) {
  const date = new Date(`${value}T00:00:00Z`);

  return Number.isNaN(date.getTime()) ? value : lastReviewFormatter.format(date);
}
