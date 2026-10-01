// Нормализация записанной фикстуры: всё, что API черновика генерирует заново при
// каждом запросе, заменяется стабильным значением. Цель — две записи одного
// визита совпадают побайтно, а эталон не меняется от того, в какой день записан.
//
// Правила:
//  * JWT и поля токенов → постоянные строки (заодно в фикстурах нет ничего,
//    похожего на настоящий токен);
//  * UUID → заглушки по порядку первого появления в отсортированной фикстуре,
//    одинаково везде — в телах, путях и строках запроса;
//  * метки времени в пределах суток после момента стенда сравнения — это «сейчас» API
//    под libfaketime, которое сдвигается на секунды записи → сам момент, в том
//    же формате. Засев задаёт прошлое и будущее явно и вне этого окна.

import type { Exchange, Fixture, JsonValue } from "../fixtures/format.ts";

const JWT = /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g;
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const ISO_DATETIME = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?/g;
const DAY_MS = 24 * 60 * 60 * 1000;

/** Поля, значение которых выдаётся заново на каждый вход или запрос, где бы они
 *  ни встретились. Имена однозначные: `code` сюда не входит — это и код тарифа. */
const VOLATILE_FIELDS: ReadonlySet<string> = new Set([
  "access_token",
  "refresh_token",
  "csrf_token",
  "csrfToken",
  "request_id",
]);

/** Случайные значения конкретных ответов: «метод путь» → поля верхнего уровня. */
const VOLATILE_RESPONSE_FIELDS: ReadonlyMap<string, readonly string[]> = new Map([
  // Одноразовый код входа десктопа (scheme whisperer://auth?code=…).
  ["POST /v1/auth/desktop/code", ["code"]],
  // PKCE входа через VK ID: свежие state и code_verifier на каждый показ кнопки.
  ["GET /v1/auth/social/vk/prepare", ["state", "code_verifier"]],
]);

class Normalizer {
  private readonly uuids = new Map<string, string>();
  private readonly clock: Date;

  constructor(clock: Date) {
    this.clock = clock;
  }

  string(value: string): string {
    return value
      .replace(JWT, "parity.jwt.token")
      .replace(UUID, (uuid) => this.uuid(uuid.toLowerCase()))
      .replace(ISO_DATETIME, (stamp, fraction: string | undefined, zone: string | undefined) =>
        this.timestamp(stamp, fraction, zone),
      );
  }

  json(value: JsonValue): JsonValue {
    if (typeof value === "string") return this.string(value);
    if (Array.isArray(value)) return value.map((item) => this.json(item));
    if (value === null || typeof value !== "object") return value;
    const result: { [key: string]: JsonValue } = {};
    for (const [key, item] of Object.entries(value)) {
      result[key] = VOLATILE_FIELDS.has(key) && typeof item === "string" ? `parity-${key}` : this.json(item);
    }
    return result;
  }

  private uuid(original: string): string {
    const known = this.uuids.get(original);
    if (known !== undefined) return known;
    const placeholder = `00000000-0000-4000-8000-${String(this.uuids.size + 1).padStart(12, "0")}`;
    this.uuids.set(original, placeholder);
    return placeholder;
  }

  private timestamp(stamp: string, fraction: string | undefined, zone: string | undefined): string {
    const moment = new Date(zone === undefined ? `${stamp}Z` : stamp).getTime();
    const offset = moment - this.clock.getTime();
    if (Number.isNaN(moment) || offset < 0 || offset >= DAY_MS) return stamp;
    // Формат сохраняется: число знаков дробной части и запись пояса как в оригинале.
    const base = this.clock.toISOString().slice(0, 19);
    const digits = fraction === undefined ? "" : `.${"0".repeat(fraction.length - 1)}`;
    return `${base}${digits}${zone ?? ""}`;
  }
}

function withoutVolatileFields(exchange: Exchange): JsonValue {
  const fields = VOLATILE_RESPONSE_FIELDS.get(`${exchange.method} ${exchange.path}`);
  const body = exchange.body;
  if (fields === undefined || body === null || typeof body !== "object" || Array.isArray(body)) return body;
  const result: { [key: string]: JsonValue } = { ...body };
  for (const field of fields) {
    if (field in result) result[field] = `parity-${field}`;
  }
  return result;
}

function normalizeExchange(normalizer: Normalizer, exchange: Exchange): Exchange {
  return {
    ...exchange,
    path: normalizer.string(exchange.path),
    query: normalizer.string(exchange.query),
    ...(exchange.requestBody === undefined ? {} : { requestBody: normalizer.json(exchange.requestBody) }),
    body: normalizer.json(withoutVolatileFields(exchange)),
  };
}

/** Нормализует фикстуру; обмены должны быть уже отсортированы. */
export function normalizeFixture(fixture: Fixture, clock: Date): Fixture {
  const normalizer = new Normalizer(clock);
  const storage: Record<string, string> = {};
  for (const [key, value] of Object.entries(fixture.storage)) {
    // В localStorage лежат и JSON (wh-auth), и простые строки (wh.theme).
    storage[key] = value.startsWith("{")
      ? JSON.stringify(normalizer.json(JSON.parse(value) as JsonValue))
      : normalizer.string(value);
  }
  return {
    ...fixture,
    storage,
    exchanges: fixture.exchanges.map((exchange) => normalizeExchange(normalizer, exchange)),
  };
}
