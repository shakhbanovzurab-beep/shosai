import type { BroadcastTicket } from "../domain/broadcast";

/*
 * Ответы ссылки трансляции на моках по её токену: `studio` — ведущий до эфира с залом ожидания, `speaker` — спикер,
 * `waiting` — зритель ждёт впуска (его впускают через несколько секунд), `soon` — эфир ещё не начался, `full` — мест
 * нет, `ended` — закончилась; любой другой токен — зритель идущего эфира.
 */

const TITLE = "Product update: what shipped in October";
const KNOCK_ANSWER_MS = 6_000;
const knockedAt = new Map<string, number>();

const identityOf = (seed: string) => `guest-${seed.padEnd(12, "0").slice(0, 12)}__0a1b2c3d`;

export function demoTicket(token: string, name: string | null): BroadcastTicket {
  const ticket = (entry: BroadcastTicket["entry"], role: BroadcastTicket["role"] = null): BroadcastTicket => ({
    entry,
    title: TITLE,
    role,
    waitingRoom: token === "studio" || token === "waiting",
    identity: identityOf(name ? "a1b2c3" : "d4e5f6"),
  });
  if (token === "studio") return ticket("stage", "host");
  if (token === "speaker") return ticket("stage", "speaker");
  if (token === "soon") return ticket("not_live");
  if (token === "full") return ticket("full");
  if (token === "ended") return ticket("ended");
  if (token === "waiting") {
    knockedAt.set(token, Date.now());
    return ticket("wait");
  }
  return ticket("audience");
}

export function demoKnock(token: string, ticket: BroadcastTicket): BroadcastTicket {
  const since = knockedAt.get(token) ?? Date.now();
  return Date.now() - since >= KNOCK_ANSWER_MS ? { ...ticket, entry: "audience" } : ticket;
}
