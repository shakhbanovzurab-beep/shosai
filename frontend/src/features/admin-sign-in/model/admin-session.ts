import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useRouter } from "@/lib/navigation";

import { signInAdmin, signOutAdmin } from "../api/admin-session-api";
import { signInProblem } from "../domain/problems";

/** Войти; null — вошёл, иначе слова о причине отказа для формы. */
export async function signIn(username: string, password: string): Promise<string | null> {
  try {
    await signInAdmin(username, password);
    return null;
  } catch (error) {
    return signInProblem(error);
  }
}

// Адрес входа из сборки; после выхода вкладка уходит туда (сам адрес проверяют маршруты).
const LOGIN_PATH = import.meta.env.VITE_ADMIN_LOGIN_PATH?.trim() || "/";

/**
 * Выход из меню админки: сервер закрывает сессию, вкладка забывает загруженные данные админки и уходит на
 * страницу входа. Если сервер не ответил, сессия могла остаться — администратор узнаёт об этом из сообщения.
 */
export function useAdminSignOut(): () => void {
  const router = useRouter();
  const client = useQueryClient();
  return () => {
    signOutAdmin()
      .then(() => {
        client.removeQueries({ queryKey: ["admin"] });
        router.replace(LOGIN_PATH);
      })
      .catch(() => toast.error("Не удалось выйти", { description: "Сервер не ответил. Попробуйте ещё раз." }));
  };
}
