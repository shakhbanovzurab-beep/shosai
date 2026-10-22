import { beforeEach, describe, expect, it } from "vitest";

import type { ChatDigest } from "@/features/chats/domain/digest-contract";
import { digestRoute } from "@/features/chats/mocks/routes/digest-routes";
import { call, codeOf } from "@/features/chats/mocks/routes/test-client";
import { RELEASE_CHAT } from "@/features/chats/mocks/seed/connections";
import { RELEASE_DIGEST } from "@/features/chats/mocks/seed/digests";
import { resetDemo } from "@/features/chats/mocks/store/state";
import { demo as kanbanDemo } from "@/features/kanban/mocks/store/state";
import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { LeoProposal } from "../domain/proposals";
import { decideProposal } from "./demo-proposals";
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
    const reply = await propose(["p1", "p2"]);
    const proposal = reply.body as LeoProposal;
    expect([reply.status, proposal.tool, proposal.status]).toEqual([201, "tasks.create", "proposed"]);
    expect((await digest()).promises.slice(0, 2).map((p) => p.proposal_id)).toEqual([proposal.id, proposal.id]);
    const again = await propose(["p2"]);
    expect([again.status, codeOf(again)]).toEqual([409, "item_already_proposed"]);
    const unknown = await propose(["nope"]);
    expect([unknown.status, codeOf(unknown)]).toEqual([404, "item_not_found"]);
  });

  it("creates workspace tasks with the chat source on approval", async () => {
    const proposal = (await propose(["p1"])).body as LeoProposal;
    decideProposal(proposal.id, true, 0);
    const [item] = (await digest()).promises;
    const task = kanbanDemo().tasks.get(item.task_id ?? "");
    expect(task?.space?.workspace_id).toBe(LUMEN);
    expect(task?.assignee?.name).toBe("Maya Chen");
    expect(task?.source.kind).toBe("chat");
    expect(task?.source.chat).toMatchObject({
      connection_id: RELEASE_CHAT,
      messenger: "telegram",
      chat_title: "Release team",
    });
    expect(task?.source.chat?.message?.url).toBe(item.message.url);
  });

  it("frees the items when the card is declined", async () => {
    const proposal = (await propose(["d1"])).body as LeoProposal;
    decideProposal(proposal.id, false, 0);
    expect((await propose(["d1"])).status).toBe(201);
  });
});
