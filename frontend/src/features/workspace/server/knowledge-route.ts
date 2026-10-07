import { NextResponse } from "next/server";

import { formatBytes } from "@/i18n/format-units";

import type { Member } from "../domain/contract";
import {
  KNOWLEDGE_FILE_MAX_BYTES,
  KNOWLEDGE_FILES_PER_UPLOAD,
  type KnowledgeAccess,
  type KnowledgeItem,
  type KnowledgeResponse,
} from "../domain/knowledge-contract";
import { isAdmin } from "../domain/roles";
import { canUseKnowledge } from "../domain/visibility";
import { advanceIndexing, connectedItem, uploadedItem } from "./demo-knowledge";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { type Problem, refuse } from "./problems";
import {
  connectSourceSchema,
  firstIssue,
  knowledgeAccessSchema,
  knowledgeUpdateSchema,
  readJson,
  shareFileSchema,
} from "./schemas";
import { shareFile } from "./sharing";

const canManage = (me: Member, entry: KnowledgeItem) => isAdmin(me) || entry.added_by === me.id;
const visible = (me: Member, entry: KnowledgeItem) => canUseKnowledge(me, isAdmin(me), entry);
const teamExists = ({ data }: Found, access: KnowledgeAccess) =>
  access.team_id === null || data.teams.some((t) => t.id === access.team_id);
const projectExists = ({ data }: Found, projectId: string | null) =>
  projectId === null || data.projects.some((p) => p.id === projectId);

function accessFrom(form: FormData): KnowledgeAccess | Problem {
  const teamId = form.get("team_id");
  const parsed = knowledgeAccessSchema.safeParse({
    level: form.get("level"),
    team_id: typeof teamId === "string" && teamId ? teamId : null,
  });
  return parsed.success ? parsed.data : firstIssue(parsed.error);
}

/** /api/workspaces/[ws]/knowledge: what the member can see, and new uploads. */
export const knowledgeRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/knowledge",
      ({ data, me }) => {
        advanceIndexing(data.knowledge);
        return NextResponse.json<KnowledgeResponse>({ items: data.knowledge.filter((k) => visible(me, k)) });
      },
    ),

  /** multipart/form-data: one or more `files`, `level`, for a team `team_id`, and optionally `project_id`. */
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/knowledge",
      async (found) => {
        const form = await request.formData().catch(() => null);
        if (!form) return refuse("sendFilesAsForm", 422);
        const files = form.getAll("files").filter((part): part is File => part instanceof File);
        if (files.length === 0) return refuse("chooseFile", 422);
        if (files.length > KNOWLEDGE_FILES_PER_UPLOAD)
          return refuse((t) => t("tooManyFiles", { count: KNOWLEDGE_FILES_PER_UPLOAD }), 422);
        const tooBig = files.find((f) => f.size > KNOWLEDGE_FILE_MAX_BYTES);
        if (tooBig)
          return refuse(
            (t, locale) =>
              t("fileTooLarge", { name: tooBig.name, size: formatBytes(locale, KNOWLEDGE_FILE_MAX_BYTES) }),
            413,
          );
        const access = accessFrom(form);
        if (typeof access === "string") return refuse(access, 422);
        if (!teamExists(found, access)) return refuse("teamGone", 422);
        const project = form.get("project_id");
        const projectId = typeof project === "string" && project ? project : null;
        if (!projectExists(found, projectId)) return refuse("projectGone", 422);
        const items = files.map((file) => uploadedItem(file, found.me.id, access, projectId));
        found.data.knowledge.unshift(...items);
        return NextResponse.json<KnowledgeResponse>({ items }, { status: 201 });
      },
    ),
};

/** /api/workspaces/[ws]/knowledge/publish: one of the member's own files, pointed to rather than copied. */
export const knowledgePublishRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/knowledge/publish",
      async (found) => {
        const body = shareFileSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        if (!teamExists(found, body.data.access)) return refuse("teamGone", 422);
        if (!projectExists(found, body.data.project_id)) return refuse("projectGone", 422);
        return NextResponse.json<KnowledgeItem>(shareFile(found.data, found.me, body.data), { status: 201 });
      },
    ),
};

/** /api/workspaces/[ws]/knowledge/sources: a source the workspace connects (Drive, Notion…); admins. */
export const knowledgeSourcesRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/knowledge/sources",
      async (found) => {
        if (!isAdmin(found.me)) return refuse("adminsConnectSources", 403);
        const body = connectSourceSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        if (!teamExists(found, body.data.access)) return refuse("teamGone", 422);
        const entry = connectedItem(body.data, found.me.id);
        found.data.knowledge.unshift(entry);
        return NextResponse.json<KnowledgeItem>(entry, { status: 201 });
      },
    ),
};

/** /api/workspaces/[ws]/knowledge/[id] */
export const knowledgeItemRoute = {
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/knowledge"), async (found, { id }) => {
      const entry = found.data.knowledge.find((k) => k.id === id);
      if (!entry || !visible(found.me, entry)) return refuse("knowledgeGone", 404);
      if (!canManage(found.me, entry)) return refuse("knowledgeChangeDenied", 403);
      const body = knowledgeUpdateSchema.safeParse(await readJson(request));
      if (!body.success) return refuse(firstIssue(body.error), 422);
      const { access, project_id } = body.data;
      if (access && !teamExists(found, access)) return refuse("teamGone", 422);
      if (project_id !== undefined && !projectExists(found, project_id)) return refuse("projectGone", 422);
      if (access) entry.access = access;
      if (project_id !== undefined) entry.project_id = project_id;
      return NextResponse.json<KnowledgeItem>(entry);
    }),

  /** Removes an upload or a source, or stops sharing a member's file (it stays in their File Manager). */
  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/knowledge"), (found, { id }) => {
      const entry = found.data.knowledge.find((k) => k.id === id);
      if (!entry || !visible(found.me, entry)) return refuse("knowledgeGone", 404);
      if (!canManage(found.me, entry)) return refuse("knowledgeRemoveDenied", 403);
      found.data.knowledge = found.data.knowledge.filter((k) => k.id !== id);
      return new Response(null, { status: 204 });
    }),
};
