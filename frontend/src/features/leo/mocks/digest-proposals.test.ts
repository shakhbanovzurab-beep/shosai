import { beforeEach, describe, expect, it } from "vitest";

import type { ChatDigest } from "@/features/chats/domain/digest-contract";
import { digestRoute } from "@/features/chats/mocks/routes/digest-routes";
import { call, codeOf } from "@/features/chats/mocks/routes/test-client";
import { RELEASE_CHAT } from "@/features/chats/mocks/seed/connections";
import { RELEASE_DIGEST } from "@/features/chats/mocks/seed/digests";
import { resetDemo } from "@/features/chats/mocks/store/state";
import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { LeoProposal } from "../domain/proposals";
import { pickScenario } from "./demo-scenarios";
import { digestTaskProposalsRoute } from "./digest-proposals";

const params = { id: LUMEN, chatId: RELEASE_CHAT, digestId: RELEASE_DIGEST };
const propose = (item_ids: string[]) =>
  call(digestTaskProposalsRoute, "POST", "/proposals", { params, body: { item_ids } });
const digest = async () => (await call(digestRoute, "GET", "/digest", { params })).body as ChatDigest;

beforeEach(() => {
  resetDemo();
});

describe("Make a task from a chat digest (CF-D5)", () => {
  it("streams the digest as an artifact when asked to go through a chat", () => {
    const artifact = pickScenario("Go through #release for the week")?.artifact?.();
    expect(artifact).toMatchObject({
      kind: "chat_digest",
      ref: RELEASE_DIGEST,
      chat_id: RELEASE_CHAT,
      workspace_id: LUMEN,
    });
  });

  it("makes one approval card for the items and refuses them while it waits", async () => {
    const reply = await propose(["p3", "p4"]);
    const proposal = reply.body as LeoProposal;
    expect([reply.status, proposal.tool, proposal.status]).toEqual([201, "tasks.create", "proposed"]);
    expect((await digest()).promises.slice(2, 4).map((p) => p.proposal_id)).toEqual([proposal.id, proposal.id]);
    const again = await propose(["p4"]);
    expect([again.status, codeOf(again)]).toEqual([409, "item_already_proposed"]);
    // Договорённость, которую Leo уже сделал задачей, второй раз не предлагается.
    const made = await propose(["p1"]);
    expect([made.status, codeOf(made)]).toEqual([409, "item_already_proposed"]);
    const unknown = await propose(["nope"]);
    expect([unknown.status, codeOf(unknown)]).toEqual([404, "item_not_found"]);
  });
});
