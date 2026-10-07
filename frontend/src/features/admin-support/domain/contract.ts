/**
 * Admin support inbox contract, shared by /admin/support and the route handlers in `../server`
 * (served at `src/app/api/admin/support`). They forward to `${BACKEND_API_URL}/v1/admin/support/*` when it
 * is set and otherwise answer from an in-memory demo. snake_case to match Pydantic; errors are `{ "detail": string }`.
 *
 * GET   /admin/support/conversations?status=&mine=   → ConversationsResponse
 * GET   /admin/support/conversations/{id}            → ConversationDetail   (also marks it read)
 * POST  /admin/support/conversations/{id}/messages   → 201 ConversationDetail (SendMessageRequest)
 * PATCH /admin/support/conversations/{id}            → ConversationDetail   (UpdateConversationRequest)
 * GET   /admin/support/canned-replies                → CannedRepliesResponse
 */

/** "open": the user waits for us; "pending": we replied and wait for the user; "resolved": closed. */
export const CONVERSATION_STATUSES = ["open", "pending", "resolved"] as const;
export type ConversationStatus = (typeof CONVERSATION_STATUSES)[number];

/** List filter: one status or everything. */
export const STATUS_FILTERS = ["open", "pending", "resolved", "all"] as const;
export type StatusFilter = (typeof STATUS_FILTERS)[number];

export const PRIORITIES = ["low", "normal", "high", "urgent"] as const;
export type ConversationPriority = (typeof PRIORITIES)[number];

/** Where the user wrote from: the web app or the desktop apps. */
export type SupportChannel = "web" | "macos" | "windows";

export type SupportPlan = "free" | "pro" | "team" | "enterprise";

export type Teammate = { id: string; name: string; avatar_url: string | null };

/** Demo keeps metadata only, so `url` is null until a real backend stores the file. */
export type SupportAttachment = { name: string; size_bytes: number; content_type: string; url: string | null };

export type MessageKind = "reply" | "note";

export type SupportMessage = {
  id: string;
  /** "system" is an event in the thread (assigned, resolved…), not a person. */
  author: "user" | "agent" | "system";
  /** "note" is internal: only teammates see it. Always "reply" for user and system messages. */
  kind: MessageKind;
  /** The teammate's or the user's name; null for system events. */
  author_name: string | null;
  body: string;
  attachments: SupportAttachment[];
  created_at: string;
  /** When the user saw an agent reply; null while unread. Always null for other messages. */
  read_at: string | null;
};

export type SupportUserSummary = { id: string; name: string; email: string; avatar_url: string | null };

export type SupportUserProfile = SupportUserSummary & {
  plan: SupportPlan;
  app_version: string;
  /** e.g. "macOS 15.1", "Windows 11", "Chrome 129 · macOS". */
  os: string;
  signed_up_at: string;
  /** Errors reported by this user's apps in the last 7 days. */
  recent_errors: number;
};

export type Conversation = {
  id: string;
  /** Human-facing number, shown as #2041. */
  number: number;
  subject: string;
  user: SupportUserSummary;
  channel: SupportChannel;
  status: ConversationStatus;
  priority: ConversationPriority;
  assignee: Teammate | null;
  /** User messages since a teammate last opened the conversation. */
  unread_count: number;
  last_message: { author: SupportMessage["author"]; kind: MessageKind; body: string; created_at: string };
  created_at: string;
  updated_at: string;
};

export type PastConversation = Pick<Conversation, "id" | "number" | "subject" | "status" | "updated_at">;

export type ConversationDetail = Conversation & {
  messages: SupportMessage[];
  profile: SupportUserProfile;
  /** The user's other conversations, newest first. */
  past_conversations: PastConversation[];
};

export type ConversationsResponse = {
  conversations: Conversation[];
  /** Per-tab totals for the same `mine` filter. */
  counts: Record<StatusFilter, number>;
  /** The signed-in teammate, for «Мои» and «Назначить мне». */
  me: Teammate;
  teammates: Teammate[];
};

export type AttachmentMeta = Omit<SupportAttachment, "url">;

export type SendMessageRequest = { body: string; kind: MessageKind; attachments?: AttachmentMeta[] };

/** `assignee` is a teammate id, or null to unassign. */
export type UpdateConversationRequest = {
  status?: ConversationStatus;
  assignee?: string | null;
  priority?: ConversationPriority;
};

export type CannedReply = {
  id: string;
  title: string;
  /** May contain {name}, replaced with the user's first name when inserted. */
  body: string;
};
export type CannedRepliesResponse = { replies: CannedReply[] };

export const MESSAGE_MAX = 5000;
export const MAX_ATTACHMENTS = 5;
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;
