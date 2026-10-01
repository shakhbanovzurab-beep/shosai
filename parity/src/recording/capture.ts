// Проксирование /v1 в API черновика с журналом обменов.
//
// Браузер ходит на ORIGIN, перехват пересылает запрос в API черновика во
// внутренней сети стенда и отдаёт браузеру настоящий ответ — вместе с Set-Cookie,
// поэтому сессия живёт так же, как у пользователя. Каждый обмен пишется в журнал.

import type { Route } from "@playwright/test";

import { canonicalQuery, type Exchange, type JsonValue } from "../fixtures/format.ts";

/** Адрес API черновика из контейнера гармошки (compose.yaml, сеть draft). */
export const DRAFT_API = process.env["PARITY_DRAFT_API"] ?? "http://draft-api:8000";

function isText(contentType: string): boolean {
  return contentType.includes("json") || contentType.startsWith("text/") || contentType.includes("javascript");
}

/** Тело ответа для фикстуры: JSON разобранным, текст строкой, прочее — base64. */
function recordedBody(bytes: Buffer, contentType: string): Pick<Exchange, "body" | "bodyEncoding"> {
  if (bytes.length === 0) return { body: null };
  if (!isText(contentType)) return { body: bytes.toString("base64"), bodyEncoding: "base64" };
  const text = bytes.toString("utf8");
  return { body: contentType.includes("json") ? (JSON.parse(text) as JsonValue) : text };
}

function requestBody(route: Route): JsonValue | undefined {
  const raw = route.request().postData();
  if (raw === null) return undefined;
  const contentType = route.request().headers()["content-type"] ?? "";
  if (contentType.includes("json")) return JSON.parse(raw) as JsonValue;
  // Тело не в JSON (multipart с файлом аватара) в фикстуру не кладётся: сравнение
  // идёт по ключу запроса, а байты файла засорили бы её.
  return `<${contentType.split(";")[0] ?? "binary"}>`;
}

/** Сколько API должен молчать, чтобы визит считался законченным. */
const QUIET_MS = 1000;
const QUIET_DEADLINE_MS = 20_000;

export class ExchangeJournal {
  private readonly entries: Exchange[] = [];
  private inFlight = 0;
  private lastActivity = Date.now();

  /** country — страна посетителя для заголовка CF-IPCountry. */
  constructor(private readonly country: string) {}

  get exchanges(): readonly Exchange[] {
    return this.entries;
  }

  /** Ждёт, пока запросов к API нет QUIET_MS подряд: поздние запросы страницы
   *  (ленивые разделы, фоновые обновления) тоже попадают в фикстуру. */
  async waitForQuiet(): Promise<void> {
    const deadline = Date.now() + QUIET_DEADLINE_MS;
    while (this.inFlight > 0 || Date.now() - this.lastActivity < QUIET_MS) {
      if (Date.now() > deadline) {
        throw new Error(`API не затих за ${QUIET_DEADLINE_MS} мс: запросов в полёте ${this.inFlight}`);
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  /** Пересылает запрос в API черновика, отдаёт ответ браузеру и пишет обмен. */
  async proxy(route: Route, url: URL): Promise<void> {
    this.inFlight += 1;
    this.lastActivity = Date.now();
    try {
      await this.forward(route, url);
    } finally {
      this.inFlight -= 1;
      this.lastActivity = Date.now();
    }
  }

  private async forward(route: Route, url: URL): Promise<void> {
    const request = route.request();
    const target = `${DRAFT_API}${url.pathname}${url.search}`;
    // Host — адрес API, а не ORIGIN; куки и CSRF-заголовок идут как есть. Страну
    // в бою дописывает Cloudflare, здесь — рекордер.
    const { host: _host, ...headers } = await request.allHeaders();
    const response = await route.fetch({
      url: target,
      headers: { ...headers, "cf-ipcountry": this.country },
      maxRedirects: 0,
    });
    // Браузеру — исходные байты: текстовая перекодировка испортила бы двоичный ответ.
    const bytes = await response.body();
    const contentType = response.headers()["content-type"] ?? "";
    const sent = requestBody(route);
    this.entries.push({
      method: request.method(),
      path: url.pathname,
      query: canonicalQuery(url.searchParams),
      ...(sent === undefined ? {} : { requestBody: sent }),
      status: response.status(),
      contentType: contentType.split(";")[0] ?? "",
      ...recordedBody(bytes, contentType),
      origin: "recorded",
    });
    await route.fulfill({ response, body: bytes });
  }
}
