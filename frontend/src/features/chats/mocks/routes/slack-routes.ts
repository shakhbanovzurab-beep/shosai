import type { SlackConnectResponse, SlackInstallationsResponse } from "../../domain/slack-contract";
import {
  beginHandoff,
  channelsPage,
  completeHandoff,
  connectChannels,
  installationsOf,
  removeInstallation,
} from "../store/slack";
import { answer, answerEmpty, bodyOf, type Ctx, inWorkspace, json } from "./http";
import { handoffSchema, slackConnectSchema } from "./schemas";

/* Slack (chats §1.2): передача OAuth, установки, их каналы и подключение каналов пачкой. */

const same = <T>(value: T) => value;
const CHANNELS_PAGE_MAX = 100;
const CHANNELS_PAGE_DEFAULT = 50;

/** /v1/workspaces/[id]/chats/slack/installations */
export const installationsRoute = {
  async GET(_request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "member", (ws) => json<SlackInstallationsResponse>({ items: installationsOf(ws) }));
  },
  async POST(request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "admin", async (ws) => {
      const body = await bodyOf(request, handoffSchema);
      if ("refusal" in body) return body.refusal;
      return answer(beginHandoff(ws, body.data.installation_id), same, 201);
    });
  },
};

const installationOf = async (params: Promise<Record<"id" | "installationId", string>>) =>
  (await params).installationId;

/** /v1/workspaces/[id]/chats/slack/installations/[installationId] */
export const installationRoute = {
  async DELETE(_request: Request, { params }: Ctx<"id" | "installationId">) {
    const id = await installationOf(params);
    return inWorkspace(params, "admin", (ws) => answerEmpty(removeInstallation(ws, id)));
  },
};

/** /v1/workspaces/[id]/chats/slack/installations/[installationId]/channels */
export const channelsRoute = {
  async GET(request: Request, { params }: Ctx<"id" | "installationId">) {
    const id = await installationOf(params);
    const query = new URL(request.url).searchParams;
    const limit = Math.min(CHANNELS_PAGE_MAX, Math.max(1, Number(query.get("limit")) || CHANNELS_PAGE_DEFAULT));
    return inWorkspace(params, "admin", (ws) =>
      answer(channelsPage(ws, id, { q: query.get("q") ?? "", cursor: query.get("cursor"), limit }), same),
    );
  },
};

/** /v1/workspaces/[id]/chats/slack */
export const slackConnectRoute = {
  async POST(request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "admin", async (ws) => {
      const body = await bodyOf(request, slackConnectSchema);
      if ("refusal" in body) return body.refusal;
      return answer(connectChannels(ws, body.data), (items): SlackConnectResponse => ({ items }), 201);
    });
  },
};

/**
 * /v1/integrations/oauth/slack/callback — в жизни это маршрут connectors, куда Slack возвращает согласие. Здесь
 * его зовёт страница-заглушка согласия; он завершает установку и отправляет окно на `/oauth/callback`.
 */
export const slackCallbackRoute = {
  async GET(request: Request) {
    const query = new URL(request.url).searchParams;
    const next = completeHandoff(query.get("state") ?? "", query.get("decision") === "allow");
    // Относительный Location держит окно на том источнике, где человек, как у заглушки connectors.
    return new Response(null, { status: 303, headers: { Location: `/oauth/callback?${next}` } });
  },
};
