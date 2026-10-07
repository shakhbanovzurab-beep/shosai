import { NextResponse } from "next/server";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import type { IssueDetail, IssuesResponse } from "../domain/contract";
import { parseIssuesQuery } from "../domain/query";
import { updateIssueSchema } from "../domain/schemas";
import { getIssue, updateIssue } from "./issue";
import { listIssues } from "./list";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/errors`: the issue list with KPIs and timeline. */
export const issuesRoute = {
  async GET(request: Request) {
    const { searchParams, search } = new URL(request.url);
    const upstream = await forwardToBackend(request, `/v1/admin/errors${search}`);
    if (upstream) return upstream;
    return NextResponse.json<IssuesResponse>(listIssues(parseIssuesQuery(searchParams)));
  },
};

/** `/api/admin/errors/{id}`: one issue, and changing its status or assignee. */
export const issueRoute = {
  async GET(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/admin/errors/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    const issue = getIssue(id);
    return issue ? NextResponse.json<IssueDetail>(issue) : detail("Ошибка не найдена.", 404);
  },

  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/admin/errors/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    const body = updateIssueSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Некорректный запрос.", 422);
    const issue = updateIssue(id, body.data);
    if (issue === "unknown_assignee") return detail("Такого администратора нет.", 422);
    return issue ? NextResponse.json<IssueDetail>(issue) : detail("Ошибка не найдена.", 404);
  },
};
