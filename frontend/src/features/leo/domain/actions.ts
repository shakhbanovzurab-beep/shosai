// Every action Leo can take. The agent reports each one as a step, so the user always sees what it is doing.
// `access` describes the effect on the user's data: reasoning steps touch nothing, `read` only looks,
// `write` changes data, and `approval` changes data in a way that must be confirmed by the user first.

export type LeoActionCategory = "reasoning" | "web" | "workspace" | "admin" | "compute" | "memory";
export type LeoActionAccess = "none" | "read" | "write" | "approval";

/** What an action is; its words ("Searching the web") are in the `leoActions` messages, keyed by its id. */
export interface LeoActionDefinition {
  readonly category: LeoActionCategory;
  readonly access: LeoActionAccess;
}

export const LEO_ACTIONS = {
  // Reasoning
  analyze_request: { category: "reasoning", access: "none" },
  think: { category: "reasoning", access: "none" },
  plan: { category: "reasoning", access: "none" },
  synthesize: { category: "reasoning", access: "none" },
  write_answer: { category: "reasoning", access: "none" },

  // Internet
  web_search: { category: "web", access: "read" },
  web_read: { category: "web", access: "read" },
  web_news: { category: "web", access: "read" },

  // Productivity & Hub
  read_activity: { category: "workspace", access: "read" },
  search_hub: { category: "workspace", access: "read" },

  // Email
  search_mail: { category: "workspace", access: "read" },
  read_email: { category: "workspace", access: "read" },
  draft_email: { category: "workspace", access: "write" },
  send_email: { category: "workspace", access: "approval" },
  organize_mail: { category: "workspace", access: "write" },

  // Calendar
  search_calendar: { category: "workspace", access: "read" },
  find_free_time: { category: "workspace", access: "read" },
  create_event: { category: "workspace", access: "approval" },
  update_event: { category: "workspace", access: "approval" },
  cancel_event: { category: "workspace", access: "approval" },

  // Meetings
  search_meetings: { category: "workspace", access: "read" },
  read_transcript: { category: "workspace", access: "read" },
  summarize_meeting: { category: "workspace", access: "read" },

  // Kanban
  search_tasks: { category: "workspace", access: "read" },
  create_task: { category: "workspace", access: "write" },
  update_task: { category: "workspace", access: "write" },
  move_task: { category: "workspace", access: "write" },

  // Team chats
  read_chat: { category: "workspace", access: "read" },

  // Files
  search_files: { category: "workspace", access: "read" },
  read_file: { category: "workspace", access: "read" },
  create_file: { category: "workspace", access: "write" },
  organize_files: { category: "workspace", access: "write" },
  share_file: { category: "workspace", access: "approval" },
  delete_file: { category: "workspace", access: "approval" },

  // Knowledge
  search_knowledge: { category: "workspace", access: "read" },
  read_article: { category: "workspace", access: "read" },
  update_knowledge: { category: "workspace", access: "write" },

  // Studio
  search_prompts: { category: "workspace", access: "read" },
  read_context: { category: "workspace", access: "read" },
  compare_models: { category: "workspace", access: "read" },
  update_prompt: { category: "workspace", access: "write" },

  // Admin
  query_analytics: { category: "admin", access: "read" },
  query_crm: { category: "admin", access: "read" },
  search_people: { category: "admin", access: "read" },
  update_user: { category: "admin", access: "approval" },
  update_role: { category: "admin", access: "approval" },

  // Compute
  run_code: { category: "compute", access: "none" },
  analyze_data: { category: "compute", access: "none" },
  create_chart: { category: "compute", access: "none" },

  // Memory
  recall_memory: { category: "memory", access: "read" },
  save_memory: { category: "memory", access: "write" },
} as const satisfies Record<string, LeoActionDefinition>;

export type LeoActionId = keyof typeof LEO_ACTIONS;

export function isLeoActionId(value: string): value is LeoActionId {
  return Object.hasOwn(LEO_ACTIONS, value);
}
