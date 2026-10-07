import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { Skill, SkillSearchResponse, SkillsResponse } from "../domain/contract";
import { detachSkill } from "./demo-prompts";
import { installSkill, listSkills, uninstallSkill, updateSkill } from "./demo-skills";
import { scanRepository } from "./github-skills";
import { isProblem, refuse } from "./problems";
import { readJson, referenceSchema, repositorySchema } from "./prompt-schemas";
import { searchDirectory } from "./skills-directory";

const PATH = "/v1/studio/skills";

type Context = { params: Promise<{ id: string }> };

const notFound = () => refuse({ code: "skillNotFound" }, 404);
const invalid = () => refuse({ code: "invalidRequest" }, 422);

/** /api/studio/skills */
export const skillsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    return NextResponse.json<SkillsResponse>({ skills: listSkills() });
  },

  /** Installs a skill from a skills.sh result, a repository scan, or a pasted link. */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    const body = referenceSchema.safeParse(await readJson(request));
    if (!body.success) return invalid();
    const skill = await installSkill(body.data.reference);
    return isProblem(skill) ? refuse(skill, 422) : NextResponse.json<Skill>(skill, { status: 201 });
  },
};

/** /api/studio/skills/[id] */
export const skillRoute = {
  /** Uninstalls a skill and detaches it from every prompt. */
  async DELETE(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/studio/skills/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    if (!uninstallSkill(id)) return notFound();
    detachSkill(id);
    return new Response(null, { status: 204 });
  },
};

/** /api/studio/skills/[id]/update */
export const skillUpdateRoute = {
  /** Re-reads the skill at the latest commit of its repository. */
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/studio/skills/${encodeURIComponent(id)}/update`);
    if (upstream) return upstream;
    const skill = await updateSkill(id);
    if (skill === null) return notFound();
    return isProblem(skill) ? refuse(skill, 422) : NextResponse.json(skill);
  },
};

/** /api/studio/skills/scan */
export const skillScanRoute = {
  /** Lists the SKILL.md files in a public GitHub repository. */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/studio/skills/scan");
    if (upstream) return upstream;
    const body = repositorySchema.safeParse(await readJson(request));
    if (!body.success) return invalid();
    const results = await scanRepository(body.data.repository);
    return Array.isArray(results) ? NextResponse.json<SkillSearchResponse>({ results }) : refuse(results, 422);
  },
};

/** /api/studio/skills/search */
export const skillSearchRoute = {
  /** GET ?q= — searches the skills.sh directory (at least 2 characters). */
  async GET(request: Request) {
    const q = new URL(request.url).searchParams.get("q")?.trim() ?? "";
    const upstream = await forwardToBackend(request, `/v1/studio/skills/search?q=${encodeURIComponent(q)}`);
    if (upstream) return upstream;
    if (q.length < 2) return NextResponse.json<SkillSearchResponse>({ results: [] });
    const results = await searchDirectory(q);
    return Array.isArray(results) ? NextResponse.json<SkillSearchResponse>({ results }) : refuse(results, 502);
  },
};
