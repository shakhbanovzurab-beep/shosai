import type {
  AddMaterialRequest,
  DailyBrief,
  Digest,
  FeedPage,
  Hub,
  HubsResponse,
  Loaded,
  Material,
  MeetingHub,
  MeetingPrep,
  PrepResponse,
  SignalResponse,
} from "../domain/contract";
import type { GapKind, ThreadDetail, ThreadSummary } from "../domain/contract-threads";
import { hubRequest, json } from "./hub-request";

/*
 * The one gateway to the Hub's routes. Screens never call it directly: they go through the
 * resources and actions in ../model. A real backend plugs in behind the routes (BACKEND_API_URL).
 */

const e = encodeURIComponent;
const hub = (id: string, path = "") => `/api/hubs/${e(id)}${path}`;
const thread = (id: string, path = "") => `/api/threads/${e(id)}${path}`;

export const hubApi = {
  hubs: (includeArchived: boolean) => hubRequest<HubsResponse>(`/api/hubs?include_archived=${includeArchived}`),
  create: (name: string) => hubRequest<Hub>("/api/hubs", json("POST", { name })),
  rename: (id: string, name: string) => hubRequest<Hub>(hub(id), json("PATCH", { name })),
  charter: (id: string, purpose: string | null, success: string | null) =>
    hubRequest<Hub>(hub(id, "/charter"), json("PUT", { purpose, success })),
  board: (id: string, boardId: string | null) => hubRequest<Hub>(hub(id, "/board"), json("PUT", { boardId })),
  archived: (id: string, archived: boolean) => hubRequest<Hub>(hub(id, "/archived"), json("PUT", { archived })),
  remove: (id: string) => hubRequest<void>(hub(id), { method: "DELETE" }),

  threads: (id: string) => hubRequest<Loaded<ThreadSummary[]>>(hub(id, "/threads?state=open")),
  digest: (id: string, sessionId = "latest") => hubRequest<Loaded<Digest | null>>(hub(id, `/digest/${e(sessionId)}`)),
  feed: (id: string, cursor: string | null) =>
    hubRequest<Loaded<FeedPage>>(hub(id, cursor ? `/feed?cursor=${e(cursor)}` : "/feed")),

  materials: (id: string) => hubRequest<Loaded<Material[]>>(hub(id, "/materials")),
  addMaterial: (id: string, body: AddMaterialRequest) =>
    hubRequest<Material>(hub(id, "/materials"), json("POST", body)),
  uploadMaterial: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return hubRequest<Material>(hub(id, "/materials"), { method: "POST", body: form });
  },
  removeMaterial: (id: string, materialId: string) =>
    hubRequest<void>(hub(id, `/materials/${e(materialId)}`), { method: "DELETE" }),

  thread: (id: string) => hubRequest<ThreadDetail>(thread(id)),
  done: (id: string) => hubRequest<ThreadSummary>(thread(id, "/done"), { method: "POST" }),
  undoDone: (id: string) => hubRequest<ThreadSummary>(thread(id, "/done"), { method: "DELETE" }),
  dismiss: (id: string, gapKind: GapKind) =>
    hubRequest<ThreadSummary>(thread(id, "/dismiss"), json("POST", { gapKind })),
  undoDismiss: (id: string) => hubRequest<ThreadSummary>(thread(id, "/dismiss"), { method: "DELETE" }),
  abandon: (id: string) => hubRequest<ThreadSummary>(thread(id, "/abandon"), { method: "POST" }),
  assign: (id: string, owner: string) => hubRequest<ThreadSummary>(thread(id, "/assign"), json("POST", { owner })),

  meetingHub: (meetingId: string) => hubRequest<MeetingHub>(`/api/meetings/${e(meetingId)}/hub`),
  fileMeeting: (hubId: string, sessionId: string) =>
    hubRequest<MeetingHub>(hub(hubId, `/meetings/${e(sessionId)}`), { method: "POST" }),
  unfileMeeting: (hubId: string, sessionId: string) =>
    hubRequest<MeetingHub>(hub(hubId, `/meetings/${e(sessionId)}`), { method: "DELETE" }),

  brief: () => hubRequest<Loaded<DailyBrief>>("/api/brief/today"),
  claimSignal: (id: string) => hubRequest<SignalResponse>(hub(id, "/signal"), { method: "POST" }),
  preps: () => hubRequest<PrepResponse>("/api/meetings/prep"),
  prep: (meetingId: string) => hubRequest<MeetingPrep | null>(`/api/meetings/${e(meetingId)}/prep`),
};
