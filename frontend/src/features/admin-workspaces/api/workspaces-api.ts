import { apiRequest, isNotFound, jsonBody } from "@/lib/api-client";

import type { AdminWorkspaceDetail, AdminWorkspacesResponse } from "../domain/contract";

const BASE = "/api/admin/workspaces";
const one = (id: string, rest = "") => `${BASE}/${encodeURIComponent(id)}${rest}`;

export const workspacesApi = {
  list: () => apiRequest<AdminWorkspacesResponse>(BASE),
  /** Null when it was deleted meanwhile. */
  get: (id: string) =>
    apiRequest<AdminWorkspaceDetail>(one(id)).catch((error: unknown) => {
      if (isNotFound(error)) return null;
      throw error;
    }),
  setSeats: (id: string, seats: number) => apiRequest<AdminWorkspaceDetail>(one(id), jsonBody("PATCH", { seats })),
  suspend: (id: string, reason: string) =>
    apiRequest<AdminWorkspaceDetail>(one(id, "/suspend"), jsonBody("POST", { reason })),
  resume: (id: string) => apiRequest<AdminWorkspaceDetail>(one(id, "/resume"), { method: "POST" }),
  transferOwner: (id: string, memberId: string) =>
    apiRequest<AdminWorkspaceDetail>(one(id, "/owner"), jsonBody("POST", { member_id: memberId })),
  remove: (id: string) => apiRequest<void>(one(id), { method: "DELETE" }),
};
