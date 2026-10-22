import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type { MessengerLinksResponse } from "../domain/messenger-links-contract";

const api = vi.hoisted(() => ({
  messengerLinksApi: { list: vi.fn<() => Promise<MessengerLinksResponse>>() },
}));

vi.mock("../api/messenger-links-api", () => api);

const { hideLinkHintHere, messengerLinksQuery } = await import("./messenger-links");

describe("the link hint's dismissal", () => {
  it("keeps the hint hidden in this tab even when the server has not saved the dismissal yet", async () => {
    api.messengerLinksApi.list.mockResolvedValue({ items: [], hint_dismissed: false });
    const client = new QueryClient();
    expect((await client.fetchQuery(messengerLinksQuery)).hint_dismissed).toBe(false);

    hideLinkHintHere(client);
    expect(client.getQueryData<MessengerLinksResponse>(messengerLinksQuery.queryKey)?.hint_dismissed).toBe(true);

    const refetched = await client.fetchQuery({ ...messengerLinksQuery, staleTime: 0 });
    expect(refetched.hint_dismissed).toBe(true);
  });
});
