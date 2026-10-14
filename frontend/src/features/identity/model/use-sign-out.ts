import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { signOut } from "./session";

/**
 * Выход из меню. Вкладка забывает сессию в любом случае, и наблюдатель сессии уводит на вход; если сервер
 * не подтвердил выход (нет сети), человек узнаёт об этом из сообщения.
 */
export function useSignOut(): () => void {
  const t = useTranslations("identity");
  return () => {
    signOut().catch(() => toast.error(t("session.signOutUnconfirmed")));
  };
}
