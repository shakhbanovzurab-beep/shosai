/**
 * Hub API contract, shared by the Hub screens and the route handlers in `../server`. They forward to
 * `${BACKEND_API_URL}/v1/*` when it is set and otherwise answer from an in-memory demo. Field names
 * follow the Hub specification (camelCase). Errors are `{ "detail": { "code", "message" } }`; the
 * client shows its own text for the code (see `./errors.ts`).
 *
 * GET    /hubs?include_archived=          → HubsResponse          (with the summary each row needs)
 * POST   /hubs                            → 201 Hub               (CreateHubRequest)
 * PATCH  /hubs/:id                        → Hub                   (RenameHubRequest)
 * PUT    /hubs/:id/charter                → Hub                   (CharterRequest)
 * PUT    /hubs/:id/board                  → Hub                   (BoardRequest)
 * PUT    /hubs/:id/archived               → Hub                   (ArchivedRequest)
 * DELETE /hubs/:id                        → 204; meetings, tasks and documents stay where they are
 * GET    /hubs/:id/threads?state=open     → Loaded<ThreadSummary[]>  (one request per hub)
 * GET    /hubs/:id/digest/:sessionId      → Loaded<Digest | null> ("latest" for the last meeting)
 * GET    /hubs/:id/feed?cursor=           → Loaded<FeedPage>
 * GET    /hubs/:id/materials              → Loaded<Material[]>
 * POST   /hubs/:id/materials              → 201 Material          (AddMaterialRequest, or a multipart upload)
 * DELETE /hubs/:id/materials/:materialId  → 204
 * POST   /hubs/:id/meetings/:sessionId    → MeetingHub            (a person files the meeting here)
 * DELETE /hubs/:id/meetings/:sessionId    → MeetingHub
 * GET    /threads/:id                     → ThreadDetail
 * POST   /threads/:id/done                → ThreadSummary         (DELETE undoes it)
 * POST   /threads/:id/dismiss             → ThreadSummary         (DismissRequest, for 90 days; DELETE undoes it)
 * POST   /threads/:id/abandon             → ThreadSummary
 * POST   /threads/:id/assign              → ThreadSummary         (AssignRequest)
 * GET    /meetings/:id/hub                → MeetingHub
 * GET    /meetings/:id/prep               → MeetingPrep | null
 * GET    /meetings/prep                   → PrepResponse          (upcoming meetings that have a hub)
 * GET    /brief/today                     → Loaded<DailyBrief>
 * POST   /hubs/:id/signal                 → SignalResponse        (claims the assistant's signal: once a day)
 */

import type { Gap, GapKind, ThreadSummary } from "./contract-threads";

export type * from "./contract-threads";

export type HubKind = "client" | "internal" | "pipeline";

export interface Hub {
  id: string;
  /** Written by a person, 2–200 characters. */
  name: string;
  kind: HubKind;
  /** The tracker board work goes to; null means work has nowhere to go. */
  boardId: string | null;
  boardName: string | null;
  /** "Why this hub exists", up to 500 characters. */
  purpose: string | null;
  /** "What counts as success", up to 500 characters. */
  success: string | null;
  archived: boolean;
  /** Open topics; 0 means everything is closed. */
  openThreads: number;
  /** The most urgent gap of the hub, for its row in the list. */
  topGap: Gap | null;
  /** Median days between meetings; null with fewer than three meetings. */
  rhythmDays: number | null;
  lastConversationAt: string | null;
  createdAt: string;
  /** Meetings filed here and the agreements (decisions and promises) made in them. */
  meetingCount: number;
  agreementCount: number;
}

/** "Since the last meeting": what appeared, what closed, and what nobody mentioned. */
export interface Digest {
  sessionId: string;
  meetingTitle: string;
  meetingStartedAt: string;
  opened: ThreadSummary[];
  closed: ThreadSummary[];
  /** The main block: holds the hub up, yet nobody said a word about it. */
  untouched: ThreadSummary[];
}

export type AddressSignal = "human" | "series" | "subject" | "title" | "entity" | "organisation";

export type HubRef = Pick<Hub, "id" | "name">;

/** The hub on a meeting's page, or a suggestion when the server isn't sure. */
export interface MeetingHub {
  hub: Pick<Hub, "id" | "name" | "boardId" | "archived"> | null;
  signal: AddressSignal | null;
  suggestion: { hub: HubRef; signal: AddressSignal } | null;
}

export interface Material {
  id: string;
  kind: "document" | "file";
  title: string;
  /** Null: added by hand. */
  sessionId: string | null;
  /** Where it opens; null when it can't be opened from here. */
  url: string | null;
  addedAt: string;
  /** The source was deleted: "this material is gone". */
  gone: boolean;
}

export type FactKind = "decision" | "promise" | "risk" | "problem" | "question";

export interface FeedFact {
  id: string;
  kind: FactKind;
  text: string;
  speaker: string | null;
  startMs: number | null;
  /** A decision a later one replaced. */
  supersededBy: { text: string; sessionId: string; meetingTitle: string; at: string } | null;
}

/** "What happened here": one meeting of the hub and what was said in it. */
export interface FeedMeeting {
  sessionId: string;
  meetingTitle: string;
  meetingStartedAt: string;
  facts: FeedFact[];
}

export interface FeedPage {
  meetings: FeedMeeting[];
  /** Pass back as `cursor` for earlier meetings; null at the start of the hub. */
  nextCursor: string | null;
}

export interface BriefItem {
  hub: HubRef;
  thread: ThreadSummary;
}

/** What is really on fire today, across hubs. Empty is a valid answer. */
export interface DailyBrief {
  date: string;
  items: BriefItem[];
}

/** Preparing for a meeting whose hub is known. */
export interface MeetingPrep {
  sessionOrEventId: string;
  meetingTitle: string;
  hub: HubRef;
  startsAt: string;
  open: ThreadSummary[];
  lastDigest: Digest | null;
  materials: Material[];
}

/** A block's data; `partial` when some of it didn't arrive. */
export interface Loaded<T> {
  data: T;
  partial: boolean;
}

/**
 * The assistant's one signal for a hub: a topic that came back three times without moving. At most
 * once a day per hub; quiet hours postpone it rather than drop it. Claiming it marks it delivered.
 */
export interface HubSignal {
  hub: HubRef;
  thread: ThreadSummary;
  blockers: string[];
}

export type SignalResponse = { signal: HubSignal | null };

export type HubsResponse = { hubs: Hub[] };
export type PrepResponse = { preps: MeetingPrep[] };

export const HUB_NAME_MIN = 2;
export const HUB_NAME_MAX = 200;
export const CHARTER_MAX = 500;
/** How long "Not the case" keeps a gap off, in days. */
export const DISMISS_DAYS = 90;

export type CreateHubRequest = { name: string };
export type RenameHubRequest = { name: string };
export type CharterRequest = { purpose: string | null; success: string | null };
export type BoardRequest = { boardId: string | null };
export type ArchivedRequest = { archived: boolean };
export type DismissRequest = { gapKind: GapKind };
export type AssignRequest = { owner: string };
export type AddMaterialRequest = { title: string; url: string };
