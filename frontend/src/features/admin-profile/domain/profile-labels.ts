import type { ProfileDocument, ProfileRecord } from "./profile";

export const engagementStatusLabels: Record<ProfileRecord["engagementStatus"], string> = {
  Active: "Активен",
};

export const documentStatusLabels: Record<ProfileDocument["status"], string> = {
  Signed: "Подписан",
  Current: "Действует",
};
