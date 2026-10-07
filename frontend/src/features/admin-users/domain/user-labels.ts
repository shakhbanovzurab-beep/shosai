import type { UserStatus, UserTeam } from "./user";

export const ALL_FILTER_VALUE = "All";

export const roleLabels: Record<string, string> = {
  "Workspace Owner": "Владелец пространства",
  Admin: "Администратор",
  "Billing Admin": "Администратор биллинга",
  "Security Admin": "Администратор безопасности",
  "Team Lead": "Руководитель команды",
  Contributor: "Участник",
  Guest: "Гость",
  "Read-only": "Только чтение",
};

export const teamLabels: Record<UserTeam, string> = {
  Platform: "Платформа",
  Growth: "Рост",
  Revenue: "Выручка",
  "Customer Ops": "Клиентский сервис",
  "Internal Tools": "Внутренние инструменты",
  Compliance: "Комплаенс",
  "People Ops": "HR",
  Finance: "Финансы",
};

export const statusLabels: Record<UserStatus, string> = {
  Active: "Активен",
  "Pending invite": "Приглашение отправлено",
  Deactivated: "Деактивирован",
  Locked: "Заблокирован",
  Suspended: "Приостановлен",
};

const filterOptionLabels: Record<string, string> = {
  ...roleLabels,
  ...teamLabels,
  ...statusLabels,
  [ALL_FILTER_VALUE]: "Все",
};

export function getFilterOptionLabel(value: string) {
  return filterOptionLabels[value] ?? value;
}
