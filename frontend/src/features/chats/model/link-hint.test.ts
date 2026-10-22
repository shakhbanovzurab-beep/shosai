import { describe, expect, it } from "vitest";

import type { MessengerLink, MessengerLinksResponse } from "@/features/identity/domain/messenger-links-contract";

import type { ChatConnection } from "../domain/contract";
import type { SlackInstallation } from "../domain/slack-contract";
import { linkHintFor, mayHint } from "./link-hint";

const link = (messenger: MessengerLink["messenger"], state: MessengerLink["state"], space = "T1"): MessengerLink => ({
  id: `${messenger}-${state}`,
  messenger,
  account: { handle: "@mara", name: "Mara" },
  space: messenger === "slack" ? { id: space, name: "Acme" } : null,
  state,
  linked_at: null,
  proposed_at: null,
});

const chat = (messenger: ChatConnection["messenger"], title: string, extra: Partial<ChatConnection> = {}) =>
  ({
    id: title,
    messenger,
    title,
    state: "working",
    problem: null,
    slack: messenger === "slack" ? { installation_id: "inst-1", channel_id: "C1" } : null,
    ...extra,
  }) as ChatConnection;

const installation = { id: "inst-1", team: { id: "T1", name: "Acme", icon_url: null } } as SlackInstallation;
const links = (items: MessengerLink[], dismissed = false): MessengerLinksResponse => ({
  items,
  hint_dismissed: dismissed,
});

describe("the hint for an unlinked member", () => {
  it("asks to link Telegram while a Telegram group works and Telegram is not linked", () => {
    expect(linkHintFor(links([]), [chat("telegram", "Release team")], [])).toEqual({
      kind: "telegram",
      chat: "Release team",
    });
  });

  it("stays away once closed, whatever the chats", () => {
    expect(mayHint(links([], true))).toBe(false);
    expect(linkHintFor(links([], true), [chat("telegram", "Release team")], [])).toBeNull();
  });

  it("stays away when Telegram is linked or no Telegram group works", () => {
    expect(linkHintFor(links([link("telegram", "linked")]), [chat("telegram", "Release")], [])).toBeNull();
    const broken = chat("telegram", "Release", { state: "needs_attention", problem: "bot_not_in_chat" });
    expect(linkHintFor(links([]), [broken], [])).toBeNull();
  });

  it("asks to confirm a proposed Slack account when a channel of that Slack workspace works", () => {
    const proposed = link("slack", "proposed");
    const hint = linkHintFor(links([link("telegram", "linked"), proposed]), [chat("slack", "release")], [installation]);
    expect(hint).toEqual({ kind: "slack", chat: "release", link: proposed });
  });

  it("does not ask to confirm a Slack account of another Slack workspace", () => {
    const other = link("slack", "proposed", "T2");
    expect(
      linkHintFor(links([link("telegram", "linked"), other]), [chat("slack", "release")], [installation]),
    ).toBeNull();
    expect(mayHint(links([link("telegram", "linked"), other]))).toBe(true);
  });
});
