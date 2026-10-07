import { apiRequest, isNotFound, jsonBody } from "@/lib/api-client";

import type {
  DecisionsResponse,
  MeetingShareRequest,
  MeetingsResponse,
  ShareRecordingRequest,
  Task,
  TaskCreate,
  TasksResponse,
  TaskUpdate,
  TeamMeetingDetail,
  UsageResponse,
} from "../domain/content-contract";
import type {
  CreateWorkspaceRequest,
  InviteRequest,
  ProjectInput,
  TeamInput,
  UpdateMemberRequest,
  UpdateWorkspaceRequest,
  WorkspaceState,
  WorkspacesResponse,
} from "../domain/contract";
import type {
  ConnectSourceRequest,
  KnowledgeAccess,
  KnowledgeItem,
  KnowledgeResponse,
  KnowledgeUpdate,
  ShareFileRequest,
} from "../domain/knowledge-contract";
import type {
  MyKnowledgeResponse,
  MyMeetingsResponse,
  MySharesResponse,
  MyTasksResponse,
} from "../domain/personal-contract";

const e = encodeURIComponent;

/** Calls under one workspace, `/api/workspaces/{id}…`. */
export function workspaceApi(ws: string) {
  const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/workspaces/${e(ws)}${path}`, init);
  return {
    get: () => request<WorkspaceState>(""),
    update: (body: UpdateWorkspaceRequest) => request<WorkspaceState>("", jsonBody("PATCH", body)),
    remove: () => request<void>("", { method: "DELETE" }),
    leave: () => request<void>("/leave", { method: "POST" }),
    usage: () => request<UsageResponse>("/usage"),

    invite: (body: InviteRequest) => request<WorkspaceState>("/invitations", jsonBody("POST", body)),
    revokeInvitation: (id: string) => request<WorkspaceState>(`/invitations/${e(id)}`, { method: "DELETE" }),
    resendInvitation: (id: string) => request<WorkspaceState>(`/invitations/${e(id)}/resend`, { method: "POST" }),
    updateMember: (id: string, body: UpdateMemberRequest) =>
      request<WorkspaceState>(`/members/${e(id)}`, jsonBody("PATCH", body)),
    removeMember: (id: string) => request<WorkspaceState>(`/members/${e(id)}`, { method: "DELETE" }),

    createTeam: (body: TeamInput) => request<WorkspaceState>("/teams", jsonBody("POST", body)),
    updateTeam: (id: string, body: TeamInput) => request<WorkspaceState>(`/teams/${e(id)}`, jsonBody("PATCH", body)),
    deleteTeam: (id: string) => request<WorkspaceState>(`/teams/${e(id)}`, { method: "DELETE" }),

    createProject: (body: ProjectInput) => request<WorkspaceState>("/projects", jsonBody("POST", body)),
    updateProject: (id: string, body: Partial<ProjectInput>) =>
      request<WorkspaceState>(`/projects/${e(id)}`, jsonBody("PATCH", body)),
    deleteProject: (id: string) => request<WorkspaceState>(`/projects/${e(id)}`, { method: "DELETE" }),

    meetings: () => request<MeetingsResponse>("/meetings"),
    /** Null when the meeting doesn't exist or isn't shared with the member. */
    meeting: (id: string) =>
      request<TeamMeetingDetail>(`/meetings/${e(id)}`).catch((error: unknown) => {
        if (isNotFound(error)) return null;
        throw error;
      }),
    shareRecording: (body: ShareRecordingRequest) => request<TeamMeetingDetail>("/meetings", jsonBody("POST", body)),
    updateMeeting: (id: string, body: MeetingShareRequest) =>
      request<TeamMeetingDetail>(`/meetings/${e(id)}`, jsonBody("PATCH", body)),
    unshareMeeting: (id: string) => request<void>(`/meetings/${e(id)}`, { method: "DELETE" }),

    decisions: () => request<DecisionsResponse>("/decisions"),
    tasks: () => request<TasksResponse>("/tasks"),
    createTask: (body: TaskCreate) => request<Task>("/tasks", jsonBody("POST", body)),
    updateTask: (id: string, body: TaskUpdate) => request<Task>(`/tasks/${e(id)}`, jsonBody("PATCH", body)),

    knowledge: () => request<KnowledgeResponse>("/knowledge"),
    upload: (files: File[], access: KnowledgeAccess, projectId: string | null) => {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      form.append("level", access.level);
      if (access.team_id) form.append("team_id", access.team_id);
      if (projectId) form.append("project_id", projectId);
      return request<KnowledgeResponse>("/knowledge", { method: "POST", body: form });
    },
    shareFile: (body: ShareFileRequest) => request<KnowledgeItem>("/knowledge/publish", jsonBody("POST", body)),
    connectSource: (body: ConnectSourceRequest) => request<KnowledgeItem>("/knowledge/sources", jsonBody("POST", body)),
    updateKnowledge: (id: string, body: KnowledgeUpdate) =>
      request<KnowledgeItem>(`/knowledge/${e(id)}`, jsonBody("PATCH", body)),
    removeKnowledge: (id: string) => request<void>(`/knowledge/${e(id)}`, { method: "DELETE" }),
  };
}

export type WorkspaceApi = ReturnType<typeof workspaceApi>;

/** The account's workspaces, and what Personal shows of them. */
export const accountApi = {
  workspaces: () => apiRequest<WorkspacesResponse>("/api/workspaces"),
  create: (body: CreateWorkspaceRequest) => apiRequest<WorkspaceState>("/api/workspaces", jsonBody("POST", body)),
  myTasks: () => apiRequest<MyTasksResponse>("/api/me/tasks"),
  myMeetings: () => apiRequest<MyMeetingsResponse>("/api/me/meetings"),
  myShares: () => apiRequest<MySharesResponse>("/api/me/shares"),
  myKnowledge: () => apiRequest<MyKnowledgeResponse>("/api/me/knowledge"),
};
