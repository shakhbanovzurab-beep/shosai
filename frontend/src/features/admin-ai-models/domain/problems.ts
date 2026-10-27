import { ApiError } from "@/lib/api/errors";

/** Слова админки для кодов ошибок studio (ADR 0008): сервер шлёт код, текст — здесь. */
const PROBLEMS: Record<string, string> = {
  model_not_found: "Такой модели нет в каталоге. Обновите страницу.",
  model_already_listed: "Эта модель уже в каталоге.",
  model_not_on_openrouter: "OpenRouter не знает такой модели. Проверьте id — например, anthropic/claude-sonnet-5.",
  model_is_default: "Модель — умолчание или запасная модель роли. Сначала назначьте роли другую.",
  model_enabled: "Включённую модель нельзя убрать из каталога. Сначала выключите её.",
  model_disabled: "Модель выключена: умолчанием роли может быть только включённая модель.",
  default_not_standard: "Умолчание роли — только стандартная модель: frontier доступен не всем тарифам.",
  model_cant_do_role: "Модель не умеет того, что нужно роли (например, читать картинки).",
  fallback_same_as_default: "Запасная модель должна отличаться от модели по умолчанию.",
  no_tier_proposal: "Предложения уровня уже нет. Обновите страницу.",
  openrouter_unreachable: "OpenRouter сейчас не отвечает. Попробуйте позже.",
  management_key_missing: "Ключ управления OPENROUTER_MANAGEMENT_KEY не задан: баланс и проверка недоступны.",
  admin_sign_in_required: "Сессия администратора закончилась. Войдите снова.",
};

/** Текст кода, если админка его знает. */
export function problemText(code: string | null | undefined): string | null {
  return code ? (PROBLEMS[code] ?? null) : null;
}

/** Описание ошибки строкой — для подписи в форме. */
export function problemMessage(error: unknown): string {
  if (error instanceof ApiError) return problemText(error.code) ?? error.message;
  return error instanceof Error ? error.message : "Не удалось выполнить действие.";
}
