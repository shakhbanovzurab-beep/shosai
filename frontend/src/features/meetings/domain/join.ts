/* Вход в комнату по ссылке: отказы сервера как состояния страницы (meetings §3.3, frontend/docs/meetings-api.md). */

/** Почему в звонок не войти; коды — `code` сервера, `unknown` — всё прочее. */
export const JOIN_PROBLEMS = [
  "not_found",
  "room_finished",
  "removed",
  "room_full",
  "video_unavailable",
  "rate_limited",
  "unknown",
] as const;
export type JoinProblem = (typeof JOIN_PROBLEMS)[number];

const BY_CODE: Record<string, JoinProblem> = {
  not_found: "not_found",
  room_finished: "room_finished",
  removed: "removed",
  room_full: "room_full",
  video_unavailable: "video_unavailable",
};

/** Состояние страницы по ответу сервера; 429 — подождать и повторить. */
export function joinProblemOf(status: number, code: string | null): JoinProblem {
  if (status === 429) return "rate_limited";
  return (code && BY_CODE[code]) || "unknown";
}

/** Можно ли повторить попытку с этой страницы: конец встречи и удаление — окончательны. */
export const retryable = (problem: JoinProblem) =>
  problem === "video_unavailable" || problem === "rate_limited" || problem === "unknown" || problem === "room_full";

/** Имя гостя: 1–100 символов после обрезки пробелов; null — нельзя. */
export const GUEST_NAME_MAX = 100;
export const guestName = (value: string) => {
  const name = value.trim();
  return name.length > 0 && [...name].length <= GUEST_NAME_MAX ? name : null;
};

/** Почему звонок закончился у этого участника. */
export type CallEnd = "left" | "ended" | "removed" | "lost";
