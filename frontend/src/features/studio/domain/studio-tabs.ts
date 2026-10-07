// Plain module so the server page can read it; values exported from a "use client" file reach the server as references.
export const STUDIO_TABS = ["context", "prompts", "models"] as const;
export type StudioTab = (typeof STUDIO_TABS)[number];
