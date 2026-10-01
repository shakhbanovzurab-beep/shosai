// Строгое воспроизведение фикстуры: фронтенд получает от /v1 ровно записанные
// ответы черновика.
//
// Запрос сопоставляется по ключу: метод, путь и строка запроса. Повторы одного
// ключа получают записанные ответы по очереди, последний повторяется (так
// работают опросы раз в 15 с). Переопределение состояния заменяет ответы пути.
// Запрос без ответа — ошибка состояния: он попадает в `unmatched`, и тест
// падает со списком. Черновик-инструмент отвечал на такие запросы `[]`, и
// сломанный экран выглядел «чистым».

import type { Route } from "@playwright/test";

import { canonicalQuery, exchangeKey, type Exchange, type Fixture, type JsonValue } from "../fixtures/format.ts";
import type { Override, OverrideMerge, OverrideReply, OverrideResponse } from "../states/types.ts";
import { BACKGROUND } from "./background.ts";
import { matchesTemplate } from "./path-template.ts";

interface Reply {
  readonly status: number;
  readonly contentType: string;
  readonly body: Buffer;
}

function exchangeReply(exchange: Exchange): Reply {
  const { status, contentType, body } = exchange;
  if (body === null) return { status, contentType, body: Buffer.alloc(0) };
  if (exchange.bodyEncoding === "base64" && typeof body === "string") {
    return { status, contentType, body: Buffer.from(body, "base64") };
  }
  const text = contentType.includes("json") || typeof body !== "string" ? JSON.stringify(body) : body;
  return { status, contentType, body: Buffer.from(text, "utf8") };
}

function overrideReply(response: OverrideResponse): Reply {
  const contentType = response.contentType ?? "application/json";
  if (response.body === null) return { status: response.status, contentType, body: Buffer.alloc(0) };
  // Не-JSON (поток событий SSE) отдаётся как есть, JSON — сериализованным.
  const raw = typeof response.body === "string" && !contentType.includes("json");
  const text = raw ? String(response.body) : JSON.stringify(response.body);
  return { status: response.status, contentType, body: Buffer.from(text, "utf8") };
}

function isObject(value: JsonValue | undefined): value is { [key: string]: JsonValue } {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepMerge(base: JsonValue, patch: { readonly [key: string]: JsonValue }): JsonValue {
  const result: { [key: string]: JsonValue } = isObject(base) ? { ...base } : {};
  for (const [key, value] of Object.entries(patch)) {
    const current = result[key];
    result[key] = isObject(value) && isObject(current) ? deepMerge(current, value) : value;
  }
  return result;
}

/** Записанный обмен с влитой правкой тела. */
function merged(exchange: Exchange, reply: OverrideMerge): Exchange {
  if (!isObject(exchange.body)) throw new Error(`Правка ${exchange.path}: записанное тело не объект JSON`);
  return { ...exchange, body: deepMerge(exchange.body, reply.merge) };
}

export class FixtureReplay {
  /** Запросы без ответа: ключ «МЕТОД путь?запрос». */
  readonly unmatched: string[] = [];
  private readonly recorded = new Map<string, Exchange[]>();
  private readonly served = new Map<string, number>();
  private readonly overrides = new Map<string, Override>();
  private lastActivity = Date.now();
  private inFlight = 0;

  constructor(fixture: Fixture, overrides: readonly Override[]) {
    for (const exchange of fixture.exchanges) {
      const key = exchangeKey(exchange);
      this.recorded.set(key, [...(this.recorded.get(key) ?? []), exchange]);
    }
    for (const override of overrides) this.overrides.set(`${override.method} ${override.path}`, override);
  }

  /** Сколько мс API молчит. Запросы, удержанные ради загрузки, не считаются. */
  get quietFor(): number {
    return this.inFlight > 0 ? 0 : Date.now() - this.lastActivity;
  }

  async handle(route: Route, url: URL): Promise<void> {
    this.lastActivity = Date.now();
    const method = route.request().method();
    const override = this.overrideFor(method, url.pathname);
    const overrideKey = override === undefined ? "" : `${override.method} ${override.path}`;
    const reply = override === undefined ? "recorded" : this.nextReply(overrideKey, override);
    // Удержанный запрос не получает ответа никогда: экран остаётся в загрузке.
    if (reply === "hold") return;
    if (reply === "fail") return route.abort("failed");
    // Открытый поток отдаёт страница сама (determinism/open-streams.ts); запрос,
    // дошедший сюда, значит, что подмена fetch его не узнала.
    if (typeof reply === "object" && "open" in reply) {
      this.unmatched.push(`${method} ${url.pathname} (открытый поток дошёл до сети)`);
      return route.abort("failed");
    }
    if (reply !== "recorded" && !("merge" in reply)) return this.fulfill(route, overrideReply(reply));
    const key = exchangeKey({ method, path: url.pathname, query: canonicalQuery(url.searchParams) });
    const replies = this.recorded.get(key);
    if (replies !== undefined && replies.length > 0) {
      const index = this.served.get(key) ?? 0;
      this.served.set(key, index + 1);
      const exchange = replies[Math.min(index, replies.length - 1)];
      if (exchange !== undefined) {
        const recorded = typeof reply === "object" ? merged(exchange, reply) : exchange;
        return this.fulfill(route, exchangeReply(recorded));
      }
    }
    const background = BACKGROUND.get(`${method} ${url.pathname}`);
    if (background !== undefined) return this.fulfill(route, overrideReply(background));
    this.unmatched.push(key);
    return this.fulfill(route, {
      status: 404,
      contentType: "application/json",
      body: Buffer.from(JSON.stringify({ detail: "parity: no recorded response" }), "utf8"),
    });
  }

  /** Подмена запроса: точный путь, иначе первый подходящий шаблон с `{параметр}`. */
  private overrideFor(method: string, pathname: string): Override | undefined {
    const exact = this.overrides.get(`${method} ${pathname}`);
    if (exact !== undefined) return exact;
    for (const override of this.overrides.values()) {
      if (override.method === method && override.path.includes("{") && matchesTemplate(override.path, pathname)) return override;
    }
    return undefined;
  }

  /** Очередной ответ переопределения: по порядку запросов, последний повторяется. */
  private nextReply(key: string, override: Override): OverrideReply {
    const replies: readonly OverrideReply[] = Array.isArray(override.respond) ? override.respond : [override.respond];
    const index = this.served.get(`override ${key}`) ?? 0;
    this.served.set(`override ${key}`, index + 1);
    const reply = replies[Math.min(index, replies.length - 1)];
    if (reply === undefined) throw new Error(`Переопределение ${key} без ответов`);
    return reply;
  }

  private async fulfill(route: Route, reply: Reply): Promise<void> {
    this.inFlight += 1;
    try {
      await route.fulfill({ status: reply.status, contentType: reply.contentType, body: reply.body });
    } finally {
      this.inFlight -= 1;
      this.lastActivity = Date.now();
    }
  }
}
