import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LinkRequest, MessengerLinksResponse } from "../domain/messenger-links-contract";
import {
  confirmLinkRoute,
  hintDismissalRoute,
  linkRequestRoute,
  messengerLinkRoute,
  messengerLinksRoute,
  resetMessengerLinks,
  telegramLinkRoute,
} from "./messenger-links";

const links = async () => (await messengerLinksRoute.GET().json()) as MessengerLinksResponse;
const ctx = <K extends string>(values: Record<K, string>) => ({ params: Promise.resolve(values) });
const request = (path: string) => new Request(`http://demo.test${path}`);

beforeEach(() => {
  resetMessengerLinks();
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("messenger links", () => {
  it("links Telegram once the person presses Start, and only one Telegram account", async () => {
    const created = (await telegramLinkRoute.POST().json()) as LinkRequest;
    expect(created.url).toMatch(/^https:\/\/t\.me\/\w+\?start=\w+$/);
    const poll = async () =>
      (await (await linkRequestRoute.GET(request("/r"), ctx({ requestId: created.id }))).json()) as LinkRequest;
    expect((await poll()).status).toBe("pending");
    vi.advanceTimersByTime(3_000);
    const linked = await poll();
    expect([linked.status, linked.link?.messenger]).toEqual(["linked", "telegram"]);
    expect(telegramLinkRoute.POST().status).toBe(409);
  });

  it("confirms a Slack match by email, or forgets it as not me (CF-D4)", async () => {
    const [proposed] = (await links()).items;
    expect([proposed.messenger, proposed.state]).toEqual(["slack", "proposed"]);
    const confirmed = await confirmLinkRoute.POST(request("/c"), ctx({ linkId: proposed.id }));
    expect(((await confirmed.json()) as { state: string }).state).toBe("linked");
    expect((await messengerLinkRoute.DELETE(request("/d"), ctx({ linkId: proposed.id }))).status).toBe(204);
    expect((await links()).items).toEqual([]);
  });

  it("keeps the hint closed on the account (CF-D9)", async () => {
    expect((await links()).hint_dismissed).toBe(false);
    expect(hintDismissalRoute.POST().status).toBe(204);
    expect((await links()).hint_dismissed).toBe(true);
  });
});
