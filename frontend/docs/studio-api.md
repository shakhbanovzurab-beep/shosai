# Studio API

The contract between the Studio screen (`/app/studio`: Context, Prompts, Models) and the backend's `studio` slice:
the `/v1/studio/*` routes of the [studio plan](../../docs/plan/slices/studio.md) §3.5 ([ADR 0074](../../docs/adr/0074-studio-slice.md)),
served since its step 8, and the skills dialog on the `agent` slice's `/v1/agent/skills*`. `api/` calls them through
the generated client; `src/features/studio/domain/contract.ts` names the generated schemas of `backend/openapi.json`
next to the limits the screens check. Refusals are the platform's envelope `{error: {code, request_id, params?}}`
(ADR 0008), worded by the cabinet in the person's language from `domain/studio-problems.ts` (the `studioApi`
catalog) and `domain/skill-problems.ts` (`studioSkills.problems`). Snake_case. Without a backend (`npm run dev`)
Studio has no data; run the API and `npm run dev:api`.

## Endpoints

| Method   | Path                              | Body                                                     | Response            |
| -------- | --------------------------------- | -------------------------------------------------------- | ------------------- |
| `GET`    | `/v1/studio/context`              | —                                                        | `StudioContext`     |
| `PUT`    | `/v1/studio/context`              | `{content}` (≤ 4 000 characters)                         | `StudioContext`     |
| `PUT`    | `/v1/studio/context/roles`        | `{roles}`: `"all"` or a list of roles, possibly empty    | `StudioContext`     |
| `GET`    | `/v1/studio/prompts`              | —                                                        | `StudioPrompts`     |
| `POST`   | `/v1/studio/prompts`              | `{name, role, content?, skill_ids?}` + `Idempotency-Key` | `201 StudioPrompt`  |
| `PATCH`  | `/v1/studio/prompts/{id}`         | any of `name`, `role`, `content`, `skill_ids`            | `StudioPrompt`      |
| `DELETE` | `/v1/studio/prompts/{id}`         | —                                                        | `204`               |
| `PUT`    | `/v1/studio/prompts/active`       | `{role, prompt_id \| null}`                              | `StudioPrompts`     |
| `GET`    | `/v1/studio/models`               | —                                                        | `StudioModels`      |
| `PUT`    | `/v1/studio/models/roles/{role}`  | `{model_id \| null, temperature, max_tokens, reasoning}` | `StudioRoleModel`   |

The roles are the five of Studio: `live_answers`, `screenshots`, `code`, `system_design`, `notes`. Live and recorded
transcription are the platform's choice and have no role (ST-D2); Leo's own model is chosen in Settings › Leo.

## Behaviour the screen relies on

- **Everything is the person's own.** Another person's prompt is `prompt_not_found` (404) on every route; lists show
  only the person's rows.
- **Context** — the person's words about themselves, stored trimmed, and the roles that take them;
  `{"content": "", "updated_at": null, "roles": "all"}` before the first save. An answer in a role takes the words
  after Shosai's instructions and before the role's prompt when `roles` is `"all"` — also any role added later — or
  names the role; Leo in chat always takes them. `notes` is a role like the others: the switch says colleagues read
  the notes. The editor autosaves `content` with `PUT /v1/studio/context`, which keeps `roles`; the six switches of
  "How it's sent" save `PUT /v1/studio/context/roles` at once and return the choice to what it was if refused
  (ST-D2 as amended by the owner on 2026-10-29).
- **Prompts.** A name of 1–80 characters, instructions of at most 20 000, at most 20 skills in order, at most 100
  prompts a person (`prompt_limit_reached`, 409). A create takes an `Idempotency-Key`: the editor keeps one key for a
  draft, so a retry after a lost answer returns the same prompt; the same key with another draft is
  `idempotency_key_reused`. The skills must be ones the person installed (`skill_not_installed`), and the
  instructions with them must fit the role's budget of 12 000 tokens (`prompt_over_budget` with `tokens` and `max`).
  `active` maps every role to a prompt id or `null` (the built-in prompt); a prompt of another role is
  `prompt_for_other_role`. Moving a prompt to another role, or deleting it, gives the role it served back its
  built-in prompt. The editor autosaves with `PATCH` and names the reason when a save is refused.
- **Skills** are agent's store (`GET`, `POST /v1/agent/skills`, `POST …/{id}/update`, `DELETE …/{id}`,
  `GET …/search?q=`, `POST …/scan`): pinned to the commit their reference names, twenty a person. Uninstalling a
  skill takes it off every prompt of the person (`agent.skill.removed`, studio's consumer); the prompts may show the
  old id for a moment until the event is delivered.
- **Models.** `models` holds only what the person's plan offers: usable models of the operator's catalogue,
  frontier ones only on a plan with frontier models. Each has a `tier`; frontier models draw on the weekly frontier
  allowance in Settings › Usage. `roles` holds the five roles; a role never set reads as its defaults (no model,
  temperature 0.7, 4 096 output tokens, 8 192 for notes, reasoning off). `model_id: null` is the role's default,
  chosen by Shosai. A role takes only a model on the plan (`model_not_on_plan`) that reads what the role needs —
  a screenshot's model reads pictures (`model_cant_do_role` with `model` and `role`); `max_tokens` lies in
  256…min(the model's limit, 32 768) (`max_tokens_range` with `min` and `max`); reasoning is stored off for a model
  that cannot reason, and a temperature is ignored by one that takes none. A saved model the plan no longer offers
  is shown as the default with a note: the default answers until the person picks again. The screen saves each
  change at once and rolls back if the `PUT` is refused; an unreadable plan is `entitlements_unavailable` (503).
