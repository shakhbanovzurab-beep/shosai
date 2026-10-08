import type { StudioContext } from "../domain/contract";

// In-memory stand-in used when BACKEND_API_URL is unset; on globalThis so every route bundle shares it.
const shared = globalThis as typeof globalThis & { studioDemoContext?: StudioContext };
shared.studioDemoContext ??= { content: "", updated_at: null };

export const getContext = (): StudioContext => shared.studioDemoContext ?? { content: "", updated_at: null };

export function saveContext(content: string): StudioContext {
  shared.studioDemoContext = { content, updated_at: new Date().toISOString() };
  return shared.studioDemoContext;
}
