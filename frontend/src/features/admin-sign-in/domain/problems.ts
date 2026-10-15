import { ApiError } from "@/lib/api/errors";

/** Почему вход в админку не удался, словами для администратора (админка — только на русском). */
export function signInProblem(error: unknown): string {
  if (!(error instanceof ApiError)) return "Нет связи с сервером. Проверьте подключение и попробуйте ещё раз.";
  switch (error.code) {
    case "invalid_credentials":
      return "Неверный логин или пароль.";
    case "rate_limited": {
      const seconds = Number(error.params.retry_after_seconds ?? 60);
      return `Слишком много попыток. Повторите через ${Math.max(1, Math.ceil(seconds / 60))} мин.`;
    }
    case "admin_sign_in_disabled":
      return "Вход закрыт: на сервере не заданы логин и пароль администратора.";
    case "admin_unavailable":
      return "Сервис входа временно недоступен. Попробуйте позже.";
    default:
      return error.requestId ? `Не удалось войти. Номер запроса: ${error.requestId}.` : "Не удалось войти.";
  }
}
