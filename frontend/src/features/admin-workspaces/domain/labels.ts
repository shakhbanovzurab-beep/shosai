import type { AdminEvent, MemberRole, WorkspaceStatus } from "./contract";

export const STATUS_LABEL: Record<WorkspaceStatus, string> = {
  active: "Активно",
  trialing: "Пробный период",
  past_due: "Просрочена оплата",
  suspended: "Приостановлено",
};

export const STATUS_OPTIONS = (Object.keys(STATUS_LABEL) as WorkspaceStatus[]).map((id) => ({
  id,
  label: STATUS_LABEL[id],
}));

export const ROLE_LABEL: Record<MemberRole, string> = {
  owner: "Владелец",
  admin: "Администратор",
  member: "Участник",
};

export const SHARE_LEVEL_LABEL = {
  private: "Только организатору",
  participants: "Участникам встречи",
  workspace: "Всему пространству",
} as const;

const SETTING_LABEL: Record<string, string> = {
  name: "название",
  join_domain: "домен для входа",
  sharing: "правила доступа к встречам",
};

const settings = (value: string | null) =>
  (value ?? "")
    .split(",")
    .map((key) => SETTING_LABEL[key.trim()] ?? key.trim())
    .filter(Boolean)
    .join(", ");

const roleOf = (value: string | null) => ROLE_LABEL[(value ?? "member") as MemberRole]?.toLowerCase() ?? value;

/** What happened, in one line without the actor: the row shows who and when next to it. */
export function eventText(event: AdminEvent) {
  const { target, value } = event;
  switch (event.action) {
    case "workspace_created":
      return "Пространство создано";
    case "member_invited":
      return `Приглашения отправлены: ${target ?? ""}`;
    case "invitation_revoked":
      return `Приглашение отозвано: ${target ?? ""}`;
    case "role_changed":
      return `Роль изменена: ${target ?? ""} — ${roleOf(value)}`;
    case "member_removed":
      return `Участник удалён: ${target ?? ""}`;
    case "member_left":
      return "Участник вышел из пространства";
    case "settings_changed":
      return `Настройки изменены: ${settings(value)}`;
    case "file_transferred":
      return `Файл передан пространству: ${target ?? ""}`;
    case "seats_changed":
      return `Количество мест: ${value ?? ""}`;
    case "owner_transferred":
      return `Владение передано: ${target ?? ""}`;
    case "suspended":
      return `Доступ приостановлен. Причина: ${value ?? "не указана"}`;
    case "resumed":
      return "Доступ восстановлен";
  }
}
