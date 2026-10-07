import type { ErrorsKpis } from "../domain/contract";
import { DESKTOP_SESSIONS } from "./reference";
import { DAY, type Store } from "./types";

const crashFreeRate = (crashCount: number, sessions: number) => Math.max(0, 1 - crashCount / sessions);

/** The last 24 hours against the 24 hours before; crashes are critical desktop events. */
export function kpis(data: Store, now: number): ErrorsKpis {
  const dayAgo = now - DAY;
  const twoDaysAgo = now - 2 * DAY;
  const firstSeen = new Map<string, number>();
  const users = { current: new Set<string>(), previous: new Set<string>() };
  const crashes = { macos: [0, 0], windows: [0, 0] };
  let events24 = 0;
  let eventsPrev = 0;

  for (const event of data.events) {
    if (!firstSeen.has(event.issue_id)) firstSeen.set(event.issue_id, event.at);
    if (event.at < twoDaysAgo) continue;
    const current = event.at >= dayAgo;
    if (current) events24++;
    else eventsPrev++;
    if (event.user_id) (current ? users.current : users.previous).add(event.user_id);
    const issue = data.issues.get(event.issue_id);
    if (issue && issue.source !== "platform" && issue.severity === "critical") crashes[issue.source][current ? 0 : 1]++;
  }

  const firsts = [...firstSeen.values()];
  return {
    new_issues_24h: firsts.filter((at) => at >= dayAgo).length,
    new_issues_prev_24h: firsts.filter((at) => at >= twoDaysAgo && at < dayAgo).length,
    events_24h: events24,
    events_prev_24h: eventsPrev,
    affected_users_24h: users.current.size,
    affected_users_prev_24h: users.previous.size,
    crash_free: (["macos", "windows"] as const).map((source) => ({
      source,
      rate: crashFreeRate(crashes[source][0], DESKTOP_SESSIONS[source]),
      previous_rate: crashFreeRate(crashes[source][1], DESKTOP_SESSIONS[source] * 0.97),
      sessions: DESKTOP_SESSIONS[source],
    })),
  };
}
