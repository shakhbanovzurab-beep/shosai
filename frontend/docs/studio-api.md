# Studio API

The contract between the Studio screens (Context, Prompts, Models) and the FastAPI backend; the
skills dialog is on the API already (see Skills below). The
TypeScript types in `src/features/studio/domain/contract.ts` are the source of truth; Pydantic
models should mirror them field for field (snake_case). Roles and what each needs are in
`src/features/studio/domain/roles.ts`.

The browser calls Next.js route handlers under `/api/studio/*`, which forward to
`${BACKEND_API_URL}/v1/studio/*` when `BACKEND_API_URL` is set (optional `BACKEND_API_KEY` is sent
as a Bearer token), and otherwise answer from an in-memory demo in `src/features/studio/server/`
(the route handlers live there too). Errors use FastAPI's `{"detail": "message"}`; the UI shows
`detail` to the user.

## Endpoints (prefix `/v1/studio`)

| Method   | Path                        | Body                                          | Response                    |
| -------- | --------------------------- | --------------------------------------------- | --------------------------- |
| `GET`    | `/context`                  | —                                             | `StudioContext`             |
| `PUT`    | `/context`                  | `{"content": str}` (≤ 4,000 chars)            | `StudioContext`             |
| `GET`    | `/prompts`                  | —                                             | `PromptsResponse`           |
| `POST`   | `/prompts`                  | `PromptDraft` (name, role, content, skill_ids) | `201 Prompt`               |
| `PATCH`  | `/prompts/{id}`             | part of `PromptDraft`                         | `Prompt`                    |
| `DELETE` | `/prompts/{id}`             | —                                             | `204`                       |
| `PUT`    | `/prompts/active`           | `{"role": StudioRole, "prompt_id": str\|null}` | `PromptsResponse`         |
| `GET`    | `/models`                   | —                                             | `ModelsResponse`            |
| `PUT`    | `/models/roles/{role}`      | `{"model_id", "temperature", "max_tokens", "reasoning"}` | `RoleModelSettings` |

## Behaviour the UI relies on

- **Context** is sent as the first system message of every model request, before the role's
  prompt. Store it trimmed and return `updated_at`.
- **Prompts** belong to the user. Each has a role, instructions and `skill_ids` (installed skills
  appended to the instructions, in order). `active` maps every role to a prompt id or `null` (the
  built-in default); reject a prompt whose role differs (422). Moving a prompt to another role, or
  deleting it, resets a role that used it. The editor autosaves with `PATCH`.
- **Skills** are served by the backend's `agent` slice since its step 15, on `/v1/agent/skills*`
  (`GET` and `POST /v1/agent/skills`, `POST …/{id}/update`, `DELETE …/{id}`, `GET …/search?q=`,
  `POST …/scan`), with the platform's error envelope; `api/skills-api.ts` calls them and
  `domain/skill-problems.ts` lists the codes the dialog words (`studioSkills.problems`). A skill is
  pinned to the commit its reference names (a link's ref, else the default branch's head);
  `reference` is `owner/repo/path/to/folder`, and `POST` also takes skills.sh ids and links, whose
  last segment is the skill's name. Installing a folder twice is 409 `skill_already_installed`;
  twenty per person. `update` reads the default branch again. Search fails soft to an empty list;
  scan lists up to 40 skills. Uninstalling does not touch the prompts' `skill_ids` until studio's
  prompts are on the API (studio composes a prompt with the skills it still finds).
- **Models.** `models` contains only what the user's subscription allows. Each has a `tier`
  (`standard` or `frontier`); frontier models are the expensive ones and draw on the weekly frontier
  allowance in Settings › Usage. A role can only take a
  model with the capability it `requires` (`text`, `vision`, `speech_to_text`); otherwise 422.
  `max_tokens` must be 256–`max_output_tokens`. Store `reasoning: false` when the model doesn't
  support it; ignore `temperature` when it doesn't. The UI saves each change immediately and rolls
  back if the PUT fails.
