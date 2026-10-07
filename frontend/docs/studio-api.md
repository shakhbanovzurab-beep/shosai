# Studio API

The contract between the Studio screens (Context, Prompts, Models) and the FastAPI backend. The
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
| `GET`    | `/skills`                   | —                                             | `SkillsResponse`            |
| `POST`   | `/skills`                   | `{"reference": str}`                          | `201 Skill`                 |
| `POST`   | `/skills/{id}/update`       | —                                             | `Skill`                     |
| `DELETE` | `/skills/{id}`              | —                                             | `204`                       |
| `GET`    | `/skills/search?q=`         | —                                             | `SkillSearchResponse`       |
| `POST`   | `/skills/scan`              | `{"repository": str}`                         | `SkillSearchResponse`       |
| `GET`    | `/models`                   | —                                             | `ModelsResponse`            |
| `PUT`    | `/models/roles/{role}`      | `{"model_id", "temperature", "max_tokens", "reasoning"}` | `RoleModelSettings` |

## Behaviour the UI relies on

- **Context** is sent as the first system message of every model request, before the role's
  prompt. Store it trimmed and return `updated_at`.
- **Prompts** belong to the user. Each has a role, instructions and `skill_ids` (installed skills
  appended to the instructions, in order). `active` maps every role to a prompt id or `null` (the
  built-in default); reject a prompt whose role differs (422). Moving a prompt to another role, or
  deleting it, resets a role that used it. The editor autosaves with `PATCH`.
- **Skills** are SKILL.md-based instructions installed from public GitHub repositories and pinned
  to the short SHA of the last commit that touched the skill folder. `reference` is
  `owner/repo/path/to/folder`; `POST /skills` also accepts skills.sh ids (`owner/repo/skill-id`) and
  skills.sh or GitHub links, resolving the folder from the repository tree. Read `name` and
  `description` from SKILL.md's front matter and the body as `content`; set `has_extra_files` when
  the folder has scripts or other files (only the text is used). Installing an already-installed
  folder returns the existing skill. `update` re-reads it at the latest commit. Uninstalling removes
  it from every prompt's `skill_ids`.
- **Finding skills.** `GET /skills/search` searches the skills.sh directory; use its documented API
  (`/api/v1/skills/search`, Vercel OIDC token). The demo calls the public search endpoint the
  skills.sh site uses, which is undocumented. `POST /skills/scan` lists up to 40 SKILL.md files in
  a public repository. The demo implementation is in
  `src/features/studio/server/github-skills.ts` and `skills-directory.ts`.
- **Models.** `models` contains only what the user's subscription allows. Each has a `tier`
  (`standard` or `frontier`); frontier models are the expensive ones and draw on the weekly frontier
  allowance in Settings › Usage. A role can only take a
  model with the capability it `requires` (`text`, `vision`, `speech_to_text`); otherwise 422.
  `max_tokens` must be 256–`max_output_tokens`. Store `reasoning: false` when the model doesn't
  support it; ignore `temperature` when it doesn't. The UI saves each change immediately and rolls
  back if the PUT fails.
