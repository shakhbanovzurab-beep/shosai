import { z } from "zod";

import { CHAT_MODES } from "../../domain/contract";
import { DIGEST_ITEMS_PER_PROPOSAL } from "../../domain/digest-contract";
import { SLACK_CHANNELS_PER_CONNECT } from "../../domain/slack-contract";

/* Тела запросов `/v1/workspaces/{id}/chats*` (chats §1.2); сообщение проверки — код отказа кабинета. */

const mode = z.enum(CHAT_MODES, "mode_invalid");
const notice = z.literal(true, "data_notice_required");
const projectId = z.string().min(1).nullable();

export const settingsPatchSchema = z.object({ retention_days: z.int("retention_invalid") });

export const connectionPatchSchema = z.object({
  project_id: projectId.optional(),
  mode: mode.optional(),
  data_notice_accepted: z.boolean().optional(),
});

export const connectCodeSchema = z.object({
  project_id: projectId,
  mode,
  data_notice_accepted: notice,
  connection_id: z.string().min(1).optional(),
});

export const handoffSchema = z.object({ installation_id: z.string().min(1).optional() });

export const slackConnectSchema = z.object({
  installation_id: z.string().min(1),
  channels: z
    .array(z.object({ channel_id: z.string().min(1), project_id: projectId }))
    .min(1)
    .max(SLACK_CHANNELS_PER_CONNECT),
  mode,
  data_notice_accepted: notice,
});

export const taskProposalsSchema = z.object({
  item_ids: z.array(z.string().min(1)).min(1).max(DIGEST_ITEMS_PER_PROPOSAL),
});
