import type { ConversationPriority, ConversationStatus, StatusFilter, SupportChannel, SupportPlan } from "./contract";

/* Russian labels shared by the admin support screen and the demo store's system events. */

export const STATUS_LABELS: Record<ConversationStatus, string> = {
  open: "Открыт",
  pending: "Ожидает",
  resolved: "Решён",
};

export const FILTER_LABELS: Record<StatusFilter, string> = {
  open: "Открытые",
  pending: "Ожидают ответа",
  resolved: "Решённые",
  all: "Все",
};

export const PRIORITY_LABELS: Record<ConversationPriority, string> = {
  low: "Низкий",
  normal: "Обычный",
  high: "Высокий",
  urgent: "Срочный",
};

export const CHANNEL_LABELS: Record<SupportChannel, string> = {
  web: "Веб",
  macos: "macOS",
  windows: "Windows",
};

export const PLAN_LABELS: Record<SupportPlan, string> = {
  free: "Free",
  pro: "Pro",
  team: "Team",
  enterprise: "Enterprise",
};
