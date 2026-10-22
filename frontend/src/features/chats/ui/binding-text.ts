"use client";

import { useTranslations } from "use-intl";

import type { Binding } from "../domain/contract";

/** Привязка словами: «Всё пространство» или «Проект „Запуск“». */
export function useBindingText() {
  const t = useTranslations("chats");
  return (binding: Binding) =>
    binding.kind === "workspace" ? t("binding.workspace") : t("binding.project", { project: binding.project.name });
}
