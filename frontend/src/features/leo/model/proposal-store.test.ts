import { describe, expect, it, vi } from "vitest";

import { inDomain } from "@/lib/resource-domains";

import type { LeoProposal, ProposalStatus } from "../domain/proposals";

const api = vi.hoisted(() => ({
  proposalsApi: { pending: vi.fn(), card: vi.fn<(id: string) => Promise<LeoProposal>>() },
}));
vi.mock("../api/proposals-api", () => api);

const { receiveCard } = await import("./proposal-store");
const { rereadCard } = await import("./proposals");
const { onCardEvent } = await import("./card-events");

const card = (id: string, status: ProposalStatus, invalidates?: string[]): LeoProposal => ({
  id,
  tool: "boards.create",
  title: "New board",
  space: "Personal",
  origin: { kind: "thread", app: null },
  reversibility: "reversible",
  warning: false,
  taint: null,
  preview: { kind: "fields", fields: [], body: null },
  status,
  outcome: null,
  nonce: "n",
  created_at: "2026-10-27T17:00:00Z",
  expires_at: "2026-10-27T18:00:00Z",
  resolved_at: null,
  ...(invalidates ? { invalidates } : {}),
});

function watched(domain: string) {
  const refreshIfWatched = vi.fn(() => Promise.resolve());
  inDomain(domain, { refreshIfWatched });
  return refreshIfWatched;
}

describe("a card's outcome on the shown screens", () => {
  it("re-reads the data the card changed once, however many times its outcome arrives", () => {
    const tasks = watched("tasks");
    const notes = watched("notes");

    receiveCard(card("a1", "executing"));
    receiveCard(card("a1", "succeeded", ["tasks"]));
    receiveCard(card("a1", "succeeded", ["tasks"]));

    expect(tasks).toHaveBeenCalledTimes(1);
    expect(notes).not.toHaveBeenCalled();
  });

  it("re-reads nothing for a rejected card or one that changed nothing", () => {
    const files = watched("files");

    receiveCard(card("a2", "rejected", []));
    receiveCard(card("a3", "failed", []));

    expect(files).not.toHaveBeenCalled();
  });

  it("re-reads after a card approved by voice, read again from the server", async () => {
    const files = watched("files");
    api.proposalsApi.card.mockResolvedValue(card("a4", "succeeded", ["files"]));
    api.proposalsApi.pending.mockResolvedValue({ items: [], next_cursor: null });

    await rereadCard("a4");

    expect(api.proposalsApi.card).toHaveBeenCalledWith("a4");
    expect(files).toHaveBeenCalledTimes(1);
  });

  it("takes the stream's `invalidates` for a card from a server that does not put it in the card", () => {
    const notes = watched("notes");

    onCardEvent({ seq: 3, kind: "action.updated", data: { action: card("a5", "succeeded"), invalidates: ["notes"] } });

    expect(notes).toHaveBeenCalledTimes(1);
  });
});
