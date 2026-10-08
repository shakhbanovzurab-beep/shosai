import { apiRequest, jsonBody } from "@/lib/api/request";

import type { IssueDetail, IssuesResponse, UpdateIssueRequest } from "../domain/contract";

const BASE = "/api/admin/errors";

export const errorsApi = {
  list: (search: string) => apiRequest<IssuesResponse>(`${BASE}${search ? `?${search}` : ""}`),
  get: (id: string) => apiRequest<IssueDetail>(`${BASE}/${encodeURIComponent(id)}`),
  update: (id: string, patch: UpdateIssueRequest) =>
    apiRequest<IssueDetail>(`${BASE}/${encodeURIComponent(id)}`, jsonBody("PATCH", patch)),
};
