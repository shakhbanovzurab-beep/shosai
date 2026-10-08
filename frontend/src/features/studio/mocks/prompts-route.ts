import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { type Prompt, type PromptsResponse, STUDIO_ROLES } from "../domain/contract";
import { createPrompt, deletePrompt, listPrompts, setActive, updatePrompt } from "./demo-prompts";
import { refuse } from "./problems";
import { firstIssue, promptDraftSchema, readJson } from "./prompt-schemas";

type Context = { params: Promise<{ id: string }> };

const activeBodySchema = z.object({ role: z.enum(STUDIO_ROLES), prompt_id: z.string().max(200).nullable() });
const notFound = () => refuse({ code: "promptNotFound" }, 404);

/** /api/studio/prompts */
export const promptsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<PromptsResponse>(listPrompts());
  },

  async POST(request: Request) {
    const body = promptDraftSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    return JsonResponse.json<Prompt>(createPrompt(body.data), { status: 201 });
  },
};

/** /api/studio/prompts/[id] */
export const promptRoute = {
  /** Edits any subset of name, role, content and skill_ids. */
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = promptDraftSchema.partial().safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const prompt = updatePrompt(id, body.data);
    return prompt ? JsonResponse.json(prompt) : notFound();
  },

  /** Deletes a prompt; a role using it goes back to its built-in default. */
  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    return deletePrompt(id) ? new Response(null, { status: 204 }) : notFound();
  },
};

/** /api/studio/prompts/active */
export const activePromptRoute = {
  /** Chooses the prompt a role plays by; returns the updated prompts. */
  async PUT(request: Request) {
    const body = activeBodySchema.safeParse(await readJson(request));
    if (!body.success) return refuse({ code: "invalidRequest" }, 422);
    const problem = setActive(body.data.role, body.data.prompt_id);
    return problem ? refuse(problem, 422) : JsonResponse.json<PromptsResponse>(listPrompts());
  },
};
