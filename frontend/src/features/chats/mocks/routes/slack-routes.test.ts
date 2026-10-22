import { beforeEach, describe, expect, it } from "vitest";

import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type {
  SlackChannelsPage,
  SlackConnectResponse,
  SlackHandoff,
  SlackInstallationsResponse,
} from "../../domain/slack-contract";
import { resetDemo } from "../store/state";
import {
  channelsRoute,
  installationRoute,
  installationsRoute,
  slackCallbackRoute,
  slackConnectRoute,
} from "./slack-routes";
import { call, codeOf } from "./test-client";

const params = { id: LUMEN };
const installations = async () =>
  ((await call(installationsRoute, "GET", "/inst", { params })).body as SlackInstallationsResponse).items;
const channels = async (installationId: string, q = "") =>
  call(channelsRoute, "GET", `/channels?q=${q}`, { params: { ...params, installationId } });
const connect = (body: unknown) => call(slackConnectRoute, "POST", "/slack", { params, body });

/** Пройти демо-согласие: начать передачу и вернуть решение, как страница-заглушка. */
async function consent(decision: "allow" | "deny", installation_id?: string) {
  const handoff = (await call(installationsRoute, "POST", "/inst", { params, body: { installation_id } }))
    .body as SlackHandoff;
  const state = new URL(handoff.authorize_url, "http://demo.test").searchParams.get("state") ?? "";
  const response = await slackCallbackRoute.GET(
    new Request(`http://demo.test/cb?${new URLSearchParams({ state, decision })}`),
  );
  return new URL(response.headers.get("location") ?? "", "http://demo.test").searchParams;
}

beforeEach(() => {
  resetDemo();
});

describe("Slack", () => {
  it("installs through the consent and lands on /oauth/callback with the installation", async () => {
    const result = await consent("allow");
    expect(result.get("flow")).toBe("chats");
    expect(result.get("status")).toBe("connected");
    expect((await installations()).map((i) => i.id)).toContain(result.get("installation_id"));
    expect((await consent("deny")).get("status")).toBe("denied");
  });

  it("reconnects an installation whose token expired, and its chats work again", async () => {
    expect((await installations()).find((i) => i.id === "inst-partners")?.state).toBe("token_expired");
    const refused = await channels("inst-partners");
    expect([refused.status, codeOf(refused)]).toEqual([409, "token_expired"]);
    expect((await consent("allow", "inst-partners")).get("installation_id")).toBe("inst-partners");
    expect((await installations()).find((i) => i.id === "inst-partners")?.state).toBe("working");
  });

  it("lists channels by name, marks connected ones and searches", async () => {
    const page = (await channels("inst-lumen")).body as SlackChannelsPage;
    const names = page.items.map((c) => c.name);
    expect(names).toEqual(names.toSorted((a, b) => a.localeCompare(b)));
    expect(page.items.find((c) => c.name === "pricing")?.connection_id).toBe("chat-sl-pricing");
    expect(((await channels("inst-lumen", "eng")).body as SlackChannelsPage).items.map((c) => c.name)).toEqual([
      "engineering",
    ]);
  });

  it("connects channels all or nothing, naming the ones already connected", async () => {
    const base = { installation_id: "inst-lumen", mode: "all", data_notice_accepted: true };
    const taken = await connect({ ...base, channels: [{ channel_id: "C07PRICING", project_id: null }] });
    expect([taken.status, codeOf(taken)]).toEqual([409, "channel_already_connected"]);
    expect((taken.body as { error: { params: { channel_ids: string[] } } }).error.params.channel_ids).toEqual([
      "C07PRICING",
    ]);
    const made = await connect({
      ...base,
      channels: [
        { channel_id: "C07DESIGN", project_id: "onboarding" },
        { channel_id: "C07LEADS", project_id: null },
      ],
    });
    const items = (made.body as SlackConnectResponse).items;
    expect(made.status).toBe(201);
    expect(items.map((c) => [c.title, c.kind, c.binding.kind])).toEqual([
      ["design", "public_channel", "project"],
      ["leadership", "private_channel", "workspace"],
    ]);
  });

  it("disconnects an installation with its channels", async () => {
    const gone = await call(installationRoute, "DELETE", "/inst", {
      params: { ...params, installationId: "inst-lumen" },
    });
    expect(gone.status).toBe(204);
    expect((await installations()).map((i) => i.id)).toEqual(["inst-partners"]);
  });
});
