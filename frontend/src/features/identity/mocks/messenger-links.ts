import {
  LINK_REQUEST_TTL_MS,
  type LinkRequest,
  type MessengerLink,
  type MessengerLinkProblem,
  type MessengerLinksResponse,
} from "../domain/messenger-links-contract";

/*
 * Аккаунты мессенджеров в `npm run dev` без бэкенда (identity, шаг 18; chats §1.2). Бота нет: запрос привязки
 * Telegram срабатывает при первом опросе спустя 3 с, будто человек нажал Start. Переключатель демо
 * `chats-demo` в sessionStorage (тот же, что у кодов чатов) даёт `expire` или `refuse` (аккаунт занят).
 */

const BOT = "ShosaiLeoBot";
const LINK_AFTER_MS = 3_000;
const DAY = 86_400_000;
/** Имя в профиле Telegram демо-человека — его пишет мессенджер, а не Shosai. */
const TELEGRAM_NAME = "Arham Khan";

type StoredRequest = LinkRequest & { created_at: number; outcome: "link" | "expire" | "refuse" };
type LinksDemo = { links: MessengerLink[]; requests: Map<string, StoredRequest>; hint_dismissed: boolean };

const proposedSlack = (): MessengerLink => ({
  id: "link-slack-lumen",
  messenger: "slack",
  account: { handle: "@arham", name: "Arham Khan" },
  space: { id: "T-inst-lumen", name: "Lumen" },
  state: "proposed",
  linked_at: null,
  proposed_at: new Date(Date.now() - DAY).toISOString(),
});

const seeded = (): LinksDemo => ({ links: [proposedSlack()], requests: new Map(), hint_dismissed: false });
const shared = globalThis as typeof globalThis & { messengerLinksDemo?: LinksDemo };
const store = () => (shared.messengerLinksDemo ??= seeded());

/** Начать с чистых демо-данных — для тестов. */
export function resetMessengerLinks() {
  shared.messengerLinksDemo = seeded();
}

function switched(): StoredRequest["outcome"] {
  try {
    const value = globalThis.sessionStorage?.getItem("chats-demo");
    return value === "expire" || value === "refuse" ? value : "link";
  } catch {
    return "link";
  }
}

const refused = (code: MessengerLinkProblem, status: number) =>
  Response.json({ error: { code, request_id: `demo-${crypto.randomUUID()}` }, detail: code }, { status });

const publicRequest = ({ created_at: _at, outcome: _o, ...request }: StoredRequest): LinkRequest => request;

function settle(request: StoredRequest) {
  if (request.status !== "pending") return;
  if (Date.now() > Date.parse(request.expires_at) || request.outcome === "expire") request.status = "expired";
  else if (request.outcome === "refuse")
    Object.assign(request, { status: "refused", refusal: "messenger_account_taken" });
  else {
    const link: MessengerLink = {
      id: `link-telegram-${crypto.randomUUID()}`,
      messenger: "telegram",
      account: { handle: "@arham_k", name: TELEGRAM_NAME },
      space: null,
      state: "linked",
      linked_at: new Date().toISOString(),
      proposed_at: null,
    };
    store().links.push(link);
    Object.assign(request, { status: "linked", link });
  }
}

type Ctx<K extends string> = { params: Promise<Record<K, string>> };

/** /v1/me/messenger-links */
export const messengerLinksRoute = {
  GET() {
    const { links, hint_dismissed } = store();
    return Response.json({ items: links, hint_dismissed } satisfies MessengerLinksResponse);
  },
};

/** /v1/me/messenger-links/hint-dismissal — подсказка закрыта для человека навсегда (CF-D9). */
export const hintDismissalRoute = {
  POST() {
    store().hint_dismissed = true;
    return new Response(null, { status: 204 });
  },
};

/** /v1/me/messenger-links/telegram */
export const telegramLinkRoute = {
  POST() {
    if (store().links.some((link) => link.messenger === "telegram")) return refused("messenger_already_linked", 409);
    const token = crypto.randomUUID().replaceAll("-", "");
    const request: StoredRequest = {
      id: `lr-${crypto.randomUUID()}`,
      url: `https://t.me/${BOT}?start=${token}`,
      expires_at: new Date(Date.now() + LINK_REQUEST_TTL_MS).toISOString(),
      status: "pending",
      link: null,
      refusal: null,
      created_at: Date.now(),
      outcome: switched(),
    };
    store().requests.set(request.id, request);
    return Response.json(publicRequest(request) satisfies LinkRequest, { status: 201 });
  },
};

/** /v1/me/messenger-links/telegram/requests/[requestId] */
export const linkRequestRoute = {
  async GET(_request: Request, { params }: Ctx<"requestId">) {
    const request = store().requests.get((await params).requestId);
    if (!request) return refused("request_not_found", 404);
    if (Date.now() - request.created_at >= LINK_AFTER_MS) settle(request);
    return Response.json(publicRequest(request) satisfies LinkRequest);
  },
};

/** /v1/me/messenger-links/[linkId]/confirm — совпадение Slack по почте подтверждает сам человек (CF-D4). */
export const confirmLinkRoute = {
  async POST(_request: Request, { params }: Ctx<"linkId">) {
    const { linkId } = await params;
    const link = store().links.find((item) => item.id === linkId);
    if (!link) return refused("link_not_found", 404);
    if (link.state === "proposed") Object.assign(link, { state: "linked", linked_at: new Date().toISOString() });
    return Response.json(link satisfies MessengerLink);
  },
};

/** /v1/me/messenger-links/[linkId] — отвязать или «Это не я» для предложения. */
export const messengerLinkRoute = {
  async DELETE(_request: Request, { params }: Ctx<"linkId">) {
    const { linkId } = await params;
    const links = store().links;
    if (!links.some((link) => link.id === linkId)) return refused("link_not_found", 404);
    store().links = links.filter((link) => link.id !== linkId);
    return new Response(null, { status: 204 });
  },
};
