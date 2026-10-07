import type { SkillCandidate } from "../domain/contract";
import type { Problem } from "./problems";

type DirectoryHit = { id: string; skillId: string; name: string; installs?: number };

/**
 * Searches the skills.sh directory. Its documented API (/api/v1/skills/search) needs a Vercel OIDC
 * token, so the demo uses the search endpoint the skills.sh site itself calls, which is public but
 * undocumented and may change. The FastAPI backend should call the documented API with a token.
 */
export async function searchDirectory(query: string): Promise<SkillCandidate[] | Problem> {
  const res = await fetch(`https://skills.sh/api/search?q=${encodeURIComponent(query)}`, { cache: "no-store" }).catch(
    () => null,
  );
  if (!res?.ok) return { code: "directoryUnavailable" };
  const body = (await res.json()) as { skills?: DirectoryHit[] };
  return (body.skills ?? []).slice(0, 30).map((hit) => ({
    reference: hit.id,
    name: hit.name || hit.skillId,
    description: null,
    installs: hit.installs ?? null,
    source_url: `https://skills.sh/${hit.id}`,
  }));
}
