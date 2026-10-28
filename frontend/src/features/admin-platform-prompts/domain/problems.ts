import { FEATURES, type PlatformConfig } from "./contract";
import { cleaned, type Problem } from "./platform-layer";

const tokensFormat = new Intl.NumberFormat("ru-RU");

/*
 * Поле ошибки указывает в опубликованную (очищенную) конфигурацию: пустые правила и повторы тем в ней уже убраны.
 * Номер правила здесь — тот, что видит админ в списке.
 */
function placeOf(field: unknown, config: PlatformConfig): string {
  if (field === "system_prompt") return "системный промт";
  if (field === "layer") return "слой платформы (промт, правила и темы вместе)";
  const [section, part, index] = String(field).split(".");
  if (section === "safety" && part === "rules") {
    const rule = cleaned(config).safety.rules[Number(index)];
    const position = config.safety.rules.findIndex((item) => item.id === rule?.id);
    return position < 0 ? "правило" : `правило ${position + 1}`;
  }
  if (section === "safety" && part === "blocked_topics") {
    const topic = cleaned(config).safety.blocked_topics[Number(index)];
    return topic ? `тему «${topic}»` : "запрещённую тему";
  }
  const feature = FEATURES.find((item) => item.id === part);
  return feature ? `промт функции «${feature.label}»` : "поле";
}

const capitalized = (text: string) => text.charAt(0).toLocaleUpperCase("ru-RU") + text.slice(1);

const FIXED: Record<string, string> = {
  nothing_to_publish: "Черновик совпадает с действующей версией — публиковать нечего.",
  version_not_found: "Такой версии нет. Обновите страницу.",
  invalid_cursor: "Список версий устарел. Обновите страницу.",
  idempotency_key_reused: "Этот запрос уже выполнен с другими данными. Повторите действие.",
  admin_sign_in_required: "Сессия администратора закончилась. Войдите снова.",
};

/** Слова админки для кода ошибки studio (ADR 0008) с его параметрами; null — кода админка не знает. */
export function problemText(problem: Problem, config: PlatformConfig): string | null {
  const { code, params } = problem;
  if (code === "platform_prompt_not_english") {
    return `Модель читает только английский текст — перепишите по-английски ${placeOf(params.field, config)}.`;
  }
  if (code === "platform_layer_over_budget") {
    const tokens = tokensFormat.format(Number(params.tokens));
    const max = tokensFormat.format(Number(params.max));
    return `${capitalized(placeOf(params.field, config))} — ≈${tokens} токенов при лимите ${max}. Сократите текст.`;
  }
  return FIXED[code] ?? null;
}
