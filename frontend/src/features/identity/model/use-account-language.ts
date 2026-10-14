import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { useSwitchLanguage } from "@/hooks/use-switch-language";
import { isLanguageCode } from "@/lib/language";

import { saveLanguage } from "../api/session-api";

/**
 * Язык интерфейса, который следует за аккаунтом: выбор сразу меняет страницу (cookie `ui_language`) и
 * сохраняется в профиле, чтобы письма и другие устройства говорили на нём же. Сбой сохранения не откатывает
 * выбор на этом устройстве — человек узнаёт о нём из сообщения.
 */
export function useAccountLanguage() {
  const t = useTranslations("identity");
  const { language, switchLanguage } = useSwitchLanguage();

  const chooseLanguage = (code: string) => {
    if (!isLanguageCode(code)) return;
    switchLanguage(code);
    saveLanguage(code).catch(() => toast.error(t("session.languageNotSaved")));
  };

  return { language, switchLanguage: chooseLanguage };
}
