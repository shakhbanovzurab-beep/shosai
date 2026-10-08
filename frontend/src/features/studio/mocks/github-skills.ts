import type { Skill, SkillCandidate } from "../domain/contract";
import type { Problem } from "./problems";

/*
 * Reads SKILL.md-based skills straight from public GitHub repositories, for the demo and as a
 * reference for the FastAPI backend. Unauthenticated GitHub API calls are limited to 60 an hour per
 * IP; raw file reads are not counted against it.
 */

type Repo = { owner: string; repo: string };
type TreeEntry = { path: string; type: string };

const SEGMENT = /^[\w.-]+$/;
const MAX_SCAN = 40;
/** Folders that hold examples, templates and drafts rather than skills people install. */
const SKIP_FOLDER = /^([._].*|docs|templates?|drafts?|examples?|node_modules|tests?|fixtures)$/i;

/** "owner/repo", "github.com/owner/repo" or a full GitHub link to the repository or a folder in it. */
export function parseRepository(input: string): Repo | null {
  const parts = input
    .trim()
    .replace(/^https?:\/\//, "")
    .replace(/^(www\.)?github\.com\//, "")
    .replace(/\.git$/, "")
    .split("/");
  const [owner, repo] = parts;
  return owner && repo && SEGMENT.test(owner) && SEGMENT.test(repo) ? { owner, repo } : null;
}

/** "owner/repo/path/to/skill", optionally as a skills.sh or GitHub link. */
function parseSkillReference(input: string): (Repo & { path: string }) | null {
  const parts = input
    .trim()
    .replace(/^https?:\/\//, "")
    .replace(/^(www\.)?(skills\.sh|github\.com)\//, "")
    .replace(/\/(tree|blob)\/[^/]+\//, "/")
    .replace(/\/SKILL\.md$/, "")
    .replace(/[?#].*$/, "")
    .replace(/\/+$/, "")
    .split("/");
  if (parts.length < 3 || !parts.every((part) => SEGMENT.test(part))) return null;
  const [owner, repo, ...rest] = parts;
  return { owner, repo, path: rest.join("/") };
}

async function github<T>(path: string): Promise<T | null> {
  const res = await fetch(`https://api.github.com${path}`, {
    headers: { accept: "application/vnd.github+json" },
    cache: "no-store",
  }).catch(() => null);
  return res?.ok ? ((await res.json()) as T) : null;
}

const repositoryTree = async ({ owner, repo }: Repo) =>
  (await github<{ tree?: TreeEntry[] }>(`/repos/${owner}/${repo}/git/trees/HEAD?recursive=1`))?.tree ?? null;

/** `name` and `description` from SKILL.md's YAML front matter (folded values included), and the body. */
function parseSkillFile(text: string) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text);
  if (!match) return { name: "", description: "", body: text.trim() };
  const fields: Record<string, string | undefined> = {};
  let current: string | null = null;
  for (const line of match[1].split(/\r?\n/)) {
    const field = /^([\w-]+):\s*(.*)$/.exec(line);
    if (field) {
      current = field[1];
      fields[current] = /^[>|][-+]?$/.test(field[2]) ? "" : field[2].replace(/^["']|["']$/g, "");
    } else if (current && /^\s+\S/.test(line)) {
      fields[current] = `${fields[current] ?? ""} ${line.trim()}`.trim();
    }
  }
  return { name: fields.name ?? "", description: fields.description ?? "", body: match[2].trim() };
}

async function readSkillFile({ owner, repo }: Repo, folder: string) {
  const res = await fetch(`https://raw.githubusercontent.com/${owner}/${repo}/HEAD/${folder}/SKILL.md`, {
    cache: "no-store",
  }).catch(() => null);
  return res?.ok ? parseSkillFile(await res.text()) : null;
}

/** Front matter fields can be present but blank; treat those as missing. */
const nonEmpty = (value: string | undefined) => (value?.trim() ? value : null);

const folderOf = (skillFile: string) => skillFile.slice(0, -"/SKILL.md".length);

/** The skill's folder: the exact path, else a folder with that name anywhere (skills.sh ids are just the name). */
function resolveFolder(tree: TreeEntry[] | null, path: string): string[] {
  const exact = tree?.find((e) => e.path === `${path}/SKILL.md`);
  if (exact) return [path];
  const name = path.split("/").at(-1) ?? path;
  const byName = tree?.find((e) => e.type === "blob" && e.path.endsWith(`/${name}/SKILL.md`));
  return byName ? [folderOf(byName.path)] : [path, `skills/${name}`, name];
}

/** Reads a skill for installing or updating it. Returns the skill, or why it couldn't. */
export async function loadSkill(reference: string): Promise<Omit<Skill, "id" | "updated_at"> | Problem> {
  const ref = parseSkillReference(reference);
  if (!ref) return { code: "skillReferenceInvalid" };
  const tree = await repositoryTree(ref);
  for (const folder of resolveFolder(tree, ref.path)) {
    const file = await readSkillFile(ref, folder);
    if (!file) continue;
    if (!file.body) return { code: "skillFileEmpty" };
    const commits = await github<{ sha: string }[]>(
      `/repos/${ref.owner}/${ref.repo}/commits?path=${encodeURIComponent(folder)}&per_page=1`,
    );
    const fullReference = `${ref.owner}/${ref.repo}/${folder}`;
    return {
      name: nonEmpty(file.name) ?? folder.split("/").at(-1) ?? folder,
      description: file.description,
      reference: fullReference,
      commit: commits?.[0]?.sha.slice(0, 7) ?? null,
      source_url: `https://github.com/${ref.owner}/${ref.repo}/tree/HEAD/${folder}`,
      content: file.body,
      has_extra_files: Boolean(
        tree?.some((e) => e.type === "blob" && e.path.startsWith(`${folder}/`) && !e.path.endsWith("/SKILL.md")),
      ),
    };
  }
  return { code: "skillMissing", path: ref.path, repository: `${ref.owner}/${ref.repo}` };
}

/** Every SKILL.md in a public repository (up to 40), with names and descriptions from their front matter. */
export async function scanRepository(input: string): Promise<SkillCandidate[] | Problem> {
  const repo = parseRepository(input);
  if (!repo) return { code: "repositoryInvalid" };
  const repository = `${repo.owner}/${repo.repo}`;
  const tree = await repositoryTree(repo);
  if (!tree) return { code: "repositoryUnreadable", repository };
  const folders = tree
    .filter((e) => e.type === "blob" && (e.path === "SKILL.md" || e.path.endsWith("/SKILL.md")))
    .filter((e) => !e.path.split("/").some((segment) => SKIP_FOLDER.test(segment)))
    // Shallow paths first: real skills usually sit at skills/<name>/, examples and drafts deeper.
    .toSorted((a, b) => a.path.split("/").length - b.path.split("/").length || a.path.localeCompare(b.path))
    .slice(0, MAX_SCAN)
    .map((e) => (e.path === "SKILL.md" ? "" : folderOf(e.path)));
  if (folders.length === 0) return { code: "repositoryNoSkills", repository };
  return Promise.all(
    folders.map(async (folder): Promise<SkillCandidate> => {
      const file = await readSkillFile(repo, folder);
      const path = folder ? `/${folder}` : "";
      return {
        reference: `${repo.owner}/${repo.repo}${path}`,
        name: nonEmpty(file?.name) ?? nonEmpty(folder.split("/").at(-1)) ?? repo.repo,
        description: nonEmpty(file?.description),
        installs: null,
        source_url: `https://github.com/${repo.owner}/${repo.repo}/tree/HEAD${path}`,
      };
    }),
  );
}
