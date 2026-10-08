import { z } from "zod";

import { SHARE_LEVELS, TASK_STATUSES, TASK_TITLE_MAX } from "../domain/content-contract";
import {
  DEFAULT_SHARE_LEVELS,
  INVITES_PER_REQUEST,
  PROJECT_NAME_MAX,
  PROJECT_STATUSES,
  SEATS_MAX,
  SEATS_MIN,
  TEAM_COLORS,
  TEAM_DESCRIPTION_MAX,
  TEAM_NAME_MAX,
  WORKSPACE_NAME_MAX,
} from "../domain/contract";
import { CONNECTOR_PROVIDERS } from "../domain/knowledge-contract";
import { type Problem, type ValidationProblem, validationProblem } from "./problems";

// Messages are problem codes, worded in the request's language when the refusal goes out (see problems.ts).
const name = (max: number, problem: ValidationProblem) => z.string().trim().min(1, problem).max(max);
const ref = z.string().min(1).max(64);

export const createWorkspaceSchema = z.strictObject({
  name: name(WORKSPACE_NAME_MAX, "workspaceNameRequired"),
  seats: z
    .int()
    .min(SEATS_MIN, "seatsTooFew" satisfies ValidationProblem)
    .max(SEATS_MAX),
});

export const updateWorkspaceSchema = z.strictObject({
  name: name(WORKSPACE_NAME_MAX, "workspaceNameRequired").optional(),
  join_domain: z
    .string()
    .trim()
    .toLowerCase()
    .regex(/^([a-z0-9-]+\.)+[a-z]{2,}$/, "domainInvalid" satisfies ValidationProblem)
    .nullable()
    .optional(),
  sharing: z
    .strictObject({
      default_level: z.enum(DEFAULT_SHARE_LEVELS),
      share_transcripts: z.boolean(),
      members_can_invite: z.boolean(),
    })
    .partial()
    .optional(),
});

const role = z.enum(["admin", "member"]);
const ids = z.array(ref).max(50);

export const inviteSchema = z.strictObject({
  emails: z
    .array(z.email("emailsInvalid" satisfies ValidationProblem))
    .min(1, "emailsRequired" satisfies ValidationProblem)
    .max(INVITES_PER_REQUEST),
  role,
  team_ids: ids,
});

export const updateMemberSchema = z.strictObject({ role: role.optional(), team_ids: ids.optional() });

export const teamInputSchema = z.strictObject({
  name: name(TEAM_NAME_MAX, "teamNameRequired"),
  description: z.string().trim().max(TEAM_DESCRIPTION_MAX),
  color: z.enum(TEAM_COLORS),
  private: z.boolean(),
  member_ids: ids,
});

export const projectInputSchema = z.strictObject({
  name: name(PROJECT_NAME_MAX, "projectNameRequired"),
  description: z.string().trim().max(400),
  status: z.enum(PROJECT_STATUSES),
  lead_id: ref.nullable(),
  team_id: ref.nullable(),
  target_date: z.iso.date().nullable(),
});

export const visibilitySchema = z
  .strictObject({ level: z.enum(SHARE_LEVELS), team_id: ref.nullable() })
  .refine((v) => (v.level === "team") === (v.team_id !== null), "pickTeamToShare" satisfies ValidationProblem);

export const shareRecordingSchema = z.strictObject({
  recording_id: ref,
  visibility: visibilitySchema,
  project_id: ref.nullable(),
  transcript_shared: z.boolean(),
});

export const meetingShareSchema = z.strictObject({
  visibility: visibilitySchema.optional(),
  transcript_shared: z.boolean().optional(),
  project_id: ref.nullable().optional(),
});

export const taskCreateSchema = z.strictObject({
  title: name(TASK_TITLE_MAX, "taskTitleRequired"),
  assignee_id: ref.nullable(),
  due_on: z.iso.date().nullable(),
  project_id: ref.nullable(),
});

export const taskUpdateSchema = z.strictObject({
  title: name(TASK_TITLE_MAX, "taskTitleRequired").optional(),
  status: z.enum(TASK_STATUSES).optional(),
  assignee_id: ref.nullable().optional(),
  due_on: z.iso.date().nullable().optional(),
  project_id: ref.nullable().optional(),
});

export const knowledgeAccessSchema = z
  .strictObject({ level: z.enum(["team", "workspace"]), team_id: ref.nullable() })
  .refine((v) => (v.level === "team") === (v.team_id !== null), "pickTeam" satisfies ValidationProblem);

export const knowledgeUpdateSchema = z.strictObject({
  access: knowledgeAccessSchema.optional(),
  project_id: ref.nullable().optional(),
});

export const shareFileSchema = z.strictObject({
  file_id: ref,
  name: z.string().trim().min(1).max(255),
  size_bytes: z.int().nonnegative(),
  content_type: z.string().max(255),
  access: knowledgeAccessSchema,
  project_id: ref.nullable(),
});

export const connectSourceSchema = z.strictObject({
  provider: z.enum(CONNECTOR_PROVIDERS),
  name: name(120, "sourceNameRequired"),
  url: z.url("linkInvalid" satisfies ValidationProblem).nullable(),
  access: knowledgeAccessSchema,
});

export const readJson = (request: Request) => request.json().catch(() => null);

/** What to tell the user about an invalid body: a problem they can fix, or that the request is malformed. */
export const firstIssue = (error: z.ZodError): Problem => validationProblem(error.issues[0]?.message);
