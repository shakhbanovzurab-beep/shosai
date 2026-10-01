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

import { canonicalQuery, exchangeKey, type Exchange, type Fixture } from "../fixtures/format.ts";
import type { Override, OverrideReply, OverrideResponse } from "../states/types.ts";
import { BACKGROUND } from "./background.ts";

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
  const body = response.body === null ? Buffer.alloc(0) : Buffer.from(JSON.stringify(response.body), "utf8");
  return { status: response.status, contentType, body };
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
    const overrideKey = `${method} ${url.pathname}`;
    const override = this.overrides.get(overrideKey);
    if (override !== undefined) {
      const reply = this.nextReply(overrideKey, override);
      // Удержанный запрос не получает ответа никогда: экран остаётся в загрузке.
      if (reply === "hold") return;
      if (reply === "fail") return route.abort("failed");
      return this.fulfill(route, overrideReply(reply));
    }
    const key = exchangeKey({ method, path: url.pathname, query: canonicalQuery(url.searchParams) });
    const replies = this.recorded.get(key);
    if (replies !== undefined && replies.length > 0) {
      const index = this.served.get(key) ?? 0;
      this.served.set(key, index + 1);
      const exchange = replies[Math.min(index, replies.length - 1)];
      if (exchange !== undefined) return this.fulfill(route, exchangeReply(exchange));
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
